#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把散文诗做成「精致水彩配图 + 动态效果」的 HTML 绘本（青少年向）。

和 make_picturebook.py 的区别：
  - make_picturebook.py：手写 SVG 卡通风，自包含单文件，无需外部图片。
  - make_watercolor_book.py：**用 AI 生成的水彩插画当素材**，滚动式（scroll）
    而非翻页式，视觉更"画册"，适合已经出了图的情况。

用法：
    make_watercolor_book.py --json poem.json --images-dir ./images [--out book/index.html]

目录约定（`--images-dir`）：
    cover.*          封面
    其余文件按文件名排序  →  scene1、scene2 ... 依次对应第 1、2 ... 个段落
也可以显式指定：--images a.jpg,b.jpg,...（同样 c 位第一张是封面）

插画怎么来（同一套 prompt 骨架，改场景即可）：
  精致水彩风格插画，湿画法晕染，可见细腻纸张纹理：<画面描述>。<配色>，
  克制优雅，绘本插画，青少年向，纯插画无文字，无边框
封面建议用 1024x1536（竖版），场景用 1536x1024（横版）。
出图后建议压一下：`sips -s format jpeg -s formatOptions 84 --resampleWidth 1300 x.png --out x.jpg`

输出：单个自包含 HTML（图片按相对路径引用，与 images/ 目录一起分发）。
"""

import argparse
import html
import json
import os
import sys


def split_stanzas(poem):
    """把行数组切成段落（空行分段，返回 [[行...], ...]）"""
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


ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


CSS = """
  :root{
    --paper:#f7f2e7;
    --ink:#2c2b33;
    --ink-soft:#5c5a63;
    --gold:#b8872f;
    --gold-soft:#d9b169;
    --blue:#2f4858;
    --serif: "Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Songti SC","STSong",serif;
    --sans: -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html{scroll-behavior:smooth}
  body{background:var(--paper);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden}

  .grain{position:fixed;inset:0;z-index:60;pointer-events:none;opacity:.5;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='220' height='220' filter='url(%23n)' opacity='0.42'/></svg>");
    mix-blend-mode:multiply}
  .blobs{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
  .blob{position:absolute;border-radius:50%;filter:blur(60px);opacity:.30;mix-blend-mode:multiply;animation:drift 26s ease-in-out infinite alternate}
  .b1{width:46vw;height:46vw;left:-8vw;top:6vh;background:#c9d9d2}
  .b2{width:38vw;height:38vw;right:-10vw;top:32vh;background:#e8d6b8;animation-duration:32s}
  .b3{width:52vw;height:52vw;left:14vw;bottom:-16vh;background:#cfd8e3;animation-duration:38s}
  .b4{width:30vw;height:30vw;right:6vw;bottom:6vh;background:#e6cfc0;animation-duration:29s}
  @keyframes drift{0%{transform:translate(0,0) scale(1)}50%{transform:translate(3vw,-2vh) scale(1.12)}100%{transform:translate(-2vw,3vh) scale(.94)}}

  .progress{position:fixed;top:0;left:0;right:0;height:4px;z-index:70;background:rgba(44,43,51,.06)}
  .progress span{display:block;height:100%;width:0%;
    background:linear-gradient(90deg,var(--blue),var(--gold-soft),var(--gold));
    box-shadow:0 0 12px rgba(184,135,47,.55);border-radius:0 4px 4px 0}

  .hero{position:relative;z-index:1;min-height:100vh;display:grid;place-items:center;text-align:center;padding:6vh 6vw}
  .hero-inner{max-width:min(1000px,92vw)}
  .hero-frame{position:relative;width:min(430px,72vw);margin:0 auto 3.2rem;animation:floatCard 7s ease-in-out infinite alternate}
  @keyframes floatCard{from{transform:translateY(0) rotate(-.5deg)}to{transform:translateY(-14px) rotate(.6deg)}}
  .hero-frame img{width:100%;display:block;border-radius:6px;
    box-shadow:0 30px 70px -30px rgba(47,72,88,.55),0 2px 0 rgba(255,255,255,.6);
    -webkit-mask-image:radial-gradient(115% 105% at 50% 45%,#000 62%,rgba(0,0,0,.55) 88%,transparent 100%);
    mask-image:radial-gradient(115% 105% at 50% 45%,#000 62%,rgba(0,0,0,.55) 88%,transparent 100%)}
  .hero-frame::after{content:"";position:absolute;inset:-14px;border-radius:14px;pointer-events:none;border:1px solid rgba(184,135,47,.28)}
  .kicker{font-size:.78rem;letter-spacing:.42em;text-transform:uppercase;color:var(--gold);margin-bottom:1.4rem;font-weight:600}
  h1{font-family:var(--serif);font-weight:500;font-size:clamp(2rem,6.4vw,4.1rem);line-height:1.12}
  h1 .w{display:inline-block;opacity:0;transform:translateY(22px) rotate(-2deg);filter:blur(6px);animation:ink 1s cubic-bezier(.2,.7,.2,1) forwards}
  @keyframes ink{to{opacity:1;transform:none;filter:blur(0)}}
  .sub{margin-top:1.3rem;color:var(--ink-soft);font-size:clamp(.9rem,1.6vw,1.05rem);letter-spacing:.06em}
  .rule{width:70px;height:1px;background:var(--gold);margin:2rem auto;opacity:.6}
  .scroll-hint{font-size:.76rem;letter-spacing:.3em;color:var(--ink-soft);animation:bob 2.6s ease-in-out infinite}
  .scroll-hint::after{content:"";display:block;width:1px;height:38px;margin:12px auto 0;background:linear-gradient(var(--gold),transparent)}
  @keyframes bob{0%,100%{transform:translateY(0);opacity:.7}50%{transform:translateY(7px);opacity:1}}

  main{position:relative;z-index:1}
  .spread{display:grid;grid-template-columns:1.05fr .95fr;align-items:center;gap:clamp(2rem,5vw,5.5rem);
    max-width:1240px;margin:0 auto;padding:clamp(5rem,11vh,9rem) clamp(1.4rem,5vw,4rem)}
  .spread:nth-of-type(even){grid-template-columns:.95fr 1.05fr}
  .spread:nth-of-type(even) .art{order:2}

  .art{position:relative;will-change:transform}
  .art-inner{position:relative;overflow:hidden;border-radius:5px;
    box-shadow:0 34px 70px -34px rgba(47,72,88,.5),0 1px 0 rgba(255,255,255,.7);
    -webkit-mask-image:radial-gradient(122% 112% at 50% 48%,#000 66%,rgba(0,0,0,.5) 90%,transparent 100%);
    mask-image:radial-gradient(122% 112% at 50% 48%,#000 66%,rgba(0,0,0,.5) 90%,transparent 100%)}
  .art-inner img{display:block;width:100%;height:auto;transform:scale(1.1);opacity:0;
    transition:opacity 1.5s ease,filter 1.5s ease;filter:saturate(.86) contrast(1.02)}
  .spread.in .art-inner img{opacity:1;filter:saturate(1) contrast(1.02)}
  .art-inner::before{content:"";position:absolute;inset:0;z-index:2;pointer-events:none;
    background:radial-gradient(120% 90% at 50% 50%,transparent 55%,rgba(247,242,231,.55) 100%);
    mix-blend-mode:screen;opacity:.9}
  .art-cap{position:absolute;left:-.4rem;bottom:-2.4rem;font-family:var(--serif);font-style:italic;
    color:var(--ink-soft);font-size:.86rem;letter-spacing:.04em;opacity:.8}

  .copy{max-width:34rem}
  .num{display:inline-flex;align-items:center;justify-content:center;font-family:var(--serif);
    font-size:1rem;letter-spacing:.2em;color:var(--gold);border:1px solid rgba(184,135,47,.4);
    border-radius:50%;width:2.5rem;height:2.5rem;margin-bottom:1.6rem}
  .copy p{font-family:var(--serif);font-size:clamp(1.02rem,1.55vw,1.28rem);line-height:1.95;
    letter-spacing:.012em;color:var(--ink);opacity:0;transform:translateY(16px);filter:blur(4px);
    transition:opacity .9s cubic-bezier(.2,.7,.2,1),transform .9s cubic-bezier(.2,.7,.2,1),filter .9s ease}
  .spread.in .copy p{opacity:1;transform:none;filter:blur(0)}
  .spread.in .copy p:nth-child(2){transition-delay:.10s}
  .spread.in .copy p:nth-child(3){transition-delay:.20s}
  .spread.in .copy p:nth-child(4){transition-delay:.30s}
  .spread.in .copy p:nth-child(5){transition-delay:.40s}
  .spread.in .copy p:nth-child(6){transition-delay:.50s}
  .spread.in .copy p:nth-child(7){transition-delay:.60s}
  .spread.in .copy p:nth-child(8){transition-delay:.70s}

  .word{background:linear-gradient(180deg,transparent 58%,rgba(217,177,105,.42) 58%);padding:0 .06em;border-radius:2px;transition:background .5s ease,color .3s ease}
  .word.lit{background:linear-gradient(180deg,transparent 52%,rgba(184,135,47,.72) 52%);color:#3a2a06;text-shadow:0 1px 0 rgba(255,255,255,.5)}
  body.no-hl .word{background:none;padding:0}

  /* ---- 英文 / 中文 / 双语 ---- */
  .copy .en{display:block}
  .copy .zh{display:block;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
    font-size:.58em;line-height:1.72;letter-spacing:.02em;color:#8d8779;margin-top:2px}
  html[data-lang="en"] .copy .zh{display:none}
  html[data-lang="zh"] .copy .en{display:none}
  html[data-lang="zh"] .copy .zh{font-size:.86em;color:#3a3f45;margin-top:0}
  .lang{display:flex;align-items:center;gap:3px;background:rgba(255,255,255,.82);
    border:1px solid rgba(47,72,88,.16);border-radius:999px;padding:3px;
    backdrop-filter:blur(8px);box-shadow:0 8px 20px -12px rgba(47,72,88,.6)}
  .lang button{border:0;background:transparent;font-family:inherit;font-size:.72rem;font-weight:700;
    letter-spacing:.06em;color:#8b8474;padding:5px 10px;border-radius:999px;cursor:pointer;
    white-space:nowrap;transition:background .16s,color .16s}
  .lang button:hover{background:#f4ead4}
  .lang button.on{background:var(--blue);color:#f7f2e7}

  .finale{position:relative;z-index:1;text-align:center;max-width:1100px;margin:0 auto;
    padding:clamp(4rem,9vh,7rem) clamp(1.4rem,5vw,4rem) 6rem}
  .finale h2{font-family:var(--serif);font-weight:500;letter-spacing:.24em;text-transform:uppercase;
    font-size:.82rem;color:var(--gold);margin-bottom:2.6rem}
  .cloud{display:flex;flex-wrap:wrap;gap:.7rem;justify-content:center}
  .cloud span{font-family:var(--serif);font-size:.95rem;padding:.42rem .82rem;border-radius:999px;
    background:rgba(255,255,255,.62);border:1px solid rgba(47,72,88,.12);color:var(--blue);
    opacity:0;transform:translateY(12px) scale(.96);animation:pop .8s cubic-bezier(.2,.7,.2,1) forwards}
  @keyframes pop{to{opacity:1;transform:none}}
  .cloud span:hover{background:var(--gold-soft);color:#3a2a06;border-color:transparent}
  footer{position:relative;z-index:1;text-align:center;padding:3rem 1.5rem 4rem;color:var(--ink-soft);font-size:.78rem;letter-spacing:.16em}

  .tools{position:fixed;right:1.1rem;bottom:1.1rem;z-index:80;display:flex;gap:.5rem}
  .tools button{font-family:var(--sans);font-size:.75rem;letter-spacing:.08em;padding:.5rem .85rem;
    border-radius:999px;cursor:pointer;background:rgba(255,255,255,.82);border:1px solid rgba(47,72,88,.16);
    color:var(--blue);backdrop-filter:blur(8px);box-shadow:0 8px 20px -12px rgba(47,72,88,.6);
    transition:transform .2s ease,background .2s ease}
  .tools button:hover{transform:translateY(-2px);background:#fff}

  @media (max-width:860px){
    .spread,.spread:nth-of-type(even){grid-template-columns:1fr;gap:2.6rem}
    .spread:nth-of-type(even) .art{order:0}
    .copy p{font-size:1.06rem;line-height:1.9}
    .art-cap{bottom:-1.6rem}
  }
  @media (prefers-reduced-motion:reduce){
    *{animation:none!important;transition:none!important}
    .copy p,h1 .w,.art-inner img,.cloud span{opacity:1!important;transform:none!important;filter:none!important}
  }
"""

JS = """
(function(){
  var WORDS = __WORDS__;

  function esc(s){return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');}
  function forms(w){
    var o={}, stem=w.replace(/e$/,'');
    [w, w+'s', w+'es', w+'ed', w+'d', stem+'ing', stem+'ies', stem+'ied', w+'ied'].forEach(function(f){o[f]=1;});
    return Object.keys(o).sort(function(a,b){return b.length-a.length;});
  }
  var re = new RegExp('\\\\b(' + WORDS.map(forms).map(function(fs){return fs.map(esc).join('|');}).join('|') + ')\\\\b','gi');
  /* 只高亮英文层：双语模式下 .copy p 里还有 <span class="zh">，
     直接拿 p.textContent 会把中文也一起吃进去。 */
  document.querySelectorAll('.copy .en').forEach(function(p){
    p.innerHTML = p.textContent.replace(re, '<span class="word">$1</span>');
  });

  var t = document.getElementById('title'), title = __TITLE__;
  title.split(' ').forEach(function(word,i){
    var s=document.createElement('span'); s.className='w'; s.textContent=word;
    s.style.animationDelay=(0.35+i*0.11)+'s'; t.appendChild(s);
    t.appendChild(document.createTextNode(' '));
  });

  var cloud=document.getElementById('cloud');
  WORDS.forEach(function(w,i){
    var s=document.createElement('span'); s.textContent=w; s.style.animationDelay=(i*0.035)+'s';
    cloud.appendChild(s);
  });

  /* ---- 语言切换：英文 / 中文 / 双语 ---- */
  document.documentElement.setAttribute('data-lang','bi');
  var langBox=document.getElementById('lang');
  if(langBox) langBox.addEventListener('click', function(e){
    var b=e.target.closest ? e.target.closest('button[data-l]') : null;
    if(!b) return;
    document.documentElement.setAttribute('data-lang', b.getAttribute('data-l'));
    [].forEach.call(langBox.children, function(x){ x.classList.toggle('on', x===b); });
  });

  var spreads=[].slice.call(document.querySelectorAll('.spread'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add('in'); } });
    },{threshold:.22});
    spreads.forEach(function(s){io.observe(s);});
    var io2=new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(e.isIntersecting && !e.target.dataset.lit){
          e.target.dataset.lit='1';
          e.target.querySelectorAll('.word').forEach(function(w,i){
            setTimeout(function(){ w.classList.add('lit'); setTimeout(function(){w.classList.remove('lit');},900); }, i*55);
          });
        }
      });
    },{threshold:.45});
    spreads.forEach(function(s){io2.observe(s);});
  } else {
    spreads.forEach(function(s){s.classList.add('in');});
  }

  var bar=document.getElementById('bar'), arts=[].slice.call(document.querySelectorAll('.art')), ticking=false;
  function onScroll(){
    var h=document.documentElement.scrollHeight-window.innerHeight, y=window.scrollY;
    bar.style.width=(h>0?(y/h)*100:0)+'%';
    arts.forEach(function(a){
      var r=a.getBoundingClientRect();
      if(r.bottom>-200 && r.top<window.innerHeight+200){
        var p=(r.top+r.height/2-window.innerHeight/2)/window.innerHeight;
        a.style.transform='translateY('+(-p*26).toFixed(2)+'px)';
        var img=a.querySelector('img');
        if(img && a.parentElement.classList.contains('in')){
          img.style.transition='opacity 1.5s ease, transform 1.2s cubic-bezier(.2,.7,.2,1), filter 1.5s ease';
          img.style.transform='scale('+(1.02+Math.max(0,Math.min(1,(window.innerHeight-r.top)/(window.innerHeight*1.4)))*0.09).toFixed(3)+')';
        }
      }
    });
    ticking=false;
  }
  window.addEventListener('scroll',function(){ if(!ticking){ ticking=true; requestAnimationFrame(onScroll); } },{passive:true});
  onScroll();

  document.getElementById('hl').addEventListener('click',function(){
    var on=document.body.classList.toggle('no-hl');
    this.textContent=on?'显示词高亮':'隐藏词高亮';
  });
  document.getElementById('top').addEventListener('click',function(){ window.scrollTo({top:0,behavior:'smooth'}); });
})();
"""


def rel_url(img, out_dir):
    return os.path.relpath(img, out_dir).replace(os.sep, "/")


def build_html(title, subtitle, date, panels, words, cover_url):
    spreads = []
    for i, (img, cap, lines, zhs) in enumerate(panels):
        rows = []
        for j, ln in enumerate(lines):
            zj = html.escape(zhs[j]) if j < len(zhs) and zhs[j].strip() else ""
            if zj:
                rows.append('<p><span class="en">%s</span><span class="zh">%s</span></p>'
                            % (html.escape(ln), zj))
            else:
                rows.append('<p><span class="en">%s</span></p>' % html.escape(ln))
        ps = "\n      ".join(rows)
        num = ROMAN[i] if i < len(ROMAN) else str(i + 1)
        spreads.append(
            '  <section class="spread">\n'
            '    <div class="art"><div class="art-inner">'
            '<img src="%s" alt="%s" loading="lazy">'
            '</div><div class="art-cap">%s</div></div>\n'
            '    <div class="copy"><span class="num">%s</span>\n      %s\n    </div>\n'
            '  </section>\n' % (img, html.escape(cap), html.escape(cap), num, ps)
        )

    js = JS.replace("__WORDS__", json.dumps(words, ensure_ascii=False)) \
           .replace("__TITLE__", json.dumps(title, ensure_ascii=False))

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s · 水彩诗绘本</title>
<style>%(css)s</style>
</head>
<body>

<div class="progress"><span id="bar"></span></div>
<div class="blobs">
  <div class="blob b1"></div><div class="blob b2"></div>
  <div class="blob b3"></div><div class="blob b4"></div>
</div>
<div class="grain"></div>

<header class="hero">
  <div class="hero-inner">
    <div class="hero-frame">
      <img src="%(cover)s" alt="水彩封面">
    </div>
    <p class="kicker">丫丫雅思单词 · %(date)s</p>
    <h1 id="title"></h1>
    <div class="rule"></div>
    <p class="sub">%(sub)s</p>
    <p class="scroll-hint" style="margin-top:3.4rem">向下滚动</p>
  </div>
</header>

<main>
%(spreads)s
  <section class="finale">
    <h2>今日的 %(n)d 个词 · 都在上面了</h2>
    <div class="cloud" id="cloud"></div>
  </section>
</main>

<footer>水彩绘本 · 丫丫雅思单词 · %(date)s</footer>

<div class="tools">
  <div class="lang" id="lang">
    <button data-l="en">英文</button>
    <button data-l="zh">中文</button>
    <button data-l="bi" class="on">双语</button>
  </div>
  <button id="hl">隐藏词高亮</button>
  <button id="top">回到封面</button>
</div>

<script>%(js)s</script>
</body>
</html>
""" % {
        "title": html.escape(title),
        "date": html.escape(date),
        "sub": html.escape(subtitle),
        "cover": cover_url,
        "spreads": "\n".join(spreads),
        "css": CSS,
        "js": js,
        "n": len(words),
    }


def collect_images(images_dir=None, images=None):
    if images:
        files = [os.path.abspath(p.strip()) for p in images.split(",") if p.strip()]
    elif images_dir:
        d = os.path.abspath(images_dir)
        exts = (".png", ".jpg", ".jpeg", ".webp")
        names = sorted(n for n in os.listdir(d) if n.lower().endswith(exts))
        cover = [n for n in names if n.lower().startswith("cover")]
        rest = [n for n in names if n not in cover]
        cover.sort()
        file_list = cover + rest
        files = [os.path.join(d, n) for n in file_list]
    else:
        raise SystemExit("需要 --images 或 --images-dir")

    missing = [p for p in files if not os.path.exists(p)]
    if missing:
        raise SystemExit("找不到图片：%s" % ", ".join(missing))
    if len(files) < 2:
        raise SystemExit("至少需要 1 张封面 + 1 张场景图，现在只有 %d 张" % len(files))
    return files


def main():
    ap = argparse.ArgumentParser(description="把散文诗做成水彩配图的动态 HTML 绘本")
    ap.add_argument("--json", help="内容 JSON（title/date/subtitle/story/words；兼容旧键 poem）")
    ap.add_argument("--zh", help="单独的译文 JSON：{\"poem_zh\":[...]}，行数要与 poem 对齐")
    ap.add_argument("--images-dir", help="插画目录：cover.* 作封面，其余按文件名排序")
    ap.add_argument("--images", help="显式指定图片，逗号分隔，第一张是封面")
    ap.add_argument("--out", help="输出 HTML 路径")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--date")
    ap.add_argument("--json-out", action="store_true", help="输出 {html,panels,words} 便于脚本取值")
    a = ap.parse_args()

    data = {}
    if a.json:
        with open(a.json, encoding="utf-8") as f:
            data = json.load(f)

    title = a.title or data.get("title") or "Untitled"
    subtitle = a.subtitle or data.get("subtitle") or ""
    date = a.date or data.get("date") or ""
    # 键名优先 story（童话）/ tale，最后才认旧的 poem
    poem = data.get("story") or data.get("tale") or data.get("poem") or []
    words = data.get("words") or []
    stanzas = split_stanzas(poem)
    if not stanzas:
        raise SystemExit("JSON 里没有正文段落（键名用 story，兼容 poem）")

    files = collect_images(a.images_dir, a.images)

    zh_data = {}
    if a.zh:
        with open(a.zh, encoding="utf-8-sig") as f:
            zh_data = json.load(f)
    # 译文键名：poem_zh 是历史名，也接受童话用的 zh（列表，或 {"1":"..."} 这种按段编号）
    zh_raw = zh_data.get("poem_zh") or data.get("poem_zh") or data.get("zh") or []
    if isinstance(zh_raw, dict):
        zh_raw = [zh_raw[k] for k in sorted(
            zh_raw, key=lambda x: int(x) if str(x).lstrip("-").isdigit() else 0)]
    zh_raw = [str(x) for x in zh_raw]
    # 紧凑写法（每段一条译文、中间没有分段空行，童话 JSON 就是这么存的）→
    # 补上分段空行，交给下面「按行对齐」的老逻辑，省得两套格式打架
    if zh_raw and all(x.strip() for x in zh_raw) and len(zh_raw) == len(stanzas):
        _z = []
        for _x in zh_raw:
            _z += [_x, ""]
        zh_raw = _z
    zh_blocks = split_stanzas(zh_raw)
    if zh_blocks:
        n_en = sum(len(s) for s in stanzas)
        n_zh = sum(len(b) for b in zh_blocks)
        if n_en != n_zh:
            print("⚠️ 中英行数不一致（英 %d / 中 %d），多出来的行会没有译文。" % (n_en, n_zh),
                  file=sys.stderr)

    out = os.path.abspath(a.out) if a.out else os.path.join(os.getcwd(), "index.html")
    out_dir = os.path.dirname(out)
    os.makedirs(out_dir, exist_ok=True)

    cover_url = rel_url(files[0], out_dir)
    scene_files = files[1:]
    panels = []
    for i, st in enumerate(stanzas):
        img = scene_files[i] if i < len(scene_files) else scene_files[i % len(scene_files)]
        cap = st[0][:60].strip(" ,.;—-")
        panels.append((rel_url(img, out_dir),
                       "%s · %s" % (ROMAN[i] if i < len(ROMAN) else i + 1, cap), st,
                       zh_blocks[i] if i < len(zh_blocks) else []))

    html_text = build_html(title, subtitle, date, panels, words, cover_url)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_text)

    result = {"html": out, "panels": len(panels), "words": len(words),
              "scenes_used": min(len(stanzas), len(scene_files))}
    print(json.dumps(result, ensure_ascii=False, indent=1) if a.json_out
          else "🎨 水彩绘本已生成：%s\n   段落 %d 段 · 词 %d 个 · 用了 %d 张场景图"
          % (out, len(panels), len(words), min(len(stanzas), len(scene_files))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
