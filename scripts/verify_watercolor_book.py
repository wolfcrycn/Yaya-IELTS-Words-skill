#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_watercolor_svg_book.py 的回归测试。

用法：
    python3 scripts/verify_watercolor_book.py              # 静态 + JS 语法/正则 + 朗读行为
    python3 scripts/verify_watercolor_book.py --no-browser # 只跑不需要 Chrome 的部分

退出码 0 = 通过；非 0 = 有回归。

守的都是**踩过就忘**的坑：

A. 静态（纯 Python，秒出）
   * 场景函数里手写 %-格式化数错占位符 → 整片 TypeError（hills / book_open 都中过）；
   * `#rough` 滤镜用 objectBoundingBox → 直线包围盒宽或高为 0 → 整条线被裁掉
     （太阳光芒、花茎、书页字行就这么消失过），必须 userSpaceOnUse；
   * 场景里没有小角色（退回「砖头 + 火柴人」）；
   * HTML 少了三档语言按钮 / 正文容器 / 纸纹层 / 朗读按钮；
   * 自动配景重复或关键词完全失效。

A2. 故事分镜（art_storyboard.py，2026-09-14 加）
   * 59 个主体物 + 17 个背景层逐个试画（同样防 %-占位符数错）；
   * `hits()` 必须按「单词」匹配：传字符串而被逐字符拆开 → 整篇配图乱套（踩过）；
   * **贴题**：每段每个主体物都要说得出「被哪个词引出来」，且那个词真在段/标题/正文里；
     换题材（钥匙篇 vs 陶罐篇）主体物必须换掉；
   * **跨天不重样**：同一篇童话第二天重排，「背景|主体物」组合不许和台账里重复；
   * 台账读写（写临时目录，绝不碰真实 ielts-prep 数据）；
   * 封面必须包含标题里的主体物；老的 9 个成品场景仍可用（--art scene）。

B. JS 语法与正则（需要 node，缺了会跳过）
   * `JS` 一旦被写成 r\"\"\"，`\\\\b` 会原样输出 → 正则退化成「字面反斜杠 + b」，
     **金色词高亮整体失效**、esc() 变空操作。这里真跑一遍 node 断言高亮能命中。

C. 朗读开关行为（需要 Chrome，缺了会跳过）
   * 用桩件替掉 speechSynthesis，真点按钮：点一次开始、再点一次停止；
   * **关键**：cancel() 会触发当前 utterance 的 onerror('canceled')，
     若回调没被「代次」令牌拦住，点了停止还会接着念下一行 —— 这里真断言「停止后 0 次发声」；
   * 停止后金色词高亮要复原（朗读时套的 .wd 外壳会把它顶掉）。
