#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_picturebook.py — 把当天的英文散文诗做成一本**可交互的 HTML 绘本**（适合青少年阅读）。

跟 make_poem_poster.py / make_comic.py 吃同一份 poem.json；
再喂一份词表（`ielts.py poem --json` 的输出）就能点词查义。

  $PY .../ielts.py poem --json > /tmp/vocab.json
  python3 make_picturebook.py --json /tmp/poem.json --vocab /tmp/vocab.json
  python3 make_picturebook.py --json /tmp/poem.json --vocab /tmp/vocab.json --no-png

产物：<数据目录>/poems/book-YYYY-MM-DD.html（自包含，双击即开）
     + 同名 .png（可选，用 Chrome 无头把封面截出来当缩略图）

绘本里有什么：
  · 封面 → 六格全页插画（上图下文）→ 词汇表，左右翻页 + 键盘 + 页码点
  · 诗里每一个今天背过的词都是**可点的**，点开底部词条卡：词性 / 释义 / 例句
  · 每页一条「观察」提示，引导青少年在画面里找线索，而不是干背中文释义
  · 词汇表页带搜索框，可以当场查

插画复用 make_comic.py 的 SCENES（手写 SVG，放大不糊）。
改版式改这里的 CSS_TMPL；改观察提示改 NOTES。
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_comic import (SCENES, DEFAULT_ORDER, as_lines, split_stanzas,   # noqa: E402
                        find_chrome, measure, shoot, word_forms)

HOME = os.path.expanduser("~")
DATA_DIR = os.environ.get("IELTS_DATA_DIR", os.path.join(HOME, ".workbuddy", "ielts-prep"))
POEM_DIR = os.path.join(DATA_DIR, "poems")

W = 1200
ART_H = 400

# 每一页的「观察」提示（青少年向：先让他们看见，再说词）
NOTES = {
    "city": "画面里最吵的东西是什么？数一数有几辆车在冒烟——它们对应这一段里的哪个词？",
    "council": "投票是 10 : 9。差一票说明什么？为什么越接近的票数，争论反而越激烈？",
    "policy": "同一幅图里既有农田也有新修的路。为什么一手收钱、一手发补贴？",
    "build": "屋顶、河面、马路上各多了一样新东西。找出它们分别是哪三个词变的。",
    "school": "黑板上有四个词。其中三个是「把坏事变小」，只有一个是「把好事变大」——是哪个？",
    "sky": "把这一页和第一页并起来看：天空、市场、人的表情，各说出三处不同。",
}
FALLBACK_NOTE = "这一页里藏着今天背过的词，先找画面，再找词。"

ACCENTS = ["#e05a4f", "#1d5f8a", "#3f8f52", "#d1872a", "#6b4f9e", "#2b7f8c"]


def highlight(text, words):
    """把目标词包成可点的 <em class="v" data-w="...">。"""
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
        out.append('<em class="v" data-w="%s" tabindex="0">%s</em>'
                   % (html.escape(forms[m.group(1).lower()]), html.escape(m.group(0))))
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


