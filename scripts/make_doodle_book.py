#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把散文诗做成**手绘 SVG 水彩涂鸦 + 动画 + 三语切换**的 HTML 绘本。

和另外几个渲染器的分工（别再重复造轮子）：
  make_poem_poster.py     → 一张静态诗卡（夜色 + 金字），PNG
  make_comic.py           → 哆啦 A 梦卡通风连环画，手写 SVG 场景
  make_picturebook.py     → 3D 翻页绘本，点词查义，复用 make_comic 的场景
  make_watercolor_book.py → **AI 生成的水彩位图**做素材，滚动式
  make_doodle_book.py     → 本文件：**纯手写 SVG 水彩涂鸦**，矢量不糊、
                            自带 CSS 动画、支持 英文/中文/双语 三语切换

用法：
    make_doodle_book.py --json poem-bi.json --vocab vocab.json --out book/index.html

输入 JSON（可用 `poem` 兼容旧格式，但推荐带 zh 的新格式）：
    {
      "title": "...", "title_zh": "...", "date": "...",
      "subtitle": "...", "subtitle_zh": "...",
      "words": [...],
      "stanzas": [{"scene":"city", "caption_en":"...", "caption_zh":"...",
                   "lines":[{"en":"...","zh":"..."}, ...]}, ...]
    }
`--vocab` 是 `ielts.py poem --json` 的输出，用来给高亮词挂中文tooltip（可省）。