"""

import argparse
import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "make_watercolor_svg_book.py")

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    shutil.which("google-chrome"),
    shutil.which("chromium"),
    shutil.which("chromium-browser"),
]
NODE_CANDIDATES = [
    os.environ.get("NODE_BIN"),
    shutil.which("node"),
    # WorkBuddy 托管的 Node（换机器/换用户名也不会失效）
    os.path.expanduser("~/.workbuddy/binaries/node/versions/22.22.2-3/bin/node"),
]

FAILS = []
OKS = []
SKIPS = []


def check(cond, label, detail=""):
    if cond:
        OKS.append(label)
    else:
        FAILS.append("%s%s" % (label, ("  ← " + detail) if detail else ""))


def find_first(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def load():
    spec = importlib.util.spec_from_file_location("wcbook", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SAMPLE = {
    "title": "Verify Me",
    "date": "2026-01-01",
    "subtitle": "测试",
    "words": ["foundation", "sustainable", "analyse"],
    "poem": ["A city wakes and does not analyse",
             "",
             "The kettle hums on the cold floor, a foundation",
             "",
             "Rain on the field at last, sustainable and slow"],
}


def sample_panels(m):
    st = m.split_stanzas(SAMPLE["poem"])
    return st, [{"en": s, "zh": "第%d段中文。" % (i + 1)} for i, s in enumerate(st)]


# ============================ A. 静态断言 ============================
def stage_static(m):
    check(set(m.SCENES) >= {"cover"}, "SCENES 里至少有 cover")
    check(len(m.SCENES) >= 6, "SCENES 至少 6 个场景（现有 %d）" % len(m.SCENES))
    check(set(m.ORDER) <= set(m.SCENES) - {"cover"},
          "ORDER 里的名字都在 SCENES 里（且不含 cover）")

    for name, fn in m.SCENES.items():
        try:
            out = fn()
        except Exception as e:  # noqa: BLE001
            check(False, "场景 %s 能渲染" % name, repr(e))
            continue
        check(len(out) > 1200, "场景 %s 有内容（%d 字符）" % (name, len(out)))
        check("None" not in out and "nan" not in out,
              "场景 %s 没有 None/nan（百分号格式化的典型症状）" % name)
        check(out.count('class="wface"') >= 1,
              "场景 %s 里至少有一个带脸的小角色" % name,
              "wface=%d" % out.count('class="wface"'))

    # 滤镜：直线不能被 0×0 的滤镜区域裁掉
    d = m.defs()
    check('id="rough"' in d, "defs 里有 #rough")
    check('filterUnits="userSpaceOnUse"' in d,
          "#rough 用 userSpaceOnUse（否则直线会被裁）")
    check(re.search(r'id="rough"[^>]*width="\d+"', d) is not None,
          "#rough 给了固定的 width/height 区域（不能是百分比）")

    # 关键零件
    sun = m.sun(500, 500, 200)
    check(sun.count("<line") == 12, "太阳有 12 道光（实得 %d）" % sun.count("<line"))
    check(len(sun) > 500, "太阳 svg 非空")

    fl = m.flower(100, 100, 1.0)
    check(fl.count("rotate(") == 7,
          "花有 6 片花瓣 + 1 片叶子（实得 %d 次 rotate）" % fl.count("rotate("))
    check(re.search(r'"M[-\d.]+ [-\d.]+ V [-\d.]+"', fl) is not None,
          "花有竖直的花茎（关键：就是这条线曾被滤镜吃掉）")

    bk = m.book_open(400, 400, 1.0)
    check('class="wface"' not in bk, "书没有脸（书不该有脸）")
    check(bk.count("<path") >= 9, "书有封皮 + 两页 + 字行（%d 条 path）" % bk.count("<path"))
    check(bk.count('<g class="wx-float"') == 1 and bk.count("</g>") == 1,
          "书是一个整体动画组（外层只有 1 个 g）")

    hl = m.hills(600, [(m.P["mint"], 0, 0.7), (m.P["green"], 80, 0.8)])
    check(hl.count("<path") == 2, "hills 层数正确（实得 %d）" % hl.count("<path"))
    check(" V 940" in hl, "hills 封口到画面底部")

    check(m.mottle(0, 0, 100, 100, ["#fff"], n=5).count("<ellipse") == 5, "mottle 撒了 5 团")

    # 自动配景
    for lines, want in [
        (["The silent night and all the stars"], "night"),
        (["I anticipate the kettle on the cold floor"], "home"),
        (["A sentence like rain on a field"], "rain"),
        (["A book of words, a page to learn"], "study"),
        (["Green flowers grow in the garden"], "field"),
        (["The boat would sail across the sea"], "sea"),
    ]:
        got = m.pick_scene(" ".join(lines))
        check(got == want, "pick_scene(%r) → %s" % (lines[0][:26], want), "实得 %s" % got)
    check(m.pick_scene("") is None, "pick_scene 遇空串返回 None")
    check(m.assign_scenes([["zzz qqq xxx"], ["yyy www"]]) == ["dawn", "field"],
          "没命中关键词时按 ORDER 补位")

    sc = m.assign_scenes([["night moon dark"] + ["x"] * 3, ["night moon again"],
                          ["a kettle at home"]])
    check(len(set(sc)) == len(sc), "同一篇里场景不重复（实得 %s）" % sc)
    check(sc[1] != sc[0], "重复命中同一景时自动换一个")

    # 端到端 HTML
    st, panels = sample_panels(m)
    check(len(st) == 3, "split_stanzas 切出 3 段（实得 %d）" % len(st))
    html = m.build_html(SAMPLE["title"], SAMPLE["subtitle"], SAMPLE["date"], panels,
                        SAMPLE["words"])
    js = html.split("<script>")[-1].split("</script>")[0]

    for needle, label in [
        ('data-mode="en"', "English 按钮"),
        ('data-mode="bi"', "双语按钮"),
        ('data-mode="zh"', "中文按钮"),
        ('class="lines"', "正文容器 .lines"),
        ('class="pgrain"', "纸纹层 .pgrain"),
        ("mix-blend-mode:multiply", "纸纹混合模式"),
        ("wx-float", "浮动动画类"),
        ("wx-spin", "旋转动画类"),
        ("wx-rain", "落雨动画类"),
        ("IntersectionObserver", "进视口点亮"),
        ("prefers-reduced-motion", "无动画偏好适配"),
        ("@media (max-width:860px)", "窄屏媒体查询"),
    ]:
        check(needle in html, "HTML 含 %s" % label)

    check(html.count('<svg class="art-svg"') == len(st) + 1,
          "插画数 = 封面 + 段数（%d/%d）" % (html.count('<svg class="art-svg"'), len(st) + 1))
    check(all(x not in html for x in ("__WORDS__", "__PANELS__", "__TITLE__", "__RATE__")),
          "JS 占位符都被替换掉了")
    check("z.textContent=p.zh" in js, "中文用 textContent 写入（不转义标点）")
    check('querySelector(".lines")' in js.replace("'", '"'), "JS 定位 .lines 而不是 .copy")
    hero_rule = re.search(r"\.hero\{([^}]*)\}", m.CSS)
    check(hero_rule is not None and "place-items" not in hero_rule.group(1),
          ".hero 规则里没有 place-items:center（窄屏标题会被裁）",
          hero_rule.group(1)[:60] if hero_rule else "找不到 .hero 规则")

    # ---- 朗读按钮（本次需求）----
    check('class="play-all"' in html, "语言栏里有全文朗读按钮 .play-all")
    check(html.count('class="play"') == len(st),
          "每段各有一个朗读按钮（%d/%d）" % (html.count('class="play"'), len(st)))
    check(html.count('aria-pressed="false"') == len(st) + 1,
          '所有朗读按钮都带 aria-pressed="false" 初值')
    check(html.count("data-start=") == len(st) + 1 and html.count("data-stop=") == len(st) + 1,
          "所有朗读按钮都有 data-start / data-stop（用来切换文案）")
    check(html.count('class="btxt"') == len(st) + 1, "所有朗读按钮都有 .btxt 文案位")
    check(html.count('type="button"') >= len(st) + 1, '朗读按钮都显式写了 type="button"')
    check("朗读全文英文" in html and "朗读这一段英文" in html, "朗读按钮有 aria-label")
    check("@keyframes pulse" in m.CSS, "朗读态有脉动反馈动画")

    # 开关逻辑
    check("if(narrating){ stopNarration(); return; }" in js,
          "全文按钮：正在朗读时再点一次 = 停止")
    check("narrGen++" in js and "g !== narrGen" in js,
          "有「代次」令牌拦住 cancel() 触发的旧回调（否则停止后还会接着念）")
    check("e.error === 'canceled'" in js and "e.error === 'interrupted'" in js,
          "忽略自己触发的 canceled/interrupted 错误")
    check("if(!narrating || g !== narrGen) return;" in js, "speakLine 每步都先检查是否已停止")
    check("sec._starts = null" in js, "render() 会作废朗读标记（否则高亮不再恢复）")
    check("render(narrPrevMode || mode);" in js, "停止时按当前语言重画一次，复原金色词高亮")
    check("querySelectorAll('.lang button[data-mode]')" in js,
          "语言按钮只绑 [data-mode]，不把同一个 .lang 里的「朗读」按钮也绑进去")
    check("if(!document.querySelector('.copy p.en'))" in js,
          "ensureEnVisible 以 DOM 为准判断要不要切英文")
    rm = re.search(r"u\.rate = ([\d.]+);", js)
    check(rm is not None and abs(float(rm.group(1)) - 0.92) < 0.001,
          "朗读语速被注入（实得 %s）" % (rm.group(1) if rm else "缺失"))
    check("speechSynthesis" in js and "SpeechSynthesisUtterance" in js, "用了 Web Speech API")
    check("b.style.display = 'none'" in js, "浏览器不支持语音时把朗读按钮藏起来")
    check("en-us" in js.lower() and "en-gb" in js.lower(), "优先挑英文（美音优先）的声音")

    html2 = m.build_html(SAMPLE["title"], SAMPLE["subtitle"], SAMPLE["date"], panels,
                         SAMPLE["words"], rate=1.25)
    check("u.rate = 1.25;" in html2, "--rate 能改语速")

    # —— 童话契约（2026-09-13 起：正文键 story，旧的 poem 继续兼容）——
    check('data.get("story")' in inspect.getsource(m.main),
          "main() 认 story 键（童话正文），且保留 poem 兼容")
    check('data.get("tale")' in inspect.getsource(m.main), "main() 也认 tale 键")
    cute = os.path.join(HERE, "make_watercolor_svg_cute_book.py")
    if os.path.exists(cute):
        csrc = open(cute, encoding="utf-8").read()
        check('data.get("story")' in csrc, "chibi 版也认 story 键")
        check("DEFAULT_ZH = {" not in csrc,
              "chibi 版不再内置硬编码译文（否则新内容会串上「城市规划」那套中文）")
        check("zh_stanzas" in csrc,
              "chibi 版会读 JSON 自带的中文（zh / zh_stanzas / translation）")

    # ==================== A2. 故事分镜引擎（配图贴题 + 跨天不重样）====================
    stage_storyboard(m)
    return html


# 两篇「词表几乎不重叠」的假童话：用来验分镜贴题 + 跨天不重样
TALE_A = {
    "title": "The Key That Opened Only One Door",
    "story": [
        "The key was made by a locksmith who believed every door should be difficult. "
        "It hung on a nail in a dark corridor, and it unlocked exactly one lock.",
        "A woman carried the key to the street, past the streetlight, and knocked at a gate.",
        "In the attic above the shop, a wooden chest held a letter and a broken clock.",
        "The clock had stopped at dawn, when the candle burned out on the windowsill.",
        "She put the key in the drawer and went down the ladder to the garden.",
        "Everyone agreed that a key which opens one door is worth more than a key "
        "which opens none, and the bell rang over the town.",
        "So the key stayed, and the door stayed, and the two of them kept each other honest.",
    ],
}
TALE_B = {
    "title": "The Old Jar by the Well",
    "story": [
        "There was once a clay jar that stood by the well, and the villagers "
        "thought it a trivial thing.",
        "Every morning a woman filled the jar with water and carried it home.",
        "A wheel turned in the yard, and a clock ticked, and the jar learned the "
        "sound of the village.",
        "The jar cracked, and the crack drew a line across its belly like a road.",
        "A cart took it to the market, where nobody wanted a cracked jar.",
        "So it came back to the well, and the water in it was sweeter than before.",
        "The jar said nothing, but the well answered for it, and the evening was quiet.",
    ],
}


def stage_storyboard(m):
    A = m.ART
    check(A is not None, "渲染器能加载 art_storyboard.py")
    if A is None:
        return
    check(getattr(A, "ART_VERSION", 0) >= 2, "分镜引擎版本 >= 2")
    check(len(A.BG) >= 14, "背景层至少 14 个（现有 %d）" % len(A.BG))
    check(len(A.PARTS) >= 45, "主体物至少 45 个（现有 %d）" % len(A.PARTS))

    # —— 1) 每个背景、每个主体物都画得出来 ——
    #     手写 %-格式化数错占位符会整片 TypeError（bell / loaf / teapot / nest / violin 都中过）
    bad = []
    for name in A.BG_ORDER:
        ent = A.BG.get(name)
        if not ent or len(ent) != 3:
            bad.append("%s:条目结构" % name)
            continue
        try:
            out = ent[1]()
            if len(out) < 300 or "None" in out or "nan" in out:
                bad.append("%s:内容" % name)
        except Exception as e:  # noqa: BLE001
            bad.append("%s:%s" % (name, type(e).__name__))
    check(not bad, "所有背景层都渲染正常", ",".join(bad))

    bad = []
    for name, spec in A.PARTS.items():
        slot = "air_mid" if spec["slot"] == "air" else "hero"
        x, y, base = A.slot_xy(slot)
        try:
            out = spec["draw"](x, y, base * spec["scale"], {"bg": "plain", "sky": "#fff"})
            if len(out) < 60 or "None" in out or "nan" in out:
                bad.append("%s:内容" % name)
        except Exception as e:  # noqa: BLE001
            bad.append("%s:%s" % (name, type(e).__name__))
    check(not bad, "所有主体物都渲染正常（%d 个）" % len(A.PARTS), ",".join(bad[:6]))

    # —— 2) 触发词必须能被「真词」匹配到，不能是逐字符 ——
    check(A.hits("a cat sat", ("cat",)) == ["cat"], "hits() 按单词匹配")
    check(A.hits("catch the ball", ("cat",)) == [], "hits() 不会把 catch 当成 cat")
    check(A.hits("the keys were lost", ("key", "keys")) == ["keys"], "hits() 命中变形词")
    check(A.hits("keys", "key keys") == ["keys"],
          "hits() 传字符串时按空格拆词（曾经把整串拆成字符 → 整篇配图全错）")
    check(A.PARTS["key"]["w"][0] == "key", "PARTS 的触发词已拆成词元组")

    # 触发词不许出现「谁都能命中」的通用词
    BANNED = {"a", "an", "the", "it", "he", "she", "his", "her", "was", "were", "is",
              "and", "of", "in", "on", "to", "they", "that", "this", "them", "there"}
    leaked = sorted({w for spec in A.PARTS.values() for w in spec["w"]} & BANNED)
    check(not leaked, "触发词里没有通用虚词（否则每段都会瞎命中）", ",".join(leaked))

    # —— 3) 贴题：每个主体物都要说得出「被哪个词引出来」——
    bad = []
    for tag, tale in (("A", TALE_A), ("B", TALE_B)):
        paras = [" ".join(s) for s in m.split_stanzas(tale["story"])]
        book = " ".join(paras).lower()
        title = tale["title"].lower()
        plans = A.plan_book(paras, tale["title"], history=None)
        for i, pl in enumerate(plans):
            if not [p for p in pl["parts"] if not p["decor"]]:
                bad.append("%s 第%d段没有贴题主体物" % (tag, i + 1))
            for p in pl["parts"]:
                if p["decor"]:
                    if p["why"]:
                        bad.append("%s 第%d段装饰物不该有 why" % (tag, i + 1))
                    continue
                if not p["why"]:
                    bad.append("%s 第%d段 %s 没有 why" % (tag, i + 1, p["name"]))
                    continue
                scope = p["scope"]
                text = {"para": paras[i].lower(), "title": title}.get(scope, book)
                if scope in ("para", "title"):
                    text = "%s %s" % (paras[i].lower(), title)
                if p["why"] not in text:
                    bad.append("%s 第%d段 %s 的 why=%r 不在%s里"
                               % (tag, i + 1, p["name"], p["why"], scope))
    check(not bad, "每段的每个主体物都能指回一个真实出现过的词", "; ".join(bad[:5]))

    # —— 4) 关键词真的"看得懂"内容：换题材就该换主体物 ——
    pa = [" ".join(s) for s in m.split_stanzas(TALE_A["story"])]
    pb = [" ".join(s) for s in m.split_stanzas(TALE_B["story"])]
    names_a = {p["name"] for pl in A.plan_book(pa, TALE_A["title"]) for p in pl["parts"]}
    names_b = {p["name"] for pl in A.plan_book(pb, TALE_B["title"]) for p in pl["parts"]}
    check("key" in names_a, "讲钥匙的童话配了 key（实得 %s）" % sorted(names_a)[:6])
    check("door" in names_a, "讲钥匙的童话配了 door")
    check("jar" in names_b and "well" in names_b,
          "讲陶罐/井的童话配了 jar + well（实得 %s）" % sorted(names_b)[:6])
    check(not (names_a & names_b) or len(names_a & names_b) <= 2,
          "两篇不同题材的主体物基本不重叠", "%s" % sorted(names_a & names_b))
    check("key" not in names_b, "讲陶罐的童话不会配到钥匙")

    # —— 5) 一篇之内不重样 ——
    sigs = [pl["sig"] for pl in A.plan_book(pa, TALE_A["title"])]
    check(len(set(sigs)) == len(sigs) or sigs.count(sigs[0]) <= 2,
          "同一篇里不会整段整段地重样（%d 段 / %d 种）" % (len(sigs), len(set(sigs))))

    # —— 6) 跨天防重：台账里记过的组合，第二天不再出现 ——
    day1 = A.plan_book(pa, TALE_A["title"], history=None)
    hist = [{"date": "2026-01-01",
             "bgs": sorted({p["bg"] for p in day1}),
             "sigs": sorted({p["sig"] for p in day1})}]
    day2 = A.plan_book(pa, TALE_A["title"], history=hist)
    clash = sorted({p["sig"] for p in day2} & {p["sig"] for p in day1})
    check(not clash, "同一篇童话第二天重排，配图组合全部换掉（%d 处重合）" % len(clash),
          ",".join(clash[:3]))

    # —— 7) 台账读写（在临时目录里做，绝不碰真实数据）——
    tmp = tempfile.mkdtemp(prefix="wcbook-ledger-")
    try:
        cover = A.plan_cover(pa, TALE_A["title"])
        p = A.save_history("2026-01-02", day1, data_dir=tmp, cover=cover)
        check(bool(p) and os.path.exists(p), "台账能写出来")
        h = A.load_history(data_dir=tmp)
        check(h["count"] == 1, "台账能读回来（%d 天）" % h["count"])
        check(set(h["bgs"]) >= {pl["bg"] for pl in day1}, "台账记住了用过的背景")
        check(set(h["sigs"]) >= {pl["sig"] for pl in day1}, "台账记住了用过的组合")
        A.save_history("2026-01-02", day2, data_dir=tmp)
        check(A.load_history(data_dir=tmp)["count"] == 1, "同一天重写不会写重复条目")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # —— 8) 渲染：外壳 / 每段都带 data-obj 便于回归 ——
    pl = A.plan_book(pa, TALE_A["title"])[0]
    svg = A.svg_storyboard(pl)
    check('class="art-svg"' in svg, "分镜图用同一个 .art-svg 外壳")
    check('data-art="storyboard"' in svg and 'data-bg="%s"' % pl["bg"] in svg,
          "分镜图标了 data-art / data-bg")
    check(svg.count("data-obj=") == len(pl["parts"]) + len(A._decor(pl, {})),
          "每个主体物都有一个 data-obj（%d）" % svg.count("data-obj="))
    check('filter="url(#rough)"' in svg and 'id="rough"' in svg, "分镜图复用了 #rough 滤镜")
    check(svg.count('class="pgrain"') == 1, "分镜图只有一层纸纹")

    # —— 9) 封面：标题里的东西必须上封面 ——
    cv = A.plan_cover(pa, TALE_A["title"])
    cnames = {p["name"] for p in cv["parts"]}
    check("key" in cnames, "封面配了标题里的 key（实得 %s）" % sorted(cnames))
    check(A.svg_storyboard(cv).count("data-obj=") >= 2, "封面至少 2 个主体物")

    # —— 10) 接进 HTML：封面 + 每段各一张，且老的 9 景还能用 ——
    st, panels = sample_panels(m)
    art_fn, plans, _cv, save = m.storyboard_art_fn([p["en"] for p in panels], "Verify Me",
                                                  date="2026-01-01", use_ledger=False)
    html = m.build_html("Verify Me", "t", "2026-01-01", panels, SAMPLE["words"], art_fn=art_fn)
    check(html.count('data-art="storyboard"') == len(st) + 1,
          "封面 + 每段都换成故事分镜图（%d/%d）"
          % (html.count('data-art="storyboard"'), len(st) + 1))
    check(save() is None, "--no-ledger 时不写台账")
    check(callable(m.svg) and 'data-art="storyboard"' not in m.svg("cover"),
          "老的 9 个成品场景仍然可用（--art scene）")
    check(hasattr(m, "svg_wrap"), "渲染器导出 svg_wrap（分镜引擎共用同一个 SVG 外壳）")
    src = inspect.getsource(m.main)
    check('default="storyboard"' in src, "main() 默认用分镜引擎出图")
    check("--art-ledger-dir" in src and "--no-ledger" in src, "main() 支持台账目录 / 关台账")


# ==================== B. JS 语法 + 正则高亮（node） ====================
NODE_PROBE = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const js  = src.split('<script>').pop().split('</script>')[0];
const escLine = js.split('\n').find(l => l.includes('function esc'));
const reLine  = js.split('\n').find(l => l.includes('RegExp'));
const R = { syntax_ok: true };
try { new Function(js); } catch (e) { R.syntax_ok = false; R.syntax_err = String(e).slice(0, 90); }
eval(escLine.trim());
R.esc = esc('a.b');
function forms(w){var o={},stem=w.replace(/e$/,'');
  [w,w+'s',w+'es',w+'d',w+'ed',stem+'ing',stem+'ies',stem+'ied',w+'ied'].forEach(f=>o[f]=1);
  return Object.keys(o).sort((a,b)=>b.length-a.length);}
const WORDS = ['foundation','sustainable','analyse'];
const re = eval(reLine.trim().replace(/^var re=/,''));
R.re_src = re.source.slice(0,3);
const probe = 'A foundation wakes and does not analyse its own sustainable light.';
R.hits = (probe.match(re) || []).length;
process.stdout.write('PROBE:' + JSON.stringify(R));
"""


