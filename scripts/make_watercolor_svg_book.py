#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把当天的英文散文诗做成「水彩涂鸦风 SVG 配图 + 动态效果」的可响应式 HTML 绘本。

和 make_comic.py（哆啦 A 梦卡通）、make_watercolor_book.py（AI 位图）的区别：
  - 本脚本**插画是手写的 SVG**（feTurbulence 水彩边缘 + 抖动笔触的涂鸦线），不依赖外部图片；
  - 支持 **英文 / 中文 / 双语** 三档文字切换；
  - 滚动式排版，响应式（桌面图文左右、移动端上下堆叠）。

用法：
    make_watercolor_svg_book.py --json /tmp/poem.json [--out ./book/index.html] [--zh-file zh.json]

poem.json 给英文（title/date/subtitle/poem/words）；中文翻译内置，也可用 --zh-file 覆盖
（{"1":"...","2":"...", ...} 或 {"zh":["段1","段2",...]}）。
"""

import argparse
import html
import json
import math
import os
import sys

W, H = 1200, 900  # SVG 逻辑画布

# ---------- 水彩调色盘 ----------
P = {
    "paper": "#f7f2e7",
    "cream": "#efe7d6",
    "ink": "#3f3a36",
    "skin": "#f3d9b8",
    "blue": "#9dc4dc",
    "blue2": "#6f9fc4",
    "green": "#a9c79c",
    "green2": "#7fa96f",
    "warm": "#e8c79c",
    "warm2": "#d9a468",
    "grey": "#c6c6cd",
    "grey2": "#a8a8b0",
    "rose": "#e3a7a0",
    "gold": "#d9b169",
}


def defs():
    return """<defs>
  <filter id="wc" x="-25%" y="-25%" width="150%" height="150%">
    <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="4" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="18" xChannelSelector="R" yChannelSelector="G"/>
    <feGaussianBlur stdDeviation="0.5"/>
  </filter>
  <filter id="wc2" x="-25%" y="-25%" width="150%" height="150%">
    <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="9" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="9"/>
  </filter>
  <!-- 注意：必须用 userSpaceOnUse。直线（<line> / M..V.. / M..H..）的包围盒宽或高为 0，
       用 objectBoundingBox 会让滤镜区域退化成 0×0，整条线直接被裁掉（太阳光芒、花茎、
       书页字行都因此消失过）。固定一块覆盖整幅画布的区域最稳。 -->
  <filter id="rough" filterUnits="userSpaceOnUse" x="-90" y="-80" width="1380" height="1080">
    <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="6" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="5"/>
  </filter>
  <filter id="paper">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" result="n"/>
    <feColorMatrix in="n" type="saturate" values="0"/>
    <feComponentTransfer><feFuncA type="linear" slope="0.05"/></feComponentTransfer>
    <feComposite operator="in" in2="SourceGraphic"/>
  </filter>
