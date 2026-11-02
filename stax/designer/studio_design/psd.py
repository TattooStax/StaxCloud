"""Minimal layered PSD export (export-only, per Director verdict Q4).

psd-tools is a reader library and was not installed on the build VM,
so this module is a small self-contained writer for the PSD subset our
native document model uses: 8-bit RGBA, compression 0 (raw), normal
blend, full-canvas layers. It also carries a matching read-back parser
(`read_psd`) used by the tests to prove the exported file opens with
named layers in the right order with the right pixels — the same
checks an external reader (GIMP/Photopea/Procreate) performs.

Layout (all integers big-endian): header '8BPS' v1, empty color-mode
and image-resource sections, layer-and-mask section (layer records
top-first, then per-layer channel data), empty global mask, then the
merged composite as planar channel data.
"""

from __future__ import annotations

import io
import struct

from PIL import Image

_CHANNEL_IDS = (0, 1, 2, -1)  # R, G, B, alpha


def _pascal_name(name: str) -> bytes:
    raw = name.encode("macroman", "replace")[:255]
    data = bytes([len(raw)]) + raw
    while len(data) % 4 != 0:  # name field is padded to a multiple of 4
        data += b"\x00"
    return data


def write_psd(composite: Image.Image, layers_top_first: list[tuple[str, Image.Image, float, bool]]) -> bytes:
    """Serialize a layered PSD.

    composite: full-canvas RGBA merged image.
    layers_top_first: (name, full-canvas RGBA image, opacity 0..1, visible)
    in top-to-bottom order, as PSD layer records are stored."""
    composite = composite.convert("RGBA")
    width, height = composite.size

    out = io.BytesIO()
    out.write(b"8BPS")
    out.write(struct.pack(">H", 1))          # version
    out.write(b"\x00" * 6)                    # reserved
    out.write(struct.pack(">H", 4))           # channels: R, G, B, A
    out.write(struct.pack(">I", height))
    out.write(struct.pack(">I", width))
    out.write(struct.pack(">H", 8))           # depth
    out.write(struct.pack(">H", 3))           # color mode: RGB
    out.write(struct.pack(">I", 0))           # color mode data
    out.write(struct.pack(">I", 0))           # image resources

    # ---- layer info ----
    layer_info = io.BytesIO()
    layer_info.write(struct.pack(">h", len(layers_top_first)))
    channel_data = io.BytesIO()
    for name, image, opacity, visible in layers_top_first:
        image = image.convert("RGBA")
        if image.size != (width, height):
            raise ValueError("PSD layers must be full-canvas images")
        channels = image.split()
        lengths = []
        for channel in channels:
            data = channel.tobytes()
            lengths.append(2 + len(data))  # + compression field
            channel_data.write(struct.pack(">H", 0))  # compression: raw
            channel_data.write(data)
        layer_info.write(struct.pack(">IIII", 0, 0, height, width))
        layer_info.write(struct.pack(">H", 4))
        for channel_id, length in zip(_CHANNEL_IDS, lengths):
            layer_info.write(struct.pack(">hI", channel_id, length))
        layer_info.write(b"8BIM")
        layer_info.write(b"norm")
        layer_info.write(struct.pack(">B", round(opacity * 255)))
        layer_info.write(struct.pack(">B", 0))            # clipping
        layer_info.write(struct.pack(">B", 0 if visible else 2))  # flags: bit1 = hidden
        layer_info.write(struct.pack(">B", 0))            # filler
        extra = io.BytesIO()
        extra.write(struct.pack(">I", 0))                 # layer mask data
        extra.write(struct.pack(">I", 0))                 # blending ranges
        extra.write(_pascal_name(name))
        layer_info.write(struct.pack(">I", len(extra.getvalue())))
        layer_info.write(extra.getvalue())
    layer_info.write(channel_data.getvalue())
    if layer_info.tell() % 2:  # layer info length is padded to even
        layer_info.write(b"\x00")

    layer_and_mask = io.BytesIO()
    layer_and_mask.write(struct.pack(">I", layer_info.tell()))
    layer_and_mask.write(layer_info.getvalue())
    layer_and_mask.write(struct.pack(">I", 0))            # global layer mask
    out.write(struct.pack(">I", layer_and_mask.tell()))
    out.write(layer_and_mask.getvalue())

    # ---- merged composite ----
    out.write(struct.pack(">H", 0))                       # compression: raw
    for channel in composite.split():
        out.write(channel.tobytes())
    return out.getvalue()