CSS_TMPL = """
:root{
  --paper:#f7f1e4; --ink:#2b2f36; --soft:#6b7280; --line:#e3d9c6;
  --card:#fffdf7; --accent:__ACC__;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%%}
body{
  background:
    radial-gradient(900px 520px at 12%% -10%%, rgba(255,214,140,.30), transparent 60%%),
    radial-gradient(820px 520px at 100%% 110%%, rgba(120,170,220,.26), transparent 62%%),
    var(--paper);
  color:var(--ink);
  font-family:-apple-system,"PingFang SC","Helvetica Neue",Helvetica,sans-serif;
  display:flex;align-items:center;justify-content:center;padding:26px 18px 92px;
}
.book{width:100%%;max-width:920px}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:12px}
.brand{font-size:12px;letter-spacing:.28em;text-transform:uppercase;color:#9a8f7a}
.ctrl{display:flex;align-items:center;gap:8px}
.ctrl button{
  width:42px;height:42px;border:2px solid var(--ink);border-radius:999px;background:var(--card);
  font-size:22px;line-height:1;cursor:pointer;color:var(--ink);transition:transform .12s,background .12s;
}
.ctrl button:hover:not(:disabled){background:#ffe9b8;transform:translateY(-1px)}
.ctrl button:disabled{opacity:.32;cursor:default}
.pager{font-size:13px;color:var(--soft);min-width:64px;text-align:center;font-variant-numeric:tabular-nums}
.stage{perspective:2200px}
.page{display:none;background:var(--card);border:3px solid var(--ink);border-radius:20px;
  overflow:hidden;box-shadow:0 14px 0 rgba(43,47,54,.10), 0 26px 46px rgba(43,47,54,.16);
  transform-style:preserve-3d}
.page.active{display:block}
.page.anim-out-l{animation:outL .33s ease-in forwards;transform-origin:left center}
.page.anim-out-r{animation:outR .33s ease-in forwards;transform-origin:right center}
.page.anim-in-l{animation:inL .44s cubic-bezier(.22,.9,.24,1);transform-origin:left center}
.page.anim-in-r{animation:inR .44s cubic-bezier(.22,.9,.24,1);transform-origin:right center}
@keyframes outL{from{transform:rotateY(0);opacity:1}to{transform:rotateY(-64deg);opacity:0}}
@keyframes outR{from{transform:rotateY(0);opacity:1}to{transform:rotateY(64deg);opacity:0}}
@keyframes inL{from{transform:rotateY(-64deg);opacity:0}to{transform:rotateY(0);opacity:1}}
@keyframes inR{from{transform:rotateY(64deg);opacity:0}to{transform:rotateY(0);opacity:1}}

/* 封面 */
.cover{position:relative}
.cover svg{display:block;width:100%%;height:auto}
.cover .veil{position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,253,247,.86) 0%%,
  rgba(255,253,247,.30) 42%%, rgba(255,253,247,.92) 100%%)}
.cover .txt{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center;padding:0 34px}
.cover .kicker{font-size:11.5px;letter-spacing:.34em;text-transform:uppercase;color:#1d5f8a;
  border:2px solid var(--ink);border-radius:999px;padding:6px 16px;background:var(--card)}
.cover h1{font-family:Georgia,"Times New Roman",serif;font-style:italic;font-weight:400;
  font-size:clamp(30px,5.4vw,58px);line-height:1.12;margin:20px 0 12px;color:#15304a;
  text-shadow:2px 2px 0 #fff}
.cover .sub{font-size:14px;color:#55606e;background:rgba(255,255,255,.72);
  border-radius:999px;padding:6px 16px}
.start{margin-top:26px;border:3px solid var(--ink);border-radius:999px;background:#ffd75e;
  font-size:15px;font-weight:700;padding:12px 30px;cursor:pointer;color:var(--ink);
  box-shadow:0 4px 0 var(--ink);transition:transform .12s}
.start:active{transform:translateY(4px);box-shadow:0 0 0 var(--ink)}

/* 正文页 */
.artwrap{position:relative;background:#cfe4f2}
.artwrap svg{display:block;width:100%%;height:auto}
.artwrap .sheen{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(255,255,255,.16),rgba(43,47,54,.10))}
.badge{position:absolute;left:20px;top:18px;min-width:42px;height:42px;border-radius:999px;
  background:var(--accent);color:#fff;font-weight:800;font-size:19px;display:flex;
  align-items:center;justify-content:center;border:3px solid var(--card);box-shadow:0 3px 0 rgba(0,0,0,.18)}
.card{margin:-46px 20px 22px;position:relative;background:var(--card);border:3px solid var(--ink);
  border-radius:18px;padding:24px 26px 20px}
.lines{font-family:Georgia,"Times New Roman",serif;font-size:clamp(18px,2.5vw,24px);
  line-height:1.85;color:#2c3238}
.lines p{letter-spacing:.004em}
em.v{font-style:italic;color:#a8641a;border-bottom:2px dashed rgba(190,130,40,.6);
  padding-bottom:1px;cursor:pointer;border-radius:3px}
em.v:hover,em.v:focus{background:#ffeec7;outline:none}
.note{margin-top:18px;border-top:2px dashed var(--line);padding-top:14px;
  font-size:14.5px;line-height:1.7;color:#5a6572}
.note b{display:inline-block;background:#eaf3ea;border:2px solid #3f8f52;border-radius:999px;
  color:#2f6f3d;font-size:12px;padding:2px 11px;margin-right:9px}

/* 词汇表 */
.vpage{padding:26px 26px 24px}
.vpage h2{font-family:Georgia,serif;font-size:26px;font-weight:400;margin-bottom:6px}
.vpage .hint{font-size:13.5px;color:var(--soft);margin-bottom:16px}
.search{width:100%%;border:3px solid var(--ink);border-radius:14px;padding:11px 15px;font-size:15px;
  margin-bottom:18px;background:#fffdf7;color:var(--ink)}
.search:focus{outline:none;background:#fff8e6}
.vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:11px;
  max-height:min(52vh,520px);overflow:auto;padding-right:4px}
.vitem{border:2px solid var(--line);border-radius:13px;padding:11px 13px;background:#fffdf7;
  cursor:pointer;transition:border-color .14s,transform .12s}
.vitem:hover{border-color:var(--ink);transform:translateY(-2px)}
.vitem .w{font-family:Georgia,serif;font-size:18px;font-weight:700}
.vitem .p{font-size:11px;color:#9a8f7a;margin-left:7px}
.vitem .m{font-size:13.5px;color:#4b5563;margin-top:4px}
.vitem .e{font-family:Georgia,serif;font-size:12.5px;color:#8a8574;margin-top:5px;font-style:italic;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.dots{display:flex;justify-content:center;gap:9px;margin-top:20px;flex-wrap:wrap}
.dot{width:11px;height:11px;border-radius:999px;border:2px solid var(--ink);background:transparent;
  cursor:pointer;padding:0}
.dot.on{background:var(--ink)}

/* 词条卡 */
.sheet{position:fixed;left:0;right:0;bottom:0;transform:translateY(110%%);transition:transform .28s
  cubic-bezier(.22,.9,.24,1);background:var(--card);border-top:4px solid var(--ink);
  box-shadow:0 -14px 40px rgba(43,47,54,.20);z-index:40}
.sheet.on{transform:translateY(0)}
.sheet .in{max-width:920px;margin:0 auto;padding:20px 24px 26px;position:relative}
.sheet .hd{display:flex;align-items:baseline;gap:11px;flex-wrap:wrap}
.sheet .wd{font-family:Georgia,serif;font-size:29px;font-weight:700}
.sheet .ps{font-size:13px;color:#9a8f7a}
.sheet .mn{font-size:17px;color:#a8641a;margin-top:9px;font-weight:600}
.sheet .ex{font-family:Georgia,serif;font-style:italic;font-size:15.5px;color:#5a6572;margin-top:9px;
  line-height:1.6}
.sheet .x{position:absolute;right:18px;top:14px;width:34px;height:34px;border-radius:999px;
  border:2px solid var(--ink);background:#fff;cursor:pointer;font-size:17px;line-height:1}
.foot{max-width:920px;margin:14px auto 0;text-align:center;font-size:11px;letter-spacing:.24em;
  text-transform:uppercase;color:#9a8f7a}
/* ---- 双语：英文 / 中文 / 双语 ---- */
.lines .en{display:block}
.lines .zh{display:block;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  font-size:.60em;line-height:1.75;letter-spacing:.02em;color:#8a8574;margin-top:3px}
html[data-lang="en"] .lines .zh{display:none}
html[data-lang="zh"] .lines .en{display:none}
html[data-lang="zh"] .lines .zh{font-size:.86em;color:#3a4148;margin-top:0}
html[data-lang="zh"] .lines{line-height:1.95}
.lang{display:flex;align-items:center;gap:4px;background:var(--card);
  border:2px solid var(--ink);border-radius:999px;padding:3px}
.lang button{border:0;background:transparent;font-size:12px;font-weight:700;letter-spacing:.06em;
  color:#7c7361;padding:5px 11px;border-radius:999px;cursor:pointer;font-family:inherit;
  white-space:nowrap;flex:0 0 auto;transition:background .14s,color .14s}
.lang button:hover{background:#fff3d6}
.lang button.on{background:var(--ink);color:#fff8e6}

/* ---- 动态：插画"画出来" + 环境动画 ---- */
@keyframes draw{from{opacity:0;transform:translateY(12px) scale(.94)}to{opacity:1;transform:none}}
/* 注意：位移要用「相对容器的百分比」（left/bottom），
   用 translateX/Y 的百分比是相对元素自身尺寸——云才 20%% 宽，移 122%% 只挪了容器的一小截。 */
@keyframes driftCloud{from{left:-26%%}to{left:116%%}}
@keyframes rise{0%%{bottom:4%%;opacity:0}14%%{opacity:.9}100%%{bottom:84%%;opacity:0}}
@keyframes sway{from{transform:translateY(0) rotate(0)}to{transform:translateY(-5px) rotate(.22deg)}}
@keyframes popIn{from{transform:scale(.6);opacity:0}70%%{transform:scale(1.08)}to{transform:scale(1);opacity:1}}
@keyframes cardUp{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}
@keyframes glow{0%%,100%%{opacity:.55;transform:scale(1)}50%%{opacity:.95;transform:scale(1.06)}}

/* 一幅画的元素逐个"上色"：默认暂停（停在 0%%），翻到这一页才开跑 */
.artwrap > svg > *,.cover > svg > *{animation:draw .55s cubic-bezier(.22,.86,.24,1) both;animation-play-state:paused}
.page.active .artwrap > svg > *,.page.active.cover > svg > *{animation-play-state:running}
.page.active .badge{animation:popIn .5s cubic-bezier(.2,.9,.3,1.3) both;animation-delay:.15s}
.page.active .card{animation:cardUp .5s cubic-bezier(.22,.9,.24,1) both;animation-delay:.28s}
.page.active .artwrap > svg,.page.active.cover > svg{animation:sway 9s ease-in-out infinite alternate}

/* 画上面的天气：飘云 + 上升的小颗粒 + 呼吸的光晕 */
.fx{position:absolute;inset:0;pointer-events:none;overflow:hidden}
.fx i{position:absolute;display:block}
.fx .cl{border-radius:999px;background:rgba(255,255,255,.60);filter:blur(8px);
  animation:driftCloud linear infinite}
.fx .cl.a{top:8%%;width:21%%;height:11%%;animation-duration:30s}
.fx .cl.b{top:21%%;width:15%%;height:8%%;opacity:.72;animation-duration:40s;animation-delay:-14s}
.fx .cl.c{top:4%%;width:11%%;height:6%%;opacity:.55;animation-duration:52s;animation-delay:-30s}
.fx .pt{width:7px;height:7px;border-radius:999px;background:rgba(255,255,255,.9);
  filter:blur(1.2px);animation:rise linear infinite}
.fx .pt.a{left:22%%;animation-duration:9s}
.fx .pt.b{left:47%%;animation-duration:12s;animation-delay:2.4s}
.fx .pt.c{left:63%%;animation-duration:10.5s;animation-delay:1.2s}
.fx .pt.d{left:82%%;animation-duration:14s;animation-delay:3.6s}
.fx .halo{position:absolute;right:9%%;top:8%%;width:16%%;height:44%%;border-radius:999px;
  background:radial-gradient(circle,rgba(255,232,160,.85),transparent 70%%);
  animation:glow 6s ease-in-out infinite}
.cover .fx .halo{right:14%%;top:12%%;width:12%%;height:36%%}
/* 封面有自己的 veil 层，天气元素压淡一点，别抢字 */
.cover .fx{opacity:.5}
.start{animation:glow 3.4s ease-in-out infinite}
@media (prefers-reduced-motion:reduce){
  .fx,.start{display:none}
  .artwrap > svg > *,.page.active .artwrap > svg > *,
  .page.active .badge,.page.active .card,.page.active .artwrap > svg{animation:none!important}
}

@media (max-width:640px){
  .card{margin:-30px 12px 16px;padding:18px 16px 16px}
  .lines{font-size:17px;line-height:1.8}
  .topbar{flex-wrap:wrap}
  .ctrl{gap:6px}
}
"""