</defs>"""


def wash(x, y, rx, ry, fill, op=0.7, f="wc", cls=""):
    return ('<ellipse class="wx %s" cx="%.0f" cy="%.0f" rx="%.0f" ry="%.0f" '
            'fill="%s" opacity="%.2f" filter="url(#%s)"/>' %
            (cls, x, y, rx, ry, fill, op, f))


def line(d, w=3.2, col=P["ink"], fill="none", cls="", f="rough"):
    return ('<path class="wx %s" d="%s" fill="%s" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round" filter="url(#%s)"/>' %
            (cls, d, fill, col, w, f))


def person(x, y, s=1.0, skin=P["skin"], cloth=P["warm2"], hair=P["ink"], cls="wx-float"):
    body = ('<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y))
    body += '<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (
        x, y - 30 * s, 13 * s, skin, P["ink"])
    # hair cap
    body += '<path d="M%.0f %.0f a%.0f %.0f 0 0 1 %.0f 0" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (
        x - 13 * s, y - 30 * s, 13 * s, 13 * s, 26 * s, hair, P["ink"])
    # body
    body += '<path d="M%.0f %.0f Q %.0f %.0f %.0f %.0f L %.0f %.0f Q %.0f %.0f %.0f %.0f Z" fill="%s" stroke="%s" stroke-width="2" filter="url(#rough)"/>' % (
        x - 16 * s, y - 16 * s, x - 18 * s, y + 18 * s, x - 12 * s, y + 34 * s,
        x + 12 * s, y + 34 * s, x + 18 * s, y + 18 * s, x + 16 * s, y - 16 * s,
        cloth, P["ink"])
    # legs
    body += '<path d="M%.0f %.0f L %.0f %.0f M%.0f %.0f L %.0f %.0f" stroke="%s" stroke-width="%.0f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x - 8 * s, y + 34 * s, x - 9 * s, y + 52 * s, x + 8 * s, y + 34 * s, x + 9 * s, y + 52 * s, P["ink"], 4 * s)
    body += '</g>'
    return body


def tree(x, y, s=1.0, cls="wx-sway"):
    """一株圆乎乎的小树（会随风摆）。"""
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += '<path d="M%.0f %.0f L %.0f %.0f" stroke="%s" stroke-width="%.0f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x, y, x, y - 78 * s, "#8a6b4a", 9 * s)
    g += wash(x, y - 118 * s, 46 * s, 40 * s, P["green"], 0.85)
    g += wash(x - 26 * s, y - 104 * s, 26 * s, 23 * s, P["green2"], 0.7)
    g += wash(x + 24 * s, y - 108 * s, 22 * s, 20 * s, P["green2"], 0.6)
    g += '</g>'
    return g


def curve(pts, close=True):
    """把 [(x,y), ...] 拼成平滑贝塞尔路径（点数须为 1+3n），省得手数 %-占位符。"""
    d = "M%.1f %.1f" % (pts[0][0], pts[0][1])
    for i in range(1, len(pts), 3):
        d += " C %.1f %.1f %.1f %.1f %.1f %.1f" % (
            pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], pts[i + 2][0], pts[i + 2][1])
    return d + (" Z" if close else "")


def sun(x, y, r=34, cls="wx-spin"):
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    for i in range(12):
        rr = 'rotate(%d %d %d)' % (i * 30, x, y)
        g += '<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="%.0f" stroke-linecap="round" filter="url(#rough)" transform="%s"/>' % (
            x, y - r - 8, x, y - r - 30, P["gold"], max(4.0, r * 0.16), rr)
    g += '<circle cx="%.0f" cy="%.0f" r="%s" fill="%s" opacity="0.92" filter="url(#wc)"/>' % (x, y, r, P["gold"])
    g += "</g>"
    return g


def mottle(x0, y0, x1, y1, cols, n=9, op=0.2, rmin=70, rmax=170, seed=7):
    """在一片区域里撒几团同色系的柔和色块，模拟水彩颜料晕开的层次。
    必须在主体物之前画，才不会盖住角色。"""
    out = ""
    for i in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        fx = ((seed >> 9) % 1000) / 1000.0
        seed = (seed * 1103515245 + 12345) % 2147483648
        fy = ((seed >> 9) % 1000) / 1000.0
        seed = (seed * 1103515245 + 12345) % 2147483648
        r = rmin + (rmax - rmin) * (((seed >> 3) % 1000) / 1000.0)
        out += wash(x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy,
                    r * 1.6, r, cols[i % len(cols)], op)
    return out


# ============================================================================
# 可爱水彩场景库 v2（2026-09-12 重写）
#   旧场景（city/council/policy/build/school/sky）是给另一首「城市政策」诗画的，
#   只有方块楼和火柴人，既不「可爱」也和别的诗对不上。这里换一套**通用 + 可爱造型**
#   的水彩场景：每个场景都有水彩大色块 + 1~2 个圆润的小角色（有眼睛、笑弧、腮红）
#   + 会动的部件。自动选景见 pick_scene()，未命中就按 ORDER 轮播。
# ============================================================================
P.update({
    "sky": "#dcecf6", "sky2": "#bcd9ec", "night": "#3f4a6b", "night2": "#59648a",
    "pink": "#f0bcc4", "mint": "#bfe0cd", "lav": "#cfc3e8", "peach": "#f6cfae",
    "white": "#fdfbf6", "soil": "#b08a6b",
})


def face(cx, cy, r, blush=True, eyes="dot", smile=True):
    """可爱小脸：两只眼睛 + 笑弧 + 腮红。r ≈ 脸的半径。
    外面包一层 `<g class="wface">`，既方便统一调配色，也让回归测试能数「这张图有几个小角色」。"""
    s = ""
    ey = cy - r * 0.10
    dx = r * 0.38
    if eyes == "dot":
        for k in (-1, 1):
            s += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (
                cx + k * dx, ey, max(1.6, r * 0.115), P["ink"])
            s += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#fff" opacity=".9"/>' % (
                cx + k * dx + r * 0.05, ey - r * 0.06, max(0.8, r * 0.05))
    else:  # 闭眼（睡着的弧形眼）
        for k in (-1, 1):
            s += '<path d="M%.1f %.1f q %.1f %.1f %.1f 0" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
                cx + k * dx - r * 0.16, ey, r * 0.16, r * 0.2, r * 0.32, P["ink"], max(1.5, r * 0.075))
    if smile:
        s += '<path d="M%.1f %.1f q %.1f %.1f %.1f 0" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
            cx - r * 0.2, cy + r * 0.26, r * 0.2, r * 0.24, r * 0.4, P["ink"], max(1.5, r * 0.07))
    if blush:
        for k in (-1, 1):
            s += wash(cx + k * r * 0.66, cy + r * 0.16, r * 0.24, r * 0.15, P["rose"], 0.45)
    return '<g class="wface">%s</g>' % s


def cloud(x, y, s=1.0, op=0.9, cute=False, cls="wx-float", col=None):
    """圆圆的水彩云。cute=True 时云上带一张小脸。"""
    col = col or P["white"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    for dx, dy, r in ((-54, 8, 32), (-18, -12, 44), (24, 0, 36), (58, 10, 25)):
        g += wash(x + dx * s, y + dy * s, r * s, r * 0.84 * s, col, op)
    if cute:
        g += face(x - 6 * s, y - 4 * s, 26 * s)
    g += "</g>"
    return g


def star(x, y, r, cls="wx-float", col=None):
    col = col or P["gold"]
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append("%.1f,%.1f" % (x + math.cos(a) * rr, y + math.sin(a) * rr))
    return ('<polygon class="%s" points="%s" fill="%s" opacity=".9" filter="url(#rough)" '
            'style="transform-origin:%.0fpx %.0fpx"/>' % (cls, " ".join(pts), col, x, y))


def sparkle(x, y, r, col=None, cls="wx-float"):
    """四角星芒（水彩亮点）。"""
    col = col or P["gold"]
    q = r * 0.14
    d = ("M%.1f %.1f Q %.1f %.1f %.1f %.1f Q %.1f %.1f %.1f %.1f "
         "Q %.1f %.1f %.1f %.1f Q %.1f %.1f %.1f %.1f Z") % (
        x, y - r, x + q, y - q, x + r, y,
        x + q, y + q, x, y + r,
        x - q, y + q, x - r, y,
        x - q, y - q, x, y - r)
    return ('<path class="%s" d="%s" fill="%s" opacity=".85" style="transform-origin:%.0fpx %.0fpx"/>'
            % (cls, d, col, x, y))


def moon(x, y, r, cls="wx-float", bg=None):
    """带小脸的月牙（bg 给天空色，用来「咬」出缺口）。"""
    bg = bg or P["night"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += wash(x, y, r, r, P["gold"], 0.95)
    # 缺口圆要往右上偏，否则会把小脸盖住
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" filter="url(#wc)"/>' % (
        x + r * 0.58, y - r * 0.12, r * 0.84, bg)
    g += face(x - r * 0.50, y + r * 0.04, r * 0.36)
    g += "</g>"
    return g


def bird(x, y, s=1.0, cls="wx-float", col=None, flip=False):
    """圆滚滚的小鸟。"""
    col = col or P["blue2"]
    f = -1 if flip else 1
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += wash(x, y, 27 * s, 21 * s, col, 0.92)
    g += wash(x + 17 * f * s, y - 17 * s, 16 * s, 16 * s, col, 0.92)
    g += '<path d="M%.1f %.1f q %.1f %.1f %.1f %.1f" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x - 6 * s, y - 2 * s, -12 * f * s, -6 * s, -18 * f * s, 4 * s, P["ink"], 3 * s)
    g += '<path d="M%.1f %.1f l %.1f %.1f l %.1f %.1f Z" fill="%s" filter="url(#rough)"/>' % (
        x + 32 * f * s, y - 17 * s, 9 * f * s, 4 * s, -9 * f * s, 4 * s, P["warm2"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x + 21 * f * s, y - 20 * s, 2.6 * s, P["ink"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".45"/>' % (
        x - 8 * f * s, y - 18 * s, 5 * s, 3.4 * s, P["rose"])
    g += '<path d="M%.1f %.1f l %.1f %.1f M%.1f %.1f l %.1f %.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x - 2 * s, y + 20 * s, -3 * s, 8 * s, x + 7 * s, y + 20 * s, 3 * s, 8 * s, P["warm2"], 2.6 * s)
    g += "</g>"
    return g


def cat(x, y, s=1.0, cls="wx-float", col=None, sleeping=True):
    """蜷成一团的小猫。"""
    col = col or P["peach"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += wash(x, y, 46 * s, 27 * s, col, 0.94)
    g += '<path d="M%.1f %.1f q %.1f %.1f %.1f %.1f" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x - 40 * s, y + 4 * s, -18 * s, 6 * s, -26 * s, -10 * s, P["ink"], 5 * s)
    g += wash(x + 34 * s, y - 12 * s, 23 * s, 21 * s, col, 0.95)
    g += '<path d="M%.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s" filter="url(#rough)"/>' % (
        x + 18 * s, y - 28 * s, x + 16 * s, y - 46 * s, x + 34 * s, y - 32 * s, col)
    g += '<path d="M%.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s" filter="url(#rough)"/>' % (
        x + 46 * s, y - 30 * s, x + 54 * s, y - 47 * s, x + 60 * s, y - 26 * s, col)
    g += face(x + 36 * s, y - 10 * s, 20 * s, eyes=("dot" if not sleeping else "arc"))
    g += "</g>"
    return g


def sprout(x, y, s=1.0, cls="wx-sway", pot=None):
    """花盆里的小芽（会摇）。"""
    pot = pot or P["warm2"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y + 46 * s)
    g += '<path d="M%.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s" stroke="%s" stroke-width="2.8" filter="url(#rough)"/>' % (
        x - 38 * s, y, x + 38 * s, y, x + 27 * s, y + 48 * s, x - 27 * s, y + 48 * s, pot, P["ink"])
    g += wash(x, y + 4 * s, 34 * s, 9 * s, P["soil"], 0.55)
    g += '<path d="M%.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x, y, x - 5 * s, y - 32 * s, x + 7 * s, y - 48 * s, x + 2 * s, y - 68 * s, P["green2"], 5 * s)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".9" filter="url(#wc)" transform="rotate(-28 %.1f %.1f)"/>' % (
        x - 17 * s, y - 44 * s, 17 * s, 10 * s, P["green"], x - 17 * s, y - 44 * s)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".9" filter="url(#wc)" transform="rotate(26 %.1f %.1f)"/>' % (
        x + 19 * s, y - 56 * s, 17 * s, 10 * s, P["green2"], x + 19 * s, y - 56 * s)
    g += "</g>"
    return g


def book_open(x, y, s=1.0, cls="wx-float"):
    """摊开的书：一层封皮 + 两页纸 + 页上的字行 + 飘起的字光。(x, y) = 书脊中点。"""
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    top, bot = y - 36 * s, y + 30 * s
    # 封皮（比书页大一圈，垫在底下）
    g += line(curve([
        (x, top - 8 * s),
        (x - 34 * s, top - 20 * s), (x - 70 * s, top - 14 * s), (x - 92 * s, y - 2 * s),
        (x - 76 * s, y + 24 * s), (x - 46 * s, y + 36 * s), (x, bot + 10 * s),
        (x + 46 * s, y + 36 * s), (x + 76 * s, y + 24 * s), (x + 92 * s, y - 2 * s),
        (x + 70 * s, top - 14 * s), (x + 34 * s, top - 20 * s), (x, top - 8 * s),
    ]), 3.4, P["ink"], P["blue2"])
    # 左右两页纸
    for k in (-1, 1):
        g += line(curve([
            (x, top),
            (x + k * 26 * s, top - 8 * s), (x + k * 54 * s, top - 4 * s), (x + k * 80 * s, y + 6 * s),
            (x + k * 62 * s, y + 24 * s), (x + k * 26 * s, y + 28 * s), (x, bot),
        ]), 2.8, P["ink"], P["white"])
    # 页上的字行
    for k in (-1, 1):
        for j in range(3):
            yy = y - 12 * s + j * 13 * s
            g += line('M%.1f %.1f h%.1f' % (x + k * 18 * s, yy, k * 46 * s), 3.4 * s, P["ink"], "none", "", "rough")
    # 飘起的字光
    for ox, oy, rr in ((-20, -84, 14), (16, -104, 10), (44, -74, 8)):
        g += sparkle(x + ox * s, y + oy * s, rr * s, P["gold"])
    g += "</g>"
    return g


def kettle(x, y, s=1.0, cls=""):
    """小水壶（冒热气）。"""
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    for k in (-1, 0, 1):
        g += '<path class="wx-float" style="transform-origin:%.1fpx %.1fpx;animation-delay:%dms" d="M%.1f %.1f c %.1f %.1f %.1f %.1f %.1f %.1f" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" opacity=".6" filter="url(#rough)"/>' % (
            x + k * 12 * s, y - 40 * s, k * 200,
            x + k * 12 * s, y - 40 * s, -8 * s, -22 * s, 8 * s, -30 * s, 4 * s, -46 * s, P["blue2"], 3.4 * s)
    g += '<path d="M%.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s" stroke="%s" stroke-width="2.8" filter="url(#rough)"/>' % (
        x + 30 * s, y - 6 * s, x + 62 * s, y - 30 * s, x + 74 * s, y - 14 * s, x + 34 * s, y + 8 * s, P["blue"], P["ink"])
    g += wash(x, y, 46 * s, 34 * s, P["blue"], 0.92)
    g += '<path d="M%.1f %.1f a %.1f %.1f 0 0 1 %.1f 0" fill="none" stroke="%s" stroke-width="%.1f" filter="url(#rough)"/>' % (
        x - 44 * s, y - 8 * s, 24 * s, 30 * s, 48 * s, P["ink"], 3.4 * s)
    g += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" stroke="%s" stroke-width="2.6" filter="url(#rough)"/>' % (
        x - 10 * s, y - 46 * s, 20 * s, 12 * s, 5 * s, P["blue2"], P["ink"])
    g += face(x - 2 * s, y + 2 * s, 20 * s)
    g += "</g>"
    return g


def mug(x, y, s=1.0, cls=""):
    """马克杯。"""
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += '<path d="M%.1f %.1f h%.1f v%.1f a%.1f %.1f 0 0 1 %.1f %.1f h%.1f a%.1f %.1f 0 0 1 %.1f %.1f Z" fill="%s" stroke="%s" stroke-width="2.6" filter="url(#rough)"/>' % (
        x - 24 * s, y - 22 * s, 48 * s, 40 * s, 10 * s, 10 * s, -10 * s, 10 * s, -28 * s, 10 * s, 10 * s, -10 * s, -10 * s,
        P["pink"], P["ink"])
    g += '<path d="M%.1f %.1f a %.1f %.1f 0 0 1 0 %.1f" fill="none" stroke="%s" stroke-width="%.1f" filter="url(#rough)"/>' % (
        x + 24 * s, y - 8 * s, 15 * s, 15 * s, 24 * s, P["ink"], 3 * s)
    g += wash(x, y - 22 * s, 24 * s, 7 * s, P["warm"], 0.8)
    for k in (-1, 1):
        g += '<path class="wx-float" style="transform-origin:%.1fpx %.1fpx;animation-delay:%dms" d="M%.1f %.1f c %.1f %.1f %.1f %.1f %.1f %.1f" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" opacity=".55" filter="url(#rough)"/>' % (
            x + k * 9 * s, y - 32 * s, (k + 2) * 180,
            x + k * 9 * s, y - 32 * s, -6 * s, -14 * s, 6 * s, -20 * s, 3 * s, -30 * s, P["blue2"])
    g += "</g>"
    return g


def lamp(x, y, s=1.0, cls=""):
    """台灯 + 暖光。(x, y) = 底座中心。"""
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    # 暖光晕（垫在灯后面）
    g += '<ellipse class="wx-float" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".38" filter="url(#wc)"/>' % (
        x + 26 * s, y - 34 * s, 92 * s, 84 * s, P["gold"])
    # 底座 + 灯杆
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="2.8" filter="url(#rough)"/>' % (
        x, y + 34 * s, 30 * s, 9 * s, P["grey"], P["ink"])
    g += line('M%.1f %.1f L%.1f %.1f' % (x, y + 30 * s, x, y - 40 * s), 6 * s, P["ink"], P["ink"])
    # 灯罩（下宽上窄的梯形）
    g += line('M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x - 34 * s, y - 40 * s, x + 34 * s, y - 40 * s, x + 15 * s, y - 84 * s, x - 15 * s, y - 84 * s),
        3.4, P["ink"], P["warm2"])
    g += "</g>"
    return g


def boat(x, y, s=1.0, cls="wx-float"):
    """小船（漂）。"""
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += '<path d="M%.1f %.1f q %.1f %.1f %.1f %.1f L %.1f %.1f q %.1f %.1f %.1f %.1f Z" fill="%s" stroke="%s" stroke-width="2.8" filter="url(#rough)"/>' % (
        x - 46 * s, y, 46 * s, 22 * s, 92 * s, 0, x + 34 * s, y, -46 * s, 22 * s, -92 * s, 0,
        P["warm2"], P["ink"])
    g += '<path d="M%.1f %.1f V %.1f" stroke="%s" stroke-width="3.4" stroke-linecap="round" filter="url(#rough)"/>' % (
        x, y, y - 74 * s, P["ink"])
    g += '<path d="M%.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s" opacity=".95" filter="url(#wc)"/>' % (
        x + 3 * s, y - 70 * s, x + 3 * s, y - 14 * s, x + 48 * s, y - 22 * s, P["white"])
    g += '<path d="M%.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s" opacity=".9" filter="url(#wc)"/>' % (
        x - 3 * s, y - 66 * s, x - 3 * s, y - 14 * s, x - 40 * s, y - 20 * s, P["pink"])
    g += "</g>"
    return g


def flower(x, y, s=1.0, col=None, cls="wx-sway"):
    """小野花（会随风轻摇）。(x, y) = 根部。"""
    col = col or P["pink"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += '<path d="M%.1f %.1f V %.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round" filter="url(#rough)"/>' % (
        x, y, y - 74 * s, P["green2"], 6 * s)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".9" filter="url(#wc)" transform="rotate(-22 %.1f %.1f)"/>' % (
        x - 24 * s, y - 42 * s, 20 * s, 11 * s, P["green"], x - 24 * s, y - 42 * s)
    for i in range(6):
        g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".85" filter="url(#wc)" transform="rotate(%d %.1f %.1f)"/>' % (
            x, y - 100 * s, 18 * s, 25 * s, col, i * 60, x, y - 100 * s)
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" filter="url(#rough)"/>' % (x, y - 100 * s, 12 * s, P["gold"])
    g += "</g>"
    return g


def hills(y, cols, cls=""):
    """层叠的远山/草地。cols = [(颜色, 下移量, 透明度), ...]；用平滑曲线写，避免手数错坐标。"""
    s = ""
    n = 10
    for col, dy, op in cols:
        pts = []
        for i in range(n + 1):
            px = -60 + i * (1320.0 / n)
            py = (y + dy) - math.sin(i / n * math.pi * 2.1) * 76 + math.sin(i * 1.7) * 6
            pts.append((px, py))
        d = "M%.0f %.0f " % pts[0]
        for i in range(1, n):
            d += "Q %.0f %.0f %.0f %.0f " % (
                pts[i][0], pts[i][1], (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
        d += "L %.0f %.0f V 940 H -60 Z" % pts[-1]
        s += ('<path class="%s" d="%s" fill="%s" opacity="%.2f" filter="url(#wc)"/>'
              % (cls, d, col, op))
    return s


def drops(x0, y0, n, dx, dy, cls="wx-rain", col=None):
    col = col or P["blue2"]
    s = ""
    for i in range(n):
        x = x0 + (i % 7) * dx
        y = y0 + (i // 7) * dy
        s += ('<path class="%s" style="transform-origin:%.1fpx %.1fpx;animation-delay:%dms" '
              'd="M%.1f %.1f q 4 8 0 14 q -4 -6 0 -14 Z" fill="%s" opacity=".7" filter="url(#rough)"/>' % (
                  cls, x, y, (i * 137) % 1400, x, y, col))
    return s


def puddle(x, y, rx, cls="", col=None):
    col = col or P["sky2"]
    s = wash(x, y, rx, rx * 0.26, col, 0.5)
    for i in range(3):
        s += '<ellipse class="wx-float" style="transform-origin:%.1fpx %.1fpx;animation-delay:%dms" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" stroke="%s" stroke-width="1.8" opacity=".5"/>' % (
            x, y, i * 400, x, y, rx * (0.4 + i * 0.24), rx * 0.1 * (0.4 + i * 0.24), P["blue2"])
    return s


def pane(x, y, w, h, cols, rows, lit="#f2d79b", frame=P["ink"]):
    """亮着灯的小窗（城市夜景用）。"""
    s = '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" fill="#fdf7ea" opacity=".75" stroke="%s" stroke-width="2.6" filter="url(#rough)"/>' % (
        x, y, w, h, frame)
    for c in range(cols):
        for r in range(rows):
            s += '<rect class="wx-float" style="animation-delay:%dms" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s" opacity="%.2f"/>' % (
                (c * 3 + r * 5) * 170,
                x + 8 + c * (w - 16) / cols, y + 8 + r * (h - 16) / rows,
                (w - 16) / cols - 8, (h - 16) / rows - 8, lit, 0.9 if (c + r) % 2 == 0 else 0.35)
    return s

# ============================ 场景本体 ============================
def band(x, y, w, h, fill, op=1.0, f="wc", cls="", rx=0):
    """水彩大色块（长方形，边缘靠湍流位移做成水彩晕边）。"""
    return ('<rect class="wx %s" x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="%.0f" '
            'fill="%s" opacity="%.2f" filter="url(#%s)"/>' % (cls, x, y, w, h, rx, fill, op, f))


def kid(x, y, s=1.0, cloth=None, umbrella=None, cls="wx-float"):
    """圆滚滚的小孩（可撑伞）。(x, y) = 脚底中点。"""
    cloth = cloth or P["blue2"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    if umbrella:
        g += line('M%.0f %.0f L%.0f %.0f' % (x + 6 * s, y - 12 * s, x + 48 * s, y - 196 * s), 5 * s, P["ink"])
        g += line('M%.0f %.0f a%.0f %.0f 0 0 1 %.0f 0 Z' % (x - 46 * s, y - 190 * s, 50 * s, 50 * s, 100 * s),
                  3.4, P["ink"], umbrella)
        g += line('M%.0f %.0f v-16' % (x + 48 * s, y - 196 * s), 5 * s, P["ink"])
    # 靴子
    g += line('M%.0f %.0f h%.0f M%.0f %.0f h%.0f' % (x - 23 * s, y, 22 * s, x, y, 22 * s), 9 * s, P["ink"], P["ink"])
    # 腿
    g += line('M%.0f %.0f L%.0f %.0f M%.0f %.0f L%.0f %.0f' % (
        x - 12 * s, y - 32 * s, x - 10 * s, y, x + 12 * s, y - 32 * s, x + 10 * s, y), 5 * s, "#6b6b78")
    # 身体（圆润的小袍子）
    g += line('M%.0f %.0f Q%.0f %.0f %.0f %.0f L%.0f %.0f Q%.0f %.0f %.0f %.0f Z' % (
        x - 26 * s, y - 84 * s, x - 38 * s, y - 42 * s, x - 25 * s, y - 28 * s,
        x + 25 * s, y - 28 * s, x + 38 * s, y - 42 * s, x + 26 * s, y - 84 * s), 3.4, P["ink"], cloth)
    # 手臂
    g += line('M%.0f %.0f L%.0f %.0f M%.0f %.0f L%.0f %.0f' % (
        x - 26 * s, y - 74 * s, x - 43 * s, y - 48 * s,
        x + 26 * s, y - 74 * s, x + 41 * s, y - 50 * s), 5 * s, P["ink"])
    # 头 + 头发
    g += ('<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s" stroke="%s" stroke-width="2.6" '
          'filter="url(#rough)"/>' % (x, y - 104 * s, 28 * s, P["skin"], P["ink"]))
    g += line('M%.0f %.0f a%.0f %.0f 0 0 1 %.0f 0 Z' % (
        x - 29 * s, y - 106 * s, 29 * s, 26 * s, 58 * s), 2.6, P["ink"], P["ink"])
    g += face(x, y - 101 * s, 26 * s)
    g += "</g>"
    return g


def house(x, y, w=190, h=160, col=None, roof=None, cls="wx-float"):
    """小屋。(x, y) = 底部中点。带亮着灯的小窗和拱门。"""
    col = col or P["cream"]
    roof = roof or P["rose"]
    g = '<g class="%s" style="transform-origin:%.0fpx %.0fpx">' % (cls, x, y)
    g += line('M%.0f %.0f h%.0f v%.0f h%.0f Z' % (x - w / 2, y, w, -h, -w), 3.4, P["ink"], col)
    rh = w * 0.5
    g += line('M%.0f %.0f L%.0f %.0f L%.0f %.0f Z' % (
        x - w / 2 - 18, y - h, x, y - h - rh, x + w / 2 + 18, y - h), 3.4, P["ink"], roof)
    # 拱门
    g += line('M%.0f %.0f v-52 a26 26 0 0 1 52 0 v52' % (x - 30, y, ), 3, P["ink"], P["warm2"])
    g += '<circle cx="%.0f" cy="%.0f" r="3.4" fill="%s"/>' % (x + 14, y - 30, P["gold"])
    # 亮灯的窗
    g += pane(x + w * 0.10, y - h + 28, w * 0.34, h * 0.34, 2, 1)
    g += "</g>"
    return g


def scene_cover():
    """封面：一本摊开的书里长出新芽，太阳、云、小鸟、小猫都在。"""
    s = band(0, 0, W, H, P["paper"], 1.0, "wc")
    s += band(0, 0, W, 660, P["sky"], 0.95)
    s += mottle(60, 30, 1150, 560, ["#cde5f4", "#f0f8fd", "#c2dbee"], 10, 0.22)
    s += sun(985, 195, 54)
    s += cloud(300, 180, 1.15, cute=True)
    s += cloud(870, 300, 0.78, op=0.7)
    s += bird(170, 330, 0.85)
    s += bird(690, 140, 0.62, flip=True)
    s += hills(670, [(P["mint"], 0, 0.75), (P["green"], 70, 0.85)])
    s += mottle(60, 706, 1140, 878, ["#b7d5aa", "#93bd84"], 7, 0.16)
    s += flower(130, 806, 2.0)
    s += flower(1075, 818, 1.7, col=P["lav"])
    s += flower(1168, 770, 1.3, col=P["peach"])
    s += cat(880, 796, 1.8)
    s += book_open(470, 748, 2.0)
    return s


def scene_dawn():
    """清晨：暖霞、初升的太阳、飞鸟、带露水的草地。"""
    s = band(0, 0, W, H, P["paper"], 1.0, "wc")
    s += band(0, 0, W, 650, P["sky"], 0.9)
    s += wash(600, 640, 640, 280, P["peach"], 0.6)
    s += wash(600, 720, 680, 240, P["pink"], 0.35)
    s += mottle(70, 40, 1140, 520, ["#cde5f4", "#f4e2d2", "#f6dfe2"], 9, 0.2)
    s += sun(340, 250, 60)
    s += cloud(880, 205, 1.0, cute=True, op=0.88)
    s += cloud(560, 320, 0.68, op=0.55)
    s += bird(985, 355, 0.9, flip=True)
    s += bird(1085, 292, 0.68, flip=True)
    s += hills(650, [(P["mint"], 40, 0.78), (P["green"], 104, 0.88)])
    s += mottle(60, 742, 1140, 880, ["#b7d5aa", "#8fbb80"], 6, 0.15)
    s += flower(215, 810, 2.0)
    s += flower(345, 838, 1.5, col=P["lav"])
    s += flower(1090, 822, 1.6, col=P["peach"])
    s += cat(950, 806, 1.6)
    return s


def scene_night():
    """夜里：月牙、星子、亮着灯的小屋、睡着的猫。"""
    s = band(0, 0, W, H, P["night"], 1.0, "wc")
    s += wash(600, 540, 720, 340, P["night2"], 0.55)
    s += mottle(60, 40, 1140, 600, ["#4b5680", "#6b76a0", "#3a4463"], 10, 0.22)
    s += moon(915, 215, 96, bg=P["night"])
    for px, py, pr in ((175, 150, 16), (330, 275, 11), (505, 118, 13), (665, 300, 9),
                       (1090, 385, 12), (120, 425, 9), (760, 96, 8), (415, 400, 7)):
        s += star(px, py, pr)
    s += sparkle(880, 470, 24, P["white"])
    s += sparkle(255, 330, 18, P["white"])
    s += hills(700, [(P["night2"], 26, 0.9), ("#4a5578", 92, 1.0)])
    s += house(880, 830, 250, 200, P["cream"], P["lav"])
    s += cat(260, 812, 1.55, col=P["lav"], sleeping=True)
    s += star(560, 520, 12)
    return s


def scene_study():
    """学习：台灯、摊开的书、冒热气的杯子、星星点点的灵感。"""
    s = band(0, 0, W, H, P["cream"], 1.0, "wc")
    s += wash(1020, 300, 330, 330, P["gold"], 0.3)
    s += mottle(60, 40, 900, 600, ["#f3e6cf", "#eadcc2"], 6, 0.18)
    s += band(0, 690, W, 210, P["warm"], 0.72)
    s += line('M0 690 H1200', 4, P["ink"], "none")
    s += lamp(285, 640, 1.5)
    s += book_open(625, 662, 1.4)
    s += mug(905, 655, 1.3)
    s += sprout(1092, 628, 1.15)
    s += sparkle(505, 420, 26)
    s += sparkle(765, 358, 18, P["rose"])
    s += sparkle(945, 470, 14)
    s += cat(150, 800, 1.2, col=P["grey2"])
    return s


def scene_rain():
    """下雨：抬头笑的云、雨丝、水洼、撑伞的小孩。"""
    s = band(0, 0, W, H, P["paper"], 1.0, "wc")
    s += band(0, 0, W, 660, P["grey"], 0.45)
    s += wash(600, 300, 780, 220, P["grey2"], 0.32)
    s += mottle(60, 60, 1140, 560, ["#d5d8de", "#e6e8ec", "#c3c7cf"], 9, 0.22)
    s += cloud(330, 205, 1.3, cute=True, col=P["grey"])
    s += cloud(915, 165, 1.0, op=0.8, col=P["grey"])
    s += drops(90, 340, 42, 132, 72)
    s += band(0, 655, W, 245, P["sky2"], 0.55)
    s += puddle(400, 770, 155)
    s += puddle(930, 812, 108)
    s += kid(620, 780, 1.35, cloth=P["gold"], umbrella=P["rose"])
    s += cat(150, 800, 1.05, col=P["grey"])
    return s


def scene_field():
    """田野：草地、野花、大树、太阳，风一吹会摇。"""
    s = band(0, 0, W, H, P["paper"], 1.0, "wc")
    s += band(0, 0, W, 620, P["sky"], 0.9)
    s += mottle(60, 30, 1150, 540, ["#cde5f4", "#eef8fd", "#c2dbee"], 9, 0.22)
    s += sun(965, 190, 54)
    s += cloud(285, 170, 1.1, cute=True)
    s += cloud(700, 255, 0.72, op=0.6)
    s += bird(560, 360, 0.8, flip=True)
    s += hills(600, [(P["mint"], 30, 0.75), (P["green"], 92, 0.85)])
    s += mottle(60, 700, 1140, 880, ["#b7d5aa", "#8fbb80"], 8, 0.17)
    s += tree(190, 872, 2.3)
    s += flower(430, 806, 2.1)
    s += flower(545, 842, 1.6, col=P["lav"])
    s += flower(915, 812, 2.0, col=P["peach"])
    s += flower(1030, 844, 1.5)
    s += cat(700, 802, 1.6, col=P["white"], sleeping=False)
    return s


def scene_home():
    """家：水壶冒着热气、马克杯、盆栽、摊开的书，一只猫在脚边。"""
    s = band(0, 0, W, H, P["cream"], 1.0, "wc")
    s += wash(985, 290, 320, 320, P["gold"], 0.3)
    s += mottle(60, 40, 760, 560, ["#f3e6cf", "#eadcc2"], 6, 0.2)
    s += pane(830, 150, 305, 240, 2, 2)
    s += line('M830 150 h305 v240 h-305 Z', 4, P["ink"], "none")
    s += line('M982 150 v240 M830 270 h305', 3, P["ink"], "none")
    s += band(0, 690, W, 210, P["warm"], 0.7)
    s += line('M0 690 H1200', 4, P["ink"], "none")
    s += kettle(345, 640, 1.5)
    s += mug(570, 660, 1.4)
    s += sprout(770, 640, 1.2)
    s += book_open(990, 668, 1.05)
    s += cat(145, 800, 1.3)
    return s


def scene_town():
    """小镇：三间可爱的小屋、亮着的窗、树和晒太阳的猫。"""
    s = band(0, 0, W, H, P["paper"], 1.0, "wc")
    s += band(0, 0, W, 600, P["sky"], 0.85)
    s += mottle(60, 30, 1150, 520, ["#cde5f4", "#f0f8fd", "#c2dbee"], 8, 0.2)
    s += sun(185, 190, 46)
    s += cloud(765, 158, 1.0, cute=True, op=0.82)
    s += bird(1035, 245, 0.78, flip=True)
    s += hills(575, [(P["mint"], 18, 0.72)])
    s += band(0, 700, W, 200, "#d9d2c2", 0.72)
    s += house(235, 700, 215, 178, P["white"], P["rose"])
    s += house(565, 700, 250, 215, P["cream"], P["lav"])
    s += house(905, 700, 205, 168, P["white"], P["peach"])
    s += tree(1095, 705, 1.25)
    s += cat(105, 806, 1.3, col=P["peach"], sleeping=False)
    return s


def scene_sea():
    """海：小船、一层层的水波、海鸟和晒太阳的猫。"""
    s = band(0, 0, W, H, P["paper"], 1.0, "wc")
    s += band(0, 0, W, 560, P["sky"], 0.9)
    s += mottle(60, 30, 1150, 490, ["#cde5f4", "#f0f8fd", "#c2dbee"], 8, 0.2)
    s += sun(230, 180, 50)
    s += cloud(820, 150, 1.05, cute=True, op=0.86)
    s += bird(1015, 320, 0.85, flip=True)
    s += bird(1105, 252, 0.65, flip=True)
    s += band(0, 555, W, 345, P["blue"], 0.6)
    s += mottle(60, 590, 1140, 790, ["#b7d8ea", "#8fbfdc"], 7, 0.18)
    for i, wy in enumerate((618, 688, 768, 848)):
        s += ('<path class="wx-float" style="animation-delay:%dms" d="M-30 %d q 60 -18 120 0 '
              't 120 0 t 120 0 t 120 0 t 120 0 t 120 0 t 120 0 t 120 0 t 120 0 t 120 0" '
              'fill="none" stroke="%s" stroke-width="%d" stroke-linecap="round" opacity=".55" '
              'filter="url(#rough)"/>' % (i * 330, wy, P["white"] if i % 2 else P["blue2"], 4 if i % 2 else 5))
    s += boat(790, 690, 1.7)
    # 前景的一小片沙滩，让猫有地方坐
    s += band(-40, 800, W + 80, 160, P["warm"], 0.75)
    s += puddle(300, 790, 120, col=P["sky2"])
    s += cat(330, 852, 1.7, col=P["peach"], sleeping=False)
    s += star(1080, 856, 16, col=P["warm2"])
    return s


SCENES = {
    "cover": scene_cover,
    "dawn": scene_dawn,
    "night": scene_night,
    "study": scene_study,
    "rain": scene_rain,
    "field": scene_field,
    "home": scene_home,
    "town": scene_town,
    "sea": scene_sea,
}

ORDER = ["dawn", "field", "study", "night", "home", "rain", "town", "sea"]

# 关键词 → 场景。命中数最多者胜；并列时按本表顺序（越靠前越「具体」）。
SCENE_HINTS = (
    ("rain", ("rain", "storm", "wet", "drip", "drop", "pour", "shower", "wash", "flood",
              "grey", "gray", "cloud", "mist", "tear")),
    ("field", ("field", "flower", "grow", "seed", "garden", "grass", "leaf", "tree", "spring",
               "green", "wind", "bloom", "root", "soil", "harvest", "blossom", "hill")),
    ("sea", ("sea", "ocean", "boat", "sail", "wave", "river", "water", "float", "shore",
             "harbour", "harbor", "ship", "tide", "swim")),
    ("home", ("home", "house", "room", "kitchen", "table", "tea", "cup", "kettle", "mug",
              "warm", "hearth", "bread", "family", "window", "chair", "door", "floor")),
    ("study", ("book", "read", "word", "page", "learn", "study", "write", "letter", "ink",
               "pen", "lesson", "knowledge", "spell", "note", "mind", "remember", "know")),
    ("town", ("city", "town", "street", "road", "traffic", "building", "car", "bus", "market",
              "shop", "crowd", "wall", "lamp", "tower")),
    ("dawn", ("light", "sun", "morning", "dawn", "first", "begin", "wake", "rise", "hope",
              "bright", "day", "sky", "open", "new")),
    ("night", ("night", "dark", "moon", "star", "sleep", "dream", "evening", "dusk",
               "shadow", "hush", "midnight")),
)


def pick_scene(text):
    """按关键词给一段诗挑场景；没把握时返回 None（交给 ORDER 轮播）。"""
    low = (text or "").lower()
    best, bestn = None, 0
    for name, keys in SCENE_HINTS:
        n = sum(1 for k in keys if k in low)
        if n > bestn:
            best, bestn = name, n
    return best


def assign_scenes(stanzas):
    """给每段配一张不重复的场景图（命中 → 关键词；否则按 ORDER 补位）。"""
    out, used = [], {"cover"}
    for i, st in enumerate(stanzas):
        sc = pick_scene(" ".join(st))
        if not sc or sc in used:
            sc = next((o for o in ORDER if o not in used), ORDER[i % len(ORDER)])
        used.add(sc)
        out.append(sc)
    return out


ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def svg_wrap(inner, extra=""):
    """把一段画好的 SVG 内容包成 <svg class="art-svg">。
    故事分镜引擎（art_storyboard）也走这个壳，保证 CSS / 滤镜 / 纸纹完全一致。"""
    # 最上层：一层水彩纸的纤维颗粒，让画面不那么「平坦矢量」
    grain = ('<rect class="pgrain" x="0" y="0" width="%d" height="%d" fill="#6f6455" '
             'filter="url(#paper)"/>' % (W, H))
    return ('<svg class="art-svg" viewBox="0 0 %d %d" preserveAspectRatio="xMidYMid meet" '
            'xmlns="http://www.w3.org/2000/svg" role="img"%s>%s%s%s</svg>'
            % (W, H, extra, defs(), inner, grain))


def svg(scene):
    fn = SCENES.get(scene, scene_cover)
    return svg_wrap(fn())


# ============================================================================
# 故事分镜引擎（art_storyboard.py）
#   旧的 9 个 SCENES 是「整套画好的场景」，通用但不贴题、只有 9 张必然重样。
#   分镜引擎按「这一段真实出现的词」现场拼背景 + 主体物，并读写 art-ledger.json
#   避开最近几天用过的背景/组合。见 art_storyboard.py 顶部说明。
# ============================================================================
def _load_art():
    import importlib.util
    name = "yaya_art_storyboard"
    if name in sys.modules:
        mod = sys.modules[name]
    else:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art_storyboard.py")
        if not os.path.exists(p):
            return None
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    mod.bind(globals())          # 把 wash / line / P / W / H / face … 交给它
    return mod


ART = _load_art()


def storyboard_art_fn(paragraphs, title, date="", data_dir=None, use_ledger=True):
    """返回 (art_fn, plans, save)：
      art_fn(i, panel, title) → 第 i 段的分镜 SVG；i 为 None 时是封面。
      save() → 把今天的背景/组合记进台账，供明天避开。
    """
    if ART is None:
        raise SystemExit("找不到 art_storyboard.py（和本脚本同目录）")
    # 段落可能是「一行一串」的列表（split_stanzas 的产物），先压成整段文本
    paragraphs = [" ".join(p) if isinstance(p, (list, tuple)) else str(p)
                  for p in paragraphs]
    hist = (ART.load_history(data_dir, exclude_date=date) if use_ledger
            else ART.normalize_history([]))
    plans = ART.plan_book(paragraphs, title, history=hist)
    cover = ART.plan_cover(paragraphs, title, history=hist)

    def art_fn(i, panel=None, _title=title):
        if i is None:
            return ART.svg_storyboard(cover)
        return ART.svg_storyboard(plans[i])

    def save():
        if not use_ledger:
            return None
        return ART.save_history(date, plans, data_dir, cover=cover)

    return art_fn, plans, cover, save


# ---------------- 中文翻译（优先用诗稿自带的 zh；可用 --zh-file 覆盖）----------------
# 留空是刻意的：写死别的诗的译文会串味。诗稿 json 里带 "zh"/"zh_stanzas"/"translation"
# 时自动读取，否则用 --zh-file。
DEFAULT_ZH = {}

CSS = """
  :root{
    --paper:#f7f2e7; --ink:#2c2b33; --ink-soft:#5c5a63;
    --gold:#b8872f; --gold-soft:#d9b169; --blue:#2f4858;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Songti SC","STSong",serif;
    --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html{scroll-behavior:smooth}
  body{background:var(--paper);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden}

  .grain{position:fixed;inset:0;z-index:60;pointer-events:none;opacity:.5;mix-blend-mode:multiply;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.4'/></svg>")}
  .blobs{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
  .blob{position:absolute;border-radius:50%;filter:blur(60px);opacity:.28;mix-blend-mode:multiply;animation:drift 28s ease-in-out infinite alternate}
  .b1{width:44vw;height:44vw;left:-8vw;top:4vh;background:#c9d9d2}
  .b2{width:36vw;height:36vw;right:-10vw;top:30vh;background:#e8d6b8;animation-duration:34s}
  .b3{width:50vw;height:50vw;left:12vw;bottom:-16vh;background:#cfd8e3;animation-duration:40s}
  @keyframes drift{0%{transform:translate(0,0) scale(1)}50%{transform:translate(3vw,-2vh) scale(1.12)}100%{transform:translate(-2vw,3vh) scale(.94)}}

  .progress{position:fixed;top:0;left:0;right:0;height:4px;z-index:70;background:rgba(44,43,51,.06)}
  .progress span{display:block;height:100%;width:0%;background:linear-gradient(90deg,var(--blue),var(--gold-soft),var(--gold));border-radius:0 4px 4px 0}

  /* 语言切换 */
  .lang{position:fixed;top:1rem;left:50%;transform:translateX(-50%);z-index:80;display:flex;gap:.25rem;
    background:rgba(255,255,255,.8);border:1px solid rgba(47,72,88,.16);border-radius:999px;padding:.3rem;
    backdrop-filter:blur(8px);box-shadow:0 8px 22px -12px rgba(47,72,88,.6)}
  .lang button{font-family:var(--sans);font-size:.8rem;letter-spacing:.04em;padding:.42rem .9rem;border:0;cursor:pointer;
    background:transparent;color:var(--blue);border-radius:999px;white-space:nowrap;transition:background .25s,color .25s}
  .lang button.on{background:var(--gold);color:#3a2a06}

  .hero{position:relative;z-index:1;min-height:100vh;display:grid;align-items:center;text-align:center;padding:9vh 6vw}
  /* 注意：这里只用 align-items，不要用 place-items:center。
     justify-items:center 会让网格子项按 max-content 撑宽，窄屏上标题会溢出被裁。
     水平居中交给 text-align，子项则铺满宽度。 */
  .hero-inner{width:100%;max-width:760px;margin:0 auto}
  .hero-frame{width:min(560px,90vw);margin:0 auto 2.6rem}
  .hero-frame svg{width:100%;height:auto;display:block;border-radius:8px;filter:drop-shadow(0 26px 60px rgba(47,72,88,.4))}
  .kicker{font-size:.78rem;letter-spacing:.42em;text-transform:uppercase;color:var(--gold);margin-bottom:1.2rem;font-weight:600}
  h1{font-family:var(--serif);font-weight:500;font-size:clamp(1.7rem,6vw,4rem);line-height:1.14;overflow-wrap:break-word}
  h1 .w{display:inline-block;opacity:0;transform:translateY(22px) rotate(-2deg);filter:blur(6px);animation:ink 1s cubic-bezier(.2,.7,.2,1) forwards}
  @keyframes ink{to{opacity:1;transform:none;filter:blur(0)}}
  .sub{margin-top:1.2rem;color:var(--ink-soft);font-size:clamp(.9rem,1.6vw,1.05rem);letter-spacing:.06em}
  .rule{width:70px;height:1px;background:var(--gold);margin:1.8rem auto;opacity:.6}
  .scroll-hint{font-size:.76rem;letter-spacing:.3em;color:var(--ink-soft);animation:bob 2.6s ease-in-out infinite}
  .scroll-hint::after{content:"";display:block;width:1px;height:36px;margin:12px auto 0;background:linear-gradient(var(--gold),transparent)}
  @keyframes bob{0%,100%{transform:translateY(0);opacity:.7}50%{transform:translateY(7px);opacity:1}}

  main{position:relative;z-index:1}
  .spread{display:grid;grid-template-columns:1.05fr .95fr;align-items:center;gap:clamp(2rem,5vw,5rem);
    max-width:1240px;margin:0 auto;padding:clamp(4.5rem,10vh,8rem) clamp(1.4rem,5vw,4rem)}
  .spread:nth-of-type(even){grid-template-columns:.95fr 1.05fr}
  .spread:nth-of-type(even) .art{order:2}

  .art-inner{border-radius:10px;overflow:hidden;background:#fffaf0;
    box-shadow:0 30px 64px -32px rgba(47,72,88,.5),0 1px 0 rgba(255,255,255,.7)}
  .art-svg{width:100%;height:auto;display:block}
  .pgrain{mix-blend-mode:multiply;opacity:.55}

  .copy{max-width:34rem}
  .num{display:inline-flex;align-items:center;justify-content:center;font-family:var(--serif);
    font-size:1rem;letter-spacing:.2em;color:var(--gold);border:1px solid rgba(184,135,47,.4);
    border-radius:50%;width:2.5rem;height:2.5rem;margin-bottom:1.5rem}
  .copy p{font-family:var(--serif);font-size:clamp(1.02rem,1.5vw,1.26rem);line-height:1.95;letter-spacing:.012em;
    color:var(--ink);opacity:0;transform:translateY(16px);filter:blur(4px);
    transition:opacity .9s cubic-bezier(.2,.7,.2,1),transform .9s cubic-bezier(.2,.7,.2,1),filter .9s ease}
  .spread.in .copy p{opacity:1;transform:none;filter:blur(0)}
  .spread.in .copy p:nth-child(2){transition-delay:.1s}
  .spread.in .copy p:nth-child(3){transition-delay:.2s}
  .spread.in .copy p:nth-child(4){transition-delay:.3s}
  .spread.in .copy p:nth-child(5){transition-delay:.4s}
  .spread.in .copy p:nth-child(6){transition-delay:.5s}
  .spread.in .copy p:nth-child(7){transition-delay:.6s}
  .spread.in .copy p:nth-child(8){transition-delay:.7s}
  .copy .zh{font-family:var(--sans);font-size:clamp(.92rem,1.4vw,1.05rem);line-height:1.85;color:var(--ink-soft);
    background:linear-gradient(180deg,transparent 60%,rgba(217,177,105,.3) 60%);border-radius:3px;padding:.1rem 0}

  .word{background:linear-gradient(180deg,transparent 58%,rgba(217,177,105,.42) 58%);padding:0 .06em;border-radius:2px;transition:background .5s,color .3s}
  .word.lit{background:linear-gradient(180deg,transparent 52%,rgba(184,135,47,.72) 52%);color:#3a2a06;text-shadow:0 1px 0 rgba(255,255,255,.5)}
  body.no-en .word{background:none;padding:0}

  .finale{position:relative;z-index:1;text-align:center;max-width:1100px;margin:0 auto;padding:clamp(4rem,9vh,7rem) clamp(1.4rem,5vw,4rem) 6rem}
  .finale h2{font-family:var(--serif);font-weight:500;letter-spacing:.24em;text-transform:uppercase;font-size:.82rem;color:var(--gold);margin-bottom:2.2rem}
  .cloud{display:flex;flex-wrap:wrap;gap:.7rem;justify-content:center}
  .cloud span{font-family:var(--serif);font-size:.95rem;padding:.42rem .82rem;border-radius:999px;
    background:rgba(255,255,255,.62);border:1px solid rgba(47,72,88,.12);color:var(--blue);
    opacity:0;transform:translateY(12px) scale(.96);animation:pop .8s cubic-bezier(.2,.7,.2,1) forwards}
  @keyframes pop{to{opacity:1;transform:none}}
  .cloud span:hover{background:var(--gold-soft);color:#3a2a06;border-color:transparent}
  footer{position:relative;z-index:1;text-align:center;padding:3rem 1.5rem 4rem;color:var(--ink-soft);font-size:.78rem;letter-spacing:.16em}

  /* —— SVG 水彩涂鸦动画 —— */
  .wx-float{animation:floatY 7s ease-in-out infinite alternate}
  .wx-sway{animation:sway 6s ease-in-out infinite alternate}
  .wx-spin{animation:spin 60s linear infinite}
  .wx-rain{animation:rain 1.4s linear infinite}
  .wx-heart{animation:heart 4.2s ease-in-out infinite alternate}
  .wx{transform-box:fill-box;transform-origin:center}
  @keyframes floatY{0%{transform:translateY(0)}100%{transform:translateY(-12px)}}
  @keyframes sway{0%{transform:rotate(-2.5deg)}100%{transform:rotate(2.5deg)}}
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes rain{0%{transform:translateY(-10px);opacity:0}20%{opacity:.8}100%{transform:translateY(26px);opacity:0}}
  @keyframes heart{0%{transform:translateY(0) scale(1)}100%{transform:translateY(-14px) scale(1.12)}}

  @media (max-width:860px){
    .spread,.spread:nth-of-type(even){grid-template-columns:1fr;gap:2.2rem}
    .spread:nth-of-type(even) .art{order:0}
    .spread{padding-left:clamp(1.1rem,5vw,2rem);padding-right:clamp(1.1rem,5vw,2rem)}
    .copy p{font-size:1.04rem;line-height:1.85}
  }
  /* 窄屏语言切换药丸：收紧内边距，否则「双语」会折成两行 */
  @media (max-width:480px){
    .lang{top:.6rem;padding:.22rem;gap:.1rem}
    .lang button{font-size:.74rem;padding:.34rem .6rem;letter-spacing:0}
    h1{letter-spacing:-.01em}
  }
  /* —— 英文朗读（Web Speech API） —— */
  .lang .play-all{margin-left:.3rem;border:0;background:transparent;font-size:.8rem;line-height:1;
    padding:.42rem .8rem;border-radius:999px;color:var(--blue);cursor:pointer;white-space:nowrap;
    transition:background .2s,color .2s}
  .lang .play-all:hover{background:rgba(47,72,88,.1)}
  .lang .play-all.on{background:var(--gold);color:#3a2a06}
  .copy{position:relative}
  .copy .play{position:absolute;top:0;right:0;width:2.2rem;height:2.2rem;border-radius:50%;
    border:1px solid rgba(47,72,88,.16);background:rgba(255,255,255,.75);color:var(--blue);
    cursor:pointer;font-size:.95rem;display:flex;align-items:center;justify-content:center;
    backdrop-filter:blur(6px);box-shadow:0 6px 16px -10px rgba(47,72,88,.6);
    transition:transform .15s,background .2s,color .2s}
  .copy .play:hover{transform:scale(1.08)}
  .copy .play.on{background:var(--gold);color:#3a2a06}
  .copy .play .btxt{line-height:1}
  /* 正在朗读时轻轻脉动，明确「再点一次就是停止」 */
  .copy .play.on,.lang .play-all.on{animation:pulse 1.5s ease-in-out infinite}
  @keyframes pulse{
    0%,100%{box-shadow:0 0 0 0 rgba(217,177,105,.75)}
    50%{box-shadow:0 0 0 8px rgba(217,177,105,0)}
  }
  .wd{transition:color .12s,background .12s;border-radius:3px}
  .wd.speaking{background:linear-gradient(180deg,transparent 52%,rgba(184,135,47,.82) 52%);color:#3a2a06}
  .copy p.line-on{opacity:1!important;transform:none!important;filter:none!important}
  @media (max-width:480px){ .lang .play-all{font-size:.74rem;padding:.34rem .6rem} }
  @media (prefers-reduced-motion:reduce){
    *{animation:none!important;transition:none!important}
    .copy p,h1 .w{opacity:1!important;transform:none!important;filter:none!important}
  }
"""

# ⚠️ 这个字符串**不能**写成 r"""（raw）：
#   JS 侧要的是 Python `'\\\\b'` → 输出 `'\\b'` → JS 字符串 `\b`（正则的「词边界」）。
#   一旦改成 raw，输出会变成 `'\\\\b'`，JS 只当成「字面反斜杠 + b」，**金色词高亮会整体失效**
#   （实测 esc() 会退化成空操作、正则一个词都匹配不上，已踩）。
#   代价是 Python 侧的正则反斜杠要写双份（`\\s`），否则 3.12+ 会报 SyntaxWarning。
JS = """
(function(){
  var WORDS = __WORDS__;
  var PANELS = __PANELS__;   // [{en:[...], zh:"..."}]

  function esc(s){return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');}
  function forms(w){var o={},stem=w.replace(/e$/,'');
    [w,w+'s',w+'es',w+'d',w+'ed',stem+'ing',stem+'ies',stem+'ied',w+'ied'].forEach(function(f){o[f]=1;});
    return Object.keys(o).sort(function(a,b){return b.length-a.length;});}
  var re=new RegExp('\\\\b('+WORDS.map(forms).map(function(fs){return fs.map(esc).join('|');}).join('|')+')\\\\b','gi');

  function render(mode){
    document.querySelectorAll('.spread').forEach(function(sec,i){
      // 重画会把朗读时套的 .wd 外壳冲掉，标记一并作废，下次朗读重新准备
      sec._starts = null; sec._wd = null;
      var p=PANELS[i]; if(!p) return;
      var box=sec.querySelector('.lines'); if(!box) return;
      box.innerHTML='';
      if(mode!=='zh'){
        p.en.forEach(function(ln){
          var el=document.createElement('p');
          el.className='en';
          el.innerHTML=ln.replace(re,'<span class="word">$1</span>');
          box.appendChild(el);
        });
      }
      if(mode!=='en' && p.zh){
        var z=document.createElement('p');
        z.className='zh';
        z.textContent=p.zh;          // 用 textContent，中文里的标点不会被转义
        box.appendChild(z);
      }
    });
  }

  // 封面标题逐字
  var t=document.getElementById('title'), title=__TITLE__;
  title.split(' ').forEach(function(word,i){
    var s=document.createElement('span'); s.className='w'; s.textContent=word;
    s.style.animationDelay=(.35+i*.11)+'s'; t.appendChild(s); t.appendChild(document.createTextNode(' '));
  });

  var cloud=document.getElementById('cloud');
  WORDS.forEach(function(w,i){var s=document.createElement('span');s.textContent=w;s.style.animationDelay=(i*.035)+'s';cloud.appendChild(s);});

  // 语言
  var mode='bi';
  // ⚠️ 只能绑带 data-mode 的按钮：「朗读」按钮也在 .lang 里，
  //    用 `.lang button` 会把它一起绑上，一点朗读就把 mode 覆盖成 undefined
  //    （双语同时显示、ensureEnVisible 失效，实测踩过）。
  document.querySelectorAll('.lang button[data-mode]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.lang button').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on'); mode=b.dataset.mode; render(mode);
    });
  });
  render(mode);

  // 滚动揭示 + 视差
  var spreads=[].slice.call(document.querySelectorAll('.spread'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)e.target.classList.add('in');});},{threshold:.2});
    spreads.forEach(function(s){io.observe(s);});
    var io2=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting&&!e.target.dataset.lit){e.target.dataset.lit='1';
        e.target.querySelectorAll('.word').forEach(function(w,i){setTimeout(function(){w.classList.add('lit');setTimeout(function(){w.classList.remove('lit');},900);},i*55);});}
    });},{threshold:.45});
    spreads.forEach(function(s){io2.observe(s);});
  } else { spreads.forEach(function(s){s.classList.add('in');}); }

  var bar=document.getElementById('bar');
  window.addEventListener('scroll',function(){
    var h=document.documentElement.scrollHeight-window.innerHeight;
    bar.style.width=(h>0?(window.scrollY/h)*100:0)+'%';
  },{passive:true});

  /* —— 英文朗读（Web Speech API）：点一次开始，再点一次停止 —— */
  var synth = window.speechSynthesis || null;
  var EN_VOICE = null, narrating = false, narrGen = 0;
  var activeBtn = null, narrSec = null, narrPrevMode = null;

  function pickEnVoice(){
    if(!synth) return null;
    var vs = synth.getVoices() || [];
    function score(v){
      var s = 0, l = (v.lang||'').toLowerCase(), n = (v.name||'').toLowerCase();
      if(l.indexOf('en-us') === 0) s += 4;
      else if(l.indexOf('en-gb') === 0) s += 3;
      else if(l.indexOf('en') === 0) s += 1;
      else return -1;
      if(/natural|neural|premium|enhanced|siri/.test(n)) s += 3;
      if(/google|samantha|daniel|karen|serena|alex/.test(n)) s += 2;
      if(v.localService) s += 1;
      return s;
    }
    var best = null, bs = 0;
    vs.forEach(function(v){ var s = score(v); if(s > bs){ bs = s; best = v; } });
    return best;
  }
  if(synth){
    EN_VOICE = pickEnVoice();
    if(typeof synth.addEventListener === 'function') synth.addEventListener('voiceschanged', function(){ EN_VOICE = pickEnVoice(); });
    else synth.onvoiceschanged = function(){ EN_VOICE = pickEnVoice(); };
  } else {
    // 浏览器不支持语音合成 → 藏掉按钮，别让人点了没反应
    document.querySelectorAll('.play,.play-all').forEach(function(b){ b.style.display = 'none'; });
  }

  function prepNarration(sec){
    if(sec._starts) return;
    var starts = [];
    sec.querySelectorAll('.copy p.en').forEach(function(p){
      var plain = p.textContent, toks = plain.split(/(\\s+)/), off = 0, html = '';
      toks.forEach(function(tok){
        if(tok==='') return;
        if(/^\\s+$/.test(tok)){ html += tok; off += tok.length; return; }
        starts.push(off);
        html += '<span class="wd">'+tok+'</span>';
        off += tok.length;
      });
      p.innerHTML = html;
    });
    sec._starts = starts;
    sec._wd = sec.querySelectorAll('.wd');
  }
  function clearNarration(){
    if(narrSec){
      narrSec.querySelectorAll('.wd.speaking').forEach(function(s){ s.classList.remove('speaking'); });
      narrSec.querySelectorAll('.copy p.line-on').forEach(function(p){ p.classList.remove('line-on'); });
    }
  }
  function highlightAt(sec, ci){
    var starts = sec._starts; if(!starts || !starts.length) return;
    var ans = 0;
    for(var i=0;i<starts.length;i++){ if(starts[i] <= ci) ans = i; else break; }
    sec._wd.forEach(function(s,i){ s.classList.toggle('speaking', i===ans); });
  }
  function setBtn(btn, on){
    if(!btn) return;
    btn.classList.toggle('on', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    var t = btn.querySelector('.btxt');
    if(t) t.textContent = on ? btn.getAttribute('data-stop') : btn.getAttribute('data-start');
  }
  function stopNarration(){
    narrating = false;
    /* 关键：cancel() 会触发当前 utterance 的 onend/onerror，
       回调必须靠「代次」失效，否则点了「停止」还会接着念下一行。 */
    narrGen++;
    if(synth){ try{ synth.cancel(); }catch(e){} }
    clearNarration();
    narrSec = null;
    setBtn(activeBtn, false); activeBtn = null;
    setBtn(document.querySelector('.play-all'), false);
    // 朗读时 .wd 外壳顶掉了金色词高亮 → 收尾按当前语言重画一次复原
    render(narrPrevMode || mode);
    narrPrevMode = null;
  }
  function narrateSection(sec, done){
    if(!synth){ if(done) done(); return; }
    prepNarration(sec);
    sec.classList.add('in');
    narrSec = sec;
    var g = narrGen;
    var lines = [].slice.call(sec.querySelectorAll('.copy p.en'));
    var li = 0;
    (function speakLine(){
      if(!narrating || g !== narrGen) return;      // 已停止 / 已换一轮 → 立刻退出
      if(li >= lines.length){ if(done) done(); return; }
      lines.forEach(function(p){ p.classList.remove('line-on'); });
      var p = lines[li];
      p.classList.add('line-on');
      p.scrollIntoView({behavior:'smooth', block:'center'});
      var u = new SpeechSynthesisUtterance(p.textContent);
      u.lang = (EN_VOICE && EN_VOICE.lang) || 'en-US';
      u.rate = __RATE__; u.pitch = 1.0;
      if(EN_VOICE) u.voice = EN_VOICE;
      u.onboundary = function(e){
        if(narrating && g === narrGen && typeof e.charIndex === 'number') highlightAt(sec, e.charIndex);
      };
      u.onend = function(){ if(!narrating || g !== narrGen) return; li++; speakLine(); };
      u.onerror = function(e){
        if(!narrating || g !== narrGen) return;
        if(e && (e.error === 'canceled' || e.error === 'interrupted')) return;   // 是我们自己 cancel 的
        li++; speakLine();
      };
      synth.speak(u);
    })();
  }
  function ensureEnVisible(){
    // 中文模式下没有英文行可念 → 先切英文；停止后再按 narrPrevMode 还原。
    // 不用 `mode==='zh'` 判断，是因为 mode 有可能被别的逻辑带歪，直接看 DOM 更稳。
    if(!document.querySelector('.copy p.en')){ narrPrevMode = mode; render('en'); }
  }
  function startNarration(btn, fn){
    stopNarration();
    ensureEnVisible();
    narrating = true; narrGen++;
    activeBtn = btn; setBtn(btn, true);
    fn();
  }
  // 单段朗读：再点一次停止
  document.querySelectorAll('.copy .play').forEach(function(btn){
    btn.addEventListener('click', function(){
      if(activeBtn === btn && narrating){ stopNarration(); return; }
      var sec = btn.closest('.spread');
      startNarration(btn, function(){
        narrateSection(sec, function(){ if(activeBtn === btn) stopNarration(); });
      });
    });
  });
  // 全文朗读：点一次开始，再点一次停止
  var paBtn = document.querySelector('.play-all');
  if(paBtn) paBtn.addEventListener('click', function(){
    if(narrating){ stopNarration(); return; }
    startNarration(paBtn, function(){
      var secs = [].slice.call(document.querySelectorAll('.spread'));
      var i = 0;
      (function next(){
        if(!narrating) return;
        if(i >= secs.length){ stopNarration(); return; }
        secs[i].scrollIntoView({behavior:'smooth', block:'center'});
        narrateSection(secs[i], function(){ i++; setTimeout(next, 420); });
      })();
    });
  });
  window.addEventListener('beforeunload', function(){ if(synth){ try{ synth.cancel(); }catch(e){} } });
})();
"""


def split_stanzas(poem):
    out, cur = [], []
    for ln in poem:
        if ln.strip() == "":
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(ln.rstrip())
    if cur:
        out.append(cur)
    return out


def build_html(title, subtitle, date, panels, words, svg_fn=svg, assign_fn=None, rate=0.92,
               art_fn=None):
    """art_fn(i, panel, title) 给了就用它出图（故事分镜引擎）；i=None 是封面。
    没给就走老的「9 个场景」路径（svg_fn + assign_fn）。"""
    scenes = (assign_fn or assign_scenes)([p["en"] for p in panels])
    art_cards = []
    for i, p in enumerate(panels):
        if art_fn is not None:
            art = art_fn(i, p, title)
        else:
            art = svg_fn(p.get("scene") or scenes[i])
        num = ROMAN[i] if i < len(ROMAN) else str(i + 1)
        art_cards.append(
            '  <section class="spread">\n'
            '    <div class="art"><div class="art-inner">%s</div></div>\n'
            '    <div class="copy"><span class="num">%s</span>'
            '<button class="play" type="button" aria-pressed="false" data-start="\U0001F50A" data-stop="\u23F9"'
            ' aria-label="朗读这一段英文" title="朗读这一段英文">'
            '<span class="btxt">\U0001F50A</span></button>'
            '<div class="lines"></div></div>\n'
            '  </section>\n' % (art, num)
        )
    js = (JS.replace("__WORDS__", json.dumps(words, ensure_ascii=False))
             .replace("__PANELS__", json.dumps([{"en": p["en"], "zh": p["zh"]} for p in panels], ensure_ascii=False))
             .replace("__TITLE__", json.dumps(title, ensure_ascii=False))
             .replace("__RATE__", "%.2f" % rate))
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s · 水彩涂鸦绘本</title>
<style>%(css)s</style>
</head>
<body>

<div class="progress"><span id="bar"></span></div>
<div class="lang">
  <button data-mode="en">English</button>
  <button data-mode="bi" class="on">双语</button>
  <button data-mode="zh">中文</button>
  <button class="play-all" type="button" aria-pressed="false" data-start="朗读" data-stop="停止"
    aria-label="朗读全文英文" title="朗读全文英文">&#128266; <span class="btxt">朗读</span></button>
</div>
<div class="blobs">
  <div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>
</div>
<div class="grain"></div>

<header class="hero">
  <div class="hero-inner">
    <div class="hero-frame">%(cover)s</div>
    <p class="kicker">丫丫雅思单词 · %(date)s</p>
    <h1 id="title"></h1>
    <div class="rule"></div>
    <p class="sub">%(sub)s</p>
    <p class="scroll-hint" style="margin-top:3.2rem">向下滚动</p>
  </div>
</header>

<main>
%(spreads)s
  <section class="finale">
    <h2>今日的 %(n)d 个词 · 都在上面了</h2>
    <div class="cloud" id="cloud"></div>
  </section>
</main>

<footer>水彩涂鸦绘本 · 丫丫雅思单词 · %(date)s</footer>

<script>%(js)s</script>
</body>
</html>
""" % {
        "title": html.escape(title), "date": html.escape(date), "sub": html.escape(subtitle),
        "cover": (art_fn(None, None, title) if art_fn is not None else svg("cover")),
        "spreads": "\n".join(art_cards), "css": CSS, "js": js, "n": len(words),
    }


def main():
    ap = argparse.ArgumentParser(description="水彩涂鸦 SVG 的动态 HTML 绘本（EN/中文/双语）")
    ap.add_argument("--json", help="内容 JSON（title/date/subtitle/story/words；兼容旧键 poem）")
    ap.add_argument("--zh-file", help="中文翻译 JSON：{\"1\":\"...\",\"2\":\"...\"} 或 {\"zh\":[...]}")
    ap.add_argument("--out", help="输出 HTML 路径")
    ap.add_argument("--title"); ap.add_argument("--subtitle"); ap.add_argument("--date")
    ap.add_argument("--json-out", action="store_true")
    ap.add_argument("--rate", type=float, default=0.92,
                    help="朗读语速（0.5–1.5；默认 0.92，比常速慢一点方便跟读）")
    ap.add_argument("--art", choices=("storyboard", "scene"), default="storyboard",
                    help="插画引擎：storyboard=按段落内容现场拼（默认，贴题且跨天不重样）；"
                         "scene=老的 9 个成品场景")
    ap.add_argument("--no-ledger", action="store_true",
                    help="不读写 art-ledger.json（测试用）")
    ap.add_argument("--art-ledger-dir", help="台账目录（默认 $IELTS_DATA_DIR 或 ~/.workbuddy/ielts-prep）")
    a = ap.parse_args()

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

    zh = dict(DEFAULT_ZH)

    def _absorb(z):
        if isinstance(z, list):
            vals = [str(v) for v in z]
            # 有的写法是「按行对齐」（段落之间有 "" 空行）→ 去掉空行再按段编号
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

    # 1) 诗稿自带的中文优先（zh / zh_stanzas / translation）
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
    rate = min(1.5, max(0.5, a.rate))

    art_fn, plans, cover, save = (None, [], None, None)
    if a.art == "storyboard":
        try:
            art_fn, plans, cover, save = storyboard_art_fn(
                [p["en"] for p in panels], title, date=date,
                data_dir=a.art_ledger_dir, use_ledger=not a.no_ledger)
        except SystemExit:
            raise
        except Exception as e:  # 分镜引擎出问题不该让整本绘本挂掉
            sys.stderr.write("⚠️  故事分镜引擎失败（%s），退回成品场景。\n" % e)
            art_fn = None

    with open(out, "w", encoding="utf-8") as f:
        f.write(build_html(title, subtitle, date, panels, words, rate=rate, art_fn=art_fn))

    if plans:
        lp = save()
        print("🎬 分镜配图（%d 段）：%s" % (len(plans), " / ".join(ART.describe(p) for p in plans)))
        if lp:
            print("📒 配图台账已更新：%s（最近 %d 天用过的背景/组合明天会自动避开）"
                  % (lp, ART.RECENT_DAYS))
    print("🔊 朗读按钮：点一次开始 / 再点一次停止（语速 %.2f）" % rate)

    print(json.dumps({"html": out, "panels": len(panels), "words": len(words)}, ensure_ascii=False)
          if a.json_out else "🎨 水彩涂鸦绘本已生成：%s（%d 段 · %d 词 · 含 EN/中文/双语切换）" % (out, len(panels), len(words)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
