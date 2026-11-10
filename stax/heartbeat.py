#!/usr/bin/env python3
"""Record that a background helper ran, so the owner can see it in Connections.

The box's schedule runs this right after each background script:

    */5 * * * * cd ~/openfang-play && flock -n /tmp/pull-sync.lock ./pull-sync.sh; python3 heartbeat.py pull-sync $?

It writes health/<name> into the shared records:
    {"name": "...", "ok": true|false, "exit_code": N, "at": "<UTC time>",
     "every_minutes": 5, "note": "<last log line on failure>"}

Connections reads health/* and flags a helper whose last run failed, or that
has not run for three of its intervals. Never fails the schedule: any error
here is printed and swallowed.

    python3 heartbeat.py <name> <exit-code> [--every MINUTES] [--log FILE]
"""
import argparse
import datetime
import json
import os
import urllib.parse
import urllib.request

API = os.environ.get("STAX_API", "http://127.0.0.1:4200")
SHARED = "00000000-0000-4000-8000-000000000001"


def token():
    # Same source the other scripts use: the api_key line of config.toml.
    home = os.environ.get("OPENFANG_HOME") or os.path.expanduser("~/.openfang")
    with open(os.path.join(home, "config.toml")) as f:
        for line in f:
            if line.strip().startswith("api_key"):
                return line.split('"')[1]
    return ""


def last_line(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4096))
            lines = [l.strip() for l in f.read().decode("utf-8", "replace").splitlines() if l.strip()]
        return lines[-1][:300] if lines else ""
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("exit_code", type=int)
    ap.add_argument("--every", type=int, default=5, help="minutes between runs")
    ap.add_argument("--log", default="", help="log file whose last line explains a failure")
    a = ap.parse_args()
    # flock -n exits 1 when the previous run still holds the lock: that is
    # the helper still working, not a failure.
    ok = a.exit_code == 0
    rec = {
        "name": a.name,
        "ok": ok,
        "exit_code": a.exit_code,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "every_minutes": a.every,
        "note": "" if ok else last_line(a.log),
    }
    key = urllib.parse.quote("health/" + a.name, safe="")
    body = json.dumps({"value": rec}).encode()
    r = urllib.request.Request(f"{API}/api/memory/agents/{SHARED}/kv/{key}", data=body, method="PUT")
    tok = token()
    if tok:
        r.add_header("Authorization", "Bearer " + tok)
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=10) as resp:
        resp.read()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the schedule
        print("heartbeat:", type(e).__name__, e)