def build_html(title, subtitle, day, panels, words, vocab):
    vmap = {}
    for v in vocab:
        vmap[str(v.get("word", "")).strip().lower()] = {
            "word": v.get("word", ""), "pos": v.get("pos", ""),
            "meaning": v.get("meaning", ""), "example": v.get("example", ""),
        }

    # ---- 封面
    weather = ('<div class="fx"><i class="cl a"></i><i class="cl b"></i><i class="cl c"></i>'
               '<i class="halo"></i></div>')
    cover = """<section class="page cover">
      <svg viewBox="0 0 1200 400" xmlns="http://www.w3.org/2000/svg">%s</svg>
      %s
      <div class="veil"></div>
      <div class="txt">
        <div><span class="kicker">Yaya Words · Picture Book</span></div>
        <h1>%s</h1>
        <div><span class="sub">%s · %s</span></div>
        <button class="start" id="start">开始阅读 →</button>
      </div>
    </section>""" % (SCENES["cover"](), weather, html.escape(title),
                     html.escape(subtitle or "今天的散文诗"), html.escape(day))

    # ---- 正文页
    pages = []
    for i, p in enumerate(panels):
        acc = ACCENTS[i % len(ACCENTS)]
        scene = p.get("scene", "city")
        art = SCENES.get(scene, SCENES["city"])()
        rows = []
        for j, ln in enumerate(p["lines"]):
            en = highlight(ln, words)
            zh = p.get("zh_lines") or []
            zj = html.escape(zh[j]) if j < len(zh) and zh[j].strip() else ""
            if zj:
                rows.append('<p><span class="en">%s</span><span class="zh">%s</span></p>' % (en, zj))
            else:
                rows.append('<p><span class="en">%s</span></p>' % en)
        body = "".join(rows)
        note = html.escape(p.get("note") or NOTES.get(scene, FALLBACK_NOTE))
        pages.append("""<section class="page spread" style="--accent:%s">
      <div class="artwrap">
        <svg viewBox="0 0 1200 %d" xmlns="http://www.w3.org/2000/svg">%s</svg>
        <div class="fx">
          <i class="cl a"></i><i class="cl b"></i><i class="cl c"></i>
          <i class="pt a"></i><i class="pt b"></i><i class="pt c"></i><i class="pt d"></i>
          <i class="halo"></i>
        </div>
        <div class="sheen"></div>
        <div class="badge">%d</div>
      </div>
      <div class="card">
        <div class="lines">%s</div>
        <div class="note"><b>观察</b>%s</div>
      </div>
    </section>""" % (acc, ART_H, art, i + 1, body, note))

    # ---- 词汇表
    items = []
    for w in words:
        v = vmap.get(w.lower())
        if not v:
            continue
        items.append("""<div class="vitem" data-w="%s">
          <div><span class="w">%s</span><span class="p">%s</span></div>
          <div class="m">%s</div>
          <div class="e">%s</div>
        </div>""" % (html.escape(w), html.escape(v["word"]), html.escape(v["pos"]),
                     html.escape(v["meaning"]), html.escape(v["example"])))
    vpage = """<section class="page vpage">
      <h2>今天的词</h2>
      <div class="hint">共 %d 个 · 点任意一个看例句；读诗时点金色词也能查。</div>
      <input class="search" id="q" placeholder="搜一个词，比如 inevitable">
      <div class="vgrid" id="vgrid">%s</div>
    </section>""" % (len(items), "".join(items))

    # 模板里的 %% 是历史遗留（曾经参与 % 格式化，现在只是被当作纯文本塞进来）。
    # 不还原的话 CSS 里会留下 `height:100%%` 这种非法值，浏览器整条规则丢掉。
    css = CSS_TMPL.replace("__ACC__", ACCENTS[0]).replace("%%", "%")
    vjson = json.dumps(vmap, ensure_ascii=False)
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(T)s · 绘本</title>
<style>%(CSS)s</style></head>
<body>
  <div class="book">
    <div class="topbar">
      <div class="brand">丫丫雅思单词 · 绘本</div>
      <div class="ctrl">
        <div class="lang" id="lang">
          <button data-l="en">英文</button>
          <button data-l="zh">中文</button>
          <button data-l="bi" class="on">双语</button>
        </div>
        <button id="prev" aria-label="上一页">‹</button>
        <span class="pager" id="pager">1 / %(N)d</span>
        <button id="next" aria-label="下一页">›</button>
      </div>
    </div>
    <div class="stage" id="stage">
      %(COVER)s%(PAGES)s%(VPAGE)s
    </div>
    <div class="dots" id="dots"></div>
  </div>
  <div class="sheet" id="sheet">
    <div class="in">
      <button class="x" id="closesheet" aria-label="关闭">×</button>
      <div class="hd"><span class="wd" id="sw"></span><span class="ps" id="sp"></span></div>
      <div class="mn" id="sm"></div>
      <div class="ex" id="se"></div>
    </div>
  </div>
  <div class="foot">丫丫雅思单词 · %(D)s</div>
