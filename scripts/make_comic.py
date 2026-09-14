#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_comic.py — 把当天的英文散文诗做成一张「哆啦 A 梦风格卡通连环画」。

跟 make_poem_poster.py 吃同一份 JSON（title / date / subtitle / poem / words），
不用另写一遍：poem 里的空行会把诗切成若干段，一段 = 连环画的一格。

  python3 make_comic.py --json /tmp/poem.json
  python3 make_comic.py --json /tmp/poem.json --scenes city,council,policy,build,school,sky
  python3 make_comic.py --json /tmp/poem.json --no-png      # 只要 HTML

想自己指定哪一格画什么，在 JSON 里给 panels：
  "panels": [{"scene": "city", "lines": ["...", "..."]}, ...]

内置场景（viewBox 0 0 1200 400）：
  city / council / policy / build / school / sky / cover

产物：
  <数据目录>/poems/comic-YYYY-MM-DD.html
  <数据目录>/poems/comic-YYYY-MM-DD.png   （用本机 Chrome 无头渲染，两趟：量高 → 截屏）

版面：宽 1200 逻辑像素；每格「上图下文」，是标准小人书版式。
改样式改这里的 CSS 和 SCENES 里的 SVG，改完用 /tmp 的样例 JSON 渲一张亲眼看一遍。
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

W = 1200          # 逻辑宽度
ART_H = 400       # 每格插画高度
PAD = 44
FS_LINE = 25      # 诗行字号
LH_LINE = 1.72

BLUE = "#2196d8"
INK = "#1f2328"
PAPER = "#fffdf6"


