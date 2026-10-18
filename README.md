# claude-context-usage-chart

See how much of your Claude Code session's context window you have used, as one self-contained HTML chart.

[日本語版](README.ja.md) | [AGENTS.md](AGENTS.md) (instructions for coding agents)

## What it is

A Claude Code skill (`context-usage-chart`). Ask "how much context have I used?" and it draws:

- metric cards: tokens used, usage %, auto-compact threshold, number of compactions
- a line chart of the context size at every response, with compactions marked
- a stacked bar of the current breakdown (messages, system tools, MCP tools, ...)

A Python script reads the local session log and writes a finished HTML file (inline SVG, no external dependencies, light and dark mode). Claude only runs it and shows the file, so the chart costs almost no context itself.

Example (synthetic data): [open the live sample](https://motisan-web.github.io/claude-context-usage-chart/examples/sample-output.html) ([source file](examples/sample-output.html)). The chart labels are in Japanese.

## Background

In the Claude desktop app (Code tab), the ring under the message box used to show how much of the session's context window was used. According to the official changelog, v2.42304.0 (2026-10-15) changed this: on plans with usage limits the ring now shows plan usage, and context usage moved to a Context card in the session rail (the panel to the right of the conversation; use the "Show session rail" button at the top right if it is hidden). If you only see the plan-usage ring, that is why.

This tool is an unofficial complement to that card. It reconstructs the usage history over time from the session log, shows the breakdown against the whole window including the unused part, and produces a standalone HTML file you can keep or share.

## Install

Requirements: Claude desktop app or Claude Code, Python 3.8+ (standard library only). Works on Windows, macOS and Linux.

As a plugin:

```
/plugin marketplace add motisan-web/claude-context-usage-chart
/plugin install context-usage-chart@claude-context-usage-chart
```

Or copy the skill folder:

```bash
# macOS / Linux
git clone https://github.com/motisan-web/claude-context-usage-chart
mkdir -p ~/.claude/skills && cp -R claude-context-usage-chart/skills/context-usage-chart ~/.claude/skills/
```

```powershell
# Windows (PowerShell)
git clone https://github.com/motisan-web/claude-context-usage-chart
Copy-Item -Recurse claude-context-usage-chart\skills\context-usage-chart "$HOME\.claude\skills\"
```

For a single project, copy it to `<project>/.claude/skills/` instead.

### Let an agent install it

Give your agent this sentence:

> Read AGENTS.md in https://github.com/motisan-web/claude-context-usage-chart and install the skill.

Installing writes files into your skills directory and lets the skill run a Python script, so `AGENTS.md` tells the agent to show you exactly what it will write and wait for your approval first.

## Usage

Just ask Claude: "show me the context usage as a chart", "how much of the context window have I used?", "コンテキストの使用量をグラフで見せて".

You can also run the script yourself:

```bash
python3 skills/context-usage-chart/scripts/make_chart.py --usage-file examples/sample-usage.json --path examples/sample.jsonl
```

Options: `--usage-json` / `--usage-file` (the `context` object from `get_usage`), `--session-id`, `--path`, `--max-points`, `--out` (default: `<temp dir>/claude-context-chart/context-usage.html`). Use `python` instead of `python3` if that is your command.

## How it works

1. `get_usage` (Claude desktop app only) gives the current value and the breakdown.
2. `context_usage.py` reads `~/.claude/projects/<folder>/<session id>.jsonl` (`$CLAUDE_CONFIG_DIR` replaces `~/.claude` if set; `<folder>` is the working directory with every non-alphanumeric character replaced by `-`). Each assistant response contributes `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, de-duplicated by message id; subagent (sidechain) lines are ignored.
3. A drop of at least 10,000 tokens and 30% between consecutive responses is reported as a compaction.
4. `make_chart.py` writes the HTML.

Session selection priority: `--path` > `--session-id` > env `CLAUDE_CODE_SESSION_ID` > the newest log (with a warning).

## Limitations

- `get_usage` exists only in the Claude desktop app. Without `--usage-json` the script assumes the last log point as usage, a 1,000,000-token window and 97% auto-compact, and shows no breakdown (a note appears in the chart).
- The log format is an internal detail of the app and may change with updates; the script may then need a fix.
- Compaction detection is a heuristic.
- Chart labels are Japanese only.

## Privacy

The scripts read only token counts, timestamps and the first 8 characters of the session id. Conversation text is never printed, stored or sent, and there is no network access. The HTML contains numbers, dates and category names only.

## License

MIT, see [LICENSE](LICENSE).