新增场景：往 SCENES 里加一个返回 SVG 字符串的函数即可。
所有形都用 rap_wrap() 生成（抖动 + Catmull-Rom），这才有"涂鸦"的手感——
**别手写规整的圆和矩形**，那会立刻失去水彩味。
"""

import argparse
import html
import json
import math
import os
import random
import sys

# --------------------------------------------------------------------------
# 涂鸦几何：抖动点 + Catmull-Rom → 三次贝塞尔，让每条边都不那么"直"
# --------------------------------------------------------------------------


def _jr(seed, amp, pts):
    r = random.Random(seed)
    return [(x + r.uniform(-amp, amp), y + r.uniform(-amp, amp)) for x, y in pts]


def densify(pts, step=42, closed=True):
    """顶点太少时 Catmull-Rom 会把矩形揉成胶囊。先沿边补点，曲线才会贴着直边只轻微发颤。"""
    out, n = [], len(pts)
    segs = n if closed else n - 1
    for i in range(segs):
        a, b = pts[i], pts[(i + 1) % n]
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(d / step))
        for j in range(k):
            t = j / k
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    if not closed:
        out.append(pts[-1])
    return out


def smooth(pts, closed=True, amp=0.0, seed=0):
    """Catmull-Rom 转贝塞尔；amp>0 时先给顶点加抖动"""
    p = list(pts)
    if len(p) <= 10:
        p = densify(p, 42, closed)
    if amp:
        p = _jr(seed, amp, p)
    if closed:
        P = [p[-1]] + p + [p[0], p[1]]
    else:
        P = [p[0]] + p + [p[-1]]
    d = "M%.1f %.1f" % (P[1][0], P[1][1])
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d += "C%.1f %.1f %.1f %.1f %.1f %.1f" % (c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    return d + ("Z" if closed else "")


def circle_pts(cx, cy, r, n=11, irreg=0.16, seed=0, squash=1.0):
    rr = random.Random(seed)
    return [(cx + math.cos(2 * math.pi * i / n) * r * (1 + rr.uniform(-irreg, irreg)),
             cy + math.sin(2 * math.pi * i / n) * r * squash * (1 + rr.uniform(-irreg, irreg)))
            for i in range(n)]


INK = "#33414b"
INK_SOFT = "#5e6b74"


def wash(pts, color, op=.42, seed=1, amp=9, closed=True):
    """一块水彩色：两三层叠加，边缘会积色"""
    s = ['<path d="%s" fill="%s" opacity="%.2f"/>' % (smooth(pts, closed, amp, seed), color, op)]
    s.append('<path d="%s" fill="none" stroke="%s" stroke-width="7" opacity="%.2f"/>'
             % (smooth(pts, closed, amp * 1.5, seed + 31), color, op * .45))
    return "".join(s)


def blob(cx, cy, r, color, op=.40, seed=0, squash=1.0, n=11, irreg=.16):
    return wash(circle_pts(cx, cy, r, n, irreg, seed, squash), color, op, seed + 3, 4)


def ink(pts, color=INK, w=2.4, seed=0, amp=2.2, closed=False, dash=None):
    d = smooth(pts, closed, amp, seed)
    extra = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" stroke-linejoin="round"%s/>' % (
        d, color, w, extra)


def rect_pts(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def isoroom_pts(x1, y1, x2, y2, x3, y3, x4, y4):
    return [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]


# 通用小零件 ---------------------------------------------------------------


def person(x, y, h=54, color="#7d8b93", head="#e6cfc0", hair="#3d4a54", seed=0, cls=""):
    """手绘小人：原点在头部中心，脚在 0.95h 处（场景里的 y 基本都是"头的高度"）"""
    hr = h * .17
    sh, hip = h * .26, h * .62
    s = ['<g class="%s" transform="translate(%.1f,%.1f)">' % (cls, x, y)]
    s.append(wash([(-h * .13, sh), (h * .13, sh), (h * .16, hip), (-h * .16, hip)], color, .55, seed, 3))
    s.append(ink([(-h * .13, sh), (h * .13, sh), (h * .16, hip), (-h * .16, hip)], INK, 1.9, seed + 1, 1.6, True))
    s.append(ink([(0, hr), (0, sh)], head, 2.6, seed + 9, 1.4))                      # 脖子
    s.append(ink([(-h * .07, hip), (-h * .1, h * .95)], INK, 2.3, seed + 2, 2))      # 腿
    s.append(ink([(h * .07, hip), (h * .1, h * .95)], INK, 2.3, seed + 3, 2))
    s.append(ink([(-h * .13, sh + h * .06), (-h * .23, hip)], INK, 2.0, seed + 4, 2))  # 手臂
    s.append(ink([(h * .13, sh + h * .06), (h * .23, hip)], INK, 2.0, seed + 5, 2))
    s.append('<circle cx="0" cy="0" r="%.1f" fill="%s" opacity=".92"/>' % (hr, head))
    s.append(ink(circle_pts(0, 0, hr, 9, .1, seed + 6), INK, 1.8, seed + 7, 1.1, True))
    s.append('<path d="%s" fill="%s" opacity=".9"/>' % (
        smooth([(-hr, -hr * .1), (-hr * .72, -hr * .95), (0, -hr * 1.22), (hr * .72, -hr * .95), (hr, -hr * .1)],
               True, 1.4, seed + 8), hair))
    s.append('</g>')
    return "".join(s)


def tree(x, y, s=1.0, seed=0, cls="a-sway", color="#6f9464"):
    """一棵会晃的小树"""
    top = y - 62 * s
    p = ['<g transform="translate(%.1f,%.1f) scale(%.2f)">' % (x, y, s)]
    p.append(ink([(0, 0), (0, -46)], "#6b5744", 3.4, seed, 2.4))
    p.append('<g class="%s">' % cls)
    for i, (dx, dy, rr) in enumerate([(0, -62, 30), (-22, -50, 20), (22, -50, 20)]):
        p.append(blob(dx, dy, rr, color, .52, seed + i * 5, .92))
    p.append('</g></g>')
    return "".join(p)


def house(x, y, w=110, h=90, color="#c9b79c", roof="#8d6b57", seed=0, win="#f2d79b"):
    p = [wash(rect_pts(x, y - h, w, h), color, .5, seed, 5)]
    p.append(wash([(x - 10, y - h), (x + w / 2, y - h - 46), (x + w + 10, y - h)], roof, .55, seed + 2, 5))
    for i in range(2):
        wx = x + 18 + i * (w - 52)
        p.append('<rect x="%.1f" y="%.1f" width="20" height="24" rx="3" fill="%s" opacity=".75"/>' % (wx, y - h + 26, win))
    p.append(ink(rect_pts(x, y - h, w, h), INK, 2.0, seed + 6, 2.6, True))
    return "".join(p)


def car(x, y, s=1.0, color="#7f95a5", seed=0, cls=""):
    """注意：定位用外层 <g transform>，动画放在内层 <g>——CSS transform 会覆盖
    transform 属性，两者写在同一个元素上会让车飞回原点。"""
    p = ['<g transform="translate(%.1f,%.1f) scale(%.2f)"><g class="%s">' % (x, y, s, cls)]
    p.append(wash([(-34, 0), (34, 0), (38, -18), (-10, -18), (-30, -6)], color, .58, seed, 3))
    p.append(ink([(-34, 0), (34, 0), (38, -18), (-10, -18), (-30, -6)], INK, 2.0, seed + 1, 2, True))
    p.append('<circle cx="-20" cy="0" r="6" fill="%s"/><circle cx="20" cy="0" r="6" fill="%s"/>' % (INK, INK))
    return "".join(p) + '</g></g>'


def cloud(x, y, s=1.0, color="#eef3f2", op=.75, seed=0, cls="a-drift"):
    p = ['<g transform="translate(%.1f,%.1f) scale(%.2f)"><g class="%s">' % (x, y, s, cls)]
    for i, (dx, dy, rr) in enumerate([(0, 0, 34), (34, 8, 26), (-32, 8, 24), (14, -12, 22)]):
        p.append(blob(dx, dy, rr, color, op, seed + i * 3, .62))
    return "".join(p) + '</g></g>'


def ray_of_light(pts, color="#f6d98a", op=.28, cls="a-flicker"):
    return '<path class="%s" d="%s" fill="%s" opacity="%.2f"/>' % (cls, smooth(pts, True, 0, 0), color, op)


def mote(x, y, r=3, cls="a-mote", color="#f3e3bb", delay=0.0):
    return ('<circle class="%s" cx="%.1f" cy="%.1f" r="%.1f" fill="%s" '
            'style="animation-delay:%.1fs"/>' % (cls, x, y, r, color, delay))


# --------------------------------------------------------------------------
# 场景
# --------------------------------------------------------------------------

PAPER = "#f8f3e8"


def scene_wrap(inner, vb="0 0 1200 800"):
    return ('<svg class="pic" viewBox="%s" xmlns="http://www.w3.org/2000/svg" '
            'preserveAspectRatio="xMidYMid slice" role="img">%s</svg>' % (vb, inner))


def page_bg(sky="#dfe8e6", ground="#c9bfa8", seed=0):
    p = ['<rect width="1200" height="800" fill="%s"/>' % PAPER]
    p.append(wash(rect_pts(-40, -40, 1280, 560), sky, .55, seed, 6))
    p.append(wash([(-40, 620), (1240, 600), (1240, 840), (-40, 840)], ground, .5, seed + 9, 12))
    return "".join(p)


def scene_city():
    """I · 惯常的清晨：灰霾、车流、路口仰望的人"""
    s = [page_bg("#d9dfe2", "#c8bfae", 3)]
    # 远处楼群
    for i, (x, w, h) in enumerate([(40, 150, 300), (210, 130, 240), (360, 170, 330),
                                   (560, 140, 260), (720, 180, 300), (930, 160, 250), (1110, 120, 290)]):
        c = ["#aab6bd", "#9fb0b8", "#b3bcc0"][i % 3]
        s.append(wash(rect_pts(x, 640 - h, w, h), c, .45, 100 + i, 5))
        s.append(ink(rect_pts(x, 640 - h, w, h), INK_SOFT, 1.8, 200 + i, 2.4, True))
        for r_ in range(int(h // 58)):          # 窗
            for c_ in range(int(w // 48)):
                s.append('<rect x="%.1f" y="%.1f" width="20" height="26" rx="3" fill="#8e9ba3" '
                         'opacity=".42"/>' % (x + 16 + c_ * 48, 640 - h + 22 + r_ * 58))
    # 路面
    s.append(wash([(0, 640), (1200, 630), (1200, 800), (0, 800)], "#b7aea0", .55, 12, 10))
    s.append(ink([(0, 700), (1200, 690)], "#f1ece0", 3.2, 13, 2, False, dash="26 30"))
    # 车流（两辆缓慢错身）
    s.append(car(300, 690, 1.0, "#7c93a3", 21, "a-crawl"))
    s.append(car(760, 715, 1.1, "#8e7f74", 22, "a-crawl2"))
    s.append(car(520, 668, .85, "#96a3ab", 23, "a-crawl3"))
    # 灰霾
    for i, (cx, cy, rr, delay) in enumerate([(260, 470, 150, 0), (700, 520, 170, 3), (1010, 450, 130, 6)]):
        s.append('<g class="a-haze" style="animation-delay:%.1fs">' % delay)
        s.append(blob(cx, cy, rr, "#c6c3ba", .40, 300 + i, .48))
        s.append('</g>')
    # 红绿灯 + 一个人
    s.append(ink([(175, 640), (175, 500)], INK, 3.0, 31, 2))
    s.append(wash(rect_pts(160, 470, 32, 62), "#6a7378", .65, 32, 3))
    for i, c in enumerate(["#c86b52", "#d8b25c", "#7fa06a"]):
        s.append('<circle cx="176" cy="%d" r="8" fill="%s" class="a-twinkle" style="animation-delay:%.1fs"/>'
                 % (490 + i * 18, c, i * .8))
    s.append(person(250, 700, 62, "#7f8b93", "#e8d0bd", "#3a4650", 41))
    # 尾气
    for i in range(3):
        s.append('<circle class="a-puff" cx="%d" cy="%d" r="%d" fill="#b9bcb6" style="animation-delay:%.1fs"/>'
                 % (255, 676, 8 + i * 3, i * 1.1))
    return scene_wrap("".join(s))


def scene_council():
    """II · 争论与投票：长桌、两排人、一束窗光"""
    s = ['<rect width="1200" height="800" fill="#eff0e6"/>']
    s.append(wash(rect_pts(-40, -40, 1280, 840), "#3f5a63", .82, 5, 8))
    # 窗 + 光柱
    s.append(wash(rect_pts(860, 120, 220, 250), "#f3dfa6", .5, 7, 4))
    s.append(ink(rect_pts(860, 120, 220, 250), INK, 2.4, 8, 2, True))
    s.append(ink([(980, 120), (980, 370)], INK, 2.0, 9, 2))
    s.append(ink([(860, 245), (1080, 245)], INK, 2.0, 10, 2))
    s.append(ray_of_light([(860, 150), (1080, 160), (700, 760), (330, 780)], "#f7e2a8", .22, "a-flicker"))
    # 长桌
    s.append(wash(isoroom_pts(250, 546, 960, 528, 1010, 636, 196, 662), "#c79a5e", .6, 11, 6))
    s.append(ink(isoroom_pts(250, 546, 960, 528, 1010, 636, 196, 662), INK, 2.6, 12, 2.4, True))
    # 桌上沙盘 + 焚烧炉模型
    s.append(wash(rect_pts(470, 480, 300, 70), "#8fa891", .55, 13, 4))
    s.append(ink(rect_pts(470, 480, 300, 70), INK, 2.0, 14, 2, True))
    s.append(wash(rect_pts(560, 400, 46, 82), "#8d6b57", .6, 15, 3))
    s.append(ink(rect_pts(560, 400, 46, 82), INK, 2.2, 16, 2, True))
    for i in range(3):
        s.append('<circle class="a-puff2" cx="%d" cy="%d" r="%d" fill="#cfd3cc" style="animation-delay:%.1fs"/>'
                 % (583, 392, 9 + i * 3, i * 1.3))
    # 两侧的人
    seats = [300, 400, 500, 600, 700, 800, 880]
    for i, x in enumerate(seats):
        s.append(person(x, 470, 58, ["#7b8a86", "#8b7f72", "#6f8390", "#8a7c86"][i % 4],
                        ["#e8d2bb", "#d9bb9d", "#f0dcc4", "#c9a98a"][i % 4], "#37424c", 100 + i))
    for i, x in enumerate([340, 470, 640, 810]):
        s.append(person(x, 660, 66, ["#77858c", "#88796c", "#6f8390", "#847a80"][i % 4],
                        ["#e8d2bb", "#d9bb9d", "#f0dcc4", "#c9a98a"][i % 4], "#37424c", 130 + i))
    # 争辩气泡（一个个冒出来）
    for i, (x, y, w2, delay) in enumerate([(430, 400, 46, 0), (600, 372, 38, .9),
                                           (740, 404, 42, 1.8), (520, 356, 34, 2.6)]):
        s.append('<g transform="translate(%d,%d)"><g class="a-bubble" style="animation-delay:%.1fs">' % (x, y, delay))
        s.append(wash(circle_pts(0, 0, w2, 10, .13, 200 + i), "#f2eee2", .72, 210 + i, 3))
        s.append(ink(circle_pts(0, 0, w2, 10, .13, 200 + i), INK, 2.0, 220 + i, 1.6, True))
        s.append(ink([(-18, -4), (-6, -4)], INK, 3.0, 230 + i, 1.2))
        s.append(ink([(-18, 8), (12, 8)], INK, 3.0, 240 + i, 1.2))
        s.append('</g></g>')
    # 投票箱 + 一张悬而未决的纸
    s.append(wash(rect_pts(830, 545, 90, 60), "#7d8a86", .6, 17, 3))
    s.append(ink(rect_pts(830, 545, 90, 60), INK, 2.2, 18, 2, True))
    s.append('<rect x="856" y="530" width="34" height="46" rx="3" fill="#f4f0e4" opacity=".9" class="a-tilt"/>')
    return scene_wrap("".join(s))


def scene_road():
    """III · 拓宽马路、沿路新栽的树"""
    s = [page_bg("#e6dfc9", "#cdbf9f", 21)]
    s.append(wash(rect_pts(-40, -40, 1280, 420), "#cfe0dc", .5, 22, 6))
    for i in range(4):
        s.append(cloud(180 + i * 260, 150 + (i % 2) * 40, .9 + i * .06, "#f2f6f2", .6, 400 + i,
                       "a-drift" if i % 2 == 0 else "a-drift2"))
    # 远景学校 / 房
    s.append(house(80, 560, 130, 100, "#d8c7a8", "#9d7059", 23))
    s.append(house(1010, 555, 150, 110, "#cfc1a6", "#8f6c58", 24))
    # 由远及近变宽的路面
    s.append(wash([(470, 545), (730, 545), (1180, 800), (20, 800)], "#bfae90", .62, 25, 9))
    s.append(ink([(600, 545), (600, 800)], "#f4f0e2", 3.4, 26, 2, False, dash="34 40"))
    # 新栽的树（会晃）
    for i, (x, y, sc) in enumerate([(150, 690, 1.0), (300, 640, .8), (1030, 690, 1.05), (880, 630, .75),
                                    (430, 600, .6), (790, 590, .58), (95, 570, .55), (1115, 560, .5)]):
        s.append(tree(x, y, sc, 300 + i * 4, "a-sway", ["#6f9464", "#87a06a", "#5f8a63"][i % 3]))
    # 工人 + 工具
    s.append(person(560, 640, 66, "#8a7f6d", "#e3c9ac", "#4a3f36", 51))
    s.append(person(700, 672, 72, "#7c8b84", "#d8b893", "#3f4a3c", 52))
    s.append(ink([(600, 690), (660, 640)], INK, 3.2, 53, 2.4))
    s.append(wash(circle_pts(662, 636, 16, 9, .2, 54), "#8e8378", .7, 55, 3))
    # 翻起的土：three small heaps
    for i, (x, y, rr) in enumerate([(500, 730, 34), (830, 700, 40), (300, 700, 28)]):
        s.append(wash([(x - rr, y), (x + rr, y), (x, y - rr * .7)], "#a8895f", .55, 60 + i, 4))
    # 浮起的叶子
    for i in range(5):
        s.append(mote(200 + i * 180, 520 + (i % 3) * 70, 4 + (i % 3), "a-leaf", "#8aa06a", i * .9))
    return scene_wrap("".join(s))


def scene_rooftop():
    """IV · 太阳能屋顶、雨后滴水、公交与监测浮标"""
    s = ['<rect width="1200" height="800" fill="%s"/>' % PAPER]
    s.append(wash(rect_pts(-40, -40, 1280, 620), "#bcd8dd", .58, 71, 7))
    # 散开的云
    for i in range(3):
        s.append(cloud(220 + i * 330, 130 + (i % 2) * 50, .85 + i * .1, "#f4f8f6", .8, 500 + i,
                       "a-drift" if i != 1 else "a-drift2"))
    # 太阳
    s.append('<g class="a-glow">')
    s.append(blob(1010, 165, 62, "#f2cf7d", .72, 73, 1.0))
    s.append('</g>')
    for i in range(8):
        a = math.pi * 2 * i / 8
        s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#e9c473" stroke-width="3" '
                 'stroke-linecap="round" opacity=".45" class="a-ray" style="animation-delay:%.1fs"/>'
                 % (1010 + math.cos(a) * 74, 165 + math.sin(a) * 74,
                    1010 + math.cos(a) * 96, 165 + math.sin(a) * 96, i * .2))
    # 一排屋顶 + 太阳能板
    roofs = [(60, 470, 230), (300, 440, 250), (560, 480, 210), (790, 430, 250), (1030, 480, 200)]
    for i, (x, y, w) in enumerate(roofs):
        h = 200 + (i % 2) * 40
        s.append(wash(rect_pts(x, y, w, h), ["#c9b79c", "#bfae95", "#d2c2a8"][i % 3], .55, 120 + i, 5))
        s.append(ink(rect_pts(x, y, w, h), INK, 2.2, 130 + i, 2.4, True))
        # 太阳能板（斜平行四边形 + 网格）
        for j in range(2):
            px = x + 22 + j * (w - 150)
            pts = [(px, y + 26), (px + 96, y + 26), (px + 74, y + 68), (px - 22, y + 68)]
            s.append(wash(pts, "#3f6f8c", .68, 140 + i * 3 + j, 3))
            s.append(ink(pts, "#22475c", 2.0, 150 + i * 3 + j, 1.8, True))
            for k in (1, 2):
                s.append(ink([(px + 96 * k / 3 - 22 * k / 3, y + 26), (px + 96 * k / 3 - 22 * k / 3 + 22, y + 68)],
                             "#2c5a74", 1.4, 160 + i + k, 1.2))
        # 屋檐滴水
        for k in range(3):
            s.append('<circle class="a-drip" cx="%d" cy="%d" r="4.5" fill="#7fb6c9" '
                     'style="animation-delay:%.1fs"/>' % (x + 40 + k * (w - 90), y + 34, (i * 3 + k) * .45))
    # 窗里暖灯
    for i in range(6):
        s.append('<rect x="%d" y="%d" width="26" height="30" rx="4" fill="#f2cf7d" opacity=".7" '
                 'class="a-twinkle" style="animation-delay:%.1fs"/>' % (110 + i * 175, 560, i * .6))
    # 街道 + 公交
    s.append(wash(rect_pts(-40, 700, 1280, 140), "#b5ac9a", .55, 74, 8))
    s.append(ink([(-40, 770), (1240, 770)], "#f2eee2", 3.2, 75, 2, False, dash="30 34"))
    s.append('<g class="a-bus">')
    s.append(wash(rect_pts(120, 640, 250, 74), "#d98c5b", .7, 76, 4))
    s.append(ink(rect_pts(120, 640, 250, 74), INK, 2.6, 77, 2.4, True))
    for i in range(3):
        s.append('<rect x="%d" y="%d" width="52" height="30" rx="4" fill="#e8eff0" opacity=".8"/>'
                 % (145 + i * 66, 654))
    s.append('<circle cx="170" cy="716" r="11" fill="%s"/><circle cx="320" cy="716" r="11" fill="%s"/>' % (INK, INK))
    s.append('</g>')
    # 河 + 浮标
    s.append(wash([(-40, 690), (1240, 676), (1240, 726), (-40, 742)], "#7fa8b8", .5, 78, 10))
    s.append('<g class="a-bob">')
    s.append(wash(rect_pts(880, 668, 46, 40), "#e07a56", .7, 79, 3))
    s.append(ink([(903, 668), (903, 640)], INK, 2.4, 80, 1.6))
    s.append('<circle cx="903" cy="632" r="8" fill="#f2cf7d"/>')
    s.append('</g>')
    for i in range(3):  # 河面上的波光
        s.append(ink([(60 + i * 30, 712), (100 + i * 30, 712)], "#eef4f3", 2.6, 90 + i, 3))
    return scene_wrap("".join(s))


def scene_school():
    """V · 狭小礼堂里的光柱、尘埃和耐心"""
    s = ['<rect width="1200" height="800" fill="%s"/>' % PAPER]
    s.append(wash(rect_pts(-40, -40, 1280, 720), "#44545d", .86, 91, 8))            # 墙
    s.append(wash(rect_pts(-40, 660, 1280, 200), "#6b5c4c", .5, 92, 10))            # 地板
    s.append(ink([(0, 662), (1200, 656)], "#8a7a66", 2.4, 93, 3))                    # 踢脚线
    s.append(wash(rect_pts(-40, 600, 1280, 62), "#5a4c40", .35, 94, 6))             # 墙裙
    # 窗 + 光柱
    s.append(wash(rect_pts(110, 80, 200, 280), "#f7e5b0", .62, 95, 4))
    s.append(ink(rect_pts(110, 80, 200, 280), "#2b3740", 3.0, 96, 2, True))
    s.append(ink([(210, 80), (210, 360)], "#2b3740", 2.4, 97, 2))
    s.append(ink([(110, 220), (310, 220)], "#2b3740", 2.4, 98, 2))
    s.append(wash(rect_pts(110, 80, 200, 280), "#fff3cf", .22, 99, 8))
    s.append(ray_of_light([(115, 100), (308, 112), (820, 700), (430, 730)], "#f9e9b8", .30, "a-flicker"))
    # 黑板
    s.append(wash(rect_pts(810, 110, 320, 210), "#2f3d3a", .72, 101, 4))
    s.append(ink(rect_pts(810, 110, 320, 210), "#e9e4d4", 3.2, 102, 2.4, True))
    for i in range(3):
        s.append(ink([(845, 175 + i * 44), (1090 - i * 46, 175 + i * 44)], "#ded6c3", 2.6, 103 + i, 2.6,
                     False, dash="12 14"))
    # 长桌（在画面前方，孩子坐在桌子后面）
    s.append(wash(isoroom_pts(300, 592, 900, 580, 950, 668, 258, 682), "#c49a63", .62, 111, 6))
    s.append(ink(isoroom_pts(300, 592, 900, 580, 950, 668, 258, 682), INK, 2.6, 112, 2.4, True))
    heads = ["#3a3330", "#6b4a33", "#2f2b28", "#8a6a44", "#4a3f38", "#2b2a2c"]
    skins = ["#e8cfb1", "#d9b697", "#f0dcc2", "#c69b7b", "#e8cfb1", "#d9b697"]
    cloth = ["#7d8c93", "#8a7a6e", "#6f8592", "#877a84", "#78887f", "#8b8175"]
    for i in range(6):                        # 坐着的孩子：只露出肩以上
        x = 350 + i * 100
        s.append('<g transform="translate(%d,540)">' % x)
        s.append('<g class="a-bobY" style="animation-delay:%.1fs">' % (i * .5))
        s.append(wash([(-13, 4), (13, 4), (17, 34), (-17, 34)], cloth[i], .6, 120 + i, 3))
        s.append('<circle cx="0" cy="-14" r="15" fill="%s" opacity=".92"/>' % skins[i])
        s.append(ink(circle_pts(0, -14, 15, 9, .1, 130 + i), INK, 2.0, 140 + i, 1.2, True))
        s.append('<path d="%s" fill="%s" opacity=".92"/>' % (
            smooth([(-15, -15), (-11, -28), (0, -33), (11, -28), (15, -15)], True, 1.4, 150 + i), heads[i]))
        s.append('</g></g>')
    # 老师站在窗边的光里（脚落在地板上）
    s.append(person(215, 548, 118, "#8a7f6e", "#e8cfb1", "#4a3f36", 210))
    # 浮尘
    for i in range(10):
        s.append(mote(300 + (i % 5) * 96, 360 + (i % 4) * 84, 3 + (i % 3), "a-mote", "#f9ebc4", i * .7))
    # 挂钟：秒针在走（旋转原点用 view-box 坐标，别用 fill-box——竖线的 bbox 宽度是 0，会转飞）
    s.append('<g transform="translate(1058,420)">')
    s.append(wash(circle_pts(0, 0, 58, 12, .08, 220), "#e9e3d2", .78, 221, 3))
    s.append(ink(circle_pts(0, 0, 58, 12, .08, 220), INK, 3.2, 222, 1.8, True))
    s.append(ink([(0, 0), (0, -36)], INK, 3.4, 223, 1.2))
    s.append(ink([(0, 0), (28, 12)], INK, 2.8, 224, 1.2))
    s.append('<line class="a-tick" style="--ox:1058px;--oy:420px" x1="0" y1="0" x2="0" y2="-48" '
             'stroke="#c06a52" stroke-width="2.8" stroke-linecap="round"/>')
    s.append('</g>')
    return scene_wrap("".join(s))


def scene_market():
    """VI · 放晴后的多元市集，残烟散去"""
    s = [page_bg("#dcece9", "#cdbfa2", 111)]
    s.append(wash(rect_pts(-40, -40, 1280, 480), "#bfe0dd", .5, 112, 7))
    for i in range(2):
        s.append(cloud(260 + i * 520, 140, .8 + i * .2, "#f5f9f5", .75, 600 + i, "a-drift"))
    s.append('<g class="a-glow">')
    s.append(blob(1040, 150, 58, "#f4cf7e", .75, 113, 1.0))
    s.append('</g>')
    # 远去的残烟
    for i in range(3):
        s.append('<circle class="a-fade" cx="%d" cy="%d" r="%d" fill="#c9c7be" '
                 'style="animation-delay:%.1fs"/>' % (170 + i * 40, 330 - i * 26, 20 + i * 8, i * 1.4))
    # 摊位（彩色雨棚）
    stalls = [(70, 560, "#d0796a"), (350, 540, "#7ba07b"), (630, 555, "#e0a45c")]
    for i, (x, y, c) in enumerate(stalls):
        s.append(wash(rect_pts(x, y, 210, 130), "#e2d8c2", .55, 300 + i, 4))
        s.append(ink(rect_pts(x, y, 210, 130), INK, 2.2, 310 + i, 2.4, True))
        pts = [(x - 14, y), (x + 224, y), (x + 200, y - 52), (x + 12, y - 52)]
        s.append(wash(pts, c, .62, 320 + i, 4))
        s.append(ink(pts, INK, 2.2, 330 + i, 2.2, True))
        for k in range(3):
            s.append(ink([(x + 26 + k * 62, y - 52), (x + 26 + k * 62, y)], INK, 1.8, 340 + i * 3 + k, 1.6))
        # 货物
        for k in range(4):
            s.append(blob(x + 40 + k * 44, y + 22 + (k % 2) * 26, 15,
                          ["#e07a56", "#d9b64c", "#8fae63", "#c86b7a"][k], .6, 400 + i * 5 + k, .8))
    # 人群
    skins = ["#e8cfb1", "#d9b697", "#8a5f3f", "#f0dcc2", "#c69b7b"]
    cloth = ["#6f8592", "#8a7a6e", "#7d8c93", "#a1856b", "#78887f"]
    for i in range(6):
        s.append(person(120 + i * 138, 700 + (i % 3) * 16, 62 + (i % 3) * 6, cloth[i % 5], skins[i % 5],
                        "#3a3330", 500 + i))
    # 拿到补助的那家修理铺：一栋小楼 + 挂在墙上的新招牌（轻轻晃）
    s.append(wash(rect_pts(944, 486, 250, 254), "#ddd2ba", .62, 530, 4))
    s.append(ink(rect_pts(944, 486, 250, 254), INK, 2.4, 531, 2.2, True))
    s.append(wash(rect_pts(970, 600, 76, 140), "#8d6b57", .6, 532, 3))                 # 门
    s.append('<rect x="1080" y="600" width="88" height="80" rx="4" fill="#f2cf7d" '
             'opacity=".78" class="a-twinkle"/>')                                     # 亮着的橱窗
    s.append('<g transform="translate(1069,542)"><g class="a-sign">')
    s.append(wash(rect_pts(-104, -42, 208, 84), "#6f9464", .72, 533, 3))
    s.append(ink(rect_pts(-104, -42, 208, 84), INK, 2.8, 534, 2, True))
    s.append(ink([(-70, 0), (70, 0)], "#f4eee0", 3.6, 535, 2.4, False, dash="16 12"))
    s.append('</g></g>')
    # 串灯
    for i in range(7):
        s.append('<circle class="a-twinkle" cx="%d" cy="%d" r="7" fill="#f2cf7d" '
                 'style="animation-delay:%.1fs"/>' % (120 + i * 145, 462 + (i % 2) * 22, i * .45))
    # 飞的纸飞机
    s.append('<path class="a-fly" d="M0 0 L54 22 L0 34 L14 18 Z" fill="#f4efe2" opacity=".9"/>')
    return scene_wrap("".join(s))


def scene_cover():
    """封面：左半灰霾旧工业，右半长出绿意的屋顶，中间一条路通向亮处"""
    s = ['<rect width="900" height="1200" fill="%s"/>' % PAPER]
    s.append(wash(rect_pts(-40, -40, 980, 520), "#c3d2d8", .6, 601, 8))            # 冷调天空
    s.append(wash([(-40, 360), (940, 300), (940, 820), (-40, 860)], "#f3e3ba", .5, 602, 12))  # 破晓暖带
    # 地平线光
    s.append('<g class="a-glow">')
    s.append(blob(460, 800, 170, "#f7d98f", .42, 603, .28))
    s.append(blob(460, 800, 74, "#fbeec2", .5, 604, .34))
    s.append('</g>')
    # 左侧：旧工厂 + 烟囱 + 灰霾
    s.append(wash(rect_pts(40, 560, 270, 230), "#93a0a7", .55, 605, 5))
    s.append(ink(rect_pts(40, 560, 270, 230), INK, 2.4, 606, 2.4, True))
    for i, (x, w, h) in enumerate([(96, 44, 250), (186, 38, 196)]):
        s.append(wash(rect_pts(x, 560 - h, w, h), "#8b979e", .58, 610 + i, 4))
        s.append(ink(rect_pts(x, 560 - h, w, h), INK, 2.2, 620 + i, 2.2, True))
        for k in range(3):
            s.append('<circle class="a-puff2" cx="%d" cy="%d" r="%d" fill="#c3c4bc" '
                     'style="animation-delay:%.1fs"/>' % (x + w / 2, 560 - h - 12, 12 + k * 5, i * 1.4 + k * .5))
    for i, (cx, cy, rr, delay) in enumerate([(150, 400, 130, 0), (250, 470, 110, 2.4), (330, 380, 90, 4.2)]):
        s.append('<g class="a-haze" style="animation-delay:%.1fs">' % delay)
        s.append(blob(cx, cy, rr, "#c6c6be", .42, 630 + i, .7))
        s.append('</g>')
    # 右侧：长出绿意的屋顶 + 太阳能板（用真正的坡屋顶，别做成一床被子）
    for i, (x, y, w, h) in enumerate([(556, 690, 176, 150), (734, 712, 150, 128)]):
        s.append(wash(rect_pts(x, y - h, w, h), "#cdbfa2", .58, 640 + i, 5))       # 墙
        s.append(ink(rect_pts(x, y - h, w, h), INK, 2.2, 650 + i, 2.4, True))
        for k in range(2):                                                       # 窗
            s.append('<rect x="%.1f" y="%.1f" width="34" height="40" rx="4" fill="#f2cf7d" '
                     'opacity=".62"/>' % (x + 26 + k * 68, y - h + 56))
        roof = [(x - 16, y - h), (x + 30, y - h - 58), (x + w - 30, y - h - 58), (x + w + 16, y - h)]
        s.append(wash(roof, "#6f9464", .66, 660 + i, 4))
        s.append(ink(roof, INK, 2.4, 670 + i, 2.2, True))
        sp = [(x + 34, y - h - 20), (x + 116, y - h - 44), (x + 128, y - h - 31), (x + 46, y - h - 7)]
        s.append(wash(sp, "#3f6f8c", .62, 680 + i, 3))                           # 屋面上的板
        s.append(ink(sp, "#22475c", 1.8, 690 + i, 1.6, True))
    # 那条路：先铺地平面，路才有对比、才不会读成一座沙丘
    s.append(wash([(-40, 812), (940, 806), (940, 1240), (-40, 1240)], "#a9ac86", .5, 704, 10))
    s.append(wash([(372, 806), (552, 806), (800, 1200), (104, 1200)], "#cfc4a6", .62, 700, 8))
    s.append(ink([(372, 806), (104, 1200)], "#8d7f66", 2.6, 702, 2.6))
    s.append(ink([(552, 806), (800, 1200)], "#8d7f66", 2.6, 703, 2.6))
    s.append(ink([(462, 812), (452, 1200)], "#f7f2e3", 4.2, 701, 2.4, False, dash="40 46"))
    # 树
    for i, (x, y, sc) in enumerate([(500, 1060, 1.5), (760, 1000, 1.15), (200, 1040, 1.3),
                                    (105, 930, .95), (835, 880, .85), (330, 960, .8)]):
        s.append(tree(x, y, sc, 710 + i * 4, "a-sway2", ["#6f9464", "#87a06a", "#5f8a63"][i % 3]))
    # 路上一个小小的背影
    s.append(person(452, 980, 104, "#7c8b90", "#e6cfc0", "#3a4650", 730))
    # 前景草
    for i in range(6):
        s.append(wash([(i * 160 - 30, 1210), (i * 160 + 140, 1210), (i * 160 + 55, 1120 - (i % 3) * 38)],
                      "#87a06a", .5, 740 + i, 8))
    return scene_wrap("".join(s), "0 0 900 1200")


SCENES = {
    "city": scene_city,
    "council": scene_council,
    "road": scene_road,
    "rooftop": scene_rooftop,
    "school": scene_school,
    "market": scene_market,
    "cover": scene_cover,
}

# --------------------------------------------------------------------------
# 页面
# --------------------------------------------------------------------------

CSS = """
:root{
  --paper:#f8f3e8; --paper2:#efe7d6; --ink:#2f3b42; --ink2:#6a747a;
  --gold:#b8872f; --gold2:#d9b169; --blue:#2f4858;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Songti SC","STSong",serif;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  --shadow:0 26px 60px -30px rgba(47,72,88,.45),0 1px 0 rgba(255,255,255,.7);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);
  -webkit-font-smoothing:antialiased;overflow-x:hidden}

