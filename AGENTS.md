# AGENTS.md — instructions for coding agents (Claude Code etc.)

This file tells an agent how to install, verify and use this repository for a user.
Repository: https://github.com/motisan-web/claude-context-usage-chart

## 1. What this is, and prerequisites

A Claude Code skill (`context-usage-chart`) that draws how much of the session's context window has been used, as one self-contained HTML file. A Python script reads the local session log and builds the chart; the agent only runs it and shows the file.

Prerequisites:
- Claude desktop app or Claude Code.
- Python 3.8 or newer (`python3` or `python`). Standard library only; nothing to `pip install`.
- Session logs at `~/.claude/projects/` (or `$CLAUDE_CONFIG_DIR/projects/`).

## 2. Install

Pick one. Ask the user which scope they want if it is unclear (all projects = user scope, one project = project scope).

### (a) As a plugin
In Claude Code:
```
/plugin marketplace add motisan-web/claude-context-usage-chart
/plugin install context-usage-chart@claude-context-usage-chart
```
Then run `/reload-plugins` (or restart). The skill is then namespaced by the plugin.

### (b) As a skill, by manual copy
Get the repository (`git clone https://github.com/motisan-web/claude-context-usage-chart` into a scratch directory), then copy only the skill folder.

macOS / Linux:
```
mkdir -p ~/.claude/skills
cp -R skills/context-usage-chart ~/.claude/skills/
```
Windows (PowerShell):
```
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse -Force skills\context-usage-chart "$HOME\.claude\skills\"
```
Project scope instead: copy to `<project>/.claude/skills/context-usage-chart/` (same commands with that destination). If `CLAUDE_CONFIG_DIR` is set, use it instead of `~/.claude`.

Expected result: `<skills dir>/context-usage-chart/SKILL.md` and `scripts/context_usage.py`, `scripts/make_chart.py` exist.

## 3. OS notes (checklist)

Windows works as is. macOS and Linux should also work as is. Still, run the verification in section 4 after installing, and only if it fails, make the minimum change in that environment.

- [ ] Run the verification commands first. If they pass, change nothing.
- [ ] If `python3` is missing, use `python` (or the reverse). It is fine to adjust the command in the copied `SKILL.md`.
- [ ] If a script lacks the execute bit, run it via `python3 <script>` rather than changing permissions.
- [ ] If Japanese text in the chart renders as boxes, that is a font issue on the viewer's machine; do not edit the scripts for it.
- [ ] If the log is not found, check the folder name rule (working directory with every non-alphanumeric character replaced by `-`) and `CLAUDE_CONFIG_DIR`; fix `context_usage.py` only if the real folder name differs.

May change: the interpreter name in commands, paths for the user's OS, the open-in-browser command (`open` / `xdg-open` / `start ""`), the log-folder derivation if Claude Code changed it.

Must NOT change: the privacy policy (section 7). Do not add code that prints, stores or sends conversation content, and do not add network access. Do not edit the user's other skills or settings.

## 4. Verify

Run from the repository root (use the cloned copy; for a plugin install, use the plugin's directory):
```
python3 -m unittest discover -s tests
python3 skills/context-usage-chart/scripts/make_chart.py --help
python3 skills/context-usage-chart/scripts/make_chart.py --path examples/sample.jsonl --usage-file examples/sample-usage.json --out "<temp dir>/check.html"
```
`examples/sample.jsonl` is a synthetic log (dummy dates, session id "sample"). Success criteria: the tests report `OK`, `--help` prints usage, and the last command prints the HTML path and a summary (`424,578 / 1,000,000 (42%)`, 70 responses, 1 compaction) and the file exists. Replace `python3` with `python` where needed. Delete the temporary output afterwards.

## 5. Use

When the user says things like "show me the context usage as a chart" / "コンテキストの使用量をグラフで見せて":
1. Load and call `mcp__ccd_session_mgmt__get_usage` (desktop app only; deferred tool, load via ToolSearch). Keep only its `context` object. If it does not exist, skip this and omit `--usage-json` in step 2.
2. Run `python3 "<skill dir>/scripts/make_chart.py" --usage-json '<context JSON on one line>'` (or `--usage-file`).
3. Show the printed HTML path: `SendUserFile` with `display: "render"` in the desktop app; otherwise `open` (macOS) / `xdg-open` (Linux) / `start ""` (Windows).
4. Show the chart only; add no commentary unless asked.

Without `get_usage` the chart assumes usage from the last log point (1,000,000 window, 97% auto-compact) and shows no breakdown; a note appears in the chart.

## 6. Troubleshooting

- Wrong session's log: the default session is `CLAUDE_CODE_SESSION_ID`. If the id is unavailable, the script falls back to the newest log and prints a warning. Pass `--session-id` or `--path` to be exact.
- Mismatch warning (`get_usage` vs log differ by 10% or more): the log probably belongs to another session. Re-run with the right `--session-id`.
- Log format changed by an app update (0 points, missing keys): inspect one real record's structure without printing conversation text (e.g. key names and the `usage` numbers only) and fix `scripts/context_usage.py`. Principle: context size = `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` of each assistant response's `usage`.
- Garbled text: the HTML is UTF-8; open it in a browser. On Windows consoles, stdout is switched to UTF-8 by the script.
- JSON quoting errors in the shell: write the JSON to a file and use `--usage-file`.

## 7. Privacy and safety

- The scripts read only token counts, timestamps and the first 8 characters of the session id from the local log. They never print, store or send conversation content. There is no network access.
- Agents must follow the same rule: never load the jsonl itself into your context; always go through the scripts. Do not publish the generated chart anywhere (Artifact, upload) without the user's consent.
