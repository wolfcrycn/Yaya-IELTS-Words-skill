#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丫丫雅思单词 · 故事分镜画具（make_watercolor_svg_book.py 的插画引擎）。

为什么要有这个文件
------------------
旧的 9 个 `SCENES` 是「整套画好的场景」：通用，但必然**不贴题**——讲钥匙的童话会配上
水壶 + 山丘；而且一共只有 9 张，连着写几天必然**重样**。

这里换成**分镜式**拼图：

    plan = {"bg": 背景名, "parts": [{"name":..., "slot":..., "why":..., "scope":...}],
            "why": {主体物: 触发词}}

  * **背景层**（17 个）只画「在哪里、什么气氛」，由段落里的场景词决定；
  * **主体物**（50+ 个）由**这一段真实出现的词**决定；每个主体物都要能说出它是被哪个词
    引出来的（`why` 非空，且那个词**确实**出现在段/标题/正文里）——这就是「贴题」的
    可自检标准，回归测试会逐个断言；
  * 主体物 × 背景的组合空间上千种，再加上「最近几天用过的背景」与「完全相同的组合」
    会被主动避开（`load_history` / `save_history` 读写 `art-ledger.json`），跨天几乎
    不可能重样。

只为好看而加的填充物（花、云、星）标 `decor=True`、`why` 为空，不算「贴题」。
"""

import json
import os
import re

ART_VERSION = 2

# ============================================================ 画具代理
# 本模块不 import 渲染器（会循环依赖）。渲染器 import 完本模块后回调 bind(globals())，
# 把 wash / line / P / W / H / face / … 注入进来。
_NS = {}


def bind(ns):
    """由渲染器在自身模块体末尾调用：art_storyboard.bind(globals())"""
    _NS.clear()
    _NS.update(ns)


class _R(object):
    def __getattr__(self, k):
        try:
            return _NS[k]
        except KeyError:
            raise AttributeError(
                "画具 %r 还没绑定：渲染器要先调 art_storyboard.bind(globals())" % (k,))


R = _R()


# ============================================================ 槽位
# 主体物站在哪。地面槽与空中槽分开：air=True 的主体（鸟/风筝/月亮）走空中槽，不会踩在地上。
SLOTS_GROUND = [
    ("hero", 600, 748, 1.30),
    ("left", 250, 738, 0.95),
    ("right", 952, 738, 0.95),
    ("far_left", 96, 706, 0.68),
    ("far_right", 1106, 706, 0.68),
]
SLOTS_AIR = [
    ("air_mid", 618, 246, 1.15),
    ("air_left", 262, 306, 0.95),
    ("air_right", 958, 320, 0.95),
]
SLOTS = dict((n, (x, y, s)) for n, x, y, s in (SLOTS_GROUND + SLOTS_AIR))
# 画序：远的先画、hero 压在上面；空中最后（永远在最前，不会被人挡住）
SLOT_DRAW_ORDER = ["far_left", "far_right", "left", "right", "hero",
                   "air_left", "air_right", "air_mid"]
GROUND_SLOTS = [n for n, _, _, _ in SLOTS_GROUND]
AIR_SLOTS = [n for n, _, _, _ in SLOTS_AIR]


def slot_xy(name):
    return SLOTS.get(name, SLOTS["hero"])


# ============================================================ 背景层
def _paper():
    return R.band(0, 0, R.W, R.H, R.P["paper"], 1.0, "wc")


def bg_dawn():
    """清晨：暖霞 + 初升的太阳 + 带露的草坡。"""
    s = _paper() + R.band(0, 0, R.W, 662, R.P["sky"], 0.9)
    s += R.wash(600, 656, 660, 270, R.P["peach"], 0.55)
    s += R.mottle(70, 40, 1140, 520, ["#cde5f4", "#f4e2d2", "#f6dfe2"], 8, 0.20, seed=11)
    s += R.sun(322, 248, 54)
    s += R.cloud(884, 202, 0.98, op=0.86)
    s += R.cloud(566, 322, 0.66, op=0.50)
    s += R.bird(996, 352, 0.86, flip=True)
    s += R.hills(664, [(R.P["mint"], 40, 0.75), (R.P["green"], 104, 0.86)])
    s += R.mottle(60, 752, 1140, 880, ["#b7d5aa", "#8fbb80"], 6, 0.15, seed=23)
    return s


def bg_day():
    """白天：高远的天 + 流云 + 缓坡草地。"""
    s = _paper() + R.band(0, 0, R.W, 692, R.P["sky"], 0.85)
    s += R.mottle(60, 30, 1150, 560, ["#d9ebf7", "#f0f8fd"], 9, 0.18, seed=31)
    s += R.cloud(300, 168, 1.15, op=0.90)
    s += R.cloud(905, 262, 0.82, op=0.62)
    s += R.cloud(640, 116, 0.60, op=0.45)
    s += R.hills(692, [(R.P["mint"], 30, 0.70), (R.P["green"], 92, 0.82)])
    s += R.mottle(60, 762, 1140, 880, ["#b7d5aa", "#8fbb80"], 6, 0.14, seed=37)
    return s


def bg_night_sky():
    """夜空：月牙 + 星子 + 远山剪影。"""
    s = R.band(0, 0, R.W, R.H, R.P["night"], 1.0, "wc")
    s += R.wash(600, 560, 720, 340, R.P["night2"], 0.50)
    s += R.mottle(60, 40, 1140, 600, ["#4b5680", "#6b76a0", "#3a4463"], 10, 0.22, seed=41)
    for px, py, pr in ((176, 150, 15), (330, 276, 10), (505, 118, 12), (668, 300, 9),
                       (1088, 386, 11), (120, 426, 8), (762, 96, 8), (416, 400, 7)):
        s += R.star(px, py, pr)
    s += R.sparkle(884, 466, 22, R.P["white"])
    s += R.hills(714, [(R.P["night2"], 26, 0.90), ("#4a5578", 92, 1.0)])
    return s


def bg_night_house():
    """夜色里的一间小屋：窗亮着，草是暗的。"""
    s = R.band(0, 0, R.W, R.H, R.P["night"], 1.0, "wc")
    s += R.wash(300, 480, 620, 360, R.P["night2"], 0.45)
    s += R.mottle(60, 40, 1140, 580, ["#4b5680", "#66719a"], 8, 0.20, seed=43)
    for px, py, pr in ((520, 132, 12), (700, 240, 9), (960, 128, 11), (1120, 300, 8)):
        s += R.star(px, py, pr)
    s += R.hills(724, [(R.P["night2"], 20, 0.88), ("#3d4767", 86, 1.0)])
    s += R.house(1052, 800, 250, 198, R.P["cream"], R.P["lav"])
    s += R.wash(1010, 712, 118, 88, R.P["gold"], 0.30)
    return s


def bg_room():
    """室内：一面墙、一条踢脚线、一扇窗。"""
    s = _paper()
    s += R.band(0, 0, R.W, 640, R.P["cream"], 1.0)
    s += R.mottle(60, 30, 1150, 560, ["#f2e7d3", "#e7dcc6"], 8, 0.18, seed=47)
    s += R.wash(940, 300, 320, 300, R.P["gold"], 0.16)
    s += R.band(0, 636, R.W, 264, R.P["warm"], 0.62)
    s += R.line('M0 636 H1200', 4, R.P["ink"])
    s += R.pane(212, 258, 250, 210, 2, 3)
    s += R.line('M212 258 H462 V468 H212 Z', 4, R.P["ink"])
    return s


def bg_attic():
    """阁楼：斜屋顶、木梁、一束天窗光、飘着尘埃。"""
    s = _paper() + R.band(0, 0, R.W, R.H, R.P["cream"], 1.0)
    s += R.mottle(60, 30, 1150, 700, ["#eadcc2", "#ded0b4"], 9, 0.20, seed=53)
    s += R.band(0, 0, R.W, 700, R.P["warm"], 0.18)
    s += R.line('M0 300 L600 40 L1200 300', 7, R.P["soil"])
    s += R.line('M0 470 L600 214 L1200 470', 5, "#c09a78")
    s += R.line('M300 300 L300 224', 5, R.P["soil"])
    s += R.line('M900 300 L900 224', 5, R.P["soil"])
    s += ('<path d="M760 120 L1040 120 L1180 900 L620 900 Z" fill="#fdf6e4" '
          'opacity="0.42" filter="url(#wc)"/>')
    s += R.band(0, 760, R.W, 140, "#e2d3b6", 0.85)
    s += R.mottle(120, 300, 1000, 640, ["#fdfbf2", "#f6eeda"], 5, 0.30, seed=59)
    return s


def bg_corridor():
    """走廊：两道拱门 + 尽头的一小扇门，地上一条光。"""
    s = _paper() + R.band(0, 0, R.W, R.H, "#efe5d2", 1.0)
    s += R.mottle(60, 30, 1150, 800, ["#e6d9c0", "#dccdb0"], 8, 0.20, seed=61)
    s += R.band(0, 690, R.W, 210, R.P["warm"], 0.55)
    s += R.line('M0 690 H1200', 4, R.P["ink"])
    s += ('<path d="M96 690 L96 292 A204 204 0 0 1 504 292 L504 690" fill="none" '
          'stroke="%s" stroke-width="8" filter="url(#rough)"/>' % R.P["soil"])
    s += ('<path d="M636 690 L636 348 A166 166 0 0 1 968 348 L968 690" fill="none" '
          'stroke="#c09a78" stroke-width="7" filter="url(#rough)"/>')
    s += R.band(500, 356, 132, 334, "#e9dcbe", 0.9)
    s += R.line('M500 356 H632 V690 H500 Z', 5, R.P["ink"])
    s += R.band(500, 356, 132, 334, R.P["gold"], 0.22)
    s += ('<path d="M566 690 L520 900 L700 900 L626 690 Z" fill="#fdf6e4" '
          'opacity="0.4" filter="url(#wc)"/>')
    return s


def bg_street():
    """街道：一片砖墙、一条路面、远处的屋顶。"""
    s = _paper() + R.band(0, 0, R.W, 520, R.P["sky"], 0.7)
    s += R.mottle(60, 30, 1150, 460, ["#dbeaf4", "#eef6fb"], 7, 0.18, seed=67)
    for x, w, h in ((60, 210, 300), (300, 170, 240), (820, 200, 280), (1050, 150, 210)):
        s += R.band(x, 520 - h, w, h, "#e6d5bb", 0.85)
        s += R.band(x, 520 - h, w, 26, R.P["rose"], 0.45)
        s += R.line('M%d %d H%d V520 H%d Z' % (x, 520 - h, x + w, x), 4, R.P["ink"])
        for wx in range(x + 30, x + w - 30, 62):
            for wy in range(520 - h + 56, 470, 74):
                s += R.pane(wx, wy, 40, 46, 1, 1)
                s += R.line('M%d %d h40 v46 h-40 Z' % (wx, wy), 3, R.P["ink"])
    s += R.band(0, 520, R.W, 380, R.P["grey"], 0.55)
    s += R.line('M0 520 H1200', 5, R.P["ink"])
    s += R.mottle(60, 560, 1140, 880, ["#d8d4cc", "#c8c3ba"], 7, 0.16, seed=71)
    s += R.line('M0 760 H1200', 3, "#b7b2a8")
    return s


def bg_street_night():
    """夜街：深蓝、湿路面、路灯光晕。"""
    s = R.band(0, 0, R.W, R.H, R.P["night"], 1.0, "wc")
    s += R.mottle(60, 40, 1140, 620, ["#454f74", "#5a6489"], 9, 0.20, seed=73)
    s += R.band(0, 560, R.W, 340, "#333c5c", 0.85)
    for px, py, pr in ((180, 150, 12), (420, 96, 10), (900, 132, 13), (1120, 220, 9)):
        s += R.star(px, py, pr)
    s += R.wash(820, 470, 210, 190, R.P["gold"], 0.34)
    s += R.line('M0 560 H1200', 5, "#2b3350")
    s += R.mottle(60, 600, 1140, 880, ["#3c4568", "#4d5779"], 6, 0.18, seed=79)
    return s


def bg_forest():
    """树林：多层树、苔绿地面、几束光。"""
    s = _paper() + R.band(0, 0, R.W, 700, "#e8f0e2", 1.0)
    s += R.mottle(60, 30, 1150, 620, ["#d6e6d0", "#c3dcbe"], 9, 0.20, seed=83)
    s += R.wash(360, 220, 250, 200, R.P["gold"], 0.16)
    s += R.tree(120, 706, 1.7)
    s += R.tree(1088, 712, 1.55)
    s += R.tree(276, 682, 1.15)
    s += R.tree(948, 690, 1.05)
    s += R.hills(720, [(R.P["mint"], 20, 0.72), (R.P["green2"], 78, 0.86)])
    s += R.mottle(60, 776, 1140, 880, ["#a7c79b", "#8db182"], 6, 0.16, seed=89)
    return s


def bg_sea():
    """海：天、浪、沙滩，远处一只帆。"""
    s = _paper() + R.band(0, 0, R.W, 470, R.P["sky"], 0.85)
    s += R.mottle(60, 30, 1150, 420, ["#d9ebf7", "#eef7fc"], 7, 0.18, seed=97)
    s += R.cloud(884, 156, 0.9, op=0.8)
    s += R.band(0, 470, R.W, 230, R.P["blue"], 0.72)
    s += R.band(0, 470, R.W, 60, R.P["blue2"], 0.45)
    s += R.line('M0 470 H1200', 4, R.P["ink"])
    for y, w in ((530, 6), (580, 5), (630, 5), (676, 4)):
        s += R.line('M130 %d q90 -20 180 0 t180 0 t180 0 t180 0 t180 0' % y, w, "#5b86ab")
    s += R.band(0, 700, R.W, 200, R.P["warm"], 0.72)
    s += R.mottle(60, 716, 1140, 880, ["#f0dcbc", "#e4cba4"], 6, 0.16, seed=101)
    s += R.line('M0 700 H1200', 4, R.P["ink"])
    return s


def bg_snow():
    """雪地：灰蓝天、雪丘、雪花。"""
    s = _paper() + R.band(0, 0, R.W, 640, "#e6eef5", 1.0)
    s += R.mottle(60, 30, 1150, 540, ["#dbe7f2", "#cddced"], 8, 0.20, seed=103)
    s += R.sun(960, 190, 42)
    s += R.hills(660, [("#f4f8fb", 26, 0.80), (R.P["white"], 96, 0.92)])
    s += R.mottle(60, 730, 1140, 880, ["#eef4f9", "#e2ebf3"], 6, 0.22, seed=107)
    for px, py, pr in ((180, 178, 9), (352, 288, 7), (556, 122, 8), (700, 330, 6),
                       (900, 210, 8), (1082, 372, 7), (250, 452, 6)):
        s += R.sparkle(px, py, pr, R.P["white"])
    return s


def bg_garden():
    """花园：篱笆、花丛、一条小径。"""
    s = _paper() + R.band(0, 0, R.W, 620, R.P["sky"], 0.72)
    s += R.mottle(60, 30, 1150, 540, ["#dcecf6", "#eef7fc"], 8, 0.18, seed=109)
    s += R.cloud(280, 152, 0.92, op=0.82)
    s += R.hills(628, [(R.P["mint"], 26, 0.74), (R.P["green"], 88, 0.86)])
    for x in range(40, 1200, 108):
        s += R.line('M%d 690 V584' % x, 8, R.P["soil"])
    s += R.line('M20 620 H1180', 6, R.P["soil"])
    s += R.line('M20 662 H1180', 6, R.P["soil"])
    s += R.mottle(60, 758, 1140, 880, ["#b7d5aa", "#95bf86"], 6, 0.16, seed=113)
    s += ('<path d="M470 900 Q600 780 730 900 Z" fill="#e8d8b8" opacity="0.6" '
          'filter="url(#wc)"/>')
    return s


def bg_shop():
    """店铺：货架 + 柜台 + 暖黄的灯。"""
    s = _paper() + R.band(0, 0, R.W, R.H, R.P["cream"], 1.0)
    s += R.mottle(60, 30, 1150, 700, ["#f2e7d3", "#e5d9bf"], 8, 0.18, seed=127)
    s += R.wash(600, 200, 460, 240, R.P["gold"], 0.20)
    for y in (330, 500):
        s += R.line('M60 %d H1140' % y, 8, R.P["soil"])
        for x in range(130, 1100, 150):
            s += R.band(x - 34, y - 96, 68, 92, "#e9dcc0", 0.8)
            s += R.line('M%d %d H%d V%d H%d Z' % (x - 34, y - 96, x + 34, y, x - 34), 3, "#c09a78")
    s += R.band(0, 700, R.W, 200, R.P["warm"], 0.72)
    s += R.line('M0 700 H1200', 5, R.P["ink"])
    return s


def bg_rain():
    """雨天：灰云、雨丝、水洼。"""
    s = _paper() + R.band(0, 0, R.W, R.H, "#e4e9ee", 1.0)
    s += R.mottle(60, 20, 1150, 520, ["#d3dae2", "#c3ccd6"], 9, 0.22, seed=131)
    s += R.cloud(260, 150, 1.1, op=0.9, col="#cdd5dd")
    s += R.cloud(880, 190, 0.95, op=0.8, col="#c6cfd8")
    s += R.hills(700, [("#b9c6bf", 24, 0.78), (R.P["green2"], 96, 0.88)])
    s += R.drops(60, 250, 26, 46, 560)
    s += R.mottle(60, 750, 1140, 880, ["#a9bdaa", "#93ad95"], 6, 0.18, seed=137)
    return s


def bg_market():
    """集市：几顶棚子、一串旗子、远处的人影。"""
    s = _paper() + R.band(0, 0, R.W, 640, R.P["sky"], 0.8)
    s += R.mottle(60, 30, 1150, 560, ["#dcecf6", "#f0e9d8"], 8, 0.18, seed=139)
    for x, w, col in ((90, 300, R.P["rose"]), (470, 320, R.P["gold"]), (860, 290, R.P["mint"])):
        s += R.line('M%d 620 V430' % (x + 20), 7, R.P["soil"])
        s += R.line('M%d 620 V430' % (x + w - 20), 7, R.P["soil"])
        s += R.band(x, 402, w, 46, col, 0.85)
        s += ('<path d="M%d 448 L%d 448 L%d 500 L%d 500 Z" fill="%s" opacity="0.28" '
              'filter="url(#wc)"/>' % (x, x + w, x + w - 12, x + 12, col))
    s += R.line('M60 396 Q600 356 1140 396', 4, R.P["ink"])
    for i, x in enumerate(range(120, 1120, 96)):
        s += ('<path d="M%d 384 L%d 428 L%d 384 Z" fill="%s" opacity="0.8" '
              'filter="url(#rough)"/>' % (x, x + 20, x + 40,
                                          [R.P["rose"], R.P["gold"], R.P["mint"], R.P["lav"]][i % 4]))
    s += R.band(0, 620, R.W, 280, "#ddd2ba", 0.7)
    s += R.line('M0 620 H1200', 5, R.P["ink"])
    s += R.mottle(60, 660, 1140, 880, ["#d5c9ae", "#c8bb9d"], 6, 0.16, seed=149)
    return s


def bg_plain():
    """兜底：只有纸底和几团柔和的晕染，绝不抢主体。"""
    s = _paper()
    s += R.mottle(80, 60, 1120, 620, ["#e9e2d2", "#dfe6de", "#e3e0ee"], 7, 0.18, seed=151)
    s += R.band(0, 740, R.W, 160, "#e7decb", 0.55)
    s += R.line('M0 740 H1200', 3, "#c9bda6")
    return s


# 背景名 → (关键词, 画法, 「天」的颜色——月牙缺口要用它来咬)
BG = {
    "dawn": ("清晨 早晨 黎明 日出 曙光 天亮 晨光 dawn morning sunrise first light",
             bg_dawn, "#dcecf6"),
    "day": ("白天 户外 田野 晴天 草地 云 day field outdoor sunny sky grass hill",
            bg_day, "#dcecf6"),
    "night_sky": ("夜晚 星 星星 月亮 深夜 天 night stars moon dark sky evening midnight",
                  bg_night_sky, "#3f4a6b"),
    "night_house": ("夜色 夜 小屋 窗户 灯 家 傍晚 night house window lamp home evening",
                    bg_night_house, "#3f4a6b"),
    "room": ("房间 室内 屋子 家里 地板 墙 客厅 厨房 room indoor floor wall kitchen",
             bg_room, "#efe7d6"),
    "attic": ("阁楼 屋顶 梁 尘 旧物 顶上 attic roof beam dust loft old",
              bg_attic, "#efe7d6"),
    "corridor": ("走廊 过道 长廊 尽头 拱门 楼梯 corridor hall passage arch",
                 bg_corridor, "#efe5d2"),
    "street": ("街 街道 路 城 巷 门牌 路边 street road town lane city pavement",
               bg_street, "#dcecf6"),
    "street_night": ("夜街 夜路 路灯 深夜 巷 street night lamppost lane dark",
                     bg_street_night, "#3f4a6b"),
    "forest": ("树林 森林 林 树 苔 枝 野 forest wood tree branch moss",
               bg_forest, "#e8f0e2"),
    "sea": ("海 大海 浪 沙滩 船 帆 潮 港 水 sea ocean wave shore beach boat tide harbor",
            bg_sea, "#dcecf6"),
    "snow": ("雪 冬 冰 寒 冻 冷 snow winter ice cold frost",
             bg_snow, "#e6eef5"),
    "garden": ("花园 园子 篱笆 花圃 小径 院子 garden fence flower path yard",
               bg_garden, "#dcecf6"),
    "shop": ("店铺 店 铺子 货架 柜台 商店 shop store shelf counter merchant",
             bg_shop, "#efe7d6"),
    "rain": ("雨 下雨 阴 水洼 湿 rain wet puddle drizzle storm",
             bg_rain, "#e4e9ee"),
    "market": ("集市 市集 摊 棚 叫卖 人群 market fair stall crowd",
               bg_market, "#dcecf6"),
    "plain": ("", bg_plain, "#f7f2e7"),
}

BG_ORDER = ["dawn", "day", "night_sky", "night_house", "room", "attic", "corridor",
            "street", "street_night", "forest", "sea", "snow", "garden", "shop",
            "rain", "market", "plain"]


# ============================================================ 主体物画法
# 约定：地面物的 (x, y) = **底面中点**（贴地）；空中物的 (x, y) = **中心**。
# 每个画法签名 (x, y, s, ctx)，ctx = {"bg": 背景名, "sky": 天色}。

def d_key(x, y, s, ctx=None):
    """一把立在地上的旧钥匙：上环、中杆、下齿。"""
    g = R.wash(x, y - 116 * s, 96 * s, 138 * s, R.P["gold"], 0.18)
    g += ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
          'stroke-width="%.1f" filter="url(#rough)"/>'
          % (x, y - 196 * s, 40 * s, R.P["gold"], 15 * s))
    g += R.wash(x, y - 196 * s, 30 * s, 30 * s, R.P["cream"], 0.35)
    g += R.line("M%.1f %.1f V%.1f" % (x, y - 158 * s, y - 52 * s), 15 * s, R.P["gold"])
    g += R.line("M%.1f %.1f h%.1f" % (x - 13 * s, y - 152 * s, 26 * s), 9 * s, R.P["ink"])
    g += R.line("M%.1f %.1f h%.1f v%.1f h%.1f v%.1f h%.1f v%.1f h%.1f Z" % (
        x + 7 * s, y - 52 * s, 34 * s, 16 * s, -24 * s, 14 * s, 24 * s, 14 * s, -34 * s),
        4.5 * s, R.P["gold"], R.P["gold"])
    g += R.sparkle(x + 56 * s, y - 220 * s, 17 * s, R.P["gold"])
    return g


def d_needle(x, y, s, ctx=None):
    """一根竖着的缝衣针，针眼里穿着线。"""
    g = R.wash(x, y - 140 * s, 84 * s, 150 * s, R.P["grey"], 0.20)
    g += R.line("M%.1f %.1f L%.1f %.1f" % (x, y, x - 6 * s, y - 250 * s), 8 * s, R.P["grey2"])
    g += R.line("M%.1f %.1f L%.1f %.1f" % (x + 2 * s, y - 26 * s, x - 3 * s, y - 228 * s),
                3 * s, R.P["white"])
    g += ('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" stroke="%s" '
          'stroke-width="3" filter="url(#rough)"/>'
          % (x - 6 * s, y - 234 * s, 7 * s, 12 * s, R.P["grey2"]))
    g += '<g class="wx-sway" style="transform-origin:%.1fpx %.1fpx">' % (x - 6 * s, y - 234 * s)
    g += R.line("M%.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f" % (
        x - 6 * s, y - 238 * s,
        x + 74 * s, y - 306 * s, x + 148 * s, y - 178 * s, x + 100 * s, y - 92 * s,
        x + 64 * s, y - 24 * s, x + 134 * s, y - 6 * s, x + 178 * s, y - 60 * s),
        4.2 * s, R.P["rose"])
    g += "</g>"
    return g


def d_coin(x, y, s, ctx=None):
    """几枚叠着的金币。"""
    g = R.wash(x, y - 74 * s, 160 * s, 96 * s, R.P["gold"], 0.16)
    for dx, dy, sc in ((-66, -4, 0.84), (58, -20, 0.78), (0, 0, 1.0)):
        cx, cy, r = x + dx * s, y - 80 * s + dy * s, 76 * s * sc
        g += ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" '
              'stroke-width="4.4" filter="url(#rough)"/>'
              % (cx, cy, r, R.P["gold"], R.P["ink"]))
        g += ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
              'stroke-width="2.2" opacity=".65" filter="url(#rough)"/>'
              % (cx, cy, r * 0.78, R.P["ink"]))
    g += R.star(x, y - 80 * s, 30 * s, col=R.P["cream"])
    g += R.sparkle(x + 100 * s, y - 160 * s, 18 * s, R.P["gold"])
    g += R.sparkle(x - 96 * s, y - 140 * s, 13 * s, R.P["gold"])
    return g


def d_clock(x, y, s, ctx=None):
    """落地钟：表盘 + 摆。（会晃）"""
    g = R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 66 * s, y - 318 * s, 132 * s, 318 * s, -132 * s), 5, R.P["ink"], R.P["warm"])
    g += R.line('M%.1f %.1f v-26 h%.1f v26' % (x - 40 * s, y - 318 * s, 80 * s), 4, R.P["ink"])
    g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x - 46 * s, y - 344 * s, x, y - 378 * s, x + 46 * s, y - 344 * s), 4, R.P["ink"], R.P["gold"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="4" filter="url(#rough)"/>' % (
        x, y - 246 * s, 50 * s, R.P["white"], R.P["ink"])
    for i in range(12):
        import math as _m
        a = i * _m.pi / 6
        g += R.line('M%.1f %.1f L%.1f %.1f' % (
            x + _m.cos(a) * 40 * s, y - 246 * s + _m.sin(a) * 40 * s,
            x + _m.cos(a) * 47 * s, y - 246 * s + _m.sin(a) * 47 * s), 2.6 * s, R.P["ink"])
    g += R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x, y - 246 * s, x + 26 * s, y - 268 * s,
        x, y - 246 * s, x - 8 * s, y - 216 * s), 4 * s, R.P["ink"])
    g += '<g class="wx-sway" style="transform-origin:%.1fpx %.1fpx">' % (x, y - 176 * s)
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 176 * s, y - 78 * s), 4 * s, R.P["ink"])
    g += R.wash(x, y - 70 * s, 22 * s, 22 * s, R.P["gold"], 0.95)
    g += "</g>"
    g += R.line('M%.1f %.1f h%.1f' % (x - 96 * s, y - 8 * s, 192 * s), 8 * s, R.P["soil"])
    return g


def d_candle(x, y, s, ctx=None):
    """一支点燃的蜡烛。"""
    g = R.wash(x, y - 220 * s, 130 * s, 140 * s, R.P["gold"], 0.22)
    g += ('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" '
          'stroke-width="3" filter="url(#rough)"/>'
          % (x, y - 8 * s, 54 * s, 14 * s, R.P["gold"], R.P["ink"]))
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 22 * s, y - 104 * s, 44 * s, 104 * s, -44 * s), 4, R.P["ink"], R.P["cream"])
    for dx, dy in ((-22, -96), (23, -104), (-8, -80)):
        g += R.wash(x + dx * s, y + dy * s, 12 * s, 20 * s, R.P["cream"], 0.9)
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 104 * s, y - 124 * s), 4 * s, R.P["ink"])
    g += '<g class="wx-float" style="transform-origin:%.1fpx %.1fpx">' % (x, y - 130 * s)
    g += R.wash(x, y - 158 * s, 21 * s, 32 * s, R.P["gold"], 0.95)
    g += R.wash(x, y - 154 * s, 9 * s, 16 * s, "#fff8e6", 0.92)
    g += "</g>"
    return g


def d_lantern(x, y, s, ctx=None):
    """一盏纸灯笼：会晃、带脸。"""
    g = R.wash(x, y - 150 * s, 138 * s, 148 * s, R.P["gold"], 0.26)
    g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
        x - 32 * s, y - 264 * s, 32 * s, 36 * s, 64 * s), 5, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 50 * s, y - 250 * s, 100 * s), 9 * s, R.P["ink"])
    g += R.wash(x, y - 168 * s, 72 * s, 82 * s, R.P["gold"], 0.78)
    g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
        x - 66 * s, y - 236 * s, 66 * s, 72 * s, 132 * s), 4.2, R.P["ink"], "none")
    g += R.line('M%.1f %.1f h%.1f' % (x - 46 * s, y - 88 * s, 92 * s), 8 * s, R.P["ink"])
    for dx in (-26, 0, 26):
        g += R.line('M%.1f %.1f Q%.1f %.1f %.1f %.1f' % (
            x + dx * s, y - 240 * s, x + dx * 1.5 * s, y - 168 * s, x + dx * s, y - 96 * s),
            2.6 * s, R.P["ink"], "none")
    g += R.face(x, y - 158 * s, 34 * s)
    g += R.line('M%.1f %.1f v%.1f' % (x, y - 84 * s, y - 52 * s), 5 * s, R.P["rose"])
    g += R.sparkle(x + 96 * s, y - 210 * s, 20 * s, R.P["gold"])
    return g


def d_snowman(x, y, s, ctx=None):
    """雪人：围巾 + 胡萝卜鼻子，头上扣只小桶。"""
    g = R.wash(x, y - 150 * s, 150 * s, 160 * s, R.P["white"], 0.55)
    for cy, r in ((y - 72 * s, 78 * s), (y - 186 * s, 56 * s), (y - 268 * s, 38 * s)):
        g += R.wash(x, cy, r, r * 0.94, R.P["white"], 0.95)
        g += ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
              'stroke-width="3" opacity=".55" filter="url(#rough)"/>'
              % (x, cy, r, "#9db6cc"))
    g += R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x - 56 * s, y - 200 * s, x - 128 * s, y - 254 * s,
        x + 56 * s, y - 200 * s, x + 126 * s, y - 246 * s), 6 * s, R.P["soil"])
    g += R.face(x, y - 272 * s, 30 * s)
    g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x, y - 266 * s, x + 34 * s, y - 258 * s, x, y - 250 * s), 3, R.P["warm2"], R.P["warm2"])
    g += R.band(x - 46 * s, y - 226 * s, 92 * s, 20 * s, R.P["rose"], 0.92)
    g += R.line('M%.1f %.1f l%.1f %.1f l-%.1f %.1f' % (
        x + 34 * s, y - 222 * s, 18 * s, 40 * s, -14 * s, 26 * s), 8 * s, R.P["rose"])
    g += R.line('M%.1f %.1f h%.1f v-%.1f h-%.1f Z' % (
        x - 36 * s, y - 296 * s, 72 * s, 44 * s, 72 * s), 4, R.P["ink"], R.P["grey2"])
    for px, py, pr in ((x - 116 * s, y - 330 * s, 9 * s), (x + 128 * s, y - 300 * s, 7 * s),
                       (x + 60 * s, y - 368 * s, 8 * s)):
        g += R.sparkle(px, py, pr, R.P["white"])
    return g


def d_mirror(x, y, s, ctx=None):
    """一面椭圆手镜，镜里有一张脸。"""
    g = R.wash(x, y - 150 * s, 110 * s, 140 * s, R.P["lav"], 0.24)
    g += R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x - 34 * s, y - 40 * s, x - 44 * s, y,
        x + 34 * s, y - 40 * s, x + 44 * s, y), 7 * s, R.P["ink"])
    for cy, ry in ((y - 116 * s, 30 * s),):
        g += R.line('M%.1f %.1f h%.1f' % (x - 24 * s, cy + ry, 48 * s), 6 * s, R.P["gold"])
    g += ('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" '
          'stroke-width="9" filter="url(#rough)"/>'
          % (x, y - 170 * s, 74 * s, 100 * s, R.P["lav"], R.P["ink"]))
    g += ('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".92" '
          'filter="url(#wc)"/>' % (x, y - 170 * s, 58 * s, 84 * s, R.P["white"]))
    g += R.face(x, y - 172 * s, 32 * s)
    g += R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x - 52 * s, y - 214 * s, x - 26 * s, y - 118 * s,
        x + 46 * s, y - 226 * s, x + 30 * s, y - 132 * s), 5 * s, "#e3e0f0")
    return g


def d_letter(x, y, s, ctx=None):
    """一封拆开的信：信封 + 信纸 + 火漆印。"""
    g = R.wash(x, y - 80 * s, 130 * s, 92 * s, R.P["cream"], 0.35)
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 58 * s, y - 176 * s, 116 * s, 96 * s, -116 * s), 3.4, R.P["ink"], R.P["white"])
    for i in range(4):
        g += R.line('M%.1f %.1f h%.1f' % (x - 44 * s, y - 158 * s + i * 22 * s, 88 * s),
                    3 * s, "#b9b2a4")
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 92 * s, y - 92 * s, 184 * s, 92 * s, -184 * s), 4, R.P["ink"], R.P["cream"])
    g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f' % (
        x - 92 * s, y - 92 * s, x, y - 26 * s, x + 92 * s, y - 92 * s), 4, R.P["ink"])
    g += R.wash(x, y - 40 * s, 20 * s, 20 * s, R.P["rose"], 0.95)
    g += R.star(x, y - 40 * s, 11 * s, col=R.P["cream"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x + 52 * s, y - 82 * s, 32 * s, 26 * s, -32 * s), 3, R.P["ink"], R.P["gold"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 58 * s, y - 176 * s, 116 * s, 18 * s, -116 * s), 2.6, R.P["ink"], R.P["cream"])
    return g


def d_chest(x, y, s, ctx=None):
    """一只带锁的木箱 / 抽屉。"""
    g = R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 92 * s, y - 104 * s, 184 * s, 104 * s, -184 * s), 5, R.P["ink"], R.P["warm2"])
    g += R.line('M%.1f %.1f Q%.1f %.1f %.1f %.1f L%.1f %.1f Z' % (
        x - 96 * s, y - 104 * s, x, y - 160 * s, x + 96 * s, y - 104 * s, x - 96 * s, y - 104 * s), 5,
        R.P["ink"], R.P["soil"])
    for dx in (-54, 54):
        g += R.line('M%.1f %.1f V%.1f' % (x + dx * s, y - 104 * s, y - 8 * s), 6 * s, R.P["soil"])
    g += R.band(x - 26 * s, y - 122 * s, 52 * s, 40 * s, R.P["gold"], 0.95)
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 26 * s, y - 122 * s, 52 * s, 40 * s, -52 * s), 3.4, R.P["ink"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y - 104 * s, 6 * s, R.P["ink"])
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 100 * s, y - 88 * s), 4 * s, R.P["ink"])
    g += R.sparkle(x + 116 * s, y - 168 * s, 15 * s, R.P["gold"])
    return g


def d_basket(x, y, s, ctx=None):
    """一只编篮，里面探出小花。"""
    g = R.wash(x, y - 70 * s, 110 * s, 78 * s, R.P["warm"], 0.3)
    for i in range(3):
        g += R.flower(x - 44 * s + i * 44 * s, y - 96 * s, 0.46,
                      [R.P["rose"], R.P["gold"], R.P["lav"]][i])
    g += R.line('M%.1f %.1f h%.1f l-%.1f %.1f h-%.1f Z' % (
        x - 78 * s, y - 96 * s, 156 * s, -26 * s, 96 * s, -104 * s), 4.4,
        R.P["ink"], R.P["warm2"])
    for dy in (-72, -50, -26):
        g += R.line('M%.1f %.1f h%.1f' % (x - 70 * s - (dy + 72) * 0.55 * s,
                                          y + dy * s, 140 * s + (dy + 72) * 1.1 * s),
                    2.6 * s, R.P["soil"])
    g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
        x - 62 * s, y - 96 * s, 62 * s, 62 * s, 124 * s), 5 * s, R.P["soil"])
    return g


def d_shoe(x, y, s, ctx=None):
    """一只旧靴子。"""
    g = R.wash(x, y - 40 * s, 110 * s, 50 * s, R.P["warm2"], 0.28)
    g += R.line('M%.1f %.1f v%.1f q0 %.1f %.1f %.1f h%.1f q%.1f 0 %.1f -%.1f '
                'v-%.1f h-%.1f Z' % (
                    x - 48 * s, y - 168 * s, 118 * s, 10 * s, 26 * s, 24 * s,
                    64 * s, 30 * s, -70 * s, 26 * s, 34 * s, 100 * s),
                5, R.P["ink"], R.P["warm2"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 52 * s, y - 4 * s, 116 * s), 10 * s, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 34 * s, y - 148 * s, 44 * s), 4 * s, R.P["ink"])
    for i in range(3):
        g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (
            x - 30 * s + i * 26 * s, y - 126 * s, 4 * s, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f' % (x + 16 * s, y - 96 * s, 62 * s), 3 * s, R.P["soil"])
    return g


def d_hat(x, y, s, ctx=None):
    """一顶宽檐帽，帽带上有朵小花。"""
    g = R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x - 58 * s, y - 96 * s, x + 58 * s, y - 96 * s, x + 40 * s, y - 20 * s, x - 40 * s, y - 20 * s),
        5, R.P["ink"], R.P["lav"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="5" filter="url(#rough)"/>' % (
        x, y - 20 * s, 104 * s, 24 * s, R.P["lav"], R.P["ink"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" stroke="%s" stroke-width="3" opacity=".7" filter="url(#rough)"/>' % (
        x, y - 20 * s, 86 * s, 17 * s, R.P["ink"])
    g += R.band(x - 58 * s, y - 58 * s, 116 * s, 22 * s, R.P["rose"], 0.9)
    g += R.flower(x + 40 * s, y - 48 * s, 0.3, R.P["gold"])
    return g


def d_bell(x, y, s, ctx=None):
    """一口会响的钟（声波一圈圈荡开）。"""
    g = R.wash(x, y - 100 * s, 120 * s, 130 * s, R.P["gold"], 0.2)
    g += R.line('M%.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f Z' % (
        x - 66 * s, y - 12 * s,
        x - 72 * s, y - 104 * s, x - 34 * s, y - 138 * s, x, y - 138 * s,
        x + 34 * s, y - 138 * s, x + 72 * s, y - 104 * s, x + 66 * s, y - 12 * s),
        5, R.P["ink"], R.P["gold"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 70 * s, y - 14 * s, 140 * s), 7 * s, R.P["ink"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="3" filter="url(#rough)"/>' % (
        x, y - 2 * s, 17 * s, R.P["soil"], R.P["ink"])
    g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
        x - 14 * s, y - 140 * s, 14 * s, 18 * s, 28 * s), 5, R.P["ink"])
    for i, rr in enumerate((46, 76, 104)):
        g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 0 %.1f' % (
            x - 74 * s - rr * s, y - 96 * s, rr * s, rr * s, rr * 2 * s),
            3.4 * s, R.P["gold"], "none")
        g += R.line('M%.1f %.1f a%.1f %.1f 0 0 0 0 %.1f' % (
            x + 74 * s + rr * s, y - 96 * s, rr * s, rr * s, rr * 2 * s),
            3.4 * s, R.P["gold"], "none")
    return g


def d_crown(x, y, s, ctx=None):
    """一顶金冠。"""
    g = R.wash(x, y - 80 * s, 120 * s, 88 * s, R.P["gold"], 0.3)
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 84 * s, y - 52 * s, 168 * s, 52 * s, -168 * s), 4.6, R.P["ink"], R.P["gold"])
    g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x - 84 * s, y - 52 * s, x - 62 * s, y - 116 * s, x - 34 * s, y - 60 * s,
        x, y - 134 * s, x + 34 * s, y - 60 * s, x + 62 * s, y - 116 * s, x + 84 * s, y - 52 * s),
        4.6, R.P["ink"], R.P["gold"])
    for dx, dy, col in ((-62, -124, R.P["rose"]), (0, -142, R.P["blue2"]), (62, -124, R.P["mint"])):
        g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="3" filter="url(#rough)"/>' % (
            x + dx * s, y + dy * s, 13 * s, col, R.P["ink"])
    for i in range(5):
        g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="2.4"/>' % (
            x - 60 * s + i * 30 * s, y - 26 * s, 8 * s,
            [R.P["rose"], R.P["blue"], R.P["mint"], R.P["lav"], R.P["peach"]][i], R.P["ink"])
    return g


def d_sword(x, y, s, ctx=None):
    """一把立着的剑（剑尖朝上）。"""
    g = R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x, y - 306 * s, x + 19 * s, y - 268 * s, x + 15 * s, y - 108 * s, x - 15 * s, y - 108 * s),
        4.6, R.P["ink"], R.P["grey"])
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 292 * s, y - 118 * s), 2.6 * s, R.P["white"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h-%d Z' % (
        x - 56 * s, y - 108 * s, 112 * s, 20 * s, 112), 4.6, R.P["ink"], R.P["gold"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h-%.1f Z' % (
        x - 11 * s, y - 88 * s, 22 * s, 56 * s, 22 * s), 4, R.P["ink"], R.P["warm2"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="4" filter="url(#rough)"/>' % (
        x, y - 22 * s, 18 * s, R.P["gold"], R.P["ink"])
    g += R.sparkle(x + 40 * s, y - 286 * s, 18 * s, R.P["white"])
    return g


def d_loaf(x, y, s, ctx=None):
    """一条刚出炉的面包。"""
    g = R.wash(x, y - 60 * s, 140 * s, 78 * s, R.P["warm"], 0.3)
    g += R.line('M%.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f Z' % (
        x - 92 * s, y - 8 * s,
        x - 92 * s, y - 96 * s, x - 42 * s, y - 118 * s, x, y - 118 * s,
        x + 42 * s, y - 118 * s, x + 92 * s, y - 96 * s, x + 92 * s, y - 8 * s),
        5, R.P["ink"], R.P["warm"])
    for dx in (-44, 0, 44):
        g += R.line('M%.1f %.1f q%.1f -%.1f %.1f -%.1f' % (
            x + dx * s - 20 * s, y - 62 * s, 20 * s, -14 * s, 40 * s, -6 * s), 4 * s, R.P["soil"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 84 * s, y - 8 * s, 168 * s), 5 * s, R.P["soil"])
    for px, py in ((x - 96 * s, y - 110 * s), (x + 90 * s, y - 124 * s), (x + 30 * s, y - 138 * s)):
        g += R.sparkle(px, py, 12 * s, R.P["cream"])
    return g


def d_teapot(x, y, s, ctx=None):
    """一只会冒热气的茶壶。"""
    g = R.wash(x, y - 78 * s, 118 * s, 92 * s, R.P["mint"], 0.34)
    for k in (-1, 0, 1):
        g += ('<path class="wx-float" style="transform-origin:%.1fpx %.1fpx;animation-delay:%dms" '
              'd="M%.1f %.1f c %.1f %.1f %.1f %.1f %.1f %.1f" fill="none" stroke="%s" '
              'stroke-width="%.1f" stroke-linecap="round" opacity=".6" filter="url(#rough)"/>' % (
                  x + k * 13 * s, y - 150 * s, k * 220,
                  x + k * 13 * s, y - 150 * s, -9 * s, -22 * s, 9 * s, -30 * s, 4 * s, -48 * s,
                  R.P["blue2"], 3.4 * s))
    g += R.line('M%.1f %.1f Q%.1f %.1f %.1f %.1f L%.1f %.1f Q%.1f %.1f %.1f %.1f Z' % (
        x - 62 * s, y - 122 * s, x - 46 * s, y - 156 * s, x - 14 * s, y - 160 * s,
        x + 14 * s, y - 160 * s, x + 46 * s, y - 156 * s, x + 62 * s, y - 122 * s),
        4, R.P["ink"], R.P["mint"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="4" filter="url(#rough)"/>' % (
        x, y - 62 * s, 66 * s, 64 * s, R.P["mint"], R.P["ink"])
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
        x + 62 * s, y - 84 * s, 40 * s, 22 * s, 22 * s, 56 * s), 12 * s, R.P["ink"], "none")
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
        x - 62 * s, y - 84 * s, -40 * s, 8 * s, -18 * s, 30 * s), 13 * s, R.P["ink"], "none")
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="3.4" filter="url(#rough)"/>' % (
        x, y - 168 * s, 11 * s, R.P["gold"], R.P["ink"])
    g += R.face(x, y - 56 * s, 26 * s)
    return g


def d_spruce(x, y, s, ctx=None):
    """一棵云杉（层层叠叠的尖三角）。"""
    g = R.line('M%.1f %.1f V%.1f' % (x, y, y - 40 * s), 12 * s, R.P["soil"])
    for i, (cy, half) in enumerate(((y - 78 * s, 78 * s), (y - 156 * s, 62 * s),
                                    (y - 228 * s, 44 * s))):
        g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
            x - half * s, cy, x, cy - 108 * s, x + half * s, cy), 4.6,
            R.P["ink"], [R.P["green2"], R.P["green2"], R.P["mint"]][i])
    g += R.line('M%.1f %.1f h%.1f' % (x - 18 * s, y - 40 * s, 36 * s), 6 * s, R.P["soil"])
    g += R.star(x, y - 358 * s, 17 * s, col=R.P["gold"])
    return g


def d_door(x, y, s, ctx=None):
    """一扇拱顶木门（门缝里透着光）。"""
    g = R.wash(x, y - 150 * s, 120 * s, 160 * s, R.P["warm"], 0.22)
    g += R.line('M%.1f %.1f V%.1f A%.1f %.1f 0 0 1 %.1f %.1f V%.1f Z' % (
        x - 88 * s, y, y - 168 * s, 88 * s, 88 * s, x + 88 * s, y - 168 * s, y),
        5.6, R.P["ink"], R.P["warm2"])
    g += R.line('M%.1f %.1f V%.1f A%.1f %.1f 0 0 1 %.1f %.1f V%.1f' % (
        x - 62 * s, y, y - 168 * s, 62 * s, 62 * s, x + 62 * s, y - 168 * s, y),
        3, R.P["soil"], "none")
    for dy in (-112, -46):
        g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
            x - 52 * s, y + dy * s, 104 * s, 50 * s, -104 * s), 3, R.P["soil"], "none")
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="3" filter="url(#rough)"/>' % (
        x + 56 * s, y - 92 * s, 11 * s, R.P["gold"], R.P["ink"])
    g += ('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z" fill="#fdf6e4" '
          'opacity="0.55" filter="url(#wc)"/>' % (
              x + 82 * s, y, x + 148 * s, y - 34 * s, x + 148 * s, y - 150 * s, x + 90 * s, y - 168 * s))
    g += R.line('M%.1f %.1f h%.1f' % (x - 104 * s, y, 208 * s), 5 * s, R.P["soil"])
    return g


def d_ladder(x, y, s, ctx=None):
    """一把木梯。"""
    g = R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x - 42 * s, y, x - 30 * s, y - 300 * s,
        x + 42 * s, y, x + 30 * s, y - 300 * s), 10 * s, R.P["soil"])
    for i in range(6):
        yy = y - 34 * s - i * 52 * s
        g += R.line('M%.1f %.1f h%.1f' % (x - 40 * s + i * 1.6 * s, yy, 80 * s), 8 * s, R.P["warm2"])
    g += R.sparkle(x + 76 * s, y - 292 * s, 15 * s, R.P["gold"])
    return g


def d_bridge(x, y, s, ctx=None):
    """一座小石桥。"""
    g = R.wash(x, y - 60 * s, 190 * s, 84 * s, R.P["grey"], 0.34)
    g += ('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f L%.1f %.1f Q%.1f %.1f %.1f %.1f Z" '
          'fill="%s" stroke="%s" stroke-width="5" filter="url(#rough)"/>' % (
              x - 176 * s, y - 40 * s, x, y - 152 * s, x + 176 * s, y - 40 * s,
              x + 176 * s, y - 8 * s, x, y - 118 * s, x - 176 * s, y - 8 * s,
              R.P["grey2"], R.P["ink"]))
    g += R.line('M%.1f %.1f Q%.1f %.1f %.1f %.1f' % (
        x - 176 * s, y - 46 * s, x, y - 158 * s, x + 176 * s, y - 46 * s), 4.4, R.P["ink"])
    for i in range(5):
        xx = x - 132 * s + i * 66 * s
        g += R.line('M%.1f %.1f v%.1f' % (xx, y - 52 * s, -46 * s), 4.4 * s, R.P["ink"])
    for i in range(4):
        xx = x - 120 * s + i * 80 * s
        g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
            xx, y - 6 * s, 40 * s, 40 * s, 80 * s), 3.4 * s, R.P["ink"], "none")
    return g


def d_post_lamp(x, y, s, ctx=None):
    """一盏街灯，灯下晕开一圈光。"""
    g = R.wash(x, y - 250 * s, 150 * s, 130 * s, R.P["gold"], 0.3)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="3.4" filter="url(#rough)"/>' % (
        x, y - 6 * s, 38 * s, 11 * s, R.P["grey2"], R.P["ink"])
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 14 * s, y - 258 * s), 10 * s, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h-%.1f Z' % (
        x - 42 * s, y - 258 * s, 84 * s, 66 * s, 84 * s), 5, R.P["ink"], R.P["gold"])
    g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x - 52 * s, y - 258 * s, x + 52 * s, y - 258 * s, x + 30 * s, y - 296 * s, x - 30 * s, y - 296 * s),
        4.4, R.P["ink"], R.P["gold"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 40 * s, y - 322 * s, 80 * s), 6 * s, R.P["ink"], "none")
    g += R.face(x, y - 224 * s, 24 * s)
    for i, rr in enumerate((26, 44)):
        g += R.sparkle(x - 66 * s - i * 30 * s, y - 200 * s + i * 22 * s, 12 * s, R.P["gold"])
    return g


def d_wheel(x, y, s, ctx=None):
    """一只木轮（会转）。"""
    import math as _m
    g = '<g class="wx-spin" style="transform-origin:%.1fpx %.1fpx">' % (x, y - 84 * s)
    g += ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="9" '
          'filter="url(#rough)"/>' % (x, y - 84 * s, 80 * s, R.P["soil"]))
    for i in range(8):
        a = i * _m.pi / 4
        g += R.line('M%.1f %.1f L%.1f %.1f' % (
            x, y - 84 * s, x + _m.cos(a) * 78 * s, y - 84 * s + _m.sin(a) * 78 * s), 4 * s, R.P["warm2"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="3.4" filter="url(#rough)"/>' % (
        x, y - 84 * s, 17 * s, R.P["warm2"], R.P["ink"])
    g += "</g>"
    g += R.line('M%.1f %.1f h%.1f' % (x, y - 4 * s, 8 * s), 4 * s, R.P["ink"], "none")
    return g


def d_spoon(x, y, s, ctx=None):
    """一把木勺。"""
    g = R.line('M%.1f %.1f q%.1f %.1f %.1f -%.1f' % (
        x - 10 * s, y - 8 * s, 8 * s, -100 * s, 26 * s, -180 * s), 11 * s, R.P["warm2"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="4" filter="url(#rough)" transform="rotate(24 %.1f %.1f)"/>' % (
        x + 24 * s, y - 214 * s, 34 * s, 44 * s, R.P["warm2"], R.P["ink"], x + 24 * s, y - 214 * s)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".7" transform="rotate(24 %.1f %.1f)"/>' % (
        x + 24 * s, y - 214 * s, 22 * s, 31 * s, R.P["cream"], x + 24 * s, y - 214 * s)
    return g


def d_drum(x, y, s, ctx=None):
    """一面小鼓 + 两根鼓槌。"""
    g = R.line('M%.1f %.1f v%.1f' % (x - 66 * s, y - 128 * s, 100 * s), 5 * s, R.P["ink"], "none")
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="5" filter="url(#rough)"/>' % (
        x, y - 128 * s, 66 * s, 22 * s, R.P["cream"], R.P["ink"])
    g += '<path d="M%.1f %.1f L%.1f %.1f A%.1f %.1f 0 0 0 %.1f %.1f L%.1f %.1f Z" fill="%s" stroke="%s" stroke-width="5" filter="url(#rough)"/>' % (
        x - 66 * s, y - 128 * s, x - 66 * s, y - 28 * s, 66 * s, 22 * s, x + 66 * s, y - 28 * s,
        x + 66 * s, y - 128 * s, R.P["rose"], R.P["ink"])
    for dy in (-96, -60):
        g += R.band(x - 68 * s, y + dy * s, 136 * s, 12 * s, R.P["gold"], 0.9)
    g += R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x - 96 * s, y - 190 * s, x - 42 * s, y - 140 * s,
        x + 96 * s, y - 190 * s, x + 42 * s, y - 140 * s), 7 * s, R.P["warm2"])
    return g


def d_shadow(x, y, s, ctx=None):
    """一道影子（一个暗色的、模糊的人形）。"""
    g = '<g opacity="0.5">'
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#2f2b3a" filter="url(#wc)"/>' % (
        x, y - 112 * s, 66 * s, 112 * s)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#2f2b3a" filter="url(#wc)"/>' % (
        x, y - 240 * s, 34 * s, 36 * s)
    g += R.line('M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f' % (
        x - 30 * s, y - 176 * s, x - 70 * s, y - 118 * s,
        x + 30 * s, y - 176 * s, x + 70 * s, y - 112 * s), 17 * s, "#2f2b3a")
    g += "</g>"
    g += R.sparkle(x + 74 * s, y - 272 * s, 14 * s, R.P["gold"])
    return g


def d_cage(x, y, s, ctx=None):
    """一只鸟笼（里面关着一只小鸟）。"""
    g = R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
        x - 24 * s, y - 312 * s, 24 * s, 26 * s, 48 * s), 5, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 66 * s, y - 288 * s, 132 * s), 7 * s, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 66 * s, y - 10 * s, 132 * s, -278 * s, -132 * s), 5, R.P["ink"], "none")
    for i in range(6):
        xx = x - 66 * s + i * 26.4 * s
        g += R.line('M%.1f %.1f V%.1f' % (xx, y - 28 * s, y - 280 * s), 3 * s, R.P["gold"])
    g += R.line('M%.1f %.1f h%.1f v%.1f h-%.1f Z' % (
        x - 74 * s, y - 28 * s, 148 * s, 28 * s, 148 * s), 6, R.P["ink"], R.P["warm2"])
    g += R.bird(x + 6 * s, y - 156 * s, 0.62)
    return g


def d_nest(x, y, s, ctx=None):
    """一个鸟巢，里面三只蛋。"""
    g = R.line('M%.1f %.1f Q%.1f %.1f %.1f %.1f Q%.1f %.1f %.1f %.1f Z' % (
        x - 92 * s, y - 66 * s, x - 84 * s, y - 4 * s, x, y - 4 * s,
        x + 84 * s, y - 4 * s, x + 92 * s, y - 66 * s),
        6, R.P["ink"], R.P["soil"])
    for i, dx in enumerate((-34, 2, 38)):
        g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="3" filter="url(#rough)"/>' % (
            x + dx * s, y - 76 * s, 22 * s, 27 * s, R.P["white"], R.P["ink"])
    for dx in (-60, -20, 20, 60, 90):
        g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
            x + dx * s, y - 30 * s, 8 * s, 14 * s, 18 * s, 22 * s), 3.4 * s, R.P["soil"], "none")
    return g


def d_egg(x, y, s, ctx=None):
    """一只大蛋（带着裂纹）。"""
    g = R.wash(x, y - 108 * s, 92 * s, 120 * s, R.P["white"], 0.4)
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="5" filter="url(#rough)"/>' % (
        x, y - 104 * s, 74 * s, 100 * s, R.P["white"], R.P["ink"])
    g += R.line('M%.1f %.1f l%.1f %.1f l%.1f -%.1f l%.1f %.1f l%.1f -%.1f' % (
        x - 30 * s, y - 146 * s, 18 * s, 14 * s, 16 * s, 26 * s, 18 * s, 22 * s, 16 * s, 30 * s),
        3.4 * s, R.P["grey2"])
    g += R.face(x, y - 92 * s, 30 * s)
    return g


def d_moth(x, y, s, ctx=None):
    """一只扑棱的飞蛾 / 蝴蝶。"""
    g = '<g class="wx-float">'
    for k in (-1, 1):
        g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".88" filter="url(#wc)" transform="rotate(%d %.1f %.1f)"/>' % (
            x + k * 42 * s, y - 22 * s, 44 * s, 30 * s, R.P["lav"], k * 26, x, y)
        g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".85" filter="url(#wc)" transform="rotate(%d %.1f %.1f)"/>' % (
            x + k * 32 * s, y + 22 * s, 32 * s, 24 * s, R.P["rose"], -k * 18, x, y)
    g += '</g>'
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 30 * s, y + 30 * s), 9 * s, R.P["ink"])
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
        x, y - 32 * s, -10 * s, -22 * s, -24 * s, -26 * s,
        x, y - 32 * s, 10 * s, -22 * s, 24 * s, -26 * s), 3 * s, R.P["ink"])
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x - 3 * s, y - 164 * s, 5 * s, R.P["gold"])
    return g


def d_kite(x, y, s, ctx=None):
    """一只风筝，尾巴一甩一甩。"""
    g = ('<path class="wx-float" style="transform-origin:%.1fpx %.1fpx" d="M%.1f %.1f L%.1f %.1f '
         'L%.1f %.1f L%.1f %.1f Z" fill="%s" stroke="%s" stroke-width="4" '
         'filter="url(#rough)"/>' % (
             x, y, x, y - 62 * s, x + 46 * s, y, x, y + 62 * s, x - 46 * s, y,
             R.P["rose"], R.P["ink"]))
    g += R.line('M%.1f %.1f V%.1f M%.1f %.1f H%.1f' % (
        x, y - 62 * s, y + 62 * s, x - 46 * s, y, x + 46 * s), 3 * s, R.P["ink"])
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
        x, y + 62 * s, 22 * s, 60 * s, -18 * s, 130 * s), 3.4 * s, R.P["gold"])
    for i in range(3):
        g += ('<path d="M%.1f %.1f l%.1f %.1f l-%.1f %.1f Z" fill="%s" opacity=".9" '
              'filter="url(#rough)"/>' % (x + 6 * s - i * 8 * s, y + 96 * s + i * 44 * s,
                                          18 * s, 10 * s, 6 * s, 20 * s, R.P["gold"]))
    return g


def d_note(x, y, s, ctx=None):
    """两个飘着的音符（会摇）。"""
    g = '<g class="wx-float">'
    for dx, dy in ((-38, 18), (26, -26)):
        g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="3" filter="url(#rough)"/>' % (
            x + dx * s, y + dy * s, 22 * s, 16 * s, R.P["blue2"], R.P["ink"])
        g += R.line('M%.1f %.1f V%.1f' % (x + dx * s + 20 * s, y + dy * s, y + dy * s - 100 * s),
                    6 * s, R.P["ink"])
        g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
            x + dx * s + 20 * s, y + dy * s - 100 * s, 26 * s, 8 * s, 22 * s, 34 * s),
            6 * s, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 16 * s, y - 82 * s, 52 * s), 7 * s, R.P["ink"])
    g += '</g>'
    return g


def d_snowflake(x, y, s, ctx=None):
    """一片雪花（会转）。"""
    import math as _m
    g = '<g class="wx-spin" style="transform-origin:%.1fpx %.1fpx">' % (x, y)
    for i in range(6):
        a = i * _m.pi / 3
        ex, ey = x + _m.cos(a) * 62 * s, y + _m.sin(a) * 62 * s
        g += R.line('M%.1f %.1f L%.1f %.1f' % (x, y, ex, ey), 5 * s, R.P["white"])
        for t in (0.55, 0.8):
            bx, by = x + (ex - x) * t, y + (ey - y) * t
            g += R.line('M%.1f %.1f l%.1f %.1f M%.1f %.1f l%.1f %.1f' % (
                bx, by, _m.cos(a + 1.1) * 20 * s, _m.sin(a + 1.1) * 20 * s,
                bx, by, _m.cos(a - 1.1) * 20 * s, _m.sin(a - 1.1) * 20 * s), 4 * s, R.P["white"])
    g += '</g>'
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y, 9 * s, R.P["white"])
    return g


def d_feather(x, y, s, ctx=None):
    """一根飘落的羽毛。"""
    g = '<g class="wx-float" style="transform-origin:%.1fpx %.1fpx">' % (x, y)
    g += R.line('M%.1f %.1f q%.1f -%.1f %.1f -%.1f' % (
        x - 26 * s, y + 72 * s, 30 * s, -74 * s, 54 * s, -148 * s), 6 * s, R.P["ink"])
    for i in range(7):
        t = i / 7.0
        bx, by = x - 26 * s + 30 * s * t, y + 72 * s - 74 * s * t
        g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".82" filter="url(#wc)" transform="rotate(-30 %.1f %.1f)"/>' % (
            bx - 22 * s, by, 24 * s, 10 * s, R.P["white"], bx, by)
    g += '</g>'
    return g


def d_jar(x, y, s, ctx=None):
    """一只陶罐（细颈、圆腹、带裂纹）。"""
    g = R.wash(x, y - 80 * s, 110 * s, 100 * s, R.P["soil"], 0.24)
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f q%.1f %.1f %.1f %.1f q%.1f -%.1f %.1f -%.1f '
                'q%.1f -%.1f %.1f -%.1f Z' % (
                    x - 36 * s, y - 178 * s, -14 * s, 22 * s, -58 * s, 34 * s,
                    -10 * s, 46 * s, 22 * s, 62 * s, 46 * s, 62 * s,
                    14 * s, -22 * s, 58 * s, -34 * s, 10 * s, -46 * s),
                5, R.P["ink"], R.P["warm2"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="4" filter="url(#rough)"/>' % (
        x, y - 180 * s, 40 * s, 13 * s, R.P["soil"], R.P["ink"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".8" filter="url(#wc)"/>' % (
        x, y - 180 * s, 30 * s, 8 * s, "#5f8fa8")
    g += R.line('M%.1f %.1f l%.1f %.1f l%.1f -%.1f l%.1f %.1f' % (
        x - 26 * s, y - 118 * s, 16 * s, 12 * s, 14 * s, 24 * s, 16 * s, 20 * s), 3 * s, R.P["ink"])
    g += R.face(x - 2 * s, y - 74 * s, 28 * s)
    return g


def d_well(x, y, s, ctx=None):
    """一口村井：石圈 + 木架 + 吊桶。"""
    g = R.wash(x, y - 90 * s, 130 * s, 100 * s, R.P["grey"], 0.3)
    g += R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 110 * s, y - 74 * s, 220 * s, 74 * s, -220 * s), 5, R.P["ink"], R.P["grey2"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="5" filter="url(#rough)"/>' % (
        x, y - 74 * s, 110 * s, 30 * s, "#4f6a80", R.P["ink"])
    for i in range(5):
        g += R.line('M%.1f %.1f V%.1f' % (x - 88 * s + i * 44 * s, y - 74 * s, y), 3 * s, R.P["ink"])
    g += R.line('M%.1f %.1f V%.1f M%.1f %.1f V%.1f' % (
        x - 96 * s, y - 76 * s, y - 296 * s, x + 96 * s, y - 76 * s, y - 296 * s), 10 * s, R.P["soil"])
    g += R.line('M%.1f %.1f L%.1f %.1f L%.1f %.1f Z' % (
        x - 118 * s, y - 296 * s, x, y - 366 * s, x + 118 * s, y - 296 * s), 5, R.P["ink"], R.P["rose"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 104 * s, y - 292 * s, 208 * s), 8 * s, R.P["soil"])
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 292 * s, y - 178 * s), 3.4 * s, R.P["gold"])
    g += R.line('M%.1f %.1f h%.1f l-%.1f %.1f h-%.1f Z' % (
        x - 30 * s, y - 178 * s, 60 * s, -10 * s, 34 * s, -50 * s), 4.4, R.P["ink"], R.P["warm2"])
    g += R.sparkle(x + 112 * s, y - 226 * s, 15 * s, R.P["gold"])
    return g


def d_bucket(x, y, s, ctx=None):
    """一只木水桶。"""
    g = R.line('M%.1f %.1f h%.1f l-%.1f %.1f h-%.1f Z' % (
        x - 62 * s, y - 100 * s, 124 * s, -20 * s, 100 * s, -84 * s), 5, R.P["ink"], R.P["warm2"])
    g += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" opacity=".75" filter="url(#wc)"/>' % (
        x, y - 100 * s, 60 * s, 15 * s, "#5f8fa8")
    for dy in (-84, -58, -28):
        g += R.band(x - 62 * s - (dy + 84) * 0.2 * s, y + dy * s,
                    124 * s + (dy + 84) * 0.4 * s, 10 * s, R.P["soil"], 0.9)
    g += R.line('M%.1f %.1f a%.1f %.1f 0 0 1 %.1f 0' % (
        x - 52 * s, y - 100 * s, 52 * s, 58 * s, 104 * s), 5 * s, R.P["ink"])
    return g


def d_cart(x, y, s, ctx=None):
    """一辆两轮小车。"""
    g = R.line('M%.1f %.1f h%.1f v%.1f h%.1f Z' % (
        x - 96 * s, y - 156 * s, 192 * s, 76 * s, -192 * s), 5, R.P["ink"], R.P["warm2"])
    for dx in (-56, -18, 20, 58):
        g += R.line('M%.1f %.1f V%.1f' % (x + dx * s, y - 156 * s, y - 82 * s), 3.4 * s, R.P["soil"])
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
        x + 94 * s, y - 140 * s, 46 * s, -14 * s, 62 * s, 34 * s), 7 * s, R.P["soil"])
    for dx in (-52, 52):
        g += ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="8" '
              'filter="url(#rough)"/>' % (x + dx * s, y - 44 * s, 40 * s, R.P["soil"]))
        g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="3.4"/>' % (
            x + dx * s, y - 44 * s, 8 * s, R.P["warm2"], R.P["ink"])
    return g


def d_violin(x, y, s, ctx=None):
    """一把小提琴 + 琴弓。"""
    g = R.line('M%.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f '
               'L%.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f Z' % (
                   x - 38 * s, y - 176 * s,
                   x - 70 * s, y - 158 * s, x - 76 * s, y - 124 * s, x - 38 * s, y - 96 * s,
                   x - 72 * s, y - 72 * s, x - 70 * s, y - 24 * s, x - 26 * s, y - 6 * s,
                   x + 26 * s, y - 6 * s,
                   x + 70 * s, y - 24 * s, x + 72 * s, y - 72 * s, x + 38 * s, y - 96 * s,
                   x + 76 * s, y - 124 * s, x + 70 * s, y - 158 * s, x + 38 * s, y - 176 * s),
               5, R.P["ink"], R.P["warm2"])
    g += R.line('M%.1f %.1f V%.1f' % (x, y - 176 * s, y - 268 * s), 9 * s, R.P["soil"])
    g += R.line('M%.1f %.1f q%.1f %.1f %.1f %.1f' % (
        x, y - 268 * s, -20 * s, -16 * s, -24 * s, -30 * s), 7 * s, R.P["soil"])
    for dx in (-14, -5, 4, 13):
        g += R.line('M%.1f %.1f V%.1f' % (x + dx * s, y - 172 * s, y - 14 * s), 2 * s, R.P["white"])
    g += R.line('M%.1f %.1f V%.1f' % (x - 20 * s, y - 118 * s, y - 78 * s), 3 * s, R.P["ink"])
    g += R.line('M%.1f %.1f V%.1f' % (x + 20 * s, y - 118 * s, y - 78 * s), 3 * s, R.P["ink"])
    g += R.line('M%.1f %.1f h%.1f' % (x - 32 * s, y - 56 * s, 64 * s), 5 * s, R.P["soil"])
    g += R.line('M%.1f %.1f L%.1f %.1f' % (
        x + 34 * s, y - 44 * s, x + 158 * s, y - 244 * s), 6 * s, R.P["soil"])
    g += R.line('M%.1f %.1f L%.1f %.1f' % (
        x + 20 * s, y - 64 * s, x + 144 * s, y - 264 * s), 2.6 * s, R.P["white"])
    g += R.sparkle(x + 104 * s, y - 306 * s, 18 * s, R.P["gold"])
    return g


def d_kettle(x, y, s, ctx=None):
    """小水壶（套用现成画法，把底面对齐到 y）。"""
    return R.kettle(x, y - 34 * s, s)


def d_mug(x, y, s, ctx=None):
    return R.mug(x, y - 22 * s, s)


def d_lamp(x, y, s, ctx=None):
    return R.lamp(x, y - 40 * s, s)


def d_book(x, y, s, ctx=None):
    return R.book_open(x, y - 40 * s, s)


def d_cat(x, y, s, ctx=None):
    return R.cat(x, y - 30 * s, s)


def d_person(x, y, s, ctx=None):
    return R.person(x, y - 52 * s, s)


def d_kid(x, y, s, ctx=None):
    return R.kid(x, y, s)


def d_kid_umbrella(x, y, s, ctx=None):
    return R.kid(x, y, s, umbrella=R.P["rose"])


def d_tree(x, y, s, ctx=None):
    return R.tree(x, y, s)


def d_flower(x, y, s, ctx=None):
    return R.flower(x, y, s, R.P["pink"])


def d_sprout(x, y, s, ctx=None):
    return R.sprout(x, y - 48 * s, s)


def d_house(x, y, s, ctx=None):
    return R.house(x, y, s * 150, s * 126, R.P["cream"], R.P["rose"])


def d_boat(x, y, s, ctx=None):
    return R.boat(x, y - 12 * s, s)


def d_bird(x, y, s, ctx=None):
    return R.bird(x, y, s)


def d_nightingale(x, y, s, ctx=None):
    return R.bird(x, y, s, col="#a9886a")


def d_moon(x, y, s, ctx=None):
    """带缺口的月牙（缺口用当前背景的「天色」咬出来）。"""
    sky = (ctx or {}).get("sky") or R.P["night"]
    r = 74 * s
    g = '<g class="wx-float" style="transform-origin:%.1fpx %.1fpx">' % (x, y)
    g += R.wash(x, y, r, r, R.P["gold"], 0.95)
    g += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" filter="url(#wc)"/>' % (
        x + r * 0.58, y - r * 0.12, r * 0.86, sky)
    g += R.face(x - r * 0.48, y + r * 0.06, r * 0.34)
    g += '</g>'
    return g


def d_star(x, y, s, ctx=None):
    g = R.star(x, y, 46 * s)
    g += R.star(x + 62 * s, y + 40 * s, 26 * s)
    g += R.star(x - 58 * s, y + 30 * s, 22 * s)
    return g


def d_cloud(x, y, s, ctx=None):
    g = R.cloud(x, y, s * 1.05, op=0.9)
    g += R.cloud(x + 150 * s, y + 54 * s, s * 0.6, op=0.7)
    return g


def d_sparkles(x, y, s, ctx=None):
    g = ""
    for dx, dy, r in ((-56, -30, 24), (30, -60, 34), (66, 24, 20), (-20, 46, 16)):
        g += R.sparkle(x + dx * s, y + dy * s, r * s, R.P["gold"])
    return g


# ============================================================ 主体物目录
# h = 这个造型在 s=1 时**画出来大约多大**（单位：画布 px）。
# 缩放不再手调，而是按「想让它占多大」反算：地面物目标高 ~232px（hero 槽 base 1.30），
# 空中物目标直径 ~168px（air 槽 base 1.15）。不然手调的 0.9 / 0.95 会让钥匙和帽子一样大。
TARGET_GROUND, TARGET_AIR = 232.0, 168.0
BASE_HERO, BASE_AIR = 1.30, 1.15


def _p(name, forms, slot, draw, h, k=1.0, anim="wx-float"):
    """k = 相对「目标大小」的额外系数：人/猫/杯子这类「本来就该比别人矮」的东西调小一点。"""
    base = BASE_AIR if slot == "air" else BASE_HERO
    target = TARGET_AIR if slot == "air" else TARGET_GROUND
    scale = round(max(0.35, min(3.6, target * k / (base * float(h)))), 3)
    return name, {"w": tuple(forms.split()), "slot": slot, "draw": draw,
                  "h": h, "k": k, "scale": scale, "anim": anim}


PARTS = dict([
    # ---- 地面物 ----
    _p("key", "key keys keyhole keyholes unlock unlocks unlocked locksmith keyring",
       "ground", d_key, 240),
    _p("needle", "needle needles sew sews sewing stitched stitch stitches thread "
                 "threading mend mends seam tailor", "ground", d_needle, 310),
    _p("coin", "coin coins money penny pennies payment paid price wealth fortune "
               "treasure purse silver", "ground", d_coin, 175, 0.85),
    _p("clock", "clock clocks watch watches hour hours minute minutes pendulum "
                "ticking chime chimes time", "ground", d_clock, 385),
    _p("candle", "candle candles wax wick flame flames burn burns burned burnt lit",
       "ground", d_candle, 200, 0.9),
    _p("lantern", "lantern lanterns glowing lantern-light", "ground", d_lantern, 275),
    _p("snowman", "snowman snowmen snowball snowball-fight", "ground", d_snowman, 390),
    _p("mirror", "mirror mirrors reflect reflects reflection reflected",
       "ground", d_mirror, 290),
    _p("letter", "letter letters envelope envelopes mail posted post stamp stamps "
                 "correspondence", "ground", d_letter, 190, 0.85),
    _p("chest", "chest chests box boxes drawer drawers trunk lid cabinet",
       "ground", d_chest, 170, 0.85),
    _p("basket", "basket baskets woven weave carries carried hamper", "ground", d_basket, 175, 0.85),
    _p("shoe", "shoe shoes boot boots sock socks heel sole", "ground", d_shoe, 200, 0.78),
    _p("hat", "hat hats cap caps bonnet brim", "ground", d_hat, 110, 0.85),
    _p("bell", "bell bells ring rings ringing rang toll tolls", "ground", d_bell, 155, 0.92),
    _p("crown", "crown crowns king kings queen queens throne royal majesty prince princess",
       "ground", d_crown, 155),
    _p("sword", "sword swords blade soldier soldiers warrior knight battle fought",
       "ground", d_sword, 315),
    _p("loaf", "loaf loaves bread bake baked baker oven dough flour crust", "ground", d_loaf, 130, 0.78),
    _p("teapot", "teapot teapots tea pour pours brewing", "ground", d_teapot, 205, 0.9),
    _p("spruce", "spruce pines pine evergreen conifers conifer", "ground", d_spruce, 385),
    _p("door", "door doors doorway gate gates threshold knock knocked shut", "ground", d_door, 270),
    _p("ladder", "ladder ladders climb climbs climbed rung rungs upstairs", "ground", d_ladder, 310),
    _p("bridge", "bridge bridges arch arches cross crosses crossing span", "ground", d_bridge, 170),
    _p("post_lamp", "streetlight streetlamp lamppost lamp-post gaslight", "ground", d_post_lamp, 335),
    _p("wheel", "wheel wheels wagon spoke spokes spinning", "ground", d_wheel, 180, 0.85),
    _p("spoon", "spoon spoons stir stirred ladle scoop", "ground", d_spoon, 260, 0.78),
    _p("drum", "drum drums beat beats beating rhythm march marched", "ground", d_drum, 200, 0.85),
    _p("shadow", "shadow shadows shade silhouette ghost ghostly", "ground", d_shadow, 285),
    _p("cage", "cage cages birdcage bars prison imprisoned trapped", "ground", d_cage, 330),
    _p("nest", "nest nests hatched hatch brood", "ground", d_nest, 110, 0.72),
    _p("egg", "egg eggs shell shells yolk", "ground", d_egg, 220, 0.65),
    _p("jar", "jar jars pot pots clay pitcher pitchers jug jugs vessel", "ground", d_jar, 200, 0.9),
    _p("well", "well wells fountain fountains spring springs", "ground", d_well, 375),
    _p("bucket", "bucket buckets pail pails", "ground", d_bucket, 175, 0.85),
    _p("cart", "cart carts wagon wagons barrow barrows", "ground", d_cart, 195),
    _p("violin", "violin violins fiddle fiddles", "ground", d_violin, 320),
    # ---- 地面物（复用已画好的通用造型）----
    _p("kettle", "kettle kettles boil boils boiling steam whistle", "ground", d_kettle, 140, 0.72),
    _p("mug", "mug mugs cup cups coffee sip drank drink", "ground", d_mug, 80, 0.7),
    _p("lamp", "lamp lamps desk-lamp reading-light lampshade", "ground", d_lamp, 140, 0.85),
    _p("book", "book books page pages read reading write wrote written words word "
               "story stories tale ink", "ground", d_book, 150, 0.95),
    _p("cat", "cat cats kitten kittens purr purrs whiskers furry", "ground", d_cat, 60, 0.72),
    _p("person", "man men woman women villagers villager stranger merchant elder "
                 "grandmother grandfather somebody someone", "ground", d_person, 115, 0.78),
    _p("kid", "child children boy boys girl girls kid kids", "ground", d_kid, 145, 0.7),
    _p("kid_umbrella", "umbrella umbrellas raincoat", "ground", d_kid_umbrella, 245, 0.7),
    _p("tree", "tree trees branch branches leaves leaf grove orchard", "ground", d_tree, 165),
    _p("flower", "flower flowers blossom blossoms bloom blooms petals", "ground", d_flower, 205, 0.9),
    _p("sprout", "sprout sprouts seed seeds seedling planted planting", "ground", d_sprout, 175, 0.9),
    _p("house", "house houses cottage cottages chimney roof rooftops", "ground", d_house, 230),
    _p("boat", "boat boats ship ships sail sails sailed vessel rowing", "ground", d_boat, 115, 0.95),
    # ---- 空中物 ----
    _p("moth", "moth moths butterfly butterflies flutter flutters winged", "air", d_moth, 105),
    _p("kite", "kite kites", "air", d_kite, 135),
    _p("note", "music melody melodies song songs tune tunes singing sang sung chorus",
       "air", d_note, 195),
    _p("snowflake", "snowflake snowflakes frost frosty ice", "air", d_snowflake, 135),
    _p("feather", "feather feathers plume quill", "air", d_feather, 230),
    _p("bird", "bird birds swallow swallows sparrow sparrows flock flocks", "air", d_bird, 65),
    _p("nightingale", "nightingale nightingales songbird lark", "air", d_nightingale, 65),
    _p("moon", "moon moonlight crescent moonlit lunar", "air", d_moon, 155),
    _p("star", "star stars starlight constellation twinkle twinkles", "air", d_star, 55),
    _p("cloud", "cloud clouds haze misty fog", "air", d_cloud, 195),
    _p("sparkles", "sparkle sparkles glimmer glimmers shimmer glitter",
       "air", d_sparkles, 95),
])

PART_ORDER = list(PARTS)

# 装饰填充物（why 为空、标 decor，不算「贴题」）——只记名字，颜色到画的时候再取
DECOR_GROUND = ["flower", "sprout"]
DECOR_AIR = ["cloud", "bird"]


# ============================================================ 词命中
_RE_CACHE = {}


def _hit_re(forms):
    r = _RE_CACHE.get(forms)
    if r is None:
        r = re.compile(r"\b(?:" + "|".join(re.escape(f) for f in forms) + r")\b")
        _RE_CACHE[forms] = r
    return r


def hits(text_low, forms):
    """返回 text 里真实出现过的触发词（去重、保持 forms 顺序）。
    注意：forms 必须是「词的元组」；传字符串会被当成逐字符拆开（曾经整段配图全错）。"""
    if not text_low:
        return []
    if isinstance(forms, str):
        forms = tuple(forms.split())
    else:
        forms = tuple(forms)
    found = set(m.group(0) for m in _hit_re(forms).finditer(text_low))
    return [f for f in forms if f in found]


_BG_FORMS = {}
for _name in BG_ORDER:
    _BG_FORMS[_name] = tuple(BG[_name][0].split())


def _bg_score(low, tl):
    out = {}
    for name in BG_ORDER:
        if name == "plain":
            continue
        n = len(hits(low, _BG_FORMS[name]))
        m = len(hits(tl, _BG_FORMS[name]))
        if n or m:
            out[name] = n * 2 + m
    return out


def _part_score(low, tl, book_low):
    out = {}
    for name, spec in PARTS.items():
        n = len(hits(low, spec["w"]))
        m = len(hits(tl, spec["w"]))
        b = len(hits(book_low, spec["w"])) if book_low else 0
        if n or m or b:
            sc = n * 3.0 + m * 2.0 + b * 0.35
            # 命中越多越靠前；同分时把「能贴到本段/标题」的排前面（b 只是兜底佐证）
            out[name] = (sc, n * 3.0 + m * 2.0)
    return out


# ============================================================ 排片
def _best_bg(para_low, title_low, avoid_bg, used_bg, day_bias=0, fallback=()):
    """挑背景。优先级：既没在最近几天用过、也没在本篇用过的 → 本篇没用过的 →
    最近几天没用过的 → 候选池里随便一个。
    fallback = 全篇场景词排出来的背景序（这段几乎没提「在哪里」时借它补候选，
    否则一整本童话会关在同一间屋子里）。"""
    sc = _bg_score(para_low, title_low)
    ranked = sorted(sc.items(), key=lambda kv: (-kv[1], BG_ORDER.index(kv[0])))
    if not ranked:
        ranked = []
    band = [n for n, v in ranked if v >= (ranked[0][1] - 1)] if ranked else []
    # 只有一两个候选时放宽到前三名
    if len(band) < 2:
        band = [n for n, _v in ranked[:3]]
    if len(band) < 3 and fallback:
        band = band + [n for n in fallback if n not in band]
    if not band:
        return None
    for pool in ([n for n in band if n not in avoid_bg and n not in used_bg],
                 [n for n in band if n not in used_bg],
                 [n for n in band if n not in avoid_bg]):
        if pool:
            return pool[day_bias % len(pool)]
    return band[day_bias % len(band)]


def _pick_parts(para_low, title_low, book_low, want, used_parts, avoid_ground, avoid_air,
                day_bias=0):
    """挑主体物。分两档：
      strong —— 本段或标题里**真有那个词**（why 能落到这一段）；
      weak   —— 只有本篇正文别处出现过（why 只能记到全书上）。
    strong 优先；strong 不足 2 个时才补 1 个 weak 凑画面。"""
    sc = _part_score(para_low, title_low, book_low)
    if not sc:
        return []
    ranked = sorted(sc.items(), key=lambda kv: (-kv[1][1], -kv[1][0], PART_ORDER.index(kv[0])))
    strong = [n for n, v in ranked if v[1] > 0 and n not in used_parts]
    weak = [n for n, v in ranked if v[1] <= 0 and n not in used_parts]

    ground, air = [], []
    for name in strong:
        spec = PARTS[name]
        if spec["slot"] == "air":
            if len(air) >= 2:
                continue
            air.append(name)
        else:
            if len(ground) >= 3:
                continue
            ground.append(name)

    picks = []
    want_g = max(1, want - len(air)) if want > 1 else 1
    for name in ground[:want_g]:
        picks.append(name)
    for name in air[:max(0, want - len(picks))]:
        picks.append(name)

    if len(picks) < 2:
        for name in weak:
            if name in picks:
                continue
            if PARTS[name]["slot"] == "air" and any(PARTS[p]["slot"] == "air" for p in picks):
                continue
            picks.append(name)
            break
    if not picks and ranked:
        picks = [ranked[0][0]]
    return picks[:max(want, 2)]


def _why_for(name, para_low, title_low):
    """这个主体物是被哪个词引出来的 —— 必须真在段/标题里出现。"""
    forms = PARTS[name]["w"]
    for scope, txt in (("para", para_low), ("title", title_low)):
        h = hits(txt, forms)
        if h:
            return h[0], scope
    return "", "deco"


def _why_in(name, para_low, title_low, book_low):
    """先找「这一段/标题」里的出处；找不到才退到「全篇正文」里的出处。"""
    why, scope = _why_for(name, para_low, title_low)
    if why:
        return why, scope
    h = hits(book_low or "", PARTS[name]["w"])
    if h:
        return h[0], "book"
    return "", "deco"


def plan_paragraph(para, title, book_text, used_bg, used_sig, avoid_bg, avoid_parts,
                   day_bias=0, want=3, fallback_bg=()):
    """给一段童话排一张分镜。返回 plan dict。"""
    low, tl = (para or "").lower(), (title or "").lower()
    book_low = (book_text or "").lower()

    bgn = _best_bg(low, tl, avoid_bg, used_bg, day_bias, fallback_bg)
    if bgn is None:
        bgn = "plain"

    picks = _pick_parts(low, tl, book_low, want, set(), avoid_bg, avoid_parts, day_bias)
    parts = []
    for name in picks:
        why, scope = _why_in(name, low, tl, book_low)
        spec = PARTS[name]
        parts.append({"name": name, "why": why, "scope": scope,
                      "decor": not why, "slot": None, "s": spec["scale"]})
    # 兜底：一段里一个主体物都命中不了 → 用全篇正文里最能代表这段的东西顶上
    if not parts:
        sc = _part_score(low, tl, book_low)
        for name, _v in sorted(sc.items(), key=lambda kv: -kv[1][0]):
            why, scope = _why_in(name, low, tl, book_low)
            if why:
                spec = PARTS[name]
                parts.append({"name": name, "why": why, "scope": scope,
                              "decor": False, "slot": None, "s": spec["scale"]})
                break

    plan = {"bg": bgn, "parts": parts, "para": para, "sig": ""}
    _assign_slots(plan)
    plan["sig"] = signature(plan)

    # 跨天/同书防重：换个同样贴题的背景，再不行换一个主体物
    if plan["sig"] in used_sig or (bgn in avoid_bg and bgn != "plain"):
        alt = _best_bg(low, tl, avoid_bg | {bgn}, used_bg | {bgn}, day_bias + 1, fallback_bg)
        if alt and alt != bgn:
            plan["bg"] = alt
            plan["sig"] = signature(plan)
    if plan["sig"] in used_sig and len(plan["parts"]) > 1:
        plan["parts"] = plan["parts"][:-1]
        _assign_slots(plan)
        plan["sig"] = signature(plan)
    return plan


def _assign_slots(plan):
    g_i = a_i = 0
    for p in plan["parts"]:
        air = PARTS[p["name"]]["slot"] == "air"
        pool = AIR_SLOTS if air else GROUND_SLOTS
        idx = a_i if air else g_i
        p["slot"] = pool[min(idx, len(pool) - 1)]
        if air:
            a_i += 1
        else:
            g_i += 1


def signature(plan):
    return "%s|%s" % (plan["bg"], "+".join(sorted(p["name"] for p in plan["parts"])))


def plan_book(paragraphs, title="", history=None, day_bias=None):
    """给整篇童话排片：每段一张，段与段之间不重样，也不和最近几天重样。"""
    hist = normalize_history(history)
    avoid_bg = set(hist["bgs"])
    used_sig = set(hist["sigs"])
    book_text = " ".join(paragraphs)
    if day_bias is None:
        day_bias = hist["count"]
    # 全篇场景词排出来的背景序：给「这段没提在哪里」的段落当候选池
    brank = _bg_score(book_text.lower(), (title or "").lower())
    fallback_bg = [n for n, _v in sorted(brank.items(), key=lambda kv: (-kv[1], BG_ORDER.index(kv[0])))]
    if not fallback_bg:
        fallback_bg = [n for n in BG_ORDER if n != "plain"]
    used_bg, plans = set(), []
    for i, para in enumerate(paragraphs):
        pl = plan_paragraph(para, title, book_text, used_bg, used_sig, avoid_bg,
                            set(), day_bias + i, want=3, fallback_bg=fallback_bg)
        used_bg.add(pl["bg"])
        used_sig.add(pl["sig"])
        plans.append(pl)
    return plans


def plan_cover(paragraphs, title="", history=None, day_bias=None):
    """封面：拿「标题 + 全文」排片，保证标题里的东西一定出现在封面上。"""
    hist = normalize_history(history)
    if day_bias is None:
        day_bias = hist["count"]
    tl = (title or "").lower()
    book = " ".join(paragraphs)
    low = (tl + " " + book).lower()
    bgn = _best_bg(low, tl, set(hist["bgs"]), set(), day_bias) or "plain"
    sc = _part_score(low, tl, book.lower())
    ranked = sorted(sc.items(), key=lambda kv: (-kv[1][1], -kv[1][0], PART_ORDER.index(kv[0])))
    parts, air_n = [], 0
    for name, _v in ranked:
        spec = PARTS[name]
        if name in [p["name"] for p in parts]:
            continue
        if spec["slot"] == "air" and air_n >= 1:
            continue
        why, scope = _why_for(name, low, tl)
        if not why:
            continue
        if spec["slot"] == "air":
            air_n += 1
        parts.append({"name": name, "why": why, "scope": scope, "decor": False,
                      "slot": None, "s": spec["scale"]})
        if len(parts) >= 4:
            break
    if not parts:
        parts = [{"name": "book", "why": "", "scope": "deco", "decor": True,
                  "slot": None, "s": 1.0}]
    plan = {"bg": bgn, "parts": parts, "para": title, "sig": ""}
    _assign_slots(plan)
    plan["sig"] = signature(plan)
    return plan


# ============================================================ 台账（跨天防重）
LEDGER_NAME = "art-ledger.json"
LEDGER_KEEP = 60      # 最多留 60 天
RECENT_DAYS = 3       # 「最近几天」算几天


def _data_dir(data_dir=None):
    if data_dir:
        return data_dir
    return os.environ.get("IELTS_DATA_DIR") or os.path.expanduser("~/.workbuddy/ielts-prep")


def ledger_path(data_dir=None):
    return os.path.join(_data_dir(data_dir), LEDGER_NAME)


def normalize_history(history, exclude_date=None):
    if isinstance(history, dict):
        days = history.get("days") or []
    else:
        days = history or []
    days = [d for d in days if isinstance(d, dict)]
    if exclude_date:
        # 重出同一天时，不要被「这一天自己上一次的选择」挡住
        days = [d for d in days if d.get("date") != exclude_date]
    recent = days[-RECENT_DAYS:]
    return {"count": len(days),
            "bgs": [b for d in recent for b in (d.get("bgs") or [])],
            "sigs": [s for d in recent for s in (d.get("sigs") or [])],
            "days": days}


def load_history(data_dir=None, exclude_date=None):
    p = ledger_path(data_dir)
    try:
        with open(p, encoding="utf-8") as f:
            return normalize_history(json.load(f), exclude_date=exclude_date)
    except Exception:
        return normalize_history([], exclude_date=exclude_date)


def save_history(date, plans, data_dir=None, cover=None):
    """把今天用过的背景/组合记进台账（供明天避开）。"""
    p = ledger_path(data_dir)
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {"days": []}
    days = [d for d in (raw.get("days") or []) if isinstance(d, dict) and d.get("date") != date]
    allp = list(plans) + ([cover] if cover else [])
    days.append({"date": date,
                 "bgs": sorted(set(pl["bg"] for pl in allp)),
                 "sigs": sorted(set(pl["sig"] for pl in allp)),
                 "parts": sorted(set(p["name"] for pl in allp for p in pl["parts"]))})
    raw["days"] = days[-LEDGER_KEEP:]
    raw["version"] = ART_VERSION
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
        return p
    except Exception:
        return None


# ============================================================ 渲染
def _decor(plan, ctx):
    """补一点点填充物让画面不空（why 为空、标 decor，不算「贴题」，也不参与防重）。
    只在主体物少的时候补，免得每段都飘同一朵云。"""
    used = set((p.get("slot") or "") for p in plan["parts"])
    out = []
    if len(plan["parts"]) >= 3:
        return out
    interior = plan["bg"] in ("room", "attic", "corridor", "shop")
    if not interior and "air_right" not in used:
        out.append({"name": "cloud", "slot": "air_right",
                    "s": PARTS["cloud"]["scale"] * 0.8, "why": "", "decor": True})
    if plan["bg"] not in ("room", "attic", "corridor", "shop", "sea", "market", "street",
                          "street_night") and "far_left" not in used:
        out.append({"name": "flower", "slot": "far_left",
                    "s": PARTS["flower"]["scale"] * 0.5, "why": "", "decor": True})
    return out


def svg_storyboard(plan):
    """把一个 plan 画成 <svg class="art-svg">。"""
    ctx = {"bg": plan["bg"], "sky": BG.get(plan["bg"], BG["plain"])[2]}
    items = [dict(name=p["name"], slot=p["slot"], s=p.get("s", 1.0),
                  why=p.get("why", ""), decor=p.get("decor", False)) for p in plan["parts"]]
    items += _decor(plan, ctx)
    by_slot = {}
    for it in items:
        by_slot.setdefault(it["slot"], []).append(it)

    body = BG.get(plan["bg"], BG["plain"])[1]()
    for slot in SLOT_DRAW_ORDER:
        for it in by_slot.get(slot, []):
            spec = PARTS.get(it["name"])
            if not spec:
                continue
            x, y, base = slot_xy(slot)
            sc = base * it["s"]
            inner = spec["draw"](x, y, sc, ctx)
            anim = spec["anim"] if not it["decor"] else "wx-float"
            body += ('<g class="%s" data-obj="%s" style="transform-origin:%.0fpx %.0fpx">%s</g>'
                     % (anim, it["name"], x, y, inner))
    body += ('<rect class="pgrain" x="0" y="0" width="%d" height="%d" fill="#6f6455" '
             'filter="url(#paper)"/>' % (R.W, R.H))
    return ('<svg class="art-svg" viewBox="0 0 %d %d" preserveAspectRatio="xMidYMid meet" '
            'xmlns="http://www.w3.org/2000/svg" role="img" data-art="storyboard" '
            'data-bg="%s">%s%s</svg>' % (R.W, R.H, plan["bg"], R.defs(), body))


def describe(plan):
    """给日志用的一行说明：背景 + 主体物(why)。"""
    bits = []
    for p in plan["parts"]:
        bits.append("%s(%s)" % (p["name"], p["why"] or "deco"))
    return "%s → %s" % (plan["bg"], ", ".join(bits) or "—")