def stage_js(node, html):
    js = html.split("<script>")[-1].split("</script>")[0]
    # 静态兜底：生成物里的正则必须是 '\b('（2 个反斜杠），不能是 4 个
    check("'\\\\b('" in js, "生成的 JS 里正则是 2 个反斜杠的 '\\\\b('（raw 字符串泄漏会变成 4 个）")
    if not node:
        SKIPS.append("JS 语法 / 正则高亮实测（没找到 node）")
        return
    with tempfile.TemporaryDirectory() as td:
        p_html = os.path.join(td, "book.html")
        p_probe = os.path.join(td, "probe.js")
        with open(p_html, "w", encoding="utf-8") as f:
            f.write(html)
        with open(p_probe, "w", encoding="utf-8") as f:
            f.write(NODE_PROBE)
        try:
            out = subprocess.run([node, p_probe, p_html], capture_output=True,
                                 text=True, timeout=60).stdout
        except Exception as e:  # noqa: BLE001
            check(False, "跑得动 node 探针", repr(e))
            return
    mm = re.search(r"PROBE:(\{.*\})", out)
    if not mm:
        check(False, "node 探针有输出", out[:120])
        return
    R = json.loads(mm.group(1))
    check(R.get("syntax_ok") is True, "生成的 JS 语法合法（node 编译通过）", R.get("syntax_err", ""))
    check(R.get("esc") == "a\\.b", "esc() 真的在转义正则特殊字符（实得 %r）" % R.get("esc"))
    check(R.get("re_src", "")[:2] == "\\b", "正则开头是 \\b 词边界（实得 %r）" % R.get("re_src"))
    check(R.get("hits", 0) >= 3,
          "金色词高亮能命中（实得 %s 个，期望 ≥3）" % R.get("hits"))


