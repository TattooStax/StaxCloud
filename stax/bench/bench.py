#!/usr/bin/env python3
"""StaxCloud model benchmark — every candidate, every role, the real loop.

Each case runs a candidate model through the same agent loop a hand runs in
production: the hand's real system prompt (read from stax/hands/<hand>/HAND.toml),
the real tool definitions (memory_recall, memory_store, agent_send, web_search,
schedule_list), and a fake records store seeded from the case. Tool calls are
answered by the fake store with the same reply text the daemon gives. When the
model stops calling tools, the case is graded on what it STORED and what it SAID.

Image candidates get each image case's prompt (and reference image, if any);
their outputs are saved for you to judge by eye. Vision candidates classify the
photos in --images and are graded against labels.json when one is present.

Every call goes through OpenRouter with usage accounting on, so cost is what
OpenRouter billed, not an estimate.

    export OPENROUTER_API_KEY=...
    python3 stax/bench/bench.py --dry-run                 # show the plan, spend nothing
    python3 stax/bench/bench.py                           # all roles, all candidates
    python3 stax/bench/bench.py --roles driver,router     # some roles
    python3 stax/bench/bench.py --only glm,gemma          # candidates whose id contains these
    python3 stax/bench/bench.py --repeat 3                # run every case 3 times
    python3 stax/bench/bench.py --images ~/portfolio      # add vision cases from a folder

Results land in stax/bench/results/<timestamp>/: scoreboard.md (read this),
results.jsonl (every call), and images/ (generated designs).
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import json
import mimetypes
import os
import re
import statistics
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAX = HERE.parent
API = "https://openrouter.ai/api/v1/chat/completions"
FULL_PRECISION = ["bf16", "fp16", "fp8"]

# ---------------------------------------------------------------------------
# Tools — the definitions the daemon gives the hands (tool_runner.rs)
# ---------------------------------------------------------------------------

TOOL_DEFS = {
    "memory_recall": {
        "description": "Recall a value from shared memory by key.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "The storage key to recall"}},
            "required": ["key"]},
    },
    "memory_store": {
        "description": "Store a value in shared memory accessible by all agents. Use for cross-agent coordination and data sharing.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "The storage key"},
            "value": {"type": "string", "description": "The value to store (JSON-encode objects/arrays, or pass a plain string)"}},
            "required": ["key", "value"]},
    },
    "memory_list": {
        "description": "Find records in shared memory: lists keys starting with a prefix (e.g. 'contact/', 'sms/', 'formsub/'), optionally only those whose key or content contains some words, each with a short preview. Use it to find a record when you don't know its exact key, then memory_recall that key for the full record. Never guess a key.",
        "parameters": {"type": "object", "properties": {
            "prefix": {"type": "string", "description": "Key prefix to list, e.g. 'contact/' (empty = every record)"},
            "contains": {"type": "string", "description": "Only records whose key or content contains this text (case-insensitive), e.g. a name or phone number"},
            "limit": {"type": "integer", "description": "Most records to show (default 30, max 200)"}}},
    },
    "web_fetch": {
        "description": "Fetch a web page and return its readable text.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "The URL to fetch"}}, "required": ["url"]},
    },
    "agent_send": {
        "description": "Send a message to another agent and receive their response. Accepts UUID or agent name. Use agent_find first to discover agents.",
        "parameters": {"type": "object", "properties": {
            "agent_id": {"type": "string", "description": "The target agent's UUID or name"},
            "message": {"type": "string", "description": "The message to send to the agent"}},
            "required": ["agent_id", "message"]},
    },
    "agent_list": {
        "description": "List all running agents with their IDs, names, states, and models.",
        "parameters": {"type": "object", "properties": {}},
    },
    "web_search": {
        "description": "Search the web using multiple providers (Tavily, Brave, Perplexity, DuckDuckGo) with automatic fallback. Returns structured results with titles, URLs, and snippets.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The search query"},
            "max_results": {"type": "integer", "description": "Maximum number of results to return (default: 5, max: 20)"}},
            "required": ["query"]},
    },
    "schedule_list": {
        "description": "List all scheduled tasks with their IDs, descriptions, schedules, and next run times.",
        "parameters": {"type": "object", "properties": {}},
    },
    "schedule_create": {
        "description": "Create a scheduled task.",
        "parameters": {"type": "object", "properties": {
            "description": {"type": "string"}, "schedule": {"type": "string"}},
            "required": ["description", "schedule"]},
    },
}


class FakeStore:
    """The shared records namespace, seeded from a case. Replies match the
    daemon's own memory tool output word for word."""

    def __init__(self, records: dict, agents: dict, search: dict):
        self.records = {k: v for k, v in records.items()}
        self.writes: dict[str, object] = {}
        self.calls: list[dict] = []
        self.agents = agents
        self.search = search

    def run(self, name: str, args: dict) -> str:
        self.calls.append({"tool": name, "args": args})
        if name == "memory_recall":
            key = str(args.get("key", ""))
            if key in self.writes:
                return json.dumps(self.writes[key], indent=2)
            if key in self.records:
                return json.dumps(self.records[key], indent=2)
            return f"No value found for key '{key}'."
        if name == "memory_store":
            key = str(args.get("key", ""))
            raw = args.get("value", "")
            try:
                val = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                val = raw
            self.writes[key] = val
            return f"Stored value under key '{key}'."
        if name == "memory_list":
            prefix = str(args.get("prefix") or "")
            needle = str(args.get("contains") or "").strip().lower()
            merged = {**self.records, **self.writes}
            hits = sorted((k, v) for k, v in merged.items() if k.startswith(prefix)
                          and (not needle or needle in k.lower() or needle in json.dumps(v).lower()))
            if not hits:
                return "No records found."
            return f"{len(hits)} records. Previews are shortened — memory_recall a key for the full record.\n" + \
                "\n".join(f"- {k}: {json.dumps(v)[:240]}" for k, v in hits[:30])
        if name == "web_fetch":
            url = str(args.get("url", ""))
            return self.search.get(url, f"Fetched {url}: (no readable content in this test)")
        if name == "agent_list":
            return json.dumps([{"name": n, "state": "Running"} for n in self.agents], indent=2)
        if name == "agent_send":
            target = str(args.get("agent_id", ""))
            for n, reply in self.agents.items():
                if n.lower() == target.lower():
                    return reply
            return f"Agent '{target}' not found."
        if name == "web_search":
            q = str(args.get("query", "")).lower()
            for needle, results in self.search.items():
                if needle.lower() in q:
                    return results
            return next(iter(self.search.values()), "No results found.")
        if name == "schedule_list":
            return "[]"
        if name == "schedule_create":
            return "Scheduled task created."
        return f"Unknown tool '{name}'."


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------

