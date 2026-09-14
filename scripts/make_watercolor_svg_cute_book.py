#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把当天的英文散文诗做成「可爱造型水彩风 SVG」的动态 HTML 绘本（EN/中文/双语）。

和 make_watercolor_svg_book.py（涂鸦风）共用同一套引擎（CSS / 动画 / 金色词高亮 / 语言切换 /
响应式），**只把插画换成圆头圆脑的 chibi 水彩风**：大圆脑袋、小身子、腮红、笑脸、漂浮的小爱心。

用法：
    make_watercolor_svg_cute_book.py --json /tmp/poem.json --out ./book-cute/index.html
    make_watercolor_svg_cute_book.py --json /tmp/poem.json --zh-file zh.json --out ...
"""

import argparse
import html
import json
import os
import sys

from make_watercolor_svg_book import (defs, wash, line, build_html,
                                       split_stanzas, ROMAN, ORDER)

# 马卡龙水彩调色盘
PIN = "#5b4636"          # 软棕描边
SK = "#ffe6cf"           # 皮肤
P = {
    "paper": "#fbf6ee", "ink": PIN, "skin": SK,
    "blue": "#c4e7f6", "blue2": "#86c5ef", "green": "#d3f0c4", "green2": "#a6d99a",
    "warm": "#ffe1b0", "warm2": "#f8cf90", "grey": "#e3e4ec", "grey2": "#c7c9d4",
    "rose": "#f9c4cd", "gold": "#ffd98a", "cheek": "#f6ab9f", "leaf": "#9ed29a",
    "cream": "#fff3df",
}

HEART = "M0,-6 C-6,-16 -22,-8 -14,6 C-9,15 0,20 0,20 C0,20 9,15 14,6 C22,-8 6,-16 0,-6 Z"


def rrect(x, y, w, h, fill, col=PIN, rad=16):
    d = ('M%.0f %.0f h%.0f a%.0f %.0f 0 0 1 %.0f %.0f v%.0f a%.0f %.0f 0 0 1 -%.0f %.0f '
         'h-%.0f a%.0f %.0f 0 0 1 -%.0f -%.0f v-%.0f a%.0f %.0f 0 0 1 %.0f -%.0f Z') % (
        x + rad, y, w - 2 * rad, rad, rad, rad, rad, h - 2 * rad, rad, rad, rad, rad,
        w - 2 * rad, rad, rad, rad, rad, h - 2 * rad, rad, rad, rad, rad)
    return line(d, 3, col, fill, "wc2")


def cheek(x, y, s=1.0):
    return '<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s" opacity="0.8" filter="url(#wc)"/>' % (
        x, y, 3.6 * s, P["cheek"])


def person(x, y, s=1.0, skin=SK, cloth=P["blue2"], hair=PIN, cls="wx-float"):
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += '<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s" stroke="%s" stroke-width="2.4" filter="url(#rough)"/>' % (
        x, y - 30 * s, 19 * s, skin, PIN)
    # 头发小帽
    g += '<path d="M%.0f %.0f a%.0f %.0f 0 0 1 %.0f 0" fill="%s" stroke="%s" stroke-width="2.4" filter="url(#rough)"/>' % (
        x - 19 * s, y - 30 * s, 19 * s, 19 * s, 38 * s, hair, PIN)
    # 眼睛 + 笑
    g += '<circle cx="%.0f" cy="%.0f" r="2.6" fill="%s"/>' % (x - 7 * s, y - 31 * s, PIN)
    g += '<circle cx="%.0f" cy="%.0f" r="2.6" fill="%s"/>' % (x + 7 * s, y - 31 * s, PIN)
    g += '<path d="M%.0f %.0f q%.0f %.0f %.0f 0" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round" filter="url(#rough)"/>' % (
        x - 7 * s, y - 22 * s, 7 * s, 7 * s, 14 * s, PIN)
    g += cheek(x - 12 * s, y - 23 * s, s) + cheek(x + 12 * s, y - 23 * s, s)
    # 身子（小圆角）
    g += '<path d="M%.0f %.0f Q %.0f %.0f %.0f %.0f L %.0f %.0f Q %.0f %.0f %.0f %.0f Z" fill="%s" stroke="%s" stroke-width="2.4" filter="url(#rough)"/>' % (
        x - 16 * s, y - 14 * s, x - 19 * s, y + 18 * s, x - 12 * s, y + 32 * s,
        x + 12 * s, y + 32 * s, x + 19 * s, y + 18 * s, x + 16 * s, y - 14 * s, cloth, PIN)
    g += '<path d="M%.0f %.0f L %.0f %.0f M%.0f %.0f L %.0f %.0f" stroke="%s" stroke-width="%.0f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x - 8 * s, y + 32 * s, x - 9 * s, y + 48 * s, x + 8 * s, y + 32 * s, x + 9 * s, y + 48 * s, PIN, 4 * s)
    g += '</g>'
    return g


def heart(x, y, s=1.0, fill=P["rose"]):
    return ('<g transform="translate(%.0f,%.0f) scale(%.2f)"><g class="wx-heart" style="transform-origin:center">'
            '<path d="%s" fill="%s" opacity="0.85" filter="url(#wc)"/></g></g>' % (x, y, s, HEART, fill))


def tree(x, y, s=1.0, cls="wx-sway"):
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += '<path d="M%.0f %.0f L %.0f %.0f" stroke="%s" stroke-width="%.0f" stroke-linecap="round" filter="url(#rough)"/>' % (x, y, x, y - 30 * s, "#9a7b54", 7 * s)
    g += wash(x, y - 48 * s, 34 * s, 30 * s, P["green"], 0.85)
    g += wash(x - 14 * s, y - 40 * s, 22 * s, 20 * s, P["green2"], 0.75)
    g += '</g>'
    return g


def sun(x, y, r=32, cls="wx-spin"):
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    for i in range(12):
        rr = 'rotate(%d %d %d)' % (i * 30, x, y)
        g += '<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="4" stroke-linecap="round" filter="url(#rough)" transform="%s"/>' % (
            x, y - r - 6, x, y - r - 22, P["gold"], rr)
    g += '<circle cx="%.0f" cy="%.0f" r="%s" fill="%s" opacity="0.95" filter="url(#wc)"/>' % (x, y, r, P["gold"])
    g += '<circle cx="%.0f" cy="%.0f" r="3" fill="%s"/><circle cx="%.0f" cy="%.0f" r="3" fill="%s"/>' % (x - 11, y - 4, PIN, x + 11, y - 4, PIN)
    g += '<path d="M%.0f %.0f q%.0f %.0f %.0f 0" fill="none" stroke="%s" stroke-width="2.6" stroke-linecap="round" filter="url(#rough)"/>' % (x - 9, y + 8, 9, 9, 18, PIN)
    g += '</g>'
    return g


# ---------------- 场景（chibi 水彩） ----------------
def cover_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(330, 520, 360, 300, P["grey"], 0.5)
    s += wash(880, 460, 380, 320, P["green"], 0.5)
    s += wash(1040, 260, 120, 110, P["gold"], 0.8)
    for i, (bx, bw, bh) in enumerate([(150, 90, 180), (250, 70, 140), (300, 100, 220), (390, 60, 130)]):
        s += rrect(bx, 620 - bh, bw, bh, P["grey"], PIN)
    s += rrect(360, 310, 18, 90, P["grey2"], PIN)   # 烟囱
    for i, (bx, bw, bh) in enumerate([(760, 120, 150), (880, 100, 190), (980, 90, 140)]):
        s += rrect(bx, 640 - bh, bw, bh, P["cream"], PIN)
    s += tree(840, 650, 1.1) + tree(1030, 660, 0.9)
    s += line('M600 880 Q 640 720 680 640 Q 700 560 720 470', 5, P["warm2"], "none", "wx-float")
    s += sun(1050, 260, 34)
    s += heart(470, 360, 1.0) + heart(720, 300, 0.8, P["blue"])
    return s


def city_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(600, 220, 520, 150, P["grey"], 0.4)
    for i, (bx, bw, bh) in enumerate([(120, 110, 260), (250, 90, 200), (840, 120, 280), (970, 90, 210)]):
        s += rrect(bx, 700 - bh, bw, bh, P["cream"], PIN)
    s += wash(600, 760, 560, 70, "#e7e1d3", 0.7)
    s += line('M120 770 H1080', 4, PIN, "none", "wx-float")
    for cx in [400, 580, 760]:
        s += rrect(cx, 700, 130, 70, P["blue"], PIN)
        s += '<circle cx="%.0f" cy="%.0f" r="11" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (cx + 28, 778, PIN, PIN)
        s += '<circle cx="%.0f" cy="%.0f" r="11" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (cx + 102, 778, PIN, PIN)
        s += cheek(cx + 40, 720, 0.7)  # 车头小腮红纯装饰
    s += line('M150 700 v-90', 4, PIN, "none", "wx-float")
    s += '<circle cx="150" cy="600" r="13" fill="#f29b8f" filter="url(#wc)"/>'
    s += person(250, 770, 1.0, cloth=P["rose"])
    s += heart(150, 560, 0.7, P["rose"])
    return s


def council_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(600, 200, 420, 150, P["gold"], 0.35)
    s += rrect(260, 490, 680, 90, P["warm"], PIN)
    for px in [320, 470, 620, 770, 920]:
        s += person(px, 470, 0.95, cloth=(P["blue2"] if px < 600 else P["rose"]))
    s += rrect(520, 470, 120, 80, P["cream"], PIN)   # 城市沙盘
    s += rrect(770, 470, 70, 80, P["grey"], PIN)     # 焚烧炉
    s += line('M805 470 v-44', 3, PIN, "none", "wx-float")
    s += wash(805, 430, 14, 30, P["grey2"], 0.5)
    s += rrect(980, 360, 40, 110, P["cream"], PIN)
    s += wash(1000, 350, 22, 44, P["grey"], 0.4)
    s += heart(560, 420, 0.9, P["gold"]) + heart(860, 410, 0.7, P["rose"])
    return s


def policy_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(600, 300, 520, 260, P["green"], 0.32)
    for i, (bx, bw, bh) in enumerate([(120, 110, 200), (250, 80, 150), (960, 110, 220)]):
        s += rrect(bx, 640 - bh, bw, bh, P["cream"], PIN)
    s += rrect(150, 396, 70, 44, P["warm"], PIN)
    s += wash(185, 418, 30, 26, P["rose"], 0.5)
    s += wash(600, 760, 560, 64, "#e7e1d3", 0.75)
    s += line('M120 740 H1080', 4, PIN, "none", "wx-float")
    s += line('M120 782 H1080', 4, PIN, "none", "wx-float")
    s += person(430, 700, 0.9, cloth=P["blue2"])
    s += line('M470 700 l40 -34', 4, PIN, "none", "")
    s += tree(640, 760, 1.0) + tree(720, 768, 0.85) + tree(800, 762, 1.0)
    s += heart(560, 690, 0.8, P["green2"])
    return s


def build_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(600, 200, 480, 140, P["blue"], 0.35)
    s += rrect(220, 460, 520, 100, P["warm"], PIN)
    for r in range(3):
        for c in range(4):
            s += rrect(260 + c * 52, 470 + r * 34, 44, 30, P["blue"], P["blue2"])
    g = '<g class="wx-rain" style="transform-origin:center">'
    for i in range(8):
        g += '<line x1="%.0f" y1="590" x2="%.0f" y2="614" stroke="%s" stroke-width="3" stroke-linecap="round" opacity="0.7"/>' % (240 + i * 70, 240 + i * 70, P["blue2"])
    s += g + '</g>'
    s += wash(560, 760, 560, 60, P["blue"], 0.55)
    s += rrect(520, 722, 60, 38, P["cream"], PIN)
    s += line('M550 722 v-22', 2, PIN, "none", "wx-float")
    s += rrect(120, 700, 214, 60, P["gold"], PIN)
    s += '<circle cx="182" cy="744" r="11" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (PIN, PIN)
    s += '<circle cx="300" cy="744" r="11" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (PIN, PIN)
    s += rrect(880, 610, 150, 90, P["cream"], PIN)
    s += wash(955, 650, 70, 26, P["gold"], 0.7)
    s += sun(1030, 240, 30)
    return s


def school_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(980, 320, 220, 220, P["gold"], 0.4)
    s += rrect(200, 360, 800, 360, P["cream"], PIN)
    s += rrect(260, 410, 300, 150, "#d8efe0", PIN)
    s += '<text x="278" y="470" font-family="Georgia,serif" font-size="28" fill="%s" filter="url(#rough)" opacity="0.85">adapt · enhance</text>' % PIN
    s += '<text x="278" y="520" font-family="Georgia,serif" font-size="28" fill="%s" filter="url(#rough)" opacity="0.85">mitigate</text>' % PIN
    s += rrect(300, 606, 560, 40, P["warm"], PIN)
    for i, cx in enumerate([360, 470, 580, 690, 800]):
        s += person(cx, 600, 0.78, cloth=[P["blue2"], P["rose"], P["green2"], P["gold"], P["blue2"]][i % 5])
    s += person(980, 600, 1.0, cloth=P["green2"])
    s += line('M900 360 h180 v360', 3, PIN, "none", "wx-float")
    s += heart(700, 380, 0.9, P["rose"]) + heart(470, 360, 0.7, P["gold"])
    return s


def sky_cute():
    s = wash(600, 460, 900, 900, P["paper"], 1.0)
    s += wash(300, 200, 360, 150, P["grey"], 0.3)
    s += sun(1020, 230, 38)
    for i, (bx, col) in enumerate([(180, P["rose"]), (420, P["blue"]), (900, P["green"])]):
        s += rrect(bx, 520, 150, 120, P["cream"], PIN)
        s += line('M%.0f 520 l75 -46 l75 46' % bx, 3, PIN, col, "wc2")
    s += '<g transform="translate(300,250) scale(1.1)"><path d="%s" fill="%s" opacity="0.8" filter="url(#wc)"/></g>' % (HEART, P["rose"])
    for i, cx in enumerate([300, 520, 760, 1010]):
        s += person(cx, 760, 0.92, cloth=[P["blue2"], P["warm2"], P["green2"], P["rose"]][i % 4])
    s += rrect(620, 500, 150, 150, P["cream"], PIN)
    s += wash(695, 560, 64, 22, P["gold"], 0.85, cls="wx-float")
    s += heart(700, 470, 0.9, P["gold"]) + heart(470, 430, 0.7, P["blue"])
    return s


SCENES = {"cover": cover_cute, "city": city_cute, "council": council_cute,
          "policy": policy_cute, "build": build_cute, "school": school_cute, "sky": sky_cute}

# 关键词 → 可爱版场景名（按故事顺序：城市清晨 → 议会 → 政策 → 建设 → 学校 → 天空）
ORDER_CUTE = ["city", "council", "policy", "build", "school", "sky"]
SCENE_HINTS_CUTE = (
    ("council", ("council", "meeting", "vote", "controversial", "argue", "debate", "inevitable")),
    ("build", ("solar", "panel", "roof", "feasible", "bus", "shop", "cheaper", "sensor", "river")),
    ("school", ("school", "children", "learn", "teacher", "class", "patience", "lesson", "word")),
    ("policy", ("policy", "priority", "housing", "tax", "subsidies", "farmer", "subsidy")),
    ("sky", ("sky", "smoke", "market", "repair", "fade", "diverse", "future")),
    ("city", ("city", "traffic", "morning", "air", "road", "street", "car")),
)


def pick_cute_scene(text):
    low = (text or "").lower()
    best, bestn = None, 0
    for name, keys in SCENE_HINTS_CUTE:
        n = sum(1 for k in keys if k in low)
        if n > bestn:
            best, bestn = name, n
    return best


def assign_cute_scenes(stanzas):
    out, used = [], {"cover"}
    for i, st in enumerate(stanzas):
        sc = pick_cute_scene(" ".join(st))
        if not sc or sc in used:
            sc = next((o for o in ORDER_CUTE if o not in used), ORDER_CUTE[i % len(ORDER_CUTE)])
        used.add(sc)
        out.append(sc)
    return out


def svg_cute(scene):
    fn = SCENES.get(scene, city_cute)
    return ('<svg class="art-svg" viewBox="0 0 1200 900" preserveAspectRatio="xMidYMid meet" '
            'xmlns="http://www.w3.org/2000/svg" role="img">%s%s</svg>' % (defs(), fn()))


def main():
    ap = argparse.ArgumentParser(description="可爱水彩 chibi SVG 的动态绘本（EN/中文/双语）")
    ap.add_argument("--json", help="内容 JSON（title/date/subtitle/story/words；兼容旧键 poem）")
    ap.add_argument("--zh-file")
    ap.add_argument("--out")
    ap.add_argument("--title"); ap.add_argument("--subtitle"); ap.add_argument("--date")
    ap.add_argument("--json-out", action="store_true")
    ap.add_argument("--rate", type=float, default=0.92,
                    help="朗读语速（0.5–1.5；默认 0.92，比常速慢一点方便跟读）")
    a = ap.parse_args()
    rate = max(0.5, min(1.5, a.rate))

    data = {}
    if a.json:
        with open(a.json, encoding="utf-8") as f:
            data = json.load(f)
    title = a.title or data.get("title") or "Untitled"
    subtitle = a.subtitle or data.get("subtitle") or "用今天背过的词写成"
    date = a.date or data.get("date") or ""
    words = data.get("words") or []
    # 键名优先 story（童话）/ tale，最后才认旧的 poem
    stanzas = split_stanzas(data.get("story") or data.get("tale") or data.get("poem") or [])
    if not stanzas:
        raise SystemExit("JSON 里没有正文段落（键名用 story，兼容 poem）")

    # ⚠️ 这里**不能**再放硬编码的 DEFAULT_ZH：
    #   之前内置的是「城市规划/议会」那首诗的 6 段译文，一旦新内容没给译文，
    #   中文模式就会**串上城市那套旧译文**（段数不一样时更是直接张冠李戴）。
    #   译文只从「JSON 自带」或「--zh-file」来，没有就留空、由调用方补。
    zh = {}

    def _absorb(z):
        if isinstance(z, list):
            vals = [str(v) for v in z]
            # 兼容「按行对齐」写法（段落之间有 "" 空行）→ 去掉空行再按段编号
            if any(not v.strip() for v in vals) and \
               len([v for v in vals if v.strip()]) == len(stanzas):
                vals = [v for v in vals if v.strip()]
            for i, v in enumerate(vals[:len(stanzas)]):
                zh[str(i + 1)] = v
        elif isinstance(z, dict):
            if isinstance(z.get("zh"), list):
                _absorb(z["zh"])
            else:
                for k, v in z.items():
                    zh[str(k)] = v

    # 1) 正文 JSON 自带的中文优先（zh / zh_stanzas / translation）
    for key in ("zh", "zh_stanzas", "translation"):
        if data.get(key):
            _absorb(data[key])
            break
    # 2) --zh-file 覆盖
    if a.zh_file:
        _absorb(json.load(open(a.zh_file, encoding="utf-8")))

    panels = [{"en": st, "zh": zh.get(str(i + 1), "")} for i, st in enumerate(stanzas)]
    missing = sum(1 for p in panels if not p["zh"])
    if missing:
        sys.stderr.write("⚠️  有 %d/%d 段没有中文译文，中文模式只显示有译文的部分；"
                         "可用 --zh-file 补上。\n" % (missing, len(panels)))

    out = os.path.abspath(a.out) if a.out else os.path.join(os.getcwd(), "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    page = build_html(title, subtitle, date, panels, words, svg_fn=svg_cute,
                      assign_fn=assign_cute_scenes, rate=rate)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(json.dumps({"html": out, "panels": len(panels), "words": len(words)}, ensure_ascii=False)
          if a.json_out else "🎀 可爱水彩绘本已生成：%s（%d 段 · %d 词 · EN/中文/双语）" % (out, len(panels), len(words)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