# ==================== C. 朗读开关行为（Chrome） ====================
STUB = """<script>
(function(){
  var cur = null;
  window.__spk = { log: [], rates: [], langs: [] };
  window.__probe = {};
  // ⚠️ 必须用 defineProperty 在 window **实例**上遮蔽这两个名字：
  //    speechSynthesis 是 Window.prototype 上的只读 getter，
  //    直接 `window.speechSynthesis = {...}` 会被静默忽略（非严格模式），
  //    页面于是调到了真·浏览器合成器 → 报 "parameter 1 is not of type ..."。
  function attr(k, v){
    try { Object.defineProperty(window, k, { value: v, writable: true, configurable: true });
          window.__probe[k] = 'ok'; }
    catch (e) { window.__probe[k] = String(e); }
  }
  function U(t){ this.text = String(t); this.rate = 1; this.lang = ''; }
  var api = {
    getVoices: function(){
      return [{lang:'en-US', name:'Stub US', localService:true},
              {lang:'en-GB', name:'Stub GB', localService:false}];
    },
    speak: function(u){
      cur = u;
      window.__spk.log.push('S');
      window.__spk.rates.push(u.rate);
      window.__spk.langs.push(u.lang);
      // 250ms/句 ≈ 真语音的「还在读」状态；太快的话短段落会在我们点「停止」之前
      // 就自然读完，第二次点击反而变成「重新开始」，测不出 toggle 语义。
      setTimeout(function(){
        if (cur !== u) return;                 // 已被 cancel
        cur = null;
        if (u.onend) u.onend();
      }, 250);
    },
    cancel: function(){
      window.__spk.log.push('X');
      var u = cur; cur = null;
      // 浏览器就是这样：cancel 会给当前这条抛 canceled（这里同步抛，最严苛）
      if (u && u.onerror) u.onerror({ error: 'canceled' });
    },
    pause: function(){}, resume: function(){},
    addEventListener: function(){}, removeEventListener: function(){}
  };
  attr('SpeechSynthesisUtterance', U);
  attr('speechSynthesis', api);
  window.__probe.installed = (window.speechSynthesis === api);
})();
</script>"""

