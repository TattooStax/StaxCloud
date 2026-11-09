#!/usr/bin/env python3
"""Write stax/models.toml's model pins into the hands' HAND.toml files.

    python3 stax/apply-models.py              # update stax/hands/* (the sources)
    python3 stax/apply-models.py --installed  # also update ~/.openfang/hands/*
    python3 stax/apply-models.py --check      # change nothing; exit 1 if out of date

Only the `provider` and `model` lines inside each hand's [agent] table are
touched; everything else in the file is left byte-for-byte as it was. Installed
hands take effect after the daemon restarts (or the hand is re-activated).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models.toml"
SOURCE_HANDS = HERE / "hands"


def installed_hands_dir() -> Path:
    home = os.environ.get("OPENFANG_HOME")
    return (Path(home) if home else Path.home() / ".openfang") / "hands"


def load_pins(path: Path) -> dict[str, tuple[str, str]]:
    """hand id -> (provider, model). A hand named in two roles is an error."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    pins: dict[str, tuple[str, str]] = {}
    for role, spec in data.get("roles", {}).items():
        for field in ("hands", "provider", "model"):
            if field not in spec:
                raise SystemExit(f"models.toml: role '{role}' is missing '{field}'")
        for hand in spec["hands"]:
            if hand in pins:
                raise SystemExit(f"models.toml: hand '{hand}' is in more than one role")
            pins[hand] = (str(spec["provider"]), str(spec["model"]))
    return pins


_TABLE = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*(#.*)?$")


def rewrite(text: str, provider: str, model: str) -> tuple[str, bool]:
    """Set provider/model inside [agent]. Returns (new text, found both keys)."""
    out, in_agent, seen = [], False, set()
    for line in text.splitlines(keepends=True):
        m = _TABLE.match(line)
        if m:
            in_agent = m.group(1).strip() == "agent"
        elif in_agent:
            km = re.match(r'^(\s*)(provider|model)(\s*=\s*)"[^"]*"(.*)$', line.rstrip("\r\n"))
            if km:
                key = km.group(2)
                value = provider if key == "provider" else model
                ending = line[len(line.rstrip("\r\n")):]
                line = f'{km.group(1)}{key}{km.group(3)}"{value}"{km.group(4)}{ending}'
                seen.add(key)
        out.append(line)
    return "".join(out), seen == {"provider", "model"}


def hand_id(path: Path) -> str | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")).get("id")
    except tomllib.TOMLDecodeError:
        return None


def apply(dirs: list[Path], pins: dict[str, tuple[str, str]], check: bool) -> int:
    stale = 0
    found: set[str] = set()
    for base in dirs:
        if not base.is_dir():
            print(f"skip {base} (not found)")
            continue
        for hand_toml in sorted(base.glob("*/HAND.toml")):
            hid = hand_id(hand_toml)
            if hid not in pins:
                print(f"  {hand_toml}: no role in models.toml — left alone")
                continue
            found.add(hid)
            provider, model = pins[hid]
            old = hand_toml.read_text(encoding="utf-8")
            new, ok = rewrite(old, provider, model)
            if not ok:
                print(f"  {hand_toml}: no provider/model in [agent] — left alone")
                continue
            if new == old:
                print(f"  ok      {hid}: {provider} / {model}")
                continue
            stale += 1
            if check:
                print(f"  STALE   {hid}: should be {provider} / {model}")
            else:
                hand_toml.write_text(new, encoding="utf-8")
                print(f"  updated {hid}: {provider} / {model}")
    for missing in sorted(set(pins) - found):
        print(f"  note: '{missing}' is pinned but no HAND.toml with that id was found")
    return stale


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--installed", action="store_true", help="also update the live hands")
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if anything is stale")
    args = ap.parse_args()

    pins = load_pins(MODELS)
    dirs = [SOURCE_HANDS] + ([installed_hands_dir()] if args.installed else [])
    stale = apply(dirs, pins, args.check)

    pins = tomllib.loads(MODELS.read_text(encoding="utf-8"))
    image = pins.get("image", {}).get("model")
    vision = pins.get("vision", {}).get("model")
    if image or vision:
        print("\nSet these in the daemon's environment (and the designer sidecar's), then restart:")
    if image:
        print(f"  STAX_IMAGE_MODEL={image}")
        print(f"  DESIGNER_GEN_MODEL={image}")
    if vision:
        print(f"  STAX_VISION_MODEL={vision}")
    if args.installed and not args.check and stale:
        print("restart the daemon (or re-activate the changed hands) to pick these up")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