def read_psd(data: bytes) -> dict:
    """Parse back a PSD written by `write_psd` (raw compression subset).

    Returns {width, height, layers: [{name, opacity, visible, image}]
    in stored (top-first) order, composite: merged RGBA image}."""
    buf = io.BytesIO(data)

    def read(fmt: str):
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, buf.read(size))

    if buf.read(4) != b"8BPS":
        raise ValueError("not a PSD file")
    (version,) = read(">H")
    if version != 1:
        raise ValueError(f"unsupported PSD version {version}")
    buf.read(6)
    (channels,) = read(">H")
    (height,) = read(">I")
    (width,) = read(">I")
    (depth,) = read(">H")
    (color_mode,) = read(">H")
    if (channels, depth, color_mode) != (4, 8, 3):
        raise ValueError("outside the supported PSD subset")
    (n,) = read(">I")
    buf.seek(n, io.SEEK_CUR)   # color mode data
    (n,) = read(">I")
    buf.seek(n, io.SEEK_CUR)   # image resources
    (layer_mask_len,) = read(">I")
    layer_mask_end = buf.tell() + layer_mask_len
    (layer_info_len,) = read(">I")
    layer_info_end = buf.tell() + layer_info_len
    (count,) = read(">h")
    records = []
    for _ in range(count):
        top, left, bottom, right = read(">IIII")
        (n_channels,) = read(">H")
        chan_info = [read(">hI") for _ in range(n_channels)]
        if buf.read(4) != b"8BIM":
            raise ValueError("bad blend mode signature")
        blend_key = buf.read(4)
        opacity, clipping, flags, _filler = read(">BBBB")
        (extra_len,) = read(">I")
        extra_end = buf.tell() + extra_len
        (mask_len,) = read(">I")
        buf.seek(mask_len, io.SEEK_CUR)
        (ranges_len,) = read(">I")
        buf.seek(ranges_len, io.SEEK_CUR)
        name_len = buf.read(1)[0]
        name = buf.read(name_len).decode("macroman", "replace")
        buf.seek(extra_end)
        records.append({
            "name": name, "rect": (top, left, bottom, right),
            "channels": chan_info, "blend": blend_key,
            "opacity": opacity / 255.0, "visible": not bool(flags & 2),
        })
    layers = []
    for record in records:  # channel image data follows all records
        planes = {}
        for channel_id, length in record["channels"]:
            (compression,) = read(">H")
            if compression != 0:
                raise ValueError("outside the supported PSD subset (compression)")
            raw = buf.read(length - 2)
            planes[channel_id] = Image.frombytes("L", (width, height), raw)
        image = Image.merge("RGBA", (planes[0], planes[1], planes[2], planes[-1]))
        layers.append({**record, "image": image})
    buf.seek(layer_info_end)
    (global_mask_len,) = read(">I")
    buf.seek(global_mask_len, io.SEEK_CUR)
    buf.seek(layer_mask_end)
    (compression,) = read(">H")
    if compression != 0:
        raise ValueError("outside the supported PSD subset (compression)")
    planes = [Image.frombytes("L", (width, height), buf.read(width * height))
              for _ in range(4)]
    composite = Image.merge("RGBA", tuple(planes))
    return {"width": width, "height": height, "layers": layers, "composite": composite}
