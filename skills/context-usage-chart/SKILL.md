---
name: context-usage-chart
description: Draws how much of this session's context window has been used (current value, breakdown, and history with compactions) as a single self-contained HTML chart, built by a Python script from the session log and get_usage. Use when the user says things like "context usage", "context window", "how much context have I used", "show me a graph of context", "is it heavy", "about to compact", "usage percentage". コンテキストの使用量・コンテキストウィンドウ・どこまで使った？・グラフで見せて・重い・そろそろ圧縮？・使用率、と言われたときに使う。
---

# Context usage chart

Shows "how far this session has gone in the context window" as metric cards, a history line chart and a breakdown bar.
The Python script `make_chart.py` does all aggregation and drawing and writes a finished HTML file. **Claude only runs it and shows the file** (do not read or write the HTML; that keeps the context small).

`<skill dir>` below means this skill's base directory (shown as "Base directory" when the skill is loaded).

## Steps

1. `get_usage` (`mcp__ccd_session_mgmt__get_usage`) is a deferred tool that exists only in the Claude desktop app. Load it with ToolSearch (`select:mcp__ccd_session_mgmt__get_usage`) and call it (session_id omitted). Use only the returned `context` object.
   If the tool does not exist in this environment (CLI, etc.), skip to step 2 without `--usage-json`.
2. Run the script (`python3` or `python`, whichever exists; Python 3.8+):
   ```
   python3 "<skill dir>/scripts/make_chart.py" --usage-json '<JSON>'
   ```
   - `<JSON>` is the `context` object on one line. If shell quoting breaks, write it to a temp file and pass `--usage-file <path>`.
   - Other options: `--session-id <ID>`, `--path <jsonl>`, `--max-points` (default 300), `--out <html>` (default: `<system temp dir>/claude-context-chart/context-usage.html`).
   - Which log is read (priority): `--path` > `--session-id` > env `CLAUDE_CODE_SESSION_ID` (the default; if the id is not in the current project folder, all of `~/.claude/projects/*/` is searched) > only if none of those work, the most recently updated jsonl (a warning goes to stderr). The log lives in `<config dir>/projects/<folder>/<session id>.jsonl`, where the config dir is `$CLAUDE_CONFIG_DIR` or `~/.claude`, and the folder name is the working directory with every non-alphanumeric character replaced by `-`.
   - If `tokensUsed` and the log's last value differ by 10% or more, a warning goes to stderr and a note appears in the chart (the wrong session's log may have been read). The chart footer shows the first 8 characters of the session id that was read.
   - Without `--usage-json` (no `get_usage`): the script assumes the last log point as the usage, a 1,000,000-token window and auto-compact at 97%, and draws the breakdown only as used/unused. A note in the chart says so.
   - stdout is only the HTML path and one or two summary lines.
3. Show the HTML at the printed path. In the Claude desktop app use `SendUserFile` (`files: [path]`, `display: "render"`, `status: "normal"`). Where that is unavailable (CLI, etc.), open it in a browser: `open <path>` (macOS), `xdg-open <path>` (Linux), `start "" <path>` (Windows).
4. By default show only the chart. Add no commentary, analysis or suggestions after it unless the user asks.
5. Notes:
   - The usage percentage is `percentUsed` from `get_usage`, used as is (the script does not recompute it).
   - The log format is an app internal and may change. If it breaks (0 points, missing keys), inspect the structure of a real jsonl (numbers only) and fix `scripts/context_usage.py`. The principle: the context size at each assistant response = `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`.
   - A compaction is detected as a drop of at least 10,000 tokens and at least 30% from the previous point (no dedicated log record type is relied on).
   - The HTML contains no conversation content: only numbers, dates and category names.

## Files

- `scripts/context_usage.py`: aggregates the time series from the log (can also print JSON on its own; `make_chart.py` imports `collect()`).
- `scripts/make_chart.py`: writes the finished HTML (no external libraries, CDN or JS; light and dark). Chart labels are in Japanese.

## Do not

- Do not read the jsonl itself into the conversation; always go through the scripts.
- Do not output conversation content or secrets (keep to this when modifying the scripts too).
- Do not publish the chart anywhere (e.g. as an Artifact) without the user's consent.
- Do not add unrequested explanation, analysis or suggestions after the chart.
