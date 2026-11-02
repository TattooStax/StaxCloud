"""S10 — Procreate .brush / .brushset stamp export (bonus interchange).

Exports the package's stamp elements as Procreate stamp brushes,
following the 2026-10-30 format research
(~/workspace/research_notes/procreate-brush-stamp-format-20261030-1643/
report.md):

- A brush is a Shape Source + a Grain Source, both grayscale
  LUMINANCE masks (white = fully opaque paint, black = transparent),
  square, at most 2048 x 2048 px.
- A brush behaves as a STAMP when Stroke Path spacing is pushed to
  maximum (one impression per tap) with scatter / rotation / jitter
  zeroed and Count = 1. The decoded Brush.archive parameter set also
  carries a literal `stamp` boolean and `plotSpacing`.
- `.brush` is a ZIP: Brush.archive (an NSKeyedArchiver binary plist,
  root class SilicaBrush) + Shape.png + Grain.png +
  QuickLook/Thumbnail.png. `.brushset` is a ZIP of per-brush folders
  named by brush UUID, each holding the same four members, plus a
  brushset.plist XML manifest (set name + brush UUIDs).

HONESTY — read this before believing any of it works in Procreate:
Savage Interactive publishes NO specification for these formats.
Everything here is reverse-engineered structure from community
teardowns and third-party generators that demonstrably produce
importable files; field sets differ between Procreate generations
and the research's one concrete decoded dump is an OLDER brush.
These exports are therefore RESEARCH-CONFORMANT, and their
importability is UNPROVEN: the integration gate is a test-import on
a real iPad plus a field-by-field diff against a brush exported by
the target Procreate version. That status rides in every export
record (SPEC_STATUS) and in the README inside every .brushset.
Nothing in this module — or its tests, which are structural only —
claims more.

Approximations, named:
- The Brush.archive object graph follows the NSKeyedArchiver shape
  ($archiver / $objects / $top, root SilicaBrush) and the parameter
  NAMES from the research's decoded dump (name, bundledShapePath,
  bundledGrainPath, plotSpacing, plotJitter, shapeScatter,
  shapeRotation, shapeAzimuth, shapeRandomise, shapeInverted,
  textureScale, textureRotation, textureMovement, textureInverted,
  maxSize / minSize, maxOpacity / minOpacity, oriented, stamp).
  Where the dump does not pin a stamp value, this module chooses:
  plotSpacing = 1.0 (the normalised maximum of the spacing scale),
  plotSmoothing = 0.0, shapeCount = 1 (the Handbook's Shape
  Behaviour Count; the dump has no count field under that name),
  and a `uuid` string field so an archive can be matched to its
  brushset manifest entry. Size/opacity defaults (1.0 / 0.0) are
  generator-chosen, not copied from a same-version reference.
- The brushset.plist keys ({name, brushes}) follow the research's
  description of the manifest ("set name + list of brush UUIDs");
  the exact current key set is part of what the iPad gate checks.

Shape source: the package's own luminance stamp — `make_stamp`
(generate.py), white motif on black, mask = coverage x darkness —
which is exactly Procreate's reading (white prints, black stays
empty). An L-mode input is taken as a stamp mask as-is (e.g. a
stored .l8 stamp layer); anything else is converted with
make_stamp.

Grain source: Procreate's own guidance for stamps is a BLANK grain
(the white "Blank" in the Pro Library), so the default grain is
uniform white — full deposit everywhere, no texture. grain="noise"
instead generates a subtle deterministic paper tooth (seeded,
values in [200, 255]) for artists who want texture inside the
shape; the export record always says which grain was used.

Library tie-in: the element library (library.py) stores element
METADATA, not pixels — pixels live in designs and in the chat/host
image path, as everywhere in this package. So
`export_stamp_kit_as_brushset` takes the kit's elements as
{name, image} dicts (element_id carried through when present): the
caller resolves a kit's element_ids to their images, and each
element becomes one stamp brush in the set.
"""

