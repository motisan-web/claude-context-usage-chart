# claude-context-usage-chart

Claude Code のセッションが、コンテキストウィンドウをどこまで使ったかを、単体のHTML図で見せます。

[English](README.md) | [AGENTS.md](AGENTS.md)（エージェント向け手順書）

## これは何か

Claude Code のスキル（`context-usage-chart`）です。「コンテキストはどこまで使った？」と聞くと、次の図を出します。

- 指標カード: 使用トークン、使用率、自動圧縮の開始位置、圧縮の回数
- 応答ごとのコンテキストサイズの折れ線（圧縮した箇所に印）
- 現在の内訳の積み上げ棒（メッセージ、システムツール、MCPツールなど）

Pythonスクリプトがローカルのセッションログを読み、完成したHTML（インラインSVG、外部依存なし、ライト/ダーク対応）を書き出します。Claudeは実行して表示するだけなので、図を出すこと自体がほとんどコンテキストを使いません。

サンプル（合成データ）: [ブラウザで開く](https://motisan-web.github.io/claude-context-usage-chart/examples/sample-output.html)（[ソースファイル](examples/sample-output.html)）

## インストール

必要なもの: Claudeデスクトップアプリ または Claude Code、Python 3.8以上（標準ライブラリのみ）。Windows / macOS / Linux で動きます。

プラグインとして:

```
/plugin marketplace add motisan-web/claude-context-usage-chart
/plugin install context-usage-chart@claude-context-usage-chart
```

またはスキルフォルダをコピー:

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

プロジェクト単位にするなら `<project>/.claude/skills/` にコピーします。

### エージェントに導入させる

エージェントに次の一文を渡してください。

> Read AGENTS.md in https://github.com/motisan-web/claude-context-usage-chart and install the skill.

## 使い方

Claudeに「コンテキストの使用量をグラフで見せて」「コンテキストウィンドウをどこまで使った？」と頼むだけです。

スクリプトを直接実行することもできます。

```bash
python3 skills/context-usage-chart/scripts/make_chart.py --usage-file examples/sample-usage.json --path examples/sample.jsonl
```

オプション: `--usage-json` / `--usage-file`（`get_usage` の `context` オブジェクト）、`--session-id`、`--path`、`--max-points`、`--out`（既定: `<一時フォルダ>/claude-context-chart/context-usage.html`）。コマンド名は `python3` / `python` のどちらでも構いません。

## 仕組み

1. `get_usage`（Claudeデスクトップアプリのみ）から現在値と内訳を得ます。
2. `context_usage.py` が `~/.claude/projects/<フォルダ>/<セッションID>.jsonl` を読みます（環境変数 `CLAUDE_CONFIG_DIR` があれば `~/.claude` の代わりに使用。`<フォルダ>` は作業ディレクトリの英数字以外をすべて `-` にした名前）。各応答の `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` をコンテキストの大きさとし、message id で重複を除きます。サブエージェント（sidechain）の行は無視します。
3. 連続する応答の間で1万トークン以上かつ3割以上落ちた箇所を、圧縮として検出します。
4. `make_chart.py` がHTMLを書き出します。

ログの選択優先順位: `--path` > `--session-id` > 環境変数 `CLAUDE_CODE_SESSION_ID` > 最新のログ（警告つき）。

## 制限

- `get_usage` はClaudeデスクトップアプリ専用です。`--usage-json` を省略すると、ログの最終点を使用量、枠を1,000,000、自動圧縮を97%と仮定し、内訳は出ません（図中に注記が出ます）。
- ログ形式はアプリの内部仕様で、更新で変わる可能性があります。その場合はスクリプトの修正が必要です。
- 圧縮の検出は経験則です。
- 図のラベルは日本語のみです。

## プライバシー

スクリプトが読むのはトークン数・日時・セッションIDの先頭8文字だけです。会話内容は出力・保存・送信しません。ネットワーク通信もありません。HTMLには数字・日時・カテゴリ名しか含まれません。

## ライセンス

MIT。[LICENSE](LICENSE) を参照。
