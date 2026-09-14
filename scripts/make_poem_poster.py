#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_poem_poster.py — 把一首英文散文诗做成一张可以分享的图片（PNG）。

用法（二选一）：

  # A. 推荐：把内容写进一个 JSON，再渲染
  python3 make_poem_poster.py --json /tmp/poem.json

  # B. 命令行直接给
  python3 make_poem_poster.py --title "The Quiet Tide" \
      --poem-file /tmp/poem.txt --words anticipate,fluctuate,deteriorate

poem.json 长这样：
  {
    "title": "The Quiet Tide of Words",
    "date": "2026-09-12",                 # 可省略，默认今天
    "subtitle": "写在第 3 天",              # 可省略
    "poem": ["第一行", "第二行", "..."],     # 也可以是含 \n 的整段字符串
    "words": ["anticipate", "fluctuate"]   # 今天背过的词；诗里出现它们会被点亮
  }

产物：
  <数据目录>/poems/poem-YYYY-MM-DD.html   ← 自包含网页（可单独打开/分享）
  <数据目录>/poems/poem-YYYY-MM-DD.png    ← 真正的图片（用本机 Chrome 无头渲染）

渲染依赖：本机装了 Google Chrome（macOS 默认路径）。
没有 Chrome 时只产 HTML，并明确告诉你 PNG 没生成。
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

HOME = os.path.expanduser("~")
DATA_DIR = os.environ.get("IELTS_DATA_DIR", os.path.join(HOME, ".workbuddy", "ielts-prep"))
POEM_DIR = os.path.join(DATA_DIR, "poems")

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]

# 版面参数（逻辑像素；PNG 会按 --scale 放大）
W = 1000
MIN_H = 1000     # 海报最矮也要这么高
PAD = 92
FS_POEM = 30
LH_POEM = 1.95
FS_TITLE = 56
FS_WORDS = 20
LH_WORDS = 1.9


def find_chrome(explicit=None):
    for c in ([explicit] if explicit else []) + CHROME_CANDIDATES:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def as_lines(poem):
    """把 poem（列表 / 含 \n 的字符串）统一成行列表。"""
    if isinstance(poem, (list, tuple)):
        raw = [str(x) for x in poem]
    else:
        raw = str(poem or "").split("\n")
    # 去掉首尾空行，行内右侧空白去掉，中间的空行保留（诗的停顿）
    while raw and not raw[0].strip():
        raw.pop(0)
    while raw and not raw[-1].strip():
        raw.pop()
    return [ln.rstrip() for ln in raw]


def word_forms(w):
    """目标词 + 常见屈折形式，用于在诗里高亮。"""
    w = w.lower()
    forms = {w}
    if w.endswith("e"):
        forms |= {w + "s", w + "d", w[:-1] + "ing"}
    elif w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    else:
        forms |= {w + "s", w + "ed", w + "ing"}
    if w.endswith(("s", "x", "z", "ch", "sh")):      # diminish → diminishes，别漏了 -es
        forms |= {w + "es"}
    forms |= {w + "ly"}
    return {f for f in forms if len(f) > 2}