from __future__ import annotations

import io
import plistlib
import uuid
import zipfile

from PIL import Image

from .generate import make_stamp

# Procreate's Shape/Grain ceiling (research §4): sources larger than
# this are rescaled by the app; this exporter caps them itself and
# records that it did.
MAX_SOURCE_PX = 2048

# Rides in every export record and every .brushset README. Do not
# soften this string without the iPad test-import + same-version
# diff actually happening — it is the difference between a
# structural claim and an importability claim.
SPEC_STATUS = (
    "research-conformant, import UNPROVEN — iPad test-import + diff "
    "against a real Procreate export required before any "
    "importability claim"
)

# Fixed seed: the noise grain is a product asset, not a dice roll —
# the same export must produce the same grain every time.
GRAIN_NOISE_SEED = 20261102

_GRAIN_KINDS = ("blank", "noise")


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _stamp_mask(stamp_image: Image.Image) -> Image.Image:
    """The element's luminance stamp mask (white motif on black).

    L-mode input IS a stamp mask already (a stored .l8 layer or a
    make_stamp result) and is used as-is; anything else goes through
    the package's own make_stamp so a brush shape can never drift
    from the stamp the rest of the package renders."""
    if stamp_image.mode == "L":
        return stamp_image
    return make_stamp(stamp_image.convert("RGBA"))