def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    for p in (Path.home() / ".openfang" / ".env", STAX / "designer" / "env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    sys.exit("No OPENROUTER_API_KEY in the environment, ~/.openfang/.env or stax/designer/env.")


def call(body: dict, key: str, timeout: int = 180) -> tuple[dict, float]:
    body = dict(body)
    body["usage"] = {"include": True}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Title", "StaxCloud bench")
    t0 = time.monotonic()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            return data, time.monotonic() - t0
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            if e.code in (429, 502, 503) and attempt < 2:
                time.sleep(4 * (attempt + 1))
                continue
            return {"error": f"HTTP {e.code}: {detail}"}, time.monotonic() - t0
        except Exception as e:  # network, timeout
            if attempt < 2:
                time.sleep(3)
                continue
            return {"error": f"{type(e).__name__}: {e}"}, time.monotonic() - t0
    return {"error": "unreachable"}, 0.0


def provider_block(variant: str, pin: list[str] | None) -> dict | None:
    p: dict = {}
    if pin:
        p["order"] = pin
        p["allow_fallbacks"] = False
    if variant == "full":
        p["quantizations"] = FULL_PRECISION
    return p or None


# ---------------------------------------------------------------------------
# Agent loop (text roles)
# ---------------------------------------------------------------------------

def hand_prompt(hand: str) -> tuple[str, list[str]]:
    data = tomllib.loads((STAX / "hands" / hand / "HAND.toml").read_text(encoding="utf-8"))
    return data["agent"].get("system_prompt", ""), list(data.get("tools", []))


def run_loop(model: str, provider: dict | None, case: dict, key: str, max_iters: int) -> dict:
    system, tools = hand_prompt(case["hand"])
    tools = case.get("tools", tools)
    store = FakeStore(case.get("records", {}), case.get("agents", {}), case.get("search", {}))
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": case["message"]}]
    tool_schema = [{"type": "function", "function": {"name": t, **TOOL_DEFS[t]}}
                   for t in tools if t in TOOL_DEFS]
    cost = 0.0
    tokens_in = tokens_out = 0
    latency = 0.0
    final = ""
    error = None
    for _ in range(max_iters):
        body = {"model": model, "messages": messages, "max_tokens": 2048, "temperature": 0.2}
        if tool_schema:
            body["tools"] = tool_schema
        if provider:
            body["provider"] = provider
        data, secs = call(body, key)
        latency += secs
        if "error" in data:
            error = data["error"]
            break
        u = data.get("usage") or {}
        cost += float(u.get("cost") or 0.0)
        tokens_in += int(u.get("prompt_tokens") or 0)
        tokens_out += int(u.get("completion_tokens") or 0)
        msg = ((data.get("choices") or [{}])[0].get("message")) or {}
        tcs = msg.get("tool_calls") or []
        if not tcs:
            final = msg.get("content") or ""
            break
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tcs})
        for tc in tcs:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_unparsed": fn.get("arguments")}
            out = store.run(fn.get("name", ""), args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
    else:
        error = f"no final answer within {max_iters} steps"
    return {"final": final, "writes": store.writes, "calls": store.calls, "cost": cost,
            "tokens_in": tokens_in, "tokens_out": tokens_out, "latency": latency,
            "error": error, "turns": sum(1 for m in messages if m["role"] == "assistant") + (1 if final else 0)}


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def _text_of(v) -> str:
    return v if isinstance(v, str) else json.dumps(v)


def _get(v, path: str):
    for part in path.split("."):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                return None
        if not isinstance(v, dict):
            return None
        v = v.get(part)
    return v


def grade(case: dict, run: dict) -> list[str]:
    """Return the failed checks (empty list = pass)."""
    if run["error"]:
        return [f"error: {run['error'][:160]}"]
    exp = case.get("expect", {})
    fails = []
    writes = run["writes"]
    said = run["final"]
    stored_text = "\n".join(_text_of(v) for v in writes.values())

    if exp.get("no_writes") and writes:
        fails.append(f"stored {sorted(writes)} but should store nothing")
    for pat in exp.get("write_keys", []):
        if not any(re.fullmatch(pat, k) for k in writes):
            fails.append(f"no write matching {pat} (wrote {sorted(writes) or 'nothing'})")
    for pat in exp.get("forbid_write_keys", []):
        bad = [k for k in writes if re.fullmatch(pat, k)]
        if bad:
            fails.append(f"wrote forbidden {bad}")
    for path, want in exp.get("write_fields", {}).items():
        kpat, field = path.split("::", 1)
        hits = [v for k, v in writes.items() if re.fullmatch(kpat, k)]
        got = [_get(v, field) for v in hits]
        if not any(g == want for g in got):
            fails.append(f"{field} should be {want!r}, got {got}")
    for pat in exp.get("stored_must", []):
        if not re.search(pat, stored_text, re.I):
            fails.append(f"stored text lacks /{pat}/")
    for pat in exp.get("stored_must_not", []):
        m = re.search(pat, stored_text, re.I)
        if m:
            fails.append(f"stored text has /{pat}/: {m.group(0)!r}")
    for pat in exp.get("said_must", []):
        if not re.search(pat, said, re.I):
            fails.append(f"reply lacks /{pat}/")
    for pat in exp.get("said_must_not", []):
        m = re.search(pat, said, re.I)
        if m:
            fails.append(f"reply has /{pat}/: {m.group(0)!r}")
    for tool in exp.get("must_call", []):
        if not any(c["tool"] == tool for c in run["calls"]):
            fails.append(f"never called {tool}")
    for tool in exp.get("must_not_call", []):
        if any(c["tool"] == tool for c in run["calls"]):
            fails.append(f"called {tool}")
    if exp.get("quotes_verbatim"):
        sources = " ".join(m.get("body", "") for r in case.get("records", {}).values()
                           if isinstance(r, dict) for m in r.get("messages", []))
        for k, v in writes.items():
            q = _get(v, "quote")
            if q and q not in sources:
                fails.append(f"{k} quote is not verbatim: {q!r}")
    return fails


# ---------------------------------------------------------------------------
# Image and vision roles
# ---------------------------------------------------------------------------

def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def run_image(model: str, provider: dict | None, case: dict, key: str, outdir: Path, tag: str) -> dict:
    content = [{"type": "text", "text": case["prompt"]}]
    ref = case.get("reference")
    if ref:
        rp = (HERE / ref) if not Path(ref).is_absolute() else Path(ref)
        if not rp.exists():
            return {"error": f"reference image missing: {rp}", "cost": 0.0, "latency": 0.0, "files": []}
        content.append({"type": "image_url", "image_url": {"url": data_url(rp)}})
    body = {"model": model, "modalities": ["image", "text"],
            "messages": [{"role": "user", "content": content}]}
    if provider:
        body["provider"] = provider
    data, secs = call(body, key, timeout=600)
    if "error" in data:
        return {"error": data["error"], "cost": 0.0, "latency": secs, "files": []}
    msg = ((data.get("choices") or [{}])[0].get("message")) or {}
    files = []
    for i, im in enumerate(msg.get("images") or []):
        url = (im.get("image_url") or {}).get("url", "")
        if url.startswith("data:") and "," in url:
            ext = ".png" if "png" in url[:30] else ".jpg"
            f = outdir / f"{case['id']}__{tag}__{i}{ext}"
            f.write_bytes(base64.b64decode(url.split(",", 1)[1]))
            files.append(f.name)
    u = data.get("usage") or {}
    return {"error": None if files else "no image returned", "cost": float(u.get("cost") or 0.0),
            "latency": secs, "files": files}


VISION_PROMPT = (
    "This is a photo of a finished tattoo from a studio portfolio. Classify it. "
    "Reply with JSON only: {\"style\": one of [\"black and grey realism\", \"portrait\", "
    "\"fine line\", \"lettering\", \"color realism\", \"traditional\", \"neo-traditional\", "
    "\"japanese\", \"blackwork\", \"cover-up\", \"other\"], \"subject\": \"<a few words>\", "
    "\"placement\": \"<body part or unknown>\"}"
)


def vision_cases(folder: Path) -> list[dict]:
    labels = {}
    lf = folder / "labels.json"
    if lf.exists():
        labels = json.loads(lf.read_text(encoding="utf-8"))
    out = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            out.append({"id": f"vision-{p.stem}", "role": "vision", "path": str(p),
                        "label": labels.get(p.name)})
    return out


def run_vision(model: str, provider: dict | None, case: dict, key: str) -> dict:
    body = {"model": model, "max_tokens": 300, "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url(Path(case["path"]))}}]}]}
    if provider:
        body["provider"] = provider
    data, secs = call(body, key)
    if "error" in data:
        return {"error": data["error"], "cost": 0.0, "latency": secs, "answer": None}
    u = data.get("usage") or {}
    text = (((data.get("choices") or [{}])[0].get("message")) or {}).get("content") or ""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        ans = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        ans = None
    return {"error": None if ans else f"not JSON: {text[:120]!r}", "cost": float(u.get("cost") or 0.0),
            "latency": secs, "answer": ans, "tokens_in": int(u.get("prompt_tokens") or 0)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_cases(path: Path) -> list[dict]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as e:
            sys.exit(f"{path.name} line {n}: {e}")
    return cases


def variants_for(c: dict) -> list[str]:
    v = c.get("variants", ["any"])
    return [x for x in v if x in ("any", "full")] or ["any"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", default=str(HERE / "candidates.toml"))
    ap.add_argument("--cases", default=str(HERE / "cases.jsonl"))
    ap.add_argument("--roles", default="", help="comma list: router,driver,memory,deep_work,vision,image")
    ap.add_argument("--only", default="", help="comma list of substrings of candidate ids")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--images", default="", help="folder of portfolio photos for vision cases")
    ap.add_argument("--max-iters", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cand = tomllib.loads(Path(args.candidates).read_text(encoding="utf-8"))
    traffic = cand.get("traffic", {})
    roles_wanted = {r.strip() for r in args.roles.split(",") if r.strip()}
    only = [s.strip().lower() for s in args.only.split(",") if s.strip()]
    cases = load_cases(Path(args.cases))
    if args.images:
        cases += vision_cases(Path(args.images).expanduser())

    plan = []  # (role, model, variant, pin, case, rep)
    for role, spec in cand.get("roles", {}).items():
        if roles_wanted and role not in roles_wanted:
            continue
        role_cases = [c for c in cases if c.get("role") == role]
        for c in spec.get("candidates", []):
            mid = c["id"]
            if only and not any(s in mid.lower() for s in only):
                continue
            for variant in variants_for(c):
                for case in role_cases:
                    for rep in range(args.repeat):
                        plan.append((role, mid, variant, c.get("pin"), case, rep))

    print(f"{len(plan)} runs planned across "
          f"{len({(p[0], p[1], p[2]) for p in plan})} candidate/variant pairs.")
    if args.dry_run:
        seen = set()
        for role, mid, variant, pin, case, _ in plan:
            if (role, mid, variant) not in seen:
                seen.add((role, mid, variant))
                n = sum(1 for p in plan if p[:3] == (role, mid, variant))
                print(f"  {role:10} {mid:45} {variant:4} {n} runs" + (f" pin={pin}" if pin else ""))
        return
    if not plan:
        sys.exit("Nothing to run (check --roles / --only, and that cases exist for those roles).")

    key = api_key()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = Path(args.out) if args.out else HERE / "results" / stamp
    (outdir / "images").mkdir(parents=True, exist_ok=True)
    results_path = outdir / "results.jsonl"

    def work(item):
        role, mid, variant, pin, case, rep = item
        prov = provider_block(variant, pin)
        tag = f"{mid.replace('/', '_')}__{variant}__r{rep}"
        if role == "image":
            r = run_image(mid, prov, case, key, outdir / "images", tag)
            fails = [r["error"]] if r["error"] else []
        elif role == "vision":
            r = run_vision(mid, prov, case, key)
            fails = [r["error"]] if r["error"] else []
            if not fails and case.get("label"):
                got = (r["answer"] or {}).get("style", "")
                if got.strip().lower() != case["label"].strip().lower():
                    fails.append(f"style {got!r}, labelled {case['label']!r}")
        else:
            r = run_loop(mid, prov, case, key, args.max_iters)
            fails = grade(case, r)
        return {"role": role, "model": mid, "variant": variant, "case": case["id"], "rep": rep,
                "pass": not fails, "fails": fails, **{k: v for k, v in r.items() if k not in ("calls",)}}

    rows = []
    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex, \
            results_path.open("w", encoding="utf-8") as fh:
        for i, row in enumerate(ex.map(work, plan), 1):
            rows.append(row)
            fh.write(json.dumps(row, default=str) + "\n")
            fh.flush()
            mark = "ok  " if row["pass"] else "FAIL"
            print(f"[{i}/{len(plan)}] {mark} {row['role']:9} {row['model']:42} {row['variant']:4} "
                  f"{row['case']:28} ${row.get('cost', 0):.5f} {row.get('latency', 0):.1f}s"
                  + ("" if row["pass"] else f"  {row['fails'][0][:90]}"))

    write_scoreboard(outdir, rows, traffic, cand)
    print(f"\nScoreboard: {outdir / 'scoreboard.md'}")


def write_scoreboard(outdir: Path, rows: list[dict], traffic: dict, cand: dict) -> None:
    lines = [f"# StaxCloud model benchmark — {dt.datetime.now():%Y-%m-%d %H:%M}", "",
             "Pass = every check on the case held. Cost = what OpenRouter billed. "
             "Monthly = average cost per case x the role's monthly volume in candidates.toml [traffic].",
             ""]
    by_role: dict[str, list[dict]] = {}
    for r in rows:
        by_role.setdefault(r["role"], []).append(r)
    winners = {}
    for role, rs in by_role.items():
        groups: dict[tuple, list[dict]] = {}
        for r in rs:
            groups.setdefault((r["model"], r["variant"]), []).append(r)
        table = []
        for (mid, variant), g in groups.items():
            n = len(g)
            passed = sum(1 for r in g if r["pass"])
            costs = [r.get("cost", 0.0) for r in g]
            lats = sorted(r.get("latency", 0.0) for r in g)
            p95 = lats[min(len(lats) - 1, int(0.95 * len(lats)))] if lats else 0
            tin = [r.get("tokens_in", 0) for r in g if r.get("tokens_in")]
            avg_cost = statistics.mean(costs) if costs else 0.0
            monthly = avg_cost * float(traffic.get(role, 0))
            table.append((passed / n, -avg_cost, mid, variant, passed, n, avg_cost,
                          statistics.mean(lats) if lats else 0, p95,
                          int(statistics.mean(tin)) if tin else 0, monthly))
        table.sort(reverse=True)
        if table:
            winners[role] = table[0]
        lines += [f"## {role}", "",
                  "| Model | Precision | Pass | Avg cost / case | Avg latency | p95 | Avg input tokens | Est. monthly |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in table:
            lines.append(f"| {t[2]} | {t[3]} | {t[4]}/{t[5]} | ${t[6]:.5f} | {t[7]:.1f}s | {t[8]:.1f}s | "
                         f"{t[9]:,} | ${t[10]:.2f} |")
        fails = [r for r in rs if not r["pass"]]
        if fails:
            lines += ["", "<details><summary>Failures</summary>", ""]
            for r in fails:
                lines.append(f"- **{r['model']}** ({r['variant']}) on `{r['case']}`: " + "; ".join(r["fails"])[:300])
            lines += ["", "</details>"]
        if role == "image":
            lines += ["", "Generated designs are in `images/` — judge them by eye; a pass here only means an image came back."]
        lines.append("")
    if winners:
        total = sum(w[10] for w in winners.values())
        lines += ["## Leaders by role (best pass rate, then cheapest)", ""]
        for role, w in winners.items():
            lines.append(f"- **{role}**: {w[2]} ({w[3]}) — {w[4]}/{w[5]} passed, ~${w[10]:.2f}/month")
        lines += ["", f"Estimated monthly total at the leaders: **${total:.2f}** "
                      f"(traffic profile: {cand.get('traffic_note', 'see candidates.toml')}).",
                  "", "Pin a leader by editing stax/models.toml and running stax/apply-models.py --installed. "
                      "A leader is only a winner once it also reads right to you in a real conversation."]
    (outdir / "scoreboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
