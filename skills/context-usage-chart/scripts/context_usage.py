#!/usr/bin/env python3
"""Extract the context-size time series from a Claude Code session log (jsonl).

Prints numbers only (JSON on stdout). Conversation text is never printed or stored.
Standard library only. Works on Python 3.8+ on Windows, macOS and Linux.
"""
import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path


def config_dir():
    """~/.claude, or $CLAUDE_CONFIG_DIR when set."""
    env = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(env).expanduser() if env else Path.home() / ".claude"


def project_dir_name(cwd):
    """Folder name Claude Code uses under projects/: every non-alphanumeric char becomes '-'.

    /Users/name/proj -> -Users-name-proj,  C:\\dev\\x -> C--dev-x
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def find_jsonl(args):
    """Priority: --path > --session-id > env CLAUDE_CODE_SESSION_ID > newest jsonl (with a warning)."""
    if args.path:
        return args.path
    base = Path(args.projects_dir) if args.projects_dir else config_dir() / "projects"
    d = base / project_dir_name(os.getcwd())
    sid = args.session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if sid and re.fullmatch(r"[A-Za-z0-9_-]+", sid):
        cand = d / (sid + ".jsonl")
        if cand.is_file():
            return str(cand)
        hits = glob.glob(os.path.join(glob.escape(str(base)), "*", sid + ".jsonl"))
        if hits:
            return max(hits, key=os.path.getmtime)
        if args.session_id:
            sys.exit("jsonl not found: %s" % cand)
    files = glob.glob(os.path.join(glob.escape(str(d)), "*.jsonl"))
    if not files:
        sys.exit("jsonl not found in: %s" % d)
    sys.stderr.write("warning: session id unknown; used the newest log file. It may belong to another session.\n")
    return max(files, key=os.path.getmtime)


def extract(path):
    """One point per message.id. Duplicate ids keep the max value; order is first appearance."""
    order, rec = [], {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"usage"' not in line:  # fast path: skip lines without usage
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if not isinstance(o, dict) or o.get("type") != "assistant" or o.get("isSidechain"):
                continue
            m = o.get("message") or {}
            u = m.get("usage")
            if not isinstance(u, dict):
                continue
            ctx = sum(int(u.get(k) or 0) for k in
                      ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            if ctx <= 0:
                continue
            key = m.get("id") or o.get("requestId") or o.get("uuid")
            r = {"ts": o.get("timestamp"), "context": ctx, "output": int(u.get("output_tokens") or 0)}
            if key not in rec:
                order.append(key)
                rec[key] = r
            else:
                rec[key]["context"] = max(rec[key]["context"], ctx)
                rec[key]["output"] = max(rec[key]["output"], r["output"])
    return [rec[k] for k in order]


def collect(path, max_points=300):
    """Aggregate the series into a dict (also imported by make_chart.py)."""
    pts = extract(path)
    for i, p in enumerate(pts):
        p["i"] = i

    # Compaction: a drop of >= 10,000 tokens and >= 30% from the previous point.
    comps = []
    for a, b in zip(pts, pts[1:]):
        if a["context"] - b["context"] >= 10000 and b["context"] <= a["context"] * 0.7:
            comps.append({"i": b["i"], "from": a["context"], "to": b["context"]})

    keep = set()
    if pts:
        keep |= {0, len(pts) - 1, max(pts, key=lambda p: p["context"])["i"]}
        for c in comps:
            keep |= {c["i"] - 1, c["i"]}
        n = max(max_points, len(keep))
        if len(pts) > n:
            step = (len(pts) - 1) / (n - len(keep) if n > len(keep) else 1)
            x = 0.0
            while x < len(pts):
                keep.add(int(x))
                x += max(step, 1)
        else:
            keep = set(range(len(pts)))
    out_pts = [{"i": p["i"], "ts": p["ts"], "context": p["context"], "output": p["output"]}
               for p in pts if p["i"] in keep]

    return {
        "session_id": os.path.splitext(os.path.basename(path))[0],
        "points": out_pts,
        "last": pts[-1]["context"] if pts else 0,
        "max": max((p["context"] for p in pts), default=0),
        "turns": len(pts),
        "compactions": comps,
    }


def main():
    ap = argparse.ArgumentParser(description="Print the context-size time series of a session log as JSON.")
    ap.add_argument("--session-id")
    ap.add_argument("--path")
    ap.add_argument("--projects-dir")
    ap.add_argument("--max-points", type=int, default=300)
    args = ap.parse_args()

    out = collect(find_jsonl(args), args.max_points)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    json.dump(out, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