<script>
var VOCAB = %(VJSON)s;
var pages = [].slice.call(document.querySelectorAll('.page'));
var idx = 0, busy = false;

/* ---- 语言切换：英文 / 中文 / 双语 ---- */
document.documentElement.setAttribute('data-lang', 'bi');
var langBox = document.getElementById('lang');
if (langBox) langBox.addEventListener('click', function(e){
  var b = e.target.closest ? e.target.closest('button[data-l]') : null;
  if (!b) return;
  document.documentElement.setAttribute('data-lang', b.getAttribute('data-l'));
  [].forEach.call(langBox.children, function(x){ x.classList.toggle('on', x === b); });
});

/* ---- 给每张画的元素排好"上色"顺序（越靠前的层越先出现） ---- */
[].forEach.call(document.querySelectorAll('.artwrap > svg, .cover > svg'), function(svg){
  [].forEach.call(svg.children, function(el, n){
    el.style.animationDelay = (n * 0.028) + 's';
  });
});
var pager = document.getElementById('pager');
var dots = document.getElementById('dots');

pages.forEach(function(_, i){
  var d = document.createElement('button');
  d.className = 'dot' + (i === 0 ? ' on' : '');
  d.setAttribute('aria-label', '第 ' + (i + 1) + ' 页');
  d.onclick = function(){ jump(i); };
  dots.appendChild(d);
});