ASSERT = """<script>
(function(){
  var R = {}; window.__R = R;
  R.stubInstalled = !!(window.__probe && window.__probe.installed);
  function speaks(){ return window.__spk.log.filter(function(x){ return x === 'S'; }).length; }
  function cancels(){ return window.__spk.log.filter(function(x){ return x === 'X'; }).length; }
  var pa = document.querySelector('.play-all');
  var sec0 = document.querySelector('.copy .play');
  R.hasBtns = !!pa && !!sec0;
  if (!R.hasBtns){ document.title = 'RESULT:' + JSON.stringify(R); return; }
  R.start = pa.getAttribute('data-start');
  R.stop  = pa.getAttribute('data-stop');
  R.aria0 = pa.getAttribute('aria-pressed');

  var n0 = speaks();                            // ★ 基线要在点击之前取：桩件的 speak() 是同步的
  pa.click();                                   // 点一次 → 开始
  R.onAfterStart   = pa.classList.contains('on');
  R.ariaAfterStart = pa.getAttribute('aria-pressed');
  R.txtAfterStart  = pa.querySelector('.btxt').textContent;

  setTimeout(function(){
    R.spokeAfterStart = speaks() - n0;          // ★ 期望 >= 1
    R.rateUsed = window.__spk.rates.slice(-1)[0];
    R.langUsed = window.__spk.langs.slice(-1)[0];

    pa.click();                                 // 再点一次 → 停止
    R.onAfterStop   = pa.classList.contains('on');
    R.txtAfterStop  = pa.querySelector('.btxt').textContent;
    R.ariaAfterStop = pa.getAttribute('aria-pressed');
    R.cancelCalled  = cancels() >= 1;
    var n2 = speaks();                          // 停止那一刻的发声计数

    setTimeout(function(){
      R.spokeAfterStop = speaks() - n2;         // ★ 期望 0
      R.wordSpans = document.querySelectorAll('.spread .word').length;
      R.wdSpans   = document.querySelectorAll('.spread .wd').length;

      var n3 = speaks();                        // ★ 同样：单段按钮也要在点击前取基线
      sec0.click();                             // 单段按钮
      R.secOn = sec0.classList.contains('on');
      setTimeout(function(){
        R.secSpoke = speaks() - n3;
        sec0.click();
        R.secOff = !sec0.classList.contains('on');
        var n4 = speaks();
        setTimeout(function(){
          R.secSpokeAfterStop = speaks() - n4;  // ★ 期望 0

          // 中文模式下点朗读：必须先自动切回英文，否则「没得念」
          var zh = document.querySelector('.lang button[data-mode="zh"]');
          R.hasZhBtn = !!zh;
          if (zh) zh.click();
          R.zhEnLines = document.querySelectorAll('.copy p.en').length;   // ★ 期望 0
          pa.click();                                                    // 开始朗读
          setTimeout(function(){
            R.enLinesInPlay = document.querySelectorAll('.copy p.en').length;  // ★ 期望 > 0
            pa.click();                                                       // 停止
            setTimeout(function(){
              R.enLinesAfterStop = document.querySelectorAll('.copy p.en').length;  // ★ 期望 0（还原回中文）
              R.jsErrors = window.__errs || 0;
              document.title = 'RESULT:' + JSON.stringify(R);
            }, 120);
          }, 120);
        }, 200);
      }, 150);
    }, 200);
  }, 150);
})();
</script>"""