def highlight(text, words):
    """把诗里出现的目标词包一层 <em>，其余部分转义。大小写不敏感、按词边界匹配。"""
    forms = {}
    for w in words:
        for f in word_forms(w):
            forms[f] = w
    if not forms:
        return html.escape(text)
    pat = re.compile(r"\b(" + "|".join(sorted(map(re.escape, forms), key=len, reverse=True)) + r")\b",
                     re.IGNORECASE)
    out, last = [], 0
    for m in pat.finditer(text):
        out.append(html.escape(text[last:m.start()]))
        out.append('<em class="v">' + html.escape(m.group(0)) + "</em>")
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def estimate_height(title, lines, words):
    inner = W - 2 * PAD
    h = 0
    h += 112                                   # 顶部留白
    h += 34                                    # eyebrow
    h += 34                                    # date
    tlines = max(1, int(len(title) / max(8, inner / (FS_TITLE * 0.55))) + 1)
    h += tlines * int(FS_TITLE * 1.25) + 30    # 标题
    h += 26                                    # 标题与诗之间的空隙
    cpl = max(12, int(inner / (FS_POEM * 0.50)))
    for ln in lines:
        if not ln.strip():
            h += int(FS_POEM * LH_POEM * 0.55)  # 空行只占一点点
        else:
            h += max(1, -(-len(ln) // cpl)) * int(FS_POEM * LH_POEM)
    h += 64                                    # 分隔线上下留白
    if words:
        h += 30                                # 「今日词汇」小标题
        wtxt = "  ·  ".join(words)
        wcpl = max(12, int(inner / (FS_WORDS * 0.53)))
        h += max(1, -(-len(wtxt) // wcpl)) * int(FS_WORDS * LH_WORDS)
    h += 128                                   # 底部留白
    return max(900, h)


def build_html(title, lines, words, day, subtitle):
    body = []
    for ln in lines:
        if ln.strip():
            body.append('<p class="ln">%s</p>' % highlight(ln, words))
        else:
            body.append('<p class="ln gap">&nbsp;</p>')
    poem_html = "\n      ".join(body) or '<p class="ln gap">&nbsp;</p>'
    words_html = ""
    if words:
        chips = "".join('<span class="chip">%s</span>' % html.escape(w) for w in words)
        words_html = (
            '\n    <section class="vocab">\n'
            '      <div class="vlabel">今日词汇 · %d words</div>\n'
            '      <div class="chips">%s</div>\n'
            "    </section>" % (len(words), chips)
        )
    sub = '<div class="sub">%s</div>' % html.escape(subtitle) if subtitle else ""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>%(TITLE)s</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:%(W)dpx;min-height:%(MINH)dpx}
  body{
    background:
      radial-gradient(1100px 620px at 12%% -8%%, rgba(232,176,106,.20), transparent 60%%),
      radial-gradient(900px 560px at 100%% 108%%, rgba(96,132,196,.20), transparent 62%%),
      linear-gradient(168deg,#141a2e 0%%,#1b2440 42%%,#101728 100%%);
    color:#f4efe6;
    font-family:Georgia,"Times New Roman","Songti SC",serif;
    padding:%(PAD)dpx;
    display:flex;flex-direction:column;
    position:relative;overflow:hidden;
  }
  body:before{content:"";position:absolute;inset:26px;border:1px solid rgba(232,176,106,.22);
    border-radius:4px;pointer-events:none}
  .eyebrow{font-family:-apple-system,"PingFang SC",sans-serif;font-size:11.5px;
    letter-spacing:.32em;text-transform:uppercase;color:#e0b478;margin-bottom:14px}
  .date{font-family:-apple-system,"PingFang SC",sans-serif;font-size:12.5px;letter-spacing:.16em;
    color:#8b95ad;margin-bottom:30px}
  h1{font-size:%(FST)dpx;line-height:1.22;font-weight:400;font-style:italic;
    color:#fdf8ef;letter-spacing:.01em;margin-bottom:8px}
  .sub{font-family:-apple-system,"PingFang SC",sans-serif;font-size:13px;color:#8b95ad;
    margin-bottom:26px}
  .poem{margin-top:8px;flex:1 1 auto}
  .ln{font-size:%(FSP)dpx;line-height:%(LHP)s;color:#e6e0d6;letter-spacing:.005em;
    text-wrap:pretty;hanging-punctuation:first}
  .ln.gap{line-height:.55}
  em.v{font-style:italic;color:#f0c98a;border-bottom:1px solid rgba(240,201,138,.42);
    padding-bottom:1px;font-weight:400}
  .vocab{margin-top:26px;border-top:1px solid rgba(255,255,255,.10);padding-top:28px}
  .vlabel{font-family:-apple-system,"PingFang SC",sans-serif;font-size:11.5px;letter-spacing:.24em;
    text-transform:uppercase;color:#e0b478;margin-bottom:16px}
  .chips{display:flex;flex-wrap:wrap;gap:8px 9px}
  .chip{font-family:-apple-system,"PingFang SC",sans-serif;font-size:%(FSW)dpx;line-height:1;
    color:#c9d2e4;background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.09);
    border-radius:999px;padding:7px 13px}
  .mark{position:absolute;right:%(PAD)dpx;bottom:44px;
    font-family:-apple-system,"PingFang SC",sans-serif;font-size:11px;letter-spacing:.26em;
    color:rgba(224,180,120,.55);text-transform:uppercase}
</style>
<script>
/* 量出真实高度写进 title，供无头浏览器读取（截屏只截视口，必须先知道高度） */
addEventListener("load", function () {
  document.title = "H=" + Math.max(document.body.scrollHeight,
                                   document.documentElement.scrollHeight);
});
</script>
</head>
<body>
  <div class="eyebrow">Yaya Words · Today's Prose Poem</div>
  <div class="date">%(DATE)s</div>
  <h1>%(TITLE)s</h1>%(SUB)s
  <div class="poem">
      %(POEM)s
  </div>%(VOCAB)s
  <div class="mark">丫丫雅思单词</div>
</body>
</html>
""" % {
        "W": W, "MINH": MIN_H, "PAD": PAD,
        "FST": FS_TITLE, "FSP": FS_POEM, "LHP": LH_POEM, "FSW": FS_WORDS,
        "DATE": html.escape(day), "TITLE": html.escape(title),
        "SUB": sub, "POEM": poem_html, "VOCAB": words_html,
    }


def _chrome_noise(text):
    """把无头 Chrome 在 macOS 上的固定噪音滤掉，只留真正要看的报错。"""
    keep = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if "CVDisplayLinkCreateWithCGDisplay" in ln:
            continue
        if "task_policy_set" in ln or "allocator multiple times" in ln:
            continue
        if "installwebapp" in ln or "externally_managed_app_manager" in ln:
            continue
        if "bytes written to file" in ln:        # 渲染成功是正常信息，不用当报错
            continue
        if ln.startswith("[") and "INFO:" in ln:
            continue
        keep.append(ln)
    return "\n".join(keep)


def measure_height(chrome, html_path):
    """用无头 Chrome 读页面 title 里的真实高度（截屏只截视口，必须先量）。"""
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-dev-shm-usage", "--virtual-time-budget=2000", "--dump-dom",
        "--window-size=%d,1200" % W, "file://" + html_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"<title>\s*H=(\d+)\s*</title>", r.stdout or "")
    if not m:                                    # 页面还没写上高度就再试一次
        m = re.search(r"H=(\d+)", r.stdout or "")
    return int(m.group(1)) if m else None


def render_png(chrome, html_path, png_path, height, scale):
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-sandbox", "--disable-dev-shm-usage",
        "--force-device-scale-factor=%s" % scale,
        "--window-size=%d,%d" % (W, height),
        "--screenshot=%s" % png_path,
        "file://" + html_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = os.path.exists(png_path) and os.path.getsize(png_path) > 0
    return ok, _chrome_noise(r.stderr or r.stdout or "")


def main():
    ap = argparse.ArgumentParser(description="把英文散文诗渲染成一张图片")
    ap.add_argument("--json", help="内容 JSON 文件（title/date/subtitle/story/words；兼容旧键 poem）")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--poem-file", help="诗正文文件（每行一句）")
    ap.add_argument("--poem", help="诗正文（\\n 分行）")
    ap.add_argument("--words", help="今天背过的词，逗号分隔")
    ap.add_argument("--date")
    ap.add_argument("--out", help="输出目录，默认 %s" % POEM_DIR)
    ap.add_argument("--name", help="文件名主干，默认 poem-<日期>")
    ap.add_argument("--scale", type=int, default=2, help="PNG 放大倍数（默认 2）")
    ap.add_argument("--chrome", help="Chrome 可执行文件路径")
    ap.add_argument("--no-png", action="store_true", help="只产 HTML，不渲染 PNG")
    ap.add_argument("--json-out", action="store_true", help="以 JSON 输出产物路径")
    a = ap.parse_args()

    data = {}
    if a.json:
        with open(a.json, encoding="utf-8-sig") as f:
            data = json.load(f)
    title = a.title or data.get("title") or "Untitled"
    subtitle = a.subtitle or data.get("subtitle") or ""
    day = a.date or data.get("date") or date.today().isoformat()
    if a.poem_file:
        with open(a.poem_file, encoding="utf-8-sig") as f:
            lines = as_lines(f.read())
    elif a.poem:
        lines = as_lines(a.poem)
    else:
        # 键名优先 story（童话）/ tale，最后才认旧的 poem
        lines = as_lines(data.get("story") or data.get("tale") or data.get("poem") or "")
    if a.words:
        words = [w.strip() for w in re.split(r"[,\n]", a.words) if w.strip()]
    else:
        words = [str(w).strip() for w in (data.get("words") or []) if str(w).strip()]
    if not lines:
        print("⚠️ 诗正文是空的：用 --json / --poem-file / --poem 给内容。", file=sys.stderr)
        return 2

    out_dir = os.path.expanduser(a.out or POEM_DIR)
    os.makedirs(out_dir, exist_ok=True)
    stem = a.name or ("poem-" + day)
    html_path = os.path.join(out_dir, stem + ".html")
    png_path = os.path.join(out_dir, stem + ".png")

    height_est = estimate_height(title, lines, words)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(title, lines, words, day, subtitle))

    png_ok, chrome_note, size_txt = False, "", None
    if not a.no_png:
        chrome = find_chrome(a.chrome)
        if chrome:
            measured = measure_height(chrome, html_path)      # 先量真实高度
            height = max(MIN_H, measured or height_est)
            png_ok, chrome_note = render_png(chrome, html_path, png_path, height, a.scale)
            if png_ok:
                size_txt = "%dx%d" % (W * a.scale, height * a.scale)
        else:
            chrome_note = "没找到 Chrome/Chromium，未生成 PNG（HTML 已生成，可直接打开预览）"

    result = {"html": html_path, "png": png_path if png_ok else None,
              "words": len(words), "lines": len(lines),
              "size": size_txt, "note": chrome_note}
    # --no-png 是「我只想快出 HTML」，不是失败；只有「想渲染 PNG 但渲染不出来」才返回 1
    code = 0 if (a.no_png or png_ok) else 1
    if a.json_out:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return code
    print("🖼️ 诗卡 HTML：%s" % html_path)
    if png_ok:
        print("🖼️ 诗卡图片：%s（%s，%d 个词）" % (png_path, result["size"], len(words)))
    elif chrome_note:
        print("⚠️ %s" % chrome_note)
    elif a.no_png:
        print("（--no-png：按要求只出 HTML）")
    return code


if __name__ == "__main__":
    sys.exit(main())