/* ---------- 纸纹 / 水彩底 ---------- */
.grain{position:fixed;inset:0;z-index:60;pointer-events:none;opacity:.45;mix-blend-mode:multiply;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='240' height='240' filter='url(%23n)' opacity='0.4'/></svg>")}
.blobs{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.blob{position:absolute;border-radius:50%;filter:blur(70px);opacity:.28;mix-blend-mode:multiply;
  animation:drift 28s ease-in-out infinite alternate}
.b1{width:44vw;height:44vw;left:-8vw;top:4vh;background:#c9d9d2}
.b2{width:36vw;height:36vw;right:-10vw;top:30vh;background:#e8d6b8;animation-duration:34s}
.b3{width:50vw;height:50vw;left:12vw;bottom:-18vh;background:#cfd8e3;animation-duration:40s}
.b4{width:28vw;height:28vw;right:8vw;bottom:4vh;background:#e6cfc0;animation-duration:30s}
@keyframes drift{0%{transform:translate(0,0) scale(1)}50%{transform:translate(3vw,-2vh) scale(1.12)}
  100%{transform:translate(-2vw,3vh) scale(.94)}}

/* ---------- 语言条 ---------- */
.langbar{position:fixed;top:0;left:0;right:0;z-index:75;display:flex;justify-content:center;gap:.35rem;
  padding:.6rem;background:rgba(248,243,232,.86);backdrop-filter:blur(10px);
  border-bottom:1px solid rgba(47,72,88,.10)}
.langbar button{font-family:var(--sans);font-size:.76rem;letter-spacing:.1em;padding:.42rem .95rem;
  border-radius:999px;cursor:pointer;border:1px solid transparent;background:transparent;color:var(--ink2);
  transition:.22s}
.langbar button:hover{color:var(--ink);background:rgba(255,255,255,.7)}
.langbar button[aria-pressed="true"]{background:var(--blue);color:#f6f1e6;border-color:var(--blue)}
.langbar .dot{width:4px;height:4px;border-radius:50%;background:var(--gold2);align-self:center;opacity:.7}

.progress{position:fixed;top:2.6rem;left:0;right:0;height:3px;z-index:74;background:rgba(47,72,88,.06)}
.progress span{display:block;height:100%;width:0;
  background:linear-gradient(90deg,var(--blue),var(--gold2),var(--gold));
  box-shadow:0 0 10px rgba(184,135,47,.5)}

/* ---------- 封面 ---------- */
.hero{position:relative;z-index:1;min-height:100vh;display:grid;place-items:center;text-align:center;
  padding:8vh 5vw 6vh}
.hero-inner{max-width:min(1020px,94vw)}
.hero-frame{position:relative;width:min(360px,64vw);margin:0 auto 2.6rem;
  animation:floatCard 8s ease-in-out infinite alternate}
@keyframes floatCard{from{transform:translateY(0) rotate(-.6deg)}to{transform:translateY(-16px) rotate(.7deg)}}
.hero-frame .pic{width:100%;height:auto;display:block;border-radius:5px;box-shadow:var(--shadow);
  -webkit-mask-image:radial-gradient(112% 104% at 50% 46%,#000 62%,rgba(0,0,0,.5) 88%,transparent 100%);
  mask-image:radial-gradient(112% 104% at 50% 46%,#000 62%,rgba(0,0,0,.5) 88%,transparent 100%)}
.kicker{font-size:.74rem;letter-spacing:.44em;text-transform:uppercase;color:var(--gold);
  margin-bottom:1.1rem;font-weight:600}
h1{font-family:var(--serif);font-weight:500;line-height:1.12;font-size:clamp(1.9rem,5.8vw,3.7rem)}
h1 .w{display:inline-block;opacity:0;transform:translateY(20px) rotate(-2deg);filter:blur(6px);
  animation:inkin 1s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes inkin{to{opacity:1;transform:none;filter:blur(0)}}
.t-zh{font-family:var(--sans);font-weight:400;letter-spacing:.16em}
h1 .t-zh{display:block;font-size:.42em;color:var(--ink2);margin-top:.7rem}
.rule{width:64px;height:1px;background:var(--gold);margin:1.8rem auto;opacity:.55}
.sub{color:var(--ink2);font-size:clamp(.88rem,1.5vw,1.02rem);letter-spacing:.05em}
.scroll-hint{margin-top:2.8rem;font-size:.74rem;letter-spacing:.3em;color:var(--ink2);
  animation:bob 2.6s ease-in-out infinite}
.scroll-hint::after{content:"";display:block;width:1px;height:34px;margin:10px auto 0;
  background:linear-gradient(var(--gold),transparent)}
@keyframes bob{0%,100%{transform:translateY(0);opacity:.65}50%{transform:translateY(7px);opacity:1}}

/* ---------- 章节 ---------- */
main{position:relative;z-index:1}
.spread{display:grid;grid-template-columns:1.02fr .98fr;align-items:center;
  gap:clamp(2rem,4.6vw,5rem);max-width:1220px;margin:0 auto;
  padding:clamp(4.5rem,10vh,8rem) clamp(1.3rem,4.5vw,3.5rem)}
.spread:nth-of-type(even){grid-template-columns:.98fr 1.02fr}
.spread:nth-of-type(even) .art{order:2}

.art{position:relative;will-change:transform}
.art-frame{position:relative;overflow:hidden;border-radius:5px;box-shadow:var(--shadow);
  background:var(--paper2);opacity:0;transform:translateY(26px) scale(.985);
  transition:opacity 1.1s ease,transform 1.1s cubic-bezier(.2,.7,.2,1)}
.spread.in .art-frame{opacity:1;transform:none}
.art-frame .pic{display:block;width:100%;height:auto}
.art-cap{position:absolute;left:0;bottom:-2.1rem;font-family:var(--serif);font-style:italic;
  color:var(--ink2);font-size:.84rem;letter-spacing:.03em;opacity:.85}
.art-num{position:absolute;right:.7rem;top:.7rem;z-index:3;font-family:var(--serif);
  color:#fff;background:rgba(47,72,88,.55);border-radius:999px;padding:.15rem .68rem;
  font-size:.78rem;letter-spacing:.16em;backdrop-filter:blur(4px)}

.copy{max-width:36rem}
.num{display:inline-flex;align-items:center;justify-content:center;font-family:var(--serif);
  font-size:.95rem;letter-spacing:.18em;color:var(--gold);border:1px solid rgba(184,135,47,.42);
  border-radius:50%;width:2.4rem;height:2.4rem;margin-bottom:1.5rem}
.copy .ln{font-family:var(--serif);line-height:1.72;letter-spacing:.012em;
  font-size:clamp(1rem,1.45vw,1.2rem);margin-bottom:.15rem;
  opacity:0;transform:translateY(14px);filter:blur(4px);
  transition:opacity .85s cubic-bezier(.2,.7,.2,1),transform .85s cubic-bezier(.2,.7,.2,1),filter .85s}
.spread.in .copy .ln{opacity:1;transform:none;filter:blur(0)}
.spread.in .copy .ln:nth-child(2){transition-delay:.08s}
.spread.in .copy .ln:nth-child(3){transition-delay:.16s}
.spread.in .copy .ln:nth-child(4){transition-delay:.24s}
.spread.in .copy .ln:nth-child(5){transition-delay:.32s}
.spread.in .copy .ln:nth-child(6){transition-delay:.40s}
.spread.in .copy .ln:nth-child(7){transition-delay:.48s}
.spread.in .copy .ln:nth-child(8){transition-delay:.56s}
.copy .zh{display:none;font-family:var(--sans);font-size:.78em;line-height:1.7;color:var(--ink2);
  letter-spacing:.04em;font-weight:300}
.copy .en{display:block}

/* 双语：英文在上，中文小字在下 */
body[data-lang="bi"] .copy .zh{display:block;margin-bottom:.55em}
body[data-lang="bi"] .copy .ln{margin-bottom:.5rem}
body[data-lang="zh"] .copy .en{display:none}
body[data-lang="zh"] .copy .zh{display:block;margin-bottom:.5rem}
body[data-lang="zh"] .copy .ln{font-family:var(--sans);font-size:clamp(.98rem,1.4vw,1.14rem);
  line-height:2;letter-spacing:.06em}
body[data-lang="en"] .copy .zh{display:none}
body[data-lang="en"] .u-en{display:inline}
body[data-lang="en"] .u-zh{display:none}
body[data-lang="zh"] .u-en{display:none}
body[data-lang="zh"] .u-zh{display:inline}
body[data-lang="bi"] .u-en{display:inline}
body[data-lang="bi"] .u-zh{display:inline;opacity:.55;margin-left:.4em;font-size:.8em}
body[data-lang="zh"] h1 .t-en{display:none}
body[data-lang="zh"] h1 .t-zh{display:block;font-size:1em;font-weight:500;letter-spacing:.1em;margin-top:0}
body[data-lang="en"] h1 .t-zh{display:none}
body[data-lang="bi"] h1 .t-zh{display:block}
body[data-lang="en"] .cap-zh{display:none}
body[data-lang="zh"] .cap-en{display:none}
body[data-lang="bi"] .cap-zh{display:inline;opacity:.7;margin-left:.5em;font-family:var(--sans);font-size:.9em}

/* ---------- 高亮词 ---------- */
.word{position:relative;background:linear-gradient(180deg,transparent 58%,rgba(217,177,105,.42) 58%);
  padding:0 .06em;border-radius:2px;cursor:help;transition:background .4s}
.word.lit{background:linear-gradient(180deg,transparent 52%,rgba(184,135,47,.75) 52%);color:#3a2a06}
.word:hover{background:linear-gradient(180deg,transparent 52%,rgba(184,135,47,.6) 52%)}
body.no-hl .word{background:none;padding:0}

/* ---------- 尾声 ---------- */
.finale{position:relative;z-index:1;text-align:center;max-width:1080px;margin:0 auto;
  padding:clamp(3.5rem,8vh,6rem) clamp(1.3rem,4vw,3rem) 5rem}
.finale h2{font-family:var(--serif);font-weight:500;letter-spacing:.2em;text-transform:uppercase;
  font-size:.8rem;color:var(--gold);margin-bottom:2.4rem}
.cloud{display:flex;flex-wrap:wrap;gap:.6rem;justify-content:center}
.cloud b{font-family:var(--serif);font-weight:400;font-size:.94rem;padding:.4rem .8rem;border-radius:999px;
  background:rgba(255,255,255,.6);border:1px solid rgba(47,72,88,.12);color:var(--blue);
  opacity:0;transform:translateY(10px) scale(.96);
  animation:pop .7s cubic-bezier(.2,.7,.2,1) forwards;cursor:default}
.cloud b:hover{background:var(--gold2);color:#3a2a06;border-color:transparent}
@keyframes pop{to{opacity:1;transform:none}}
footer{position:relative;z-index:1;text-align:center;padding:2.5rem 1.5rem 3.5rem;color:var(--ink2);
  font-size:.76rem;letter-spacing:.14em}

.tools{position:fixed;right:1rem;bottom:1rem;z-index:80;display:flex;gap:.45rem}
.tools button{font-family:var(--sans);font-size:.74rem;letter-spacing:.06em;padding:.48rem .82rem;
  border-radius:999px;cursor:pointer;background:rgba(255,255,255,.85);
  border:1px solid rgba(47,72,88,.16);color:var(--blue);backdrop-filter:blur(8px);
  box-shadow:0 8px 20px -12px rgba(47,72,88,.6);transition:.2s}
.tools button:hover{transform:translateY(-2px);background:#fff}

/* ---------- SVG 内的动画 ---------- */
.pic .wsh{mix-blend-mode:multiply}
.a-drift{animation:driftX 34s linear infinite;transform-box:fill-box}
.a-drift2{animation:driftX 46s linear infinite reverse;transform-box:fill-box}
@keyframes driftX{from{transform:translateX(-90px)}to{transform:translateX(90px)}}
.a-haze{animation:haze 12s ease-in-out infinite alternate;transform-box:fill-box}
@keyframes haze{from{transform:translate(-18px,6px) scale(1)}to{transform:translate(22px,-8px) scale(1.08)}}
.a-puff{animation:puff 3.4s ease-out infinite;opacity:0;transform-box:fill-box}
.a-puff2{animation:puff2 4.2s ease-out infinite;opacity:0;transform-box:fill-box}
@keyframes puff{0%{opacity:.7;transform:translate(0,0) scale(.5)}
  100%{opacity:0;transform:translate(-46px,-52px) scale(2.1)}}
@keyframes puff2{0%{opacity:.6;transform:translate(0,0) scale(.6)}
  100%{opacity:0;transform:translate(-16px,-96px) scale(2.4)}}
.a-fade{animation:fade 6s ease-out infinite;opacity:0;transform-box:fill-box}
@keyframes fade{0%{opacity:.55;transform:translate(0,0) scale(.8)}
  100%{opacity:0;transform:translate(-70px,-58px) scale(1.9)}}
.a-sway{animation:sway 5.5s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:50% 92%}
.a-sway2{animation:sway 7s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:50% 92%}
@keyframes sway{from{transform:rotate(-2.2deg)}to{transform:rotate(2.2deg)}}
.a-twinkle{animation:twinkle 3.4s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.45}50%{opacity:.95}}
.a-flicker{animation:flicker 7s ease-in-out infinite alternate}
@keyframes flicker{from{opacity:.14}to{opacity:.32}}
.a-mote{animation:mote 9s linear infinite;opacity:0}
@keyframes mote{0%{opacity:0;transform:translate(0,0)}
  20%{opacity:.9}100%{opacity:0;transform:translate(36px,-120px)}}
.a-leaf{animation:leaf 11s ease-in-out infinite;opacity:0}
@keyframes leaf{0%{opacity:0;transform:translate(0,0) rotate(0)}
  25%{opacity:.85}100%{opacity:0;transform:translate(80px,-90px) rotate(220deg)}}
.a-drip{animation:drip 2.6s ease-in infinite}
@keyframes drip{0%{opacity:0;transform:translateY(0)}
  25%{opacity:.9}70%{opacity:.5}100%{opacity:0;transform:translateY(46px)}}
.a-crawl{animation:crawl 15s linear infinite;transform-box:fill-box}
.a-crawl2{animation:crawl 19s linear infinite reverse;transform-box:fill-box}
.a-crawl3{animation:crawl 23s linear infinite;transform-box:fill-box}
@keyframes crawl{from{transform:translateX(-160px)}to{transform:translateX(1240px)}}
.a-bus{animation:busdrive 16s linear infinite;transform-box:fill-box}
@keyframes busdrive{from{transform:translateX(-260px)}to{transform:translateX(1180px)}}
.a-bob{animation:bobY 4.6s ease-in-out infinite alternate;transform-box:fill-box}
.a-bobY{animation:bobY 5.2s ease-in-out infinite alternate}
@keyframes bobY{from{transform:translateY(-5px) rotate(-4deg)}to{transform:translateY(5px) rotate(4deg)}}
.a-glow{animation:glow 6s ease-in-out infinite alternate;transform-box:fill-box}
@keyframes glow{from{opacity:.8;transform:scale(.97)}to{opacity:1;transform:scale(1.05)}}
.a-ray{animation:ray 5s ease-in-out infinite alternate}
@keyframes ray{from{opacity:.2}to{opacity:.6}}
.a-bubble{animation:bubble 3.6s ease-out infinite;transform-box:fill-box;transform-origin:50% 100%}
@keyframes bubble{0%{opacity:0;transform:scale(.4) translateY(10px)}
  18%{opacity:1;transform:scale(1) translateY(0)}
  72%{opacity:1;transform:scale(1) translateY(0)}
  100%{opacity:0;transform:scale(1.04) translateY(-14px)}}
/* 秒针：原点必须用 view-box 坐标显式给（竖线 bbox 宽为 0，fill-box 会转飞） */
.a-tick{animation:tick 60s steps(60) infinite;transform-box:view-box;
  transform-origin:var(--ox,0px) var(--oy,0px)}
@keyframes tick{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.a-sign{animation:sway 6.5s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:50% 0%}
.a-tilt{animation:sway 8s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:50% 100%}
.a-fly{animation:fly 13s cubic-bezier(.4,.1,.5,.9) infinite;opacity:0}
@keyframes fly{0%{opacity:0;transform:translate(-120px,420px) rotate(-12deg)}
  12%{opacity:.95}
  85%{opacity:.9}
  100%{opacity:0;transform:translate(1180px,180px) rotate(14deg)}}

@media (prefers-reduced-motion:reduce){
  *{animation:none!important;transition:none!important}
  .copy .ln,.art-frame,h1 .w,.cloud b{opacity:1!important;transform:none!important;filter:none!important}
}

/* ---------- 响应式 ---------- */
@media (max-width:980px){
  .spread,.spread:nth-of-type(even){grid-template-columns:1fr;gap:2.2rem}
  .spread:nth-of-type(even) .art{order:0}
  .art-cap{bottom:-1.6rem}
  .copy{max-width:none}
}
@media (max-width:560px){
  .hero{padding:7rem 1.2rem 4rem}
  .hero-frame{width:min(280px,72vw)}
  .spread{padding:3.2rem 1.2rem}
  .copy .ln{font-size:1rem;line-height:1.7}
  .copy .zh{font-size:.74em}
  .langbar{gap:.1rem;padding:.5rem .3rem}
  .langbar button{padding:.4rem .62rem;font-size:.72rem}
  .tools button{padding:.42rem .66rem}
}
"""

JS = """
(function(){
  var WORDS = __WORDS__;
  var MEAN = __MEAN__;

  function esc(s){return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');}
  function forms(w){
    var o={}, stem=w.replace(/e$/,'');
    [w,w+'s',w+'es',w+'ed',w+'d',stem+'ing',stem+'ies',stem+'ied',w+'ied'].forEach(function(f){o[f]=1;});
    return Object.keys(o).sort(function(a,b){return b.length-a.length;});
  }
  var re = new RegExp('\\\\b(' + WORDS.map(forms).map(function(fs){return fs.map(esc).join('|');}).join('|') + ')\\\\b','gi');
  document.querySelectorAll('.copy .en').forEach(function(p){
    p.innerHTML = p.textContent.replace(re, function(m){
      var k=m.toLowerCase(), tip=MEAN[k]||'';
      return tip ? '<span class="word" tabindex="0" data-t="'+tip.replace(/"/g,'&quot;')+'">'+m+'</span>' : m;
    });
  });

  var t=document.getElementById('title'), title=__TITLE__;
  title.split(' ').forEach(function(w,i){
    var s=document.createElement('span'); s.className='w'; s.textContent=w;
    s.style.animationDelay=(0.3+i*0.1)+'s'; t.appendChild(s);
    if(i<title.split(' ').length-1) t.appendChild(document.createTextNode(' '));
  });

  var cloud=document.getElementById('cloud');
  WORDS.forEach(function(w,i){
    var b=document.createElement('b'); b.textContent=w;
    b.style.animationDelay=(i*0.03)+'s';
    if(MEAN[w]) b.title=MEAN[w];
    cloud.appendChild(b);
  });

  /* 分段揭示 + 金色词依次点亮 */
  var spreads=[].slice.call(document.querySelectorAll('.spread'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting) e.target.classList.add('in'); });
    },{threshold:.2});
    spreads.forEach(function(s){io.observe(s);});
    var io2=new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(e.isIntersecting && !e.target.dataset.lit){
          e.target.dataset.lit='1';
          e.target.querySelectorAll('.word').forEach(function(w,i){
            setTimeout(function(){w.classList.add('lit');setTimeout(function(){w.classList.remove('lit');},850);},i*50);
          });
        }
      });
    },{threshold:.42});
    spreads.forEach(function(s){io2.observe(s);});
  } else { spreads.forEach(function(s){s.classList.add('in');}); }

  /* 视差 + 进度条 */
  var bar=document.getElementById('bar'), arts=[].slice.call(document.querySelectorAll('.art')), tick=false;
  function loop(){
    var h=document.documentElement.scrollHeight-window.innerHeight, y=window.scrollY;
    bar.style.width=(h>0?Math.min(100,(y/h)*100):0)+'%';
    arts.forEach(function(a){
      var r=a.getBoundingClientRect();
      if(r.bottom>-240 && r.top<window.innerHeight+240){
        var p=(r.top+r.height/2-window.innerHeight/2)/window.innerHeight;
        a.style.transform='translateY('+(-p*22).toFixed(1)+'px)';
      }
    });
    tick=false;
  }
  window.addEventListener('scroll',function(){ if(!tick){tick=true;requestAnimationFrame(loop);} },{passive:true});
  loop();

  /* 语言切换：#en / #zh / #bi 可以直接分享，优先于上次选择 */
  var KEY='doodle-book-lang';
  function setLang(l){
    document.body.setAttribute('data-lang',l);
    document.querySelectorAll('.langbar button').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.dataset.lang===l));
    });
    try{ localStorage.setItem(KEY,l); }catch(e){}
  }
  document.querySelectorAll('.langbar button').forEach(function(b){
    b.addEventListener('click',function(){ setLang(b.dataset.lang); });
  });
  var hash=(location.hash||'').replace('#','').toLowerCase();
  var saved=null;
  try{ saved=localStorage.getItem(KEY); }catch(e){}
  setLang(['en','zh','bi'].indexOf(hash)>=0 ? hash : (saved || 'bi'));

  document.getElementById('hl').addEventListener('click',function(){
    var off=document.body.classList.toggle('no-hl');
    this.querySelector('.u-en').textContent=off?'Word highlight: off':'Word highlight: on';
    this.querySelector('.u-zh').textContent=off?'词高亮：关':'词高亮：开';
  });
  document.getElementById('top').addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
})();
"""

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def build_html(data, stanzas, words, meanings, out_dir=None):
    spreads = []
    for i, st in enumerate(stanzas):
        scene = SCENES.get(st.get("scene", "city"), SCENES["city"])
        cap_en = st.get("caption_en", "")
        cap_zh = st.get("caption_zh", "")
        num = ROMAN[i] if i < len(ROMAN) else str(i + 1)
        lines = []
        for ln in st.get("lines", []):
            en = html.escape(ln.get("en", ""))
            zh = html.escape(ln.get("zh", "")) if ln.get("zh") else ""
            lines.append('<p class="ln"><span class="en">%s</span>%s</p>'
                         % (en, '<span class="zh">%s</span>' % zh if zh else ""))
        spreads.append(
            '  <section class="spread">\n'
            '    <div class="art"><div class="art-frame">%s<span class="art-num">%s</span></div>\n'
            '      <div class="art-cap"><span class="cap-en">%s · %s</span>'
            '<span class="cap-zh">%s · %s</span></div></div>\n'
            '    <div class="copy"><span class="num">%s</span>\n      %s\n    </div>\n'
            '  </section>\n'
            % (scene(), num, num, html.escape(cap_en), num, html.escape(cap_zh), num, "\n      ".join(lines))
        )

    js = JS.replace("__WORDS__", json.dumps(words, ensure_ascii=False)) \
           .replace("__MEAN__", json.dumps(meanings, ensure_ascii=False)) \
           .replace("__TITLE__", json.dumps(data.get("title", ""), ensure_ascii=False))

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s · 水彩涂鸦绘本</title>
<style>%(css)s</style>
</head>
<body data-lang="bi">

<div class="langbar">
  <button data-lang="en">English</button><span class="dot"></span>
  <button data-lang="zh">中文</button><span class="dot"></span>
  <button data-lang="bi">双语</button>
</div>
<div class="progress"><span id="bar"></span></div>
<div class="blobs"><div class="blob b1"></div><div class="blob b2"></div>
  <div class="blob b3"></div><div class="blob b4"></div></div>
<div class="grain"></div>

<header class="hero">
  <div class="hero-inner">
    <div class="hero-frame">%(cover)s</div>
    <p class="kicker">丫丫雅思单词 · %(date)s</p>
    <h1><span class="t-en" id="title"></span><span class="t-zh">%(title_zh)s</span></h1>
    <div class="rule"></div>
    <p class="sub"><span class="u-en">%(sub)s</span><span class="u-zh">%(sub_zh)s</span></p>
    <p class="scroll-hint"><span class="u-en">scroll</span><span class="u-zh">向下滚动</span></p>
  </div>
</header>

<main>
%(spreads)s
  <section class="finale">
    <h2><span class="u-en">the %(n)d words · all of them are up there</span><span class="u-zh">今日的 %(n)d 个词 · 都在上面了</span></h2>
    <div class="cloud" id="cloud"></div>
  </section>
</main>

<footer><span class="u-en">watercolour doodle book · yaya ielts words · %(date)s</span><span class="u-zh">水彩涂鸦绘本 · 丫丫雅思单词 · %(date)s</span></footer>

<div class="tools">
  <button id="hl"><span class="u-en">word highlight: on</span><span class="u-zh">词高亮：开</span></button>
  <button id="top"><span class="u-en">back to cover</span><span class="u-zh">回到封面</span></button>
</div>

<script>%(js)s</script>
</body>
</html>
""" % {
        "title": html.escape(data.get("title", "")),
        "title_zh": html.escape(data.get("title_zh", "")),
        "date": html.escape(data.get("date", "")),
        "sub": html.escape(data.get("subtitle", "")),
        "sub_zh": html.escape(data.get("subtitle_zh", "")),
        "cover": SCENES["cover"](),
        "spreads": "\n".join(spreads),
        "css": CSS,
        "js": js,
        "n": len(words),
    }


def main():
    ap = argparse.ArgumentParser(description="把手写 SVG 水彩涂鸦做成三语动态 HTML 绘本")
    ap.add_argument("--json", required=True, help="带 stanzas/lines(en,zh) 的双语 JSON（也兼容 story/poem 行数组）")
    ap.add_argument("--vocab", help="`ielts.py poem --json` 的输出，用来给词挂中文提示")
    ap.add_argument("--out", default="./index.html")
    ap.add_argument("--scenes", help="覆盖场景顺序，逗号分隔")
    ap.add_argument("--json-out", action="store_true")
    a = ap.parse_args()

    with open(a.json, encoding="utf-8") as f:
        data = json.load(f)

    words = data.get("words") or []
    meanings = {}
    if a.vocab:
        with open(a.vocab, encoding="utf-8") as f:
            vocab = json.load(f)
        for w in vocab.get("words", []):
            meanings[w["word"].lower()] = w.get("meaning", "")

    stanzas = data.get("stanzas")
    if not stanzas:  # 兼容纯文本行数组：story（童话）/ tale / 旧的 poem，自动切段
        stanzas, cur = [], []
        for ln in (data.get("story") or data.get("tale") or data.get("poem") or []):
            if ln.strip() == "":
                if cur:
                    stanzas.append({"scene": "city", "lines": [{"en": x, "zh": ""} for x in cur]})
                cur = []
            else:
                cur.append(ln)
        if cur:
            stanzas.append({"scene": "city", "lines": [{"en": x, "zh": ""} for x in cur]})

    order = [s.strip() for s in (a.scenes or "").split(",") if s.strip()]
    if order:
        for i, s in enumerate(stanzas):
            s["scene"] = order[i % len(order)]
    for i, s in enumerate(stanzas):
        if not s.get("scene"):
            fallback = ["city", "council", "road", "rooftop", "school", "market"]
            s["scene"] = fallback[i % len(fallback)]

    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    html_text = build_html(data, stanzas, words, meanings)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_text)

    res = {"html": out, "stanzas": len(stanzas), "words": len(words),
           "size_kb": round(len(html_text.encode("utf-8")) / 1024, 1)}
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json_out
          else "🎨 水彩涂鸦绘本：%s\n   %d 段 · %d 词 · %.1f KB" % (out, res["stanzas"], res["words"], res["size_kb"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