# ---------------------------------------------------------------- 角色：机器猫
def dora(x, y, s=1.0, flip=False, mood="happy", gadget=None):
    """一只手绘风的蓝色机器猫。局部坐标以双脚之间的地面为原点，向上为负。"""
    sx = -s if flip else s
    o = ['<g transform="translate(%g,%g) scale(%g,%g)">' % (x, y, sx, s)]
    o.append('<ellipse cx="0" cy="64" rx="62" ry="12" fill="rgba(0,0,0,.13)"/>')
    # 脚
    o.append('<ellipse cx="-21" cy="58" rx="23" ry="12" fill="#fff" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<ellipse cx="21" cy="58" rx="23" ry="12" fill="#fff" stroke="%s" stroke-width="3"/>' % INK)
    # 手臂
    o.append('<rect x="-64" y="0" width="27" height="48" rx="13.5" fill="%s" stroke="%s" stroke-width="3"/>' % (BLUE, INK))
    o.append('<rect x="37" y="0" width="27" height="48" rx="13.5" fill="%s" stroke="%s" stroke-width="3"/>' % (BLUE, INK))
    o.append('<circle cx="-51" cy="50" r="13" fill="#fff" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<circle cx="51" cy="50" r="13" fill="#fff" stroke="%s" stroke-width="3"/>' % INK)
    # 身体 + 肚皮 + 口袋
    o.append('<path d="M -36 2 Q -42 58 0 62 Q 42 58 36 2 Z" fill="%s" stroke="%s" stroke-width="3"/>' % (BLUE, INK))
    o.append('<ellipse cx="0" cy="32" rx="28" ry="26" fill="#fff" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<path d="M -17 30 A 17 17 0 0 0 17 30 Z" fill="#fff" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<line x1="-17" y1="30" x2="17" y2="30" stroke="%s" stroke-width="2.6"/>' % INK)
    # 项圈 + 铃铛
    o.append('<rect x="-31" y="-2" width="62" height="14" rx="7" fill="#e23b3b" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<circle cx="0" cy="15" r="11" fill="#f5c518" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<line x1="-8.5" y1="15" x2="8.5" y2="15" stroke="%s" stroke-width="2"/>' % INK)
    o.append('<circle cx="0" cy="20" r="2.8" fill="%s"/>' % INK)
    # 头
    o.append('<circle cx="0" cy="-54" r="55" fill="%s" stroke="%s" stroke-width="3"/>' % (BLUE, INK))
    o.append('<circle cx="0" cy="-44" r="46" fill="#fff" stroke="%s" stroke-width="2.6"/>' % INK)
    # 眼睛
    for ex in (-19, 19):
        o.append('<ellipse cx="%g" cy="-66" rx="10" ry="12.5" fill="#fff" stroke="%s" stroke-width="2.6"/>' % (ex, INK))
        o.append('<circle cx="%g" cy="-64" r="5" fill="%s"/>' % (ex + 1, INK))
    # 鼻子 + 嘴
    o.append('<circle cx="0" cy="-48" r="7" fill="#e23b3b" stroke="%s" stroke-width="2.4"/>' % INK)
    if mood == "worry":
        o.append('<path d="M -15 -26 Q 0 -36 15 -26" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round"/>' % INK)
        o.append('<path d="M 34 -84 q 9 12 0 16 q -9 -4 0 -16 Z" fill="#8fd3f4" stroke="%s" stroke-width="2"/>' % INK)
    elif mood == "teach":
        o.append('<ellipse cx="0" cy="-28" rx="10" ry="8" fill="#c0392b" stroke="%s" stroke-width="2.4"/>' % INK)
        o.append('<path d="M -14 -30 Q 0 -22 14 -30" fill="none" stroke="%s" stroke-width="2.4"/>' % INK)
    else:
        o.append('<path d="M -17 -30 Q 0 -18 17 -30" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round"/>' % INK)
    # 胡须
    for i, dy in enumerate((-58, -46, -34)):
        o.append('<line x1="-22" y1="%g" x2="-46" y2="%g" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'
                 % (dy, dy - 4 + i * 4, INK))
        o.append('<line x1="22" y1="%g" x2="46" y2="%g" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'
                 % (dy, dy - 4 + i * 4, INK))
    if gadget == "copter":
        o.append('<line x1="0" y1="-108" x2="0" y2="-134" stroke="%s" stroke-width="4"/>' % INK)
        o.append('<ellipse cx="0" cy="-136" rx="30" ry="6" fill="#f5c518" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append("</g>")
    return "".join(o)


def kid(x, y, s=1.0, hair="#4a3728", shirt="#f4a261", flip=False):
    sx = -s if flip else s
    o = ['<g transform="translate(%g,%g) scale(%g,%g)">' % (x, y, sx, s)]
    o.append('<ellipse cx="0" cy="62" rx="40" ry="9" fill="rgba(0,0,0,.12)"/>')
    o.append('<path d="M -24 4 Q -28 58 0 60 Q 28 58 24 4 Z" fill="%s" stroke="%s" stroke-width="3"/>' % (shirt, INK))
    o.append('<rect x="-40" y="8" width="17" height="42" rx="8.5" fill="%s" stroke="%s" stroke-width="3"/>' % (shirt, INK))
    o.append('<rect x="23" y="8" width="17" height="42" rx="8.5" fill="%s" stroke="%s" stroke-width="3"/>' % (shirt, INK))
    o.append('<circle cx="-31" cy="52" r="9" fill="#f6d3b3" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<circle cx="31" cy="52" r="9" fill="#f6d3b3" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<circle cx="0" cy="-24" r="30" fill="#f6d3b3" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<path d="M -30 -30 Q 0 -58 30 -30 Q 24 -46 0 -48 Q -24 -46 -30 -30 Z" fill="%s" stroke="%s" stroke-width="2"/>' % (hair, INK))
    o.append('<circle cx="-11" cy="-22" r="3.6" fill="%s"/>' % INK)
    o.append('<circle cx="11" cy="-22" r="3.6" fill="%s"/>' % INK)
    o.append('<path d="M -7 -10 Q 0 -4 7 -10" fill="none" stroke="%s" stroke-width="2.6" stroke-linecap="round"/>' % INK)
    o.append("</g>")
    return "".join(o)


def adult(x, y, s=1.0, suit="#5b6b7c", flip=False, glasses=False, tie="#c0392b"):
    sx = -s if flip else s
    o = ['<g transform="translate(%g,%g) scale(%g,%g)">' % (x, y, sx, s)]
    o.append('<ellipse cx="0" cy="66" rx="46" ry="10" fill="rgba(0,0,0,.12)"/>')
    o.append('<path d="M -30 8 Q -34 62 0 64 Q 34 62 30 8 Z" fill="%s" stroke="%s" stroke-width="3"/>' % (suit, INK))
    o.append('<path d="M 0 8 L -9 34 L 0 60 L 9 34 Z" fill="#fff" stroke="%s" stroke-width="2"/>' % INK)
    o.append('<path d="M 0 14 L -6 22 L 0 34 L 6 22 Z" fill="%s"/>' % tie)
    o.append('<rect x="-48" y="12" width="19" height="46" rx="9.5" fill="%s" stroke="%s" stroke-width="3"/>' % (suit, INK))
    o.append('<rect x="29" y="12" width="19" height="46" rx="9.5" fill="%s" stroke="%s" stroke-width="3"/>' % (suit, INK))
    o.append('<circle cx="-38" cy="60" r="10" fill="#f6d3b3" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<circle cx="38" cy="60" r="10" fill="#f6d3b3" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<circle cx="0" cy="-22" r="30" fill="#f6d3b3" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<path d="M -30 -28 Q -8 -52 12 -46 Q 30 -40 30 -28 Q 18 -34 0 -32 Q -18 -32 -30 -28 Z" fill="%s" stroke="%s" stroke-width="2"/>' % ("#3a3a3a", INK))
    if glasses:
        o.append('<circle cx="-11" cy="-20" r="8.5" fill="#eaf4fb" stroke="%s" stroke-width="2.4"/>' % INK)
        o.append('<circle cx="11" cy="-20" r="8.5" fill="#eaf4fb" stroke="%s" stroke-width="2.4"/>' % INK)
        o.append('<line x1="-2.5" y1="-20" x2="2.5" y2="-20" stroke="%s" stroke-width="2.4"/>' % INK)
    else:
        o.append('<circle cx="-11" cy="-22" r="3.4" fill="%s"/>' % INK)
        o.append('<circle cx="11" cy="-22" r="3.4" fill="%s"/>' % INK)
    o.append('<path d="M -8 -8 Q 0 -3 8 -8" fill="none" stroke="%s" stroke-width="2.6" stroke-linecap="round"/>' % INK)
    o.append("</g>")
    return "".join(o)


def bubble(x, y, w, h, text, tail="left", fill="#fff", size=22, color=INK):
    o = ['<g>']
    if tail == "left":
        o.append('<path d="M %g %g L %g %g L %g %g Z" fill="%s" stroke="%s" stroke-width="3"/>'
                 % (x + 18, y + h, x - 10, y + h + 26, x + 46, y + h, fill, INK))
    else:
        o.append('<path d="M %g %g L %g %g L %g %g Z" fill="%s" stroke="%s" stroke-width="3"/>'
                 % (x + w - 18, y + h, x + w + 10, y + h + 26, x + w - 46, y + h, fill, INK))
    o.append('<rect x="%g" y="%g" width="%g" height="%g" rx="18" fill="%s" stroke="%s" stroke-width="3"/>' % (x, y, w, h, fill, INK))
    o.append('<text x="%g" y="%g" text-anchor="middle" font-family="-apple-system,PingFang SC,Helvetica,sans-serif" '
             'font-size="%g" font-weight="700" fill="%s">%s</text>' % (x + w / 2, y + h / 2 + size * 0.36, size, color, html.escape(text)))
    o.append("</g>")
    return "".join(o)


def skybg(c1, c2):
    return ('<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>'
            '<rect x="0" y="0" width="1200" height="400" fill="url(#sky)"/>' % (c1, c2))


# ---------------------------------------------------------------- 场景
def scene_city():
    o = [skybg("#cfe4f2", "#f0e6d2")]
    o.append('<circle cx="1040" cy="86" r="46" fill="#ffe08a" opacity=".85"/>')
    for i, (bx, bw, bh, col) in enumerate([
            (40, 120, 210, "#b9c6d6"), (175, 96, 168, "#a9b8cb"), (285, 132, 246, "#c2cddb"),
            (430, 108, 190, "#a9b8cb"), (552, 140, 232, "#b9c6d6"), (706, 104, 176, "#c2cddb"),
            (824, 128, 214, "#a9b8cb"), (966, 112, 186, "#b9c6d6")]):
        o.append('<rect x="%g" y="%g" width="%g" height="%g" rx="4" fill="%s"/>' % (bx, 300 - bh, bw, bh, col))
        for r in range(2, int(bh // 34)):
            for c in range(1, int(bw // 30)):
                o.append('<rect x="%g" y="%g" width="13" height="16" rx="2" fill="#e9f1f8" opacity=".7"/>'
                         % (bx + c * 30 - 14, 300 - bh + r * 34))
    o.append('<rect x="0" y="300" width="1200" height="100" fill="#8d94a3"/>')
    o.append('<rect x="0" y="300" width="1200" height="8" fill="#767d8c"/>')
    for x in range(20, 1200, 96):
        o.append('<rect x="%g" y="348" width="54" height="7" rx="3.5" fill="#f4f1e6"/>' % x)
    # 车 + 尾气
    for cx, col, dy in ((150, "#e05a4f", 0), (470, "#4a90d9", 26), (900, "#f0a83c", 12)):
        y = 306 + dy
        o.append('<g><rect x="%g" y="%g" width="132" height="40" rx="14" fill="%s" stroke="%s" stroke-width="3"/>'
                 % (cx, y, col, INK))
        o.append('<path d="M %g %g L %g %g L %g %g L %g %g Z" fill="#dff0fb" stroke="%s" stroke-width="3"/>'
                 % (cx + 26, y + 2, cx + 46, y - 24, cx + 92, y - 24, cx + 110, y + 2, INK))
        o.append('<circle cx="%g" cy="%g" r="12" fill="#2f3540" stroke="%s" stroke-width="3"/>' % (cx + 34, y + 42, INK))
        o.append('<circle cx="%g" cy="%g" r="12" fill="#2f3540" stroke="%s" stroke-width="3"/>' % (cx + 100, y + 42, INK))
        for k in range(3):
            o.append('<circle cx="%g" cy="%g" r="%g" fill="#8a8f99" opacity=".55"/>'
                     % (cx - 16 - k * 26, y - 8 - k * 16, 14 + k * 6))
        o.append("</g>")
    # 红绿灯
    o.append('<rect x="1076" y="196" width="9" height="106" fill="#4a5160"/>')
    o.append('<rect x="1060" y="150" width="41" height="62" rx="12" fill="#3c424e" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<circle cx="1080" cy="168" r="8" fill="#e23b3b"/>')
    o.append('<circle cx="1080" cy="192" r="8" fill="#5b6152"/>')
    o.append(dora(250, 300, 1.02, mood="worry"))
    o.append(bubble(300, 96, 250, 58, "THIS AIR IS ADVERSE", "left", "#fff6e0", 21, "#b3541e"))
    return "".join(o)


def scene_council():
    o = ['<rect x="0" y="0" width="1200" height="400" fill="#f3ece0"/>']
    o.append('<rect x="0" y="286" width="1200" height="114" fill="#d9c9ad"/>')
    o.append('<rect x="150" y="60" width="240" height="150" rx="6" fill="#eaf1f7" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<text x="270" y="146" text-anchor="middle" font-family="-apple-system,sans-serif" font-size="26" '
             'font-weight="700" fill="#8a94a3">VOTE</text>')
    o.append('<text x="270" y="184" text-anchor="middle" font-family="-apple-system,sans-serif" font-size="34" '
             'font-weight="800" fill="#c0392b">10 : 9</text>')
    o.append('<path d="M 0 300 L 1200 300 L 1160 344 L 40 344 Z" fill="#a9743f" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<rect x="40" y="286" width="1120" height="16" rx="8" fill="#c08a4e" stroke="%s" stroke-width="3"/>' % INK)
    o.append(adult(232, 300, 1.0, "#4d6a8a", False, True))
    o.append(adult(968, 300, 1.0, "#6b5b7b", True, False))
    o.append(bubble(96, 40, 330, 62, "IT IS OBSOLETE", "left", "#e8f2fb", 22, "#1d5f8a"))
    o.append(bubble(774, 40, 330, 62, "NO, IT IS EFFICIENT", "right", "#f7ecf4", 21, "#7b3f6b"))
    o.append(dora(600, 300, 1.0, mood="worry"))
    o.append(bubble(636, 150, 300, 58, "CONTROVERSIAL…", "left", "#fff6e0", 22, "#b3541e"))
    return "".join(o)


def scene_policy():
    o = [skybg("#dcecf7", "#eef3e4")]
    o.append('<rect x="0" y="286" width="1200" height="114" fill="#7fae5a"/>')
    o.append('<path d="M 0 286 Q 300 250 620 286 Q 940 322 1200 282 L 1200 400 L 0 400 Z" fill="#6fa04d"/>')
    # 加宽的马路
    o.append('<path d="M 520 400 L 700 286 L 1100 286 L 1200 400 Z" fill="#8d94a3"/>')
    for y in range(300, 400, 26):
        o.append('<rect x="%g" y="%g" width="38" height="8" rx="4" fill="#f4f1e6"/>' % (610 + (y - 300) * 1.5, y))
    # 树
    for tx, ty, ts in ((760, 286, 1.0), (860, 292, .82), (960, 280, .92), (1058, 296, .74)):
        o.append('<g transform="translate(%g,%g) scale(%g)"><rect x="-6" y="-46" width="12" height="48" fill="#8a6239"/>'
                 '<circle cx="0" cy="-70" r="30" fill="#4f9d4a" stroke="%s" stroke-width="3"/>'
                 '<circle cx="-22" cy="-52" r="20" fill="#5cae55" stroke="%s" stroke-width="2.6"/>'
                 '<circle cx="22" cy="-54" r="21" fill="#5cae55" stroke="%s" stroke-width="2.6"/></g>' % (tx, ty, ts, INK, INK, INK))
    # 农田 + 农民
    for i in range(6):
        o.append('<path d="M %g 400 q 30 -70 60 0" fill="none" stroke="#c7a25b" stroke-width="3"/>' % (60 + i * 62))
    o.append(adult(300, 330, .92, "#8a6f4a", False, False))
    o.append('<path d="M 356 300 L 392 262" stroke="#8a6239" stroke-width="7" stroke-linecap="round"/>')
    o.append('<path d="M 380 258 L 404 250 L 396 268 Z" fill="#9aa3ad" stroke="%s" stroke-width="2.4"/>' % INK)
    # 机器猫举牌子 + 硬币
    o.append(dora(600, 360, 1.08))
    o.append('<g><rect x="666" y="150" width="230" height="76" rx="12" fill="#fff8e1" stroke="%s" stroke-width="3.4"/>' % INK)
    o.append('<text x="781" y="200" text-anchor="middle" font-family="-apple-system,sans-serif" font-size="34" '
             'font-weight="800" fill="#c0392b">LEVY</text>')
    o.append('<line x1="640" y1="196" x2="668" y2="190" stroke="%s" stroke-width="4"/>' % INK)
    o.append("</g>")
    for cx, cy in ((520, 250), (556, 206), (492, 206)):
        o.append('<g><circle cx="%g" cy="%g" r="17" fill="#f5c518" stroke="%s" stroke-width="2.6"/>' % (cx, cy, INK))
        o.append('<text x="%g" y="%g" text-anchor="middle" font-size="17" font-weight="700" fill="#8a6d16">$</text>' % (cx, cy + 6))
        o.append("</g>")
    return "".join(o)


def scene_build():
    o = [skybg("#cfe6f5", "#fdf3e0")]
    o.append('<rect x="0" y="300" width="1200" height="100" fill="#9aa3ad"/>')
    for x in range(10, 1200, 92):
        o.append('<rect x="%g" y="348" width="52" height="7" rx="3.5" fill="#f4f1e6"/>' % x)
    # 屋顶 + 太阳能板
    for bx, by, bw in ((60, 200, 210), (300, 226, 176), (520, 190, 150)):
        o.append('<rect x="%g" y="%g" width="%g" height="%g" rx="4" fill="#d8c3a5" stroke="%s" stroke-width="3"/>' % (bx, by, bw, 300 - by, INK))
        for c in range(int((bw - 30) // 56)):
            px = bx + 14 + c * 56
            o.append('<rect x="%g" y="%g" width="46" height="34" rx="3" fill="#2f4f7f" stroke="%s" stroke-width="2.4"/>'
                     % (px, by + 22, INK))
            o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#7fa7d9" stroke-width="2"/>' % (px, by + 39, px + 46, by + 39))
    # 河流 + 传感器
    o.append('<path d="M 0 306 Q 300 292 600 310 Q 900 328 1200 304 L 1200 400 L 0 400 Z" fill="#5fb3d4"/>')
    o.append('<g transform="translate(880,330)"><circle cx="0" cy="0" r="20" fill="#f5c518" stroke="%s" stroke-width="3"/>'
             '<rect x="-8" y="-30" width="16" height="22" rx="4" fill="#e23b3b" stroke="%s" stroke-width="2.4"/>'
             '<circle cx="0" cy="-36" r="6" fill="#8ce08c" stroke="%s" stroke-width="2"/></g>' % (INK, INK, INK))
    # 公交车
    o.append('<g><rect x="820" y="188" width="230" height="86" rx="16" fill="#4caf50" stroke="%s" stroke-width="3.4"/>' % INK)
    for i in range(4):
        o.append('<rect x="%g" y="204" width="40" height="34" rx="5" fill="#eaf6ff" stroke="%s" stroke-width="2.4"/>' % (832 + i * 52, INK))
    o.append('<circle cx="866" cy="282" r="15" fill="#2f3540" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<circle cx="1006" cy="282" r="15" fill="#2f3540" stroke="%s" stroke-width="3"/>' % INK)
    o.append("</g>")
    # 商店
    o.append('<g><rect x="290" y="176" width="176" height="124" rx="8" fill="#fff3d6" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<path d="M 282 178 L 378 128 L 474 178 Z" fill="#e23b3b" stroke="%s" stroke-width="3"/>' % INK)
    o.append('<rect x="326" y="228" width="104" height="70" rx="4" fill="#bfe3f7" stroke="%s" stroke-width="2.6"/>' % INK)
    o.append('<text x="378" y="272" text-anchor="middle" font-family="-apple-system,sans-serif" font-size="20" '
             'font-weight="700" fill="#2b6f9c">SHOP</text></g>')
    o.append(dora(600, 300, 1.05, gadget="copter"))
    o.append(bubble(660, 60, 320, 58, "IT IS FEASIBLE!", "left", "#fff6e0", 23, "#b3541e"))
    return "".join(o)


def scene_school():
    o = ['<rect x="0" y="0" width="1200" height="400" fill="#f6efe2"/>']
    o.append('<rect x="0" y="300" width="1200" height="100" fill="#d9c9ad"/>')
    o.append('<rect x="176" y="52" width="700" height="228" rx="8" fill="#2f4f42" stroke="%s" stroke-width="4"/>' % INK)
    o.append('<rect x="164" y="286" width="724" height="14" rx="6" fill="#8a6239" stroke="%s" stroke-width="3"/>' % INK)
    for i, (w, x) in enumerate([("mitigate", 236), ("alleviate", 236), ("adapt", 236), ("enhance", 236)]):
        o.append('<text x="%g" y="%g" font-family="Georgia,serif" font-size="34" fill="#f2f7f3">%s</text>'
                 % (x + (i % 2) * 330, 108 + (i // 2) * 66, html.escape(w)))
    o.append('<line x1="600" y1="76" x2="600" y2="222" stroke="#7fa694" stroke-width="2"/>')
    # 课桌 + 孩子背影
    for kx, ky, ks, shirt in ((880, 320, .96, "#ef7f6b"), (1010, 326, .9, "#6ba7e0"), (1120, 318, .86, "#f0b73c")):
        o.append(kid(kx, ky, ks, "#3f3126", shirt, True))
    o.append('<rect x="790" y="318" width="360" height="16" rx="7" fill="#c99a5e" stroke="%s" stroke-width="3"/>' % INK)
    o.append(dora(560, 300, 1.02, mood="teach"))
    o.append('<line x1="606" y1="252" x2="700" y2="188" stroke="#8a6239" stroke-width="6" stroke-linecap="round"/>')
    o.append(bubble(150, 296, 340, 60, "COMPULSORY, AND WORTH IT", "left", "#fff6e0", 20, "#b3541e"))
    return "".join(o)


def scene_sky():
    o = [skybg("#a8d8f0", "#fdf1d8")]
    o.append('<circle cx="150" cy="98" r="52" fill="#ffd75e"/>')
    for k in range(7):
        o.append('<circle cx="%g" cy="%g" r="%g" fill="#fff" opacity=".85"/>' % (260 + k * 128, 60 + (k % 3) * 34, 22 + (k % 3) * 7))
    o.append('<path d="M 40 210 q 90 -40 180 0" fill="none" stroke="#eaf6ff" stroke-width="12" stroke-linecap="round"/>')
    o.append('<rect x="0" y="286" width="1200" height="114" fill="#7fae5a"/>')
    # 市场摊位
    for sx, col in ((120, "#e05a4f"), (330, "#f0a83c"), (540, "#4caf50")):
        o.append('<g><rect x="%g" y="238" width="150" height="86" rx="6" fill="#fff6e6" stroke="%s" stroke-width="3"/>' % (sx, INK))
        o.append('<path d="M %g 240 L %g 198 L %g 240 Z" fill="#fff"/>' % (sx - 12, sx + 75, sx + 162))
        for i in range(5):
            o.append('<path d="M %g 240 L %g 198" stroke="%s" stroke-width="10"/>' % (sx + i * 38, sx + 75, col))
        o.append('<circle cx="%g" cy="268" r="12" fill="#e23b3b"/>' % (sx + 34))
        o.append('<circle cx="%g" cy="278" r="11" fill="#f0a83c"/>' % (sx + 74))
        o.append('<circle cx="%g" cy="266" r="12" fill="#7fae5a"/>' % (sx + 112))
        o.append("</g>")
    o.append(dora(760, 372, 1.06))
    o.append(kid(920, 372, .9, "#3f3126", "#ef7f6b"))
    o.append(kid(1040, 372, .82, "#4a3728", "#6ba7e0"))
    o.append(bubble(800, 96, 330, 60, "NOTHING WAS INEVITABLE", "left", "#fff6e0", 21, "#b3541e"))
    return "".join(o)


def scene_cover():
    o = [skybg("#bfe0f5", "#fff4dd")]
    for k in range(9):
        o.append('<circle cx="%g" cy="%g" r="%g" fill="#fff" opacity=".7"/>' % (80 + k * 130, 70 + (k % 3) * 40, 20 + (k % 3) * 8))
    o.append('<rect x="0" y="300" width="1200" height="100" fill="#8fc06a"/>')
    o.append(dora(600, 300, 1.0, gadget="copter"))
    return "".join(o)


SCENES = {
    "city": scene_city, "council": scene_council, "policy": scene_policy,
    "build": scene_build, "school": scene_school, "sky": scene_sky, "cover": scene_cover,
}
DEFAULT_ORDER = ["city", "council", "policy", "build", "school", "sky"]


# ---------------------------------------------------------------- 文字
def as_lines(poem):
    if isinstance(poem, (list, tuple)):
        raw = [str(x) for x in poem]
    else:
        raw = str(poem or "").split("\n")
    while raw and not raw[0].strip():
        raw.pop(0)
    while raw and not raw[-1].strip():
        raw.pop()
    return [ln.rstrip() for ln in raw]


def split_stanzas(lines):
    out, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln)
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def word_forms(w):
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
    forms = {}
    for w in words:
        for f in word_forms(w):
            forms[f] = w
    if not forms:
        return html.escape(text)
    pat = re.compile(r"\b(" + "|".join(sorted(map(re.escape, forms), key=len, reverse=True)) + r")\b", re.IGNORECASE)
    out, last = [], 0
    for m in pat.finditer(text):
        out.append(html.escape(text[last:m.start()]))
        out.append('<em class="v">' + html.escape(m.group(0)) + "</em>")
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


# ---------------------------------------------------------------- HTML
CSS = """
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:__W__px}
  body{background:#f0e7d6;
    background-image:radial-gradient(rgba(0,0,0,.055) 1px, transparent 1.6px);
    background-size:16px 16px;
    font-family:-apple-system,"PingFang SC",Helvetica,sans-serif;
    padding:__PAD__px;color:#1f2328}
  .cover{position:relative;border:5px solid #1f2328;border-radius:10px;overflow:hidden;
    background:#bfe0f5;box-shadow:0 6px 0 rgba(0,0,0,.16)}
  .cover .art{display:block}
  .covertxt{position:absolute;left:0;right:0;top:28px;text-align:center}
  .eyebrow{font-size:12px;letter-spacing:.34em;text-transform:uppercase;color:#1d5f8a;
    background:rgba(255,255,255,.8);display:inline-block;padding:6px 16px;border-radius:999px;
    border:2px solid #1f2328}
  h1{font-family:Georgia,"Times New Roman",serif;font-style:italic;font-weight:400;
    font-size:60px;line-height:1.14;color:#15304a;margin-top:16px;
    text-shadow:3px 3px 0 #fff, 6px 6px 0 rgba(31,35,40,.18)}
  .sub{margin-top:14px;font-size:15px;color:#3c4b5a;background:rgba(255,255,255,.78);
    display:inline-block;padding:5px 14px;border-radius:999px}
  .panel{margin-top:30px;border:5px solid #1f2328;border-radius:10px;overflow:hidden;
    background:#fff;box-shadow:0 6px 0 rgba(0,0,0,.16)}
  .art{display:block;width:100%;height:auto;background:#cfe4f2}
  .cap{background:__PAPER__;border-top:4px solid #1f2328;padding:20px 34px 24px}
  .num{display:inline-block;min-width:34px;height:34px;line-height:30px;text-align:center;
    border:3px solid #1f2328;border-radius:999px;background:#ffd75e;font-weight:800;
    font-size:17px;margin-right:12px}
  .ln{font-family:Georgia,"Times New Roman",serif;font-size:__FS__px;line-height:__LH__;
    color:#2c3238;letter-spacing:.004em;text-indent:44px}
  .ln:first-child{text-indent:0}
  em.v{font-style:italic;color:#a8641a;border-bottom:2px solid rgba(200,140,50,.55);padding-bottom:1px}
  .vocab{margin-top:30px;border:5px solid #1f2328;border-radius:10px;background:#fff;
    padding:22px 26px;box-shadow:0 6px 0 rgba(0,0,0,.16)}
  .vlabel{font-size:11.5px;letter-spacing:.26em;text-transform:uppercase;color:#a8641a;margin-bottom:14px}
  .chips{display:flex;flex-wrap:wrap;gap:7px 8px}
  .chip{font-size:14px;line-height:1;color:#3c4b5a;background:#f4f0e4;border:2px solid #d9d2bf;
    border-radius:999px;padding:6px 12px}
  .mark{margin-top:22px;text-align:right;font-size:11px;letter-spacing:.26em;
    text-transform:uppercase;color:#9a8f7a}
"""


def build_html(title, subtitle, day, panels, words):
    css = (CSS.replace("__W__", str(W)).replace("__PAD__", str(PAD))
              .replace("__FS__", str(FS_LINE)).replace("__LH__", str(LH_LINE))
              .replace("__PAPER__", PAPER))
    cover = ('<section class="cover">'
             '<svg class="art" viewBox="0 0 1200 400" xmlns="http://www.w3.org/2000/svg">%s</svg>'
             '<div class="covertxt"><div><span class="eyebrow">Yaya Words · Comic</span></div>'
             '<h1>%s</h1><div><span class="sub">%s · %s</span></div></div>'
             '</section>') % (SCENES["cover"](), html.escape(title),
                              html.escape(subtitle or "今天的散文诗"), html.escape(day))
    secs = []
    for i, p in enumerate(panels, 1):
        art = SCENES.get(p["scene"], scene_city)()
        lines = "".join('<p class="ln">%s</p>' % highlight(ln, words) for ln in p["lines"])
        secs.append('<section class="panel">'
                    '<svg class="art" viewBox="0 0 1200 %d" xmlns="http://www.w3.org/2000/svg">%s</svg>'
                    '<div class="cap"><p class="ln"><span class="num">%d</span></p>%s</div>'
                    '</section>' % (ART_H, art, i, lines))
    chips = "".join('<span class="chip">%s</span>' % html.escape(w) for w in words)
    vocab = ('<section class="vocab"><div class="vlabel">今日词汇 · %d words</div>'
             '<div class="chips">%s</div></section>' % (len(words), chips)) if words else ""
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>%(T)s</title>
<style>%(CSS)s</style>
<script>
addEventListener("load", function(){
  document.title = "H=" + Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
});
</script></head>
<body>%(COVER)s%(PANELS)s%(VOCAB)s<div class="mark">丫丫雅思单词</div></body></html>
""" % {"T": html.escape(title), "CSS": css, "COVER": cover,
       "PANELS": "".join(secs), "VOCAB": vocab}


# ---------------------------------------------------------------- 渲染
def _noise(text):
    keep = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln or "CVDisplayLinkCreateWithCGDisplay" in ln or "task_policy_set" in ln:
            continue
        if "allocator multiple times" in ln or "installwebapp" in ln or "bytes written to file" in ln:
            continue
        if ln.startswith("[") and "INFO:" in ln:
            continue
        keep.append(ln)
    return "\n".join(keep)


def find_chrome(explicit=None):
    for c in ([explicit] if explicit else []) + CHROME_CANDIDATES:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def measure(chrome, path):
    r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--disable-dev-shm-usage", "--virtual-time-budget=2500", "--dump-dom",
                        "--window-size=%d,1200" % W, "file://" + path],
                       capture_output=True, text=True)
    m = re.search(r"<title>\s*H=(\d+)\s*</title>", r.stdout or "") or re.search(r"H=(\d+)", r.stdout or "")
    return int(m.group(1)) if m else None


def shoot(chrome, html_path, png_path, height, scale):
    r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--no-sandbox", "--disable-dev-shm-usage",
                        "--force-device-scale-factor=%s" % scale,
                        "--window-size=%d,%d" % (W, height),
                        "--screenshot=%s" % png_path, "file://" + html_path],
                       capture_output=True, text=True)
    return (os.path.exists(png_path) and os.path.getsize(png_path) > 0), _noise(r.stderr or r.stdout or "")


def main():
    ap = argparse.ArgumentParser(description="把散文诗渲染成哆啦 A 梦风格连环画")
    ap.add_argument("--json", help="内容 JSON（title/date/subtitle/story/words；兼容旧键 poem）")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--poem-file")
    ap.add_argument("--poem")
    ap.add_argument("--words")
    ap.add_argument("--scenes", help="每格场景，逗号分隔，默认 city,council,policy,build,school,sky")
    ap.add_argument("--date")
    ap.add_argument("--out")
    ap.add_argument("--name")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--chrome")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--json-out", action="store_true")
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
        # 键名优先 story（童话）/ tale，最后才认旧的 poem——三个渲染器保持一致
        lines = as_lines(data.get("story") or data.get("tale") or data.get("poem") or "")
    if a.words:
        words = [w.strip() for w in re.split(r"[,\n]", a.words) if w.strip()]
    else:
        words = [str(w).strip() for w in (data.get("words") or []) if str(w).strip()]
    if not lines:
        print("⚠️ 诗正文是空的：用 --json / --poem-file / --poem 给内容。", file=sys.stderr)
        return 2

    if data.get("panels"):
        panels = [{"scene": p.get("scene", "city"), "lines": as_lines(p.get("lines") or [])}
                  for p in data["panels"]]
    else:
        order = [s.strip() for s in (a.scenes or "").split(",") if s.strip()] or DEFAULT_ORDER
        stanzas = split_stanzas(lines)
        panels = [{"scene": order[i % len(order)], "lines": st} for i, st in enumerate(stanzas)]
    panels = [p for p in panels if p["lines"]]
    if not panels:
        print("⚠️ 没切出任何一段。", file=sys.stderr)
        return 2

    out_dir = os.path.expanduser(a.out or POEM_DIR)
    os.makedirs(out_dir, exist_ok=True)
    stem = a.name or ("comic-" + day)
    html_path = os.path.join(out_dir, stem + ".html")
    png_path = os.path.join(out_dir, stem + ".png")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(title, subtitle, day, panels, words))

    png_ok, note, size = False, "", None
    if not a.no_png:
        chrome = find_chrome(a.chrome)
        if chrome:
            h = measure(chrome, html_path) or (520 + len(panels) * 780)
            png_ok, note = shoot(chrome, html_path, png_path, max(900, h), a.scale)
            if png_ok:
                size = "%dx%d" % (W * a.scale, max(900, h) * a.scale)
        else:
            note = "没找到 Chrome/Chromium，未生成 PNG（HTML 已生成，可直接打开预览）"

    res = {"html": html_path, "png": png_path if png_ok else None, "panels": len(panels),
           "words": len(words), "size": size, "note": note}
    # --no-png 是「我只想快出 HTML」，不是失败；只有「想渲染 PNG 但渲染不出来」才返回 1
    code = 0 if (a.no_png or png_ok) else 1
    if a.json_out:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return code
    print("🖼️ 连环画 HTML：%s" % html_path)
    if png_ok:
        print("🖼️ 连环画图片：%s（%s，%d 格）" % (png_path, res["size"], len(panels)))
    elif note:
        print("⚠️ %s" % note)
    elif a.no_png:
        print("（--no-png：按要求只出 HTML）")
    return code


if __name__ == "__main__":
    sys.exit(main())