function sync(){
  pager.textContent = (idx + 1) + ' / ' + pages.length;
  [].forEach.call(dots.children, function(d, i){ d.classList.toggle('on', i === idx); });
  document.getElementById('prev').disabled = idx === 0;
  document.getElementById('next').disabled = idx === pages.length - 1;
}

/* 翻到某一页时，让那幅画重新"画一遍" */
function replay(p){
  var svg = p.querySelector('svg');
  if (!svg) return;
  var kids = [].slice.call(svg.children);
  svg.style.animation = 'none';
  kids.forEach(function(el){ el.style.animation = 'none'; });
  void svg.getBoundingClientRect();
  kids.forEach(function(el){ el.style.animation = ''; });
  svg.style.animation = '';
}

function show(i){
  pages.forEach(function(p){ p.classList.remove('active'); });
  pages[i].classList.add('active');
  idx = i; sync();
  replay(pages[i]);
  var s = document.getElementById('sheet'); if (s) s.classList.remove('on');
}

function go(d){
  if (busy) return;
  var n = idx + d;
  if (n < 0 || n >= pages.length) return;
  busy = true;
  var cur = pages[idx], nxt = pages[n];
  cur.classList.add(d > 0 ? 'anim-out-l' : 'anim-out-r');
  setTimeout(function(){
    cur.classList.remove('active', 'anim-out-l', 'anim-out-r');
    nxt.classList.add('active', d > 0 ? 'anim-in-r' : 'anim-in-l');
    replay(nxt);
    idx = n; sync();
    nxt.addEventListener('animationend', function h(){
      nxt.classList.remove('anim-in-r', 'anim-in-l');
      nxt.removeEventListener('animationend', h);
      busy = false;
    });
  }, 320);
}

