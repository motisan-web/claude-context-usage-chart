#!/usr/bin/env python3
"""Write a context-usage chart as a single self-contained HTML file (inline SVG, no external deps).

Combines the time series from context_usage.collect() with the `context` object of get_usage.
Only the output path and a short summary go to stdout. Standard library only, Python 3.8+.
The chart labels are in Japanese.
"""
import argparse, json, os, sys, tempfile
from datetime import datetime, timedelta, timezone
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context_usage as cu  # noqa: E402

JST = timezone(timedelta(hours=9))
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
EXTRA = ["#6b6a66", "#a09f98", "#4d4c49"]  # 7区画目以降(系列色は循環させない)
NAMES_JA = {
    "Messages": "メッセージ", "System tools": "システムツール", "MCP tools": "MCPツール",
    "System prompt": "システムプロンプト", "Skills": "スキル",
    "MCP server instructions": "MCPサーバーの説明",
}


def fmt_ts(ts, with_time=True):
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
    except Exception:
        return ""
    return d.strftime("%m/%d %H:%M").lstrip("0") if with_time else d.strftime("%m/%d").lstrip("0")


def day_key(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST).date()
    except Exception:
        return None


def man(v):
    x = v / 10000
    return ("%d万" % x) if abs(x - round(x)) < 1e-9 else ("%.1f万" % x)


def n(v):
    return "{:,}".format(int(v))


def f(x):
    return ("%.1f" % x).rstrip("0").rstrip(".")


def nice_step(cw):
    for s in (10000, 20000, 25000, 50000, 100000, 200000, 250000, 500000, 1000000, 2000000):
        if cw / s <= 5:
            return s
    return cw


def line_svg(data, cw, auto_pct, comps, turns):
    W, H = 600, 290
    L, R, T, B = 54, 16, 26, 34
    pw, ph = W - L - R, H - T - B
    pts = data["points"]
    last_i = max(turns - 1, 1)

    def X(i): return L + pw * (i / last_i if turns > 1 else 0.5)
    def Y(v): return T + ph * (1 - min(max(v, 0), cw) / cw)

    o = []
    o.append('<svg viewBox="0 0 %d %d" role="img" aria-labelledby="t1 d1" class="chart">' % (W, H))
    o.append('<title id="t1">コンテキストの推移</title>')
    o.append('<desc id="d1">応答ごとのコンテキスト使用量の折れ線。最後は %s トークン。枠は %s トークン、自動圧縮は %s%%。</desc>'
             % (n(data["last"]), n(cw), auto_pct))
    step = nice_step(cw)
    v = 0
    while v <= cw + 1:
        y = Y(v)
        o.append('<line x1="%d" x2="%d" y1="%s" y2="%s" class="grid"/>' % (L, W - R, f(y), f(y)))
        o.append('<text x="%d" y="%s" class="tx" text-anchor="end" dominant-baseline="middle">%s</text>'
                 % (L - 6, f(y), "0" if v == 0 else man(v)))
        v += step
    # 日付ラベル(日付が変わる点にだけ)
    labels, prev = [], None
    for p in pts:
        k = day_key(p["ts"] or "")
        if k is not None and k != prev:
            labels.append((p["i"], fmt_ts(p["ts"], False)))
            prev = k
    lastx = -1e9
    for i, t in labels:
        x = X(i)
        if x - lastx < 46:
            continue
        anchor = "start" if x < L + 8 else "middle"
        if x > W - R - 20:
            anchor = "end"
        o.append('<line x1="%s" x2="%s" y1="%d" y2="%d" class="grid"/>' % (f(x), f(x), T + ph, T + ph + 4))
        o.append('<text x="%s" y="%d" class="tx" text-anchor="%s">%s</text>' % (f(x), T + ph + 20, anchor, escape(t)))
        lastx = x
    # 上限(破線)と自動圧縮(点線)
    o.append('<line x1="%d" x2="%d" y1="%s" y2="%s" class="limit"/>' % (L, W - R, f(Y(cw)), f(Y(cw))))
    ay = Y(cw * auto_pct / 100)
    o.append('<line x1="%d" x2="%d" y1="%s" y2="%s" class="auto"/>' % (L, W - R, f(ay), f(ay)))
    # 面と線
    if pts:
        xy = [(X(p["i"]), Y(p["context"])) for p in pts]
        base = T + ph
        if len(xy) > 1:
            area = "M%s,%d " % (f(xy[0][0]), base) + " ".join("L%s,%s" % (f(x), f(y)) for x, y in xy) \
                   + " L%s,%d Z" % (f(xy[-1][0]), base)
            o.append('<path d="%s" class="area"/>' % area)
            o.append('<polyline points="%s" class="ctx"/>' % " ".join("%s,%s" % (f(x), f(y)) for x, y in xy))
        for p, (x, y) in zip(pts, xy):
            o.append('<circle cx="%s" cy="%s" r="%s" class="dot"><title>%s  %s</title></circle>'
                     % (f(x), f(y), "3.5" if len(pts) < 80 else "3", escape(fmt_ts(p["ts"] or "")), n(p["context"])))
        # 圧縮の印
        for c in comps:
            p = next((q for q in pts if q["i"] == c["i"]), None)
            if p:
                x, y = X(p["i"]), Y(p["context"])
                o.append('<circle cx="%s" cy="%s" r="7" class="cmark"><title>圧縮を検出 %s → %s</title></circle>'
                         % (f(x), f(y), n(c["from"]), n(c["to"])))
        # 末尾ラベル
        x, y = xy[-1]
        o.append('<circle cx="%s" cy="%s" r="4.5" class="enddot"/>' % (f(x), f(y)))
        ly = y - 10 if y - 10 > T + 12 else y + 20
        o.append('<text x="%s" y="%s" class="tx val" text-anchor="end">%s</text>' % (f(x), f(ly), n(pts[-1]["context"])))
    o.append('</svg>')
    return "\n".join(o)