def _square_pad(mask: Image.Image) -> Image.Image:
    """Centre the mask on a square black canvas (black = empty in
    luminance-mask reading, so padding adds no paint)."""
    w, h = mask.size
    side = max(w, h)
    if (w, h) == (side, side):
        return mask
    canvas = Image.new("L", (side, side), 0)
    canvas.paste(mask, ((side - w) // 2, (side - h) // 2))
    return canvas


def _noise_grain(side: int) -> Image.Image:
    """Subtle deterministic paper tooth: white with fine seeded
    dips into [200, 255] — texture inside the shape, never a
    pattern of its own."""
    import numpy as np

    rng = np.random.default_rng(GRAIN_NOISE_SEED)
    vals = 255 - rng.integers(0, 56, size=(side, side))
    return Image.fromarray(vals.astype(np.uint8), "L")


def brush_sources_from_stamp(stamp_image: Image.Image,
                             grain: str = "blank") -> dict:
    """Shape + Grain PNG sources for one stamp element.

    Returns {shape_png_bytes, grain_png_bytes, shape_size,
    source_size, downscaled_from, grain}: the (square-padded,
    2048-capped) luminance shape from the package's stamp, and the
    grain — uniform white for grain="blank" (the default; Procreate's
    own stamp guidance), seeded fine noise for grain="noise".
    `downscaled_from` is the source's [w, h] when the 2048 cap cut
    it down, else None — the record never hides a resample."""
    if grain not in _GRAIN_KINDS:
        raise ValueError(f"unknown grain kind: {grain!r} "
                         f"(expected one of {_GRAIN_KINDS})")
    source_size = [stamp_image.size[0], stamp_image.size[1]]
    shape = _square_pad(_stamp_mask(stamp_image))
    downscaled_from = None
    if shape.size[0] > MAX_SOURCE_PX:
        downscaled_from = source_size
        shape = shape.resize((MAX_SOURCE_PX, MAX_SOURCE_PX),
                             Image.LANCZOS)
    side = shape.size[0]
    grain_img = (Image.new("L", (side, side), 255) if grain == "blank"
                 else _noise_grain(side))
    return {
        "shape_png_bytes": _png_bytes(shape),
        "grain_png_bytes": _png_bytes(grain_img),
        "shape_size": side,
        "source_size": source_size,
        "downscaled_from": downscaled_from,
        "grain": grain,
    }


# ---------------------------------------------------------------------
# Brush.archive — NSKeyedArchiver-style binary plist (SilicaBrush)
# ---------------------------------------------------------------------

def stamp_parameters(name: str, brush_uuid: str) -> dict:
    """The STAMP parameter set for one brush, per the research:
    stamp flag on, spacing maxed, scatter/rotation/jitter zeroed,
    Count = 1 — an identical motif every tap. See the module
    docstring for which values the decoded dump pins and which are
    this generator's named approximations."""
    return {
        "name": name,
        "uuid": brush_uuid,
        "bundledShapePath": "Shape.png",
        "bundledGrainPath": "Grain.png",
        "stamp": True,
        "plotSpacing": 1.0,       # normalised maximum -> one stamp per tap
        "plotJitter": 0.0,
        "plotSmoothing": 0.0,
        "shapeScatter": 0.0,
        "shapeRotation": 0.0,
        "shapeAzimuth": 0.0,
        "shapeCount": 1,
        "shapeRandomise": False,
        "shapeInverted": False,
        "textureScale": 1.0,
        "textureRotation": 0.0,
        "textureMovement": 0.0,   # static grain: prints like a stencil
        "textureInverted": False,
        "maxSize": 1.0,
        "minSize": 0.0,
        "maxOpacity": 1.0,
        "minOpacity": 0.0,
        "oriented": False,
    }


# String-valued parameters are separate objects in the $objects
# universe (as NSKeyedArchiver stores them); numbers/bools ride
# inline in the root dict.
_STRING_PARAMS = ("name", "uuid", "bundledShapePath", "bundledGrainPath")


def build_brush_archive(name: str, brush_uuid: str) -> bytes:
    """Brush.archive bytes: an NSKeyedArchiver binary plist whose
    root object is a SilicaBrush carrying the stamp parameters."""
    params = stamp_parameters(name, brush_uuid)
    objects: list = ["$null"]
    root: dict = {}
    objects.append(root)                       # index 1: root (filled below)
    objects.append({                           # index 2: the class object
        "$classes": ["SilicaBrush", "NSObject"],
        "$classname": "SilicaBrush",
    })
    root["$class"] = plistlib.UID(2)
    for key, value in params.items():
        if key in _STRING_PARAMS:
            objects.append(value)
            root[key] = plistlib.UID(len(objects) - 1)
        else:
            root[key] = value
    archive = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": plistlib.UID(1)},
        "$objects": objects,
    }
    return plistlib.dumps(archive, fmt=plistlib.FMT_BINARY)


def parse_brush_archive(data: bytes) -> dict:
    """Read a Brush.archive back: resolve the NSKeyedArchiver object
    graph to the root SilicaBrush's plain parameter dict (UID
    references followed, the class reported under "$class"). This
    is the read-back the structural tests assert against — it proves
    the graph is coherent, not that Procreate accepts it."""
    archive = plistlib.loads(data)
    if archive.get("$archiver") != "NSKeyedArchiver":
        raise ValueError("not an NSKeyedArchiver archive")
    objects = archive["$objects"]
    root = objects[archive["$top"]["root"].data]
    resolved = {}
    for key, value in root.items():
        if isinstance(value, plistlib.UID):
            target = objects[value.data]
            if isinstance(target, dict) and "$classname" in target:
                resolved[key] = target["$classname"]
            else:
                resolved[key] = target
        else:
            resolved[key] = value
    return resolved


# ---------------------------------------------------------------------
# .brush / .brushset assembly
# ---------------------------------------------------------------------

def _brush_members(name: str, brush_uuid: str, sources: dict) -> dict:
    """The four members of one brush, by archive-relative path. The
    QuickLook thumbnail is the shape itself — for a stamp, the shape
    IS the honest preview (what you tap is what you get)."""
    return {
        "Brush.archive": build_brush_archive(name, brush_uuid),
        "Shape.png": sources["shape_png_bytes"],
        "Grain.png": sources["grain_png_bytes"],
        "QuickLook/Thumbnail.png": sources["shape_png_bytes"],
    }


def export_stamp_brush(element_image: Image.Image, name: str,
                       grain: str = "blank",
                       brush_uuid: str | None = None) -> tuple[bytes, dict]:
    """One element -> one .brush file's bytes + the export record.

    The record carries {format, brushes: [{name, uuid, shape_size}],
    grain, spec_status} — and `spec_status` is never anything but
    SPEC_STATUS until the iPad gate has actually been passed."""
    brush_uuid = brush_uuid or str(uuid.uuid4())
    sources = brush_sources_from_stamp(element_image, grain=grain)
    members = _brush_members(name, brush_uuid, sources)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in members.items():
            zf.writestr(path, data)
    record = {
        "format": "procreate-brush",
        "file_ext": ".brush",
        "brushes": [{"name": name, "uuid": brush_uuid,
                     "shape_size": sources["shape_size"]}],
        "grain": sources["grain"],
        "source_size": sources["source_size"],
        "downscaled_from": sources["downscaled_from"],
        "spec_status": SPEC_STATUS,
    }
    return buf.getvalue(), record


def _brushset_readme(set_name: str, brushes: list[dict], grain: str) -> str:
    lines = [
        f"{set_name} — Procreate stamp brush set",
        "Exported by the Studio Design Generator (studio-design-plugin, S10).",
        "",
        f"SPEC STATUS: {SPEC_STATUS}",
        "",
        "Each brush is a folder named by its brush UUID, holding "
        "Brush.archive (NSKeyedArchiver binary plist, SilicaBrush), "
        "Shape.png and Grain.png (grayscale luminance masks: white "
        "prints, black stays empty), and QuickLook/Thumbnail.png. "
        "brushset.plist is the XML manifest: set name + brush UUIDs.",
        f"Grain: {grain} "
        + ("(uniform white — no texture; Procreate's own stamp guidance)"
           if grain == "blank" else
           "(deterministic seeded paper tooth inside the shape)"),
        "",
        "Brushes:",
    ]
    lines += [f"  {b['uuid']}  {b['name']}  (shape {b['shape_size']} px)"
              for b in brushes]
    return "\n".join(lines) + "\n"


def export_stamp_kit_as_brushset(elements, set_name: str,
                                 grain: str = "blank") -> tuple[bytes, dict]:
    """A stamp kit's elements -> one .brushset file's bytes + record.

    `elements` is an iterable of {name, image} dicts — one per kit
    element (an `element_id` key, when present, is carried into the
    record). The library stores kit membership as element ids; the
    caller resolves ids to images, because the library deliberately
    holds no pixels. One stamp brush per element, each under its own
    UUID folder, with the brushset.plist manifest listing exactly
    those UUIDs."""
    elements = list(elements)
    if not elements:
        raise ValueError("a brushset needs at least one element")
    brushes = []
    folders: dict[str, dict] = {}
    for element in elements:
        name = element.get("name")
        image = element.get("image")
        if not name or image is None:
            raise ValueError("each kit element needs a name and an image")
        brush_uuid = str(uuid.uuid4())
        sources = brush_sources_from_stamp(image, grain=grain)
        folders[brush_uuid] = _brush_members(name, brush_uuid, sources)
        entry = {"name": name, "uuid": brush_uuid,
                 "shape_size": sources["shape_size"]}
        if element.get("element_id"):
            entry["element_id"] = element["element_id"]
        brushes.append(entry)

    manifest = plistlib.dumps(
        {"name": set_name, "brushes": [b["uuid"] for b in brushes]},
        fmt=plistlib.FMT_XML)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("brushset.plist", manifest)
        zf.writestr("README.txt",
                    _brushset_readme(set_name, brushes, grain))
        for brush_uuid, members in folders.items():
            for path, data in members.items():
                zf.writestr(f"{brush_uuid}/{path}", data)

    record = {
        "format": "procreate-brushset",
        "file_ext": ".brushset",
        "set_name": set_name,
        "brushes": brushes,
        "grain": grain,
        "spec_status": SPEC_STATUS,
    }
    return buf.getvalue(), record