function jump(i){
  if (busy || i === idx) return;
  if (Math.abs(i - idx) === 1) { go(i > idx ? 1 : -1); return; }
  show(i);                       /* 跨页跳转直接切，不逐页翻 */
}

document.getElementById('prev').onclick = function(){ go(-1); };
document.getElementById('next').onclick = function(){ go(1); };
var st = document.getElementById('start');
if (st) st.onclick = function(){ go(1); };
document.addEventListener('keydown', function(e){
  if (e.target && e.target.id === 'q') return;
  if (e.key === 'ArrowRight') go(1);
  if (e.key === 'ArrowLeft') go(-1);
  if (e.key === 'Escape') document.getElementById('sheet').classList.remove('on');
});

/* 点词查义 */
var sheet = document.getElementById('sheet');
function openWord(w){
  var v = VOCAB[String(w).toLowerCase()];
  if (!v) return;
  document.getElementById('sw').textContent = v.word;
  document.getElementById('sp').textContent = v.pos || '';
  document.getElementById('sm').textContent = v.meaning || '';
  document.getElementById('se').textContent = v.example ? 'e.g. ' + v.example : '';
  sheet.classList.add('on');
}
document.getElementById('closesheet').onclick = function(){ sheet.classList.remove('on'); };
document.addEventListener('click', function(e){
  var t = e.target.closest ? e.target.closest('.v, .vitem') : null;
  if (t) { openWord(t.getAttribute('data-w')); return; }
  if (!e.target.closest('.sheet')) sheet.classList.remove('on');
});