ERRTRAP = ('<script>window.__errs=0;'
           'window.addEventListener("error",function(){window.__errs++;});</script>')


def stage_speak(chrome, m):
    if not chrome:
        SKIPS.append("朗读开关行为实测（没找到 Chrome）")
        return
    st, panels = sample_panels(m)
    html = m.build_html(SAMPLE["title"], SAMPLE["subtitle"], SAMPLE["date"], panels,
                        SAMPLE["words"])
    html = html.replace("</head>", ERRTRAP + STUB + "</head>")   # 桩件要在页面脚本之前
    html = html.replace("</body>", ASSERT + "</body>")           # 断言要在页面脚本之后
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "speak.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)
        try:
            dom = subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                 "--disable-dev-shm-usage", "--window-size=1200,900",
                 "--virtual-time-budget=20000", "--dump-dom", "file://" + p],
                capture_output=True, text=True, timeout=120).stdout
        except Exception as e:  # noqa: BLE001
            check(False, "跑得动 Chrome 行为测试", repr(e))
            return
    mm = re.search(r"<title>RESULT:(\{.*?\})</title>", dom)
    if not mm:
        check(False, "行为测试有输出", dom[:160].replace("\n", " "))
        return
    R = json.loads(mm.group(1))

    check(R.get("hasBtns") is True, "页面上找得到全文 / 单段朗读按钮")
    check(R.get("stubInstalled") is True,
          "测试桩成功遮蔽 window.speechSynthesis（否则量到的是真合成器）")
    check(R.get("start") == "朗读" and R.get("stop") == "停止",
          "按钮文案是 朗读 → 停止（实得 %r/%r）" % (R.get("start"), R.get("stop")))
    check(R.get("aria0") == "false", "初始 aria-pressed=false")

    check(R.get("onAfterStart") is True and R.get("ariaAfterStart") == "true",
          "点一次：进入朗读态（.on + aria-pressed=true）")
    check(R.get("txtAfterStart") == "停止",
          "点一次：文案变「停止」（实得 %r）" % R.get("txtAfterStart"))
    check(R.get("spokeAfterStart", 0) >= 1,
          "点一次：真的开始念英文（实得 %s 次发声）" % R.get("spokeAfterStart"))
    check(abs(float(R.get("rateUsed") or 0) - 0.92) < 0.001,
          "语速用注入的 0.92（实得 %s）" % R.get("rateUsed"))
    check(str(R.get("langUsed") or "").lower().startswith("en"),
          "用英文声音（实得 %r）" % R.get("langUsed"))

    check(R.get("cancelCalled") is True, "再点一次：调用了 speechSynthesis.cancel()")
    check(R.get("onAfterStop") is False and R.get("ariaAfterStop") == "false",
          "再点一次：退出朗读态")
    check(R.get("txtAfterStop") == "朗读",
          "再点一次：文案回到「朗读」（实得 %r）" % R.get("txtAfterStop"))
    check(R.get("spokeAfterStop", 1) == 0,
          "★ 停止后不再发声（实得 %s 次；不修「代次」令牌这里会 >0）" % R.get("spokeAfterStop"))

    check(R.get("wordSpans", 0) > 0, "停止后金色词高亮已复原（.word=%s）" % R.get("wordSpans"))
    check(R.get("wdSpans", 1) == 0, "停止后朗读外壳已清掉（.wd=%s）" % R.get("wdSpans"))

    check(R.get("secOn") is True, "单段按钮：点一次进入朗读态")
    check(R.get("secSpoke", 0) >= 1, "单段按钮：点一次开始念（%s 次）" % R.get("secSpoke"))
    check(R.get("secOff") is True, "单段按钮：再点一次退出朗读态")
    check(R.get("secSpokeAfterStop", 1) == 0,
          "★ 单段按钮停止后不再发声（实得 %s 次）" % R.get("secSpokeAfterStop"))

    check(R.get("hasZhBtn") is True, "语言栏里有「中文」按钮")
    check(R.get("zhEnLines", 1) == 0, "切到中文后英文行确实收起了")
    check(R.get("enLinesInPlay", 0) > 0,
          "★ 中文模式下点朗读会自动切回英文（实得 %s 行）" % R.get("enLinesInPlay"))
    check(R.get("enLinesAfterStop", 1) == 0,
          "★ 停止后语言还原回中文（实得 %s 行英文）" % R.get("enLinesAfterStop"))
    check(R.get("jsErrors", 0) == 0, "整段交互没有 JS 运行时错误（%s 个）" % R.get("jsErrors"))


def main():
    ap = argparse.ArgumentParser(description="水彩绘本回归测试")
    ap.add_argument("--no-browser", action="store_true", help="只跑不需要 Chrome 的部分")
    a = ap.parse_args()

    m = load()
    html = stage_static(m)
    stage_js(find_first(NODE_CANDIDATES), html)
    if a.no_browser:
        SKIPS.append("朗读开关行为实测（--no-browser）")
    else:
        stage_speak(find_first(CHROME_CANDIDATES), m)

    print("✓ 通过 %d 项" % len(OKS))
    for s in SKIPS:
        print("·  跳过：%s" % s)
    if FAILS:
        print("\n✗ 失败 %d 项：" % len(FAILS))
        for f in FAILS:
            print("   · " + f)
        return 1
    print("🎨 可爱水彩绘本回归通过：%d 个场景 · %d 项断言" % (len(m.SCENES), len(OKS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
