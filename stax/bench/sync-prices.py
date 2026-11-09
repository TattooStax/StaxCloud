#!/usr/bin/env python3
"""Give the daemon's cost meter OpenRouter's real prices.

The daemon prices each LLM call from its model catalog. A model it doesn't know
(GLM 5.3 Flash, MiniMax M3.1 Flash, Qwen 3.8 Flash, ...) is billed at a fallback
of $1 / $3 per million tokens — 10-30x too high for the models StaxCloud uses,
which makes the budget trip early and the usage numbers wrong.

This script reads OpenRouter's public model list (no API key needed) and writes
a catalog entry for every OpenRouter model named in stax/models.toml, the
benchmark candidates, and the budget saver, into ~/.openfang/custom_models.json.
Entries you added yourself are kept. Restart the daemon to load the prices.

    python3 stax/bench/sync-prices.py                 # write
    python3 stax/bench/sync-prices.py --dry-run       # show what would change
    python3 stax/bench/sync-prices.py --also z-ai/glm-5.3-flash,qwen/qwen3.8-flash

Prices written are OpenRouter's list price for the model (what normal routing
charges). A pinned full-precision provider can cost more; the benchmark
reports what was actually billed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAX = HERE.parent
CATALOG = "https://openrouter.ai/api/v1/models"
MARK = " · OpenRouter live price"


def home() -> Path:
    h = os.environ.get("OPENFANG_HOME")
    return Path(h) if h else Path.home() / ".openfang"


def wanted_models(extra: list[str]) -> set[str]:
    ids: set[str] = set(extra)
    pins = tomllib.loads((STAX / "models.toml").read_text(encoding="utf-8"))
    for spec in pins.get("roles", {}).values():
        if spec.get("provider") == "openrouter" and spec.get("model") not in ("", "default"):
            ids.add(spec["model"])
    cand = HERE / "candidates.toml"
    if cand.exists():
        for role, spec in tomllib.loads(cand.read_text(encoding="utf-8")).get("roles", {}).items():
            if role == "image":
                continue  # image models are billed per image, outside the text meter
            for c in spec.get("candidates", []):
                ids.add(c["id"])
    cfg = home() / "config.toml"
    if cfg.exists():
        try:
            saver = tomllib.loads(cfg.read_text(encoding="utf-8")).get("budget", {}).get("saver_model", "")
        except tomllib.TOMLDecodeError:
            saver = ""
        if "/" in saver:
            ids.add(saver)
    return {i for i in ids if "/" in i}


def fetch_catalog() -> dict[str, dict]:
    with urllib.request.urlopen(urllib.request.Request(CATALOG, headers={"User-Agent": "staxcloud-sync"}),
                                timeout=60) as r:
        data = json.loads(r.read())
    return {m["id"]: m for m in data.get("data", [])}


def entry_for(m: dict) -> dict:
    p = m.get("pricing", {})
    arch = m.get("architecture", {})
    params = m.get("supported_parameters") or []
    top = m.get("top_provider") or {}
    return {
        "id": m["id"],
        "display_name": (m.get("name") or m["id"]) + MARK,
        "provider": "openrouter",
        "tier": "custom",
        "context_window": int(m.get("context_length") or top.get("context_length") or 0),
        "max_output_tokens": int(top.get("max_completion_tokens") or 8192),
        "input_cost_per_m": round(float(p.get("prompt") or 0) * 1e6, 6),
        "output_cost_per_m": round(float(p.get("completion") or 0) * 1e6, 6),
        "supports_tools": "tools" in params,
        "supports_vision": "image" in (arch.get("input_modalities") or []),
        "supports_streaming": True,
        "aliases": [],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--also", default="", help="extra comma-separated OpenRouter model ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    want = wanted_models([s.strip() for s in args.also.split(",") if s.strip()])
    live = fetch_catalog()
    path = home() / "custom_models.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    # Keep the owner's own entries; ours are recognised by provider + marker.
    kept = [e for e in existing
            if not (e.get("provider") == "openrouter" and str(e.get("display_name", "")).endswith(MARK))]

    out, missing = list(kept), []
    for mid in sorted(want):
        m = live.get(mid)
        if not m:
            missing.append(mid)
            continue
        if any(e.get("id") == mid and e.get("provider") == "openrouter" for e in kept):
            continue  # an entry you wrote yourself wins
        e = entry_for(m)
        out.append(e)
        print(f"  {mid:45} ${e['input_cost_per_m']:.3f} / ${e['output_cost_per_m']:.3f} per M"
              f"{'  tools' if e['supports_tools'] else ''}{'  vision' if e['supports_vision'] else ''}")
    for mid in missing:
        print(f"  {mid:45} NOT in OpenRouter's catalog (renamed or retired?)")

    if args.dry_run:
        print(f"\nDry run: would write {len(out)} entries to {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"\nWrote {len(out)} entries to {path}. Restart the daemon to load them.")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