/* 词汇表搜索 */
var q = document.getElementById('q');
if (q) q.addEventListener('input', function(){
  var k = q.value.trim().toLowerCase();
  [].forEach.call(document.querySelectorAll('.vitem'), function(it){
    var hit = !k || it.textContent.toLowerCase().indexOf(k) >= 0;
    it.style.display = hit ? '' : 'none';
  });
});

show(0);
</script>
</body></html>
""" % {"T": html.escape(title), "CSS": css, "N": 1 + len(pages) + 1,
       "COVER": cover, "PAGES": "".join(pages), "VPAGE": vpage,
       "VJSON": vjson, "D": html.escape(day)}


def main():
    ap = argparse.ArgumentParser(description="把散文诗做成可交互的 HTML 绘本")
    ap.add_argument("--json", help="内容 JSON（title/date/subtitle/story/words；兼容旧键 poem）")
    ap.add_argument("--vocab", help="词表 JSON：`ielts.py poem --json` 的输出")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--poem-file")
    ap.add_argument("--poem")
    ap.add_argument("--zh", help="中文译文 JSON（`{\"poem_zh\":[...]}`），或含 poem_zh 的诗 JSON；"
                                 "行数要与 poem 一致，空行同样分段")
    ap.add_argument("--words")
    ap.add_argument("--scenes")
    ap.add_argument("--date")
    ap.add_argument("--out")
    ap.add_argument("--name")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--chrome")
    ap.add_argument("--no-png", action="store_true", help="默认就只出 HTML；加不加都一样")
    ap.add_argument("--png", action="store_true", help="额外用 Chrome 截一张封面缩略图")
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
        # 键名优先 story（童话）/ tale，最后才认旧的 poem
        lines = as_lines(data.get("story") or data.get("tale") or data.get("poem") or "")
    if a.words:
        words = [w.strip() for w in re.split(r"[,\n]", a.words) if w.strip()]
    else:
        words = [str(w).strip() for w in (data.get("words") or []) if str(w).strip()]
    if not lines:
        print("⚠️ 诗正文是空的。", file=sys.stderr)
        return 2

    vocab = []
    if a.vocab:
        with open(a.vocab, encoding="utf-8-sig") as f:
            vd = json.load(f)
        vocab = vd.get("words", vd) if isinstance(vd, dict) else vd
    if data.get("panels"):
        panels = [{"scene": p.get("scene", "city"), "lines": as_lines(p.get("lines") or []),
                   "note": p.get("note")} for p in data["panels"]]
    else:
        order = [s.strip() for s in (a.scenes or "").split(",") if s.strip()] or DEFAULT_ORDER
        panels = [{"scene": order[i % len(order)], "lines": st}
                  for i, st in enumerate(split_stanzas(lines))]
    panels = [p for p in panels if p["lines"]]
    if not panels:
        print("⚠️ 没切出任何一段。", file=sys.stderr)
        return 2

    # ---- 中文译文（有就双语，没有也不报错，退化成纯英文）
    zh_data = {}
    if a.zh:
        with open(a.zh, encoding="utf-8-sig") as f:
            zh_data = json.load(f)
    # 译文键名：poem_zh 是历史名，也接受童话用的 zh（列表，或 {"1":"..."} 这种按段编号）
    zh_raw = zh_data.get("poem_zh") or data.get("poem_zh") or data.get("zh") or []
    if isinstance(zh_raw, dict):
        zh_raw = [zh_raw[k] for k in sorted(
            zh_raw, key=lambda x: int(x) if str(x).lstrip("-").isdigit() else 0)]
    zh_raw = as_lines(zh_raw) if isinstance(zh_raw, str) else [str(x) for x in zh_raw]
    # 紧凑写法（每段一条译文、中间没有分段空行，童话 JSON 就是这么存的）→
    # 补上分段空行，交给下面「按行对齐」的老逻辑，省得两套格式打架
    if zh_raw and all(x.strip() for x in zh_raw) and len(zh_raw) == len(panels):
        _z = []
        for _x in zh_raw:
            _z += [_x, ""]
        zh_raw = _z
    zh_blocks = split_stanzas(zh_raw)
    for i, p in enumerate(panels):
        p["zh_lines"] = zh_blocks[i] if i < len(zh_blocks) else []
    if zh_blocks:
        n_en = sum(len(p["lines"]) for p in panels)
        n_zh = sum(len(b) for b in zh_blocks)
        if n_en != n_zh:
            print("⚠️ 中英行数不一致（英 %d 行 / 中 %d 行），多出来的行会没有译文。"
                  % (n_en, n_zh), file=sys.stderr)

    # 必须 abspath：--png 会用 file:// 打开这个路径，相对路径会变成 file://storybook.html → ERR_INVALID_URL
    out_dir = os.path.abspath(os.path.expanduser(a.out or POEM_DIR))
    os.makedirs(out_dir, exist_ok=True)
    stem = a.name or ("book-" + day)
    html_path = os.path.join(out_dir, stem + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(title, subtitle, day, panels, words, vocab))

    png_path = None
    if a.png:
        chrome = find_chrome(a.chrome)
        if chrome:
            png_path = os.path.join(out_dir, stem + ".png")
            h = measure(chrome, html_path) or 1200
            ok, _ = shoot(chrome, html_path, png_path, min(h, 1400), a.scale)
            if not ok:
                png_path = None

    res = {"html": html_path, "png": png_path, "pages": 1 + len(panels) + 1,
           "words": len(words), "vocab": len(vocab)}
    if a.json_out:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print("📖 绘本：%s（%d 页，%d 个可点词）" % (html_path, res["pages"], len(words)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
