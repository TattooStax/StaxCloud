#!/usr/bin/env python3
"""Merge the owner/image repair into an installed Stax hand without repinning it.

Run on the fork host only. Re-activate Stax after installing the new binary.
--check changes nothing. The original file is backed up once before writing.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import tomllib

MARKER = "OWNER AND IMAGE RECEIPTS (repair 2026-11-09)"
REPAIR = """OWNER AND IMAGE RECEIPTS (repair 2026-11-09)
- For the signed-in owner's own website, portfolio and records, copying, migrating and restyling are ordinary work orders. Execute using granted tools or identify the concrete missing file, hosting login or decision. Keep third-party protections and customer-facing approval gates in force.
- The earlier crew list describes installed capabilities, not a running roster. Call agent_list before every handoff. Use only a returned active name or ID. If needed, hand_list then hand_activate the specific installed helper and verify it with agent_list before agent_send. If activation is unavailable, work directly or name the missing capability. Never guess a running style agent. Designs are image_generate work you do yourself.
- For websites, first inspect the owner's URL with web_fetch. Use page_images/image_fetch for pictures when granted. Find existing site/ records with memory_list and memory_recall. Websites uses those records and sitejob/ publisher jobs: inspect the existing format before writing a draft, then read it back. An exact Netlify migration may need the export with source, assets, redirects and functions, or connected hosting access. Public page text alone is not that export. Do not invent a schema, status or successful publication. Publishing and customer-facing changes keep their existing approval workflow.
- For image_generate, every attached image's file_id goes in references on every attempt. Never remove references to make a failed call succeed. Report only the tool receipt and show its actual image URLs. references_used confirms submitted inputs, not a visually verified match. Do not claim a successful redo, correct palette, likeness or style without inspecting the returned image. Errors are failures, not designs.
- image_describe's style label is an interpretation. Ground it in visible palette, linework and shading, state uncertainty, and use the owner's correction. Never turn a black-and-grey request into color because of a guessed category. A missing learned profile is reported honestly; activate Style for portfolio learning only when requested.
"""


def merge_prompt(prompt: str) -> str:
    return prompt if MARKER in prompt else prompt.rstrip() + "\n\n" + REPAIR


def repair(text: str) -> str:
    before = tomllib.loads(text)
    if before.get("id") != "stax":
        raise ValueError("This repair only accepts the Stax hand")
    tools = list(before.get("tools", []))
    for tool in ("page_images", "image_fetch", "hand_list", "hand_activate"):
        if tool not in tools:
            tools.append(tool)
    # Only the hand-level tool array, owner-facing opt-in and prompt change.
    # No TOML reserialization: all other settings and custom text survive.
    import json
    text, count = re.subn(r"(?ms)^tools\s*=\s*\[.*?\]", "tools = " + json.dumps(tools), text, count=1)
    if count != 1:
        raise ValueError("Stax tools table was not found")
    if not before["agent"].get("owner_facing", False):
        agent_start = text.index("[agent]") + len("[agent]")
        end = re.search(r"(?m)^\[", text[agent_start:])
        agent_end = agent_start + end.start() if end else len(text)
        chunk = text[agent_start:agent_end]
        if re.search(r"(?m)^owner_facing\s*=", chunk):
            chunk = re.sub(r"(?m)^owner_facing\s*=.*$", "owner_facing = true", chunk)
        else:
            chunk = "\nowner_facing = true" + chunk
        text = text[:agent_start] + chunk + text[agent_end:]
    prompt = merge_prompt(before["agent"]["system_prompt"])
    # TOML basic multiline strings require escaping backslashes and quotes.
    encoded = prompt.replace("\\", "\\\\").replace('"', '\\"')
    text, count = re.subn(r'(?s)(system_prompt\s*=\s*""").*?(""")', lambda m: m[1] + encoded + m[2], text, count=1)
    if count != 1:
        raise ValueError("Expected a multiline Stax system_prompt")
    after = tomllib.loads(text)
    for key in set(before["agent"]) - {"system_prompt", "owner_facing"}:
        if after["agent"].get(key) != before["agent"][key]:
            raise ValueError(f"Refusing to change existing agent setting: {key}")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hand", type=Path, default=Path(os.environ.get("OPENFANG_HOME", str(Path.home() / ".openfang"))) / "hands/stax/HAND.toml")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    old = args.hand.read_text()
    new = repair(old)
    if old == new:
        print("Stax hand repair already installed; model pins unchanged.")
        return 0
    if args.check:
        print("Stax hand needs the repair; no changes made.")
        return 1
    backup = args.hand.with_name("HAND.toml.owner-image-repair.bak")
    if not backup.exists():
        backup.write_text(old)
    args.hand.write_text(new)
    print("Stax hand repaired; existing pins and owner instructions preserved. Reactivate Stax with the new binary.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