def bar_svg(segs, cw):
    W, H = 600, 64
    L, R = 8, 8
    pw = W - L - R
    o = ['<svg viewBox="0 0 %d %d" role="img" aria-labelledby="t2 d2" class="chart">' % (W, H),
         '<title id="t2">コンテキストの内訳</title>',
         '<desc id="d2">%s</desc>' % escape("、".join("%s %s トークン" % (s["name"], n(s["tokens"])) for s in segs)),
         ]
    x = float(L)
    for s in segs:
        w = pw * s["tokens"] / cw if cw else 0
        if w <= 0:
            continue
        rw = max(w - 2, 1)
        o.append('<rect x="%s" y="6" width="%s" height="30" rx="2" fill="%s"><title>%s %s トークン</title></rect>'
                 % (f(x), f(rw), s["color"], escape(s["name"]), n(s["tokens"])))
        x += w
    o.append('<text x="%d" y="56" class="tx">0</text>' % L)
    o.append('<text x="%d" y="56" class="tx" text-anchor="end">%s</text>' % (W - R, man(cw)))
    o.append('</svg>')
    return "\n".join(o)


def build_html(data, usage, assumed, mismatch=False):
    cw = int(usage["contextWindow"])
    used = int(usage["tokensUsed"])
    pct = usage["percentUsed"]
    auto = usage.get("autoCompactsAtPercent", 97)
    comps = data["compactions"]

    # 内訳
    segs, ci = [], 0
    for c in usage["categories"]:
        col = SERIES[ci] if ci < len(SERIES) else EXTRA[(ci - len(SERIES)) % len(EXTRA)]
        ci += 1
        p = c.get("percent")
        ptxt = "%s%%" % p if (p is not None and p >= 1) else "1%未満"
        segs.append({"name": NAMES_JA.get(c["name"], c["name"]), "tokens": int(c["tokens"]), "color": col, "ptxt": ptxt})
    unused = max(cw - used, 0)
    segs.append({"name": "未使用", "tokens": unused, "color": "var(--unused)",
                 "ptxt": "%s%%" % max(100 - int(round(pct)), 0)})

    legend = "".join('<li><span class="sw" style="background:%s"></span>%s %s（枠の%s）</li>'
                     % (s["color"], escape(s["name"]), n(s["tokens"]), s["ptxt"]) for s in segs)
    line_legend = (
        '<li><svg class="lg" viewBox="0 0 28 12" aria-hidden="true"><rect x="0" y="1" width="28" height="10" class="lgarea"/>'
        '<line x1="0" x2="28" y1="2" y2="2" class="ctx"/></svg>コンテキスト</li>'
        '<li><svg class="lg" viewBox="0 0 28 12" aria-hidden="true"><line x1="0" x2="28" y1="6" y2="6" class="auto"/></svg>自動圧縮（%s%%）</li>'
        '<li><svg class="lg" viewBox="0 0 28 12" aria-hidden="true"><line x1="0" x2="28" y1="6" y2="6" class="limit"/></svg>枠の上限（%s）</li>'
        % (auto, man(cw)))
    if comps:
        line_legend += '<li><svg class="lg" viewBox="0 0 28 12" aria-hidden="true"><circle cx="14" cy="6" r="5" class="cmark"/></svg>圧縮を検出</li>'

    note = '<p class="note">内訳は get_usage が無いため省略（使用済み／未使用のみ）。使用率は最終点からの仮定値（枠 %s、自動圧縮 %s%%）。</p>' % (n(cw), auto) if assumed else ""

    summary = "コンテキストは %s トークン（枠 %s の %s%%）。圧縮の検出は %d 回。" % (n(used), n(cw), pct, len(comps))
    cards = [
        ("使用トークン", n(used), "枠 %s" % n(cw)),
        ("使用率", "%s%%" % pct, "枠に対する割合"),
        ("自動圧縮の開始", "%s%%" % auto, "約 %s" % man(cw * auto / 100)),
        ("圧縮が起きた回数", "%d回" % len(comps), "応答 %d 回中" % data["turns"]),
    ]
    cards_html = "".join('<div class="card"><div class="k">%s</div><div class="v">%s</div><div class="s">%s</div></div>'
                         % (escape(k), escape(v), escape(s)) for k, v, s in cards)

    css = """
:root{--bg:#ffffff;--card:#fcfcfb;--t1:#0b0b0b;--t2:#52514e;--mut:#898781;--grid:#e1e0d9;--limit:#898781;--unused:#b4b2a9;--auto:#e34948;--ctx:#2a78d6;--line:#e1e0d9}
@media (prefers-color-scheme:dark){:root{--bg:#1a1a19;--card:#232322;--t1:#f0efec;--t2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;--limit:#898781;--unused:#5c5b57;--auto:#e34948;--ctx:#2a78d6;--line:#3a3a38}}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:var(--t1);font-family:system-ui,-apple-system,"Hiragino Sans","Yu Gothic UI","Noto Sans JP",Meiryo,sans-serif;font-size:14px;line-height:1.5}
.wrap{max-width:720px;margin:0 auto}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;min-width:0}
.k{font-size:12px;color:var(--t2)}.v{font-size:22px;font-weight:600;color:var(--t1);line-height:1.3}.s{font-size:12px;color:var(--mut)}
h3{font-size:14px;margin:0 0 6px;color:var(--t1);font-weight:600}
section{margin-bottom:22px}
.chart{display:block;width:100%;height:auto}
.tx{font-size:12px;fill:var(--t2)}.tx.val{fill:var(--t1);font-weight:600}
.grid{stroke:var(--grid);stroke-width:1}
.ctx{fill:none;stroke:var(--ctx);stroke-width:2.2;stroke-linejoin:round}
.area{fill:var(--ctx);fill-opacity:.12}
.lgarea{fill:var(--ctx);fill-opacity:.18}
.auto{stroke:var(--auto);stroke-width:1.8;stroke-dasharray:2 4;stroke-linecap:round}
.limit{stroke:var(--limit);stroke-width:1.6;stroke-dasharray:8 5}
.dot{fill:var(--ctx);fill-opacity:0}.dot:hover{fill-opacity:1}
.enddot{fill:var(--ctx);stroke:var(--bg);stroke-width:2}
.cmark{fill:none;stroke:var(--auto);stroke-width:2.2}
ul.lgd{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--t2)}
ul.lgd li{display:flex;align-items:center;gap:6px}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px;flex:none}
.lg{width:28px;height:12px;flex:none}
.note{font-size:11px;color:var(--mut);margin:6px 0 0}
@media (max-width:520px){.cards{grid-template-columns:repeat(2,1fr)}.tx{font-size:20px}}
"""
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>コンテキスト使用量</title><style>%s</style></head><body><div class="wrap">
<h2 class="sr-only">%s</h2>
<div class="cards">%s</div>
<section><h3>コンテキストの推移（応答ごと）</h3>
%s
<ul class="lgd">%s</ul></section>
<section><h3>現在の内訳（枠全体に対する割合）</h3>
%s
<ul class="lgd">%s</ul>%s</section>
%s<p class="note">ログ: %s</p>
</div></body></html>
""" % (css, escape(summary), cards_html, line_svg(data, cw, auto, comps, data["turns"]), line_legend,
       bar_svg(segs, cw), legend, note,
       '<p class="note">ログと get_usage の値が食い違っています</p>' if mismatch else "",
       escape(str(data["session_id"])[:8]))


def main():
    ap = argparse.ArgumentParser(description="Write a context-usage chart (single HTML) for a Claude Code session.")
    ap.add_argument("--session-id", help="session id (default: env CLAUDE_CODE_SESSION_ID)")
    ap.add_argument("--path", help="explicit session jsonl path (highest priority)")
    ap.add_argument("--projects-dir", help="override <config dir>/projects")
    ap.add_argument("--max-points", type=int, default=300)
    ap.add_argument("--usage-json", help="the `context` object returned by get_usage, as a JSON string")
    ap.add_argument("--usage-file", help="same, read from a file")
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "claude-context-chart", "context-usage.html"))
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    data = cu.collect(cu.find_jsonl(args), args.max_points)
    usage, assumed = None, False
    try:
        if args.usage_json:
            usage = json.loads(args.usage_json)
        elif args.usage_file:
            with open(args.usage_file, encoding="utf-8-sig") as fp:
                usage = json.load(fp)
    except (ValueError, OSError) as e:
        sys.exit("cannot read usage JSON: %s (try --usage-file)" % type(e).__name__)
    if isinstance(usage, dict) and isinstance(usage.get("context"), dict):
        usage = usage["context"]
    if usage is None:
        assumed = True
        cw, used = 1000000, data["last"]
        usage = {"tokensUsed": used, "contextWindow": cw, "percentUsed": round(used / cw * 100),
                 "autoCompactsAtPercent": 97, "categories": [{"name": "使用済み", "tokens": used, "percent": round(used / cw * 100)}]}
    try:
        usage["tokensUsed"], usage["contextWindow"]
        usage.setdefault("percentUsed", round(usage["tokensUsed"] / usage["contextWindow"] * 100))
        usage.setdefault("categories", [{"name": "使用済み", "tokens": usage["tokensUsed"], "percent": usage["percentUsed"]}])
    except KeyError as e:
        sys.exit("usage JSON is missing a required key: %s" % e)

    mismatch = False
    if not assumed and data["last"] > 0:
        try:
            ref = float(usage["tokensUsed"])
            mismatch = abs(ref - data["last"]) >= 0.1 * max(ref, data["last"])
        except (TypeError, ValueError):
            pass
    if mismatch:
        sys.stderr.write("warning: get_usage and the log disagree by 10% or more; the log may belong to another session\n")
    html = build_html(data, usage, assumed, mismatch)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(html)
    print(os.path.abspath(args.out))
    print("使用 %s / %s (%s%%)、応答 %d 回、圧縮検出 %d 回、%d バイト%s" % (
        n(usage["tokensUsed"]), n(usage["contextWindow"]), usage["percentUsed"], data["turns"],
        len(data["compactions"]), len(html.encode("utf-8")), "（使用量は仮定値）" if assumed else ""))


if __name__ == "__main__":
    main()
