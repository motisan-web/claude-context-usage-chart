# Changelog

## Unreleased

- `AGENTS.md`: agents must now show the user exactly what will be written (destination, files, what the scripts do) and get explicit approval before installing. README and README.ja.md mention this.

## 0.1.0

Initial release (https://github.com/motisan-web/claude-context-usage-chart).

- Skill `context-usage-chart`: draws how much of the context window a Claude Code session has used, as a single self-contained HTML file (inline SVG, no external dependencies, light/dark).
- `context_usage.py` aggregates the session log (jsonl): de-duplicates by message id, detects compactions, selects the session (`--path` > `--session-id` > `CLAUDE_CODE_SESSION_ID` > newest).
- `make_chart.py` combines the log with the `context` object of `get_usage` and writes the chart.
- Works on Windows, macOS and Linux with Python 3.8+ and the standard library only.
- Installable as a Claude Code plugin or by copying the skill folder.
- Unit tests (`python -m unittest discover -s tests`) and a synthetic example in `examples/`.
