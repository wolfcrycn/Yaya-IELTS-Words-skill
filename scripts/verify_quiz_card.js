#!/usr/bin/env node
/* 答题卡回归测试 —— 改完 assets/quiz-template.html 后跑一次，确保没把「只收数据不做判定」或防泄露改坏。
 *
 *   NODE=${NODE:-$(command -v node)}   # 或填你的 node 绝对路径
 *   "$NODE" scripts/verify_quiz_card.js                       # 默认测 assets/sample-quiz-card.html
 *   "$NODE" scripts/verify_quiz_card.js <某张生成的卡片.html>
 *   "$NODE" scripts/verify_quiz_card.js <卡片.html> <回执输出路径> <期望答案 JSON 路径>
 *
 * 用最小 DOM 桩**真实执行卡片里的 JS**（解析渲染出的 <input>/<button>、模拟输入与点击），断言：
 *   1) 正面只给题干，答案不泄露（word 模式藏中文；cn 模式藏英文）
 *   2) 卡片上只有「忘了」一个按钮，没有任何判对错的痕迹
 *   3) 输入框可编辑；输入后底栏进度自动刷新；**卡片不做回执预览**（只在点复制时现取输入框）
 *   4) 点「忘了」自动把该卡答案填成「忘了」并跳到下一张，回执里如实体现
 *   5) 「复制回执」现取全部输入框的内容生成回执；改输入框后回执同步变化；空的记「未作答」
 *   6) 回车把焦点跳到下一张
 *   7) 卡面带例句；「看中文写英文」模式下例句里的答案被遮成 ______，绝不泄露
 *   8) 把回执落到文件，交给 Python 侧 parse_raw_answers 做跨语言一致性校验
 * 每轮张数由卡片里的 DATA.cards.length 决定（当前默认 10），断言全部按张数自适应。
 * 退出码 0=全通过，1=有失败（可直接接进 CI/钩子）
 */
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const target = process.argv[2] || path.join(__dirname, "..", "assets", "sample-quiz-card.html");
const receiptOut = process.argv[3] || "";
const expectOut = process.argv[4] || "";
const raw = fs.readFileSync(target, "utf8");

const scriptMatch = raw.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.error("找不到 <script>"); process.exit(1); }
const script = scriptMatch[1];

/* ---------------- 最小 DOM 桩 ---------------- */
const copied = [];            // 剪贴板收到的内容
const focusState = { i: -1 }; // 最后获得焦点的输入框下标
const docH = {};              // document 级事件处理函数
let inputs = [];              // 从渲染结果里解析出来的输入框
let buttons = [];             // ……以及按钮

const decode = (s) => String(s)
  .replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

function mkEl(tag, id) {
  const el = {
    tag, id, track: false, _html: "", textContent: "", value: "", placeholder: "",
    disabled: false, readOnly: false, dataset: {}, style: {}, __h: {},
    focus() { focusState.i = Number(el.dataset.in); },
    blur() {},
    select() {}, setSelectionRange() {}, setAttribute() {}, appendChild() {}, removeChild() {},
    closest(sel) {
      if (/input\[data-in\]/.test(sel)) return el.tag === "input" && el.dataset.in != null ? el : null;
      if (/button\[data-forget\]/.test(sel)) return el.tag === "button" && el.dataset.forget != null ? el : null;
      return null;
    },
    addEventListener(t, fn) { (el.__h[t] = el.__h[t] || []).push(fn); },
    fire(t, ev) { (el.__h[t] || []).forEach((fn) => fn(ev || { target: el, preventDefault() {} })); },
    get innerHTML() { return el._html; },
    set innerHTML(v) { el._html = v; if (el.track) parseCards(v); },
  };
  return el;
}

function attrsOf(str) {
  const o = {};
  String(str).replace(/([a-zA-Z-]+)(?:="([^"]*)")?/g, (m, k, v) => { o[k] = v == null ? "" : v; return m; });
  return o;
}

function parseCards(html) {
  inputs = [];
  buttons = [];
  let m;
  const ire = /<input\b([^>]*?)\/?>/g;
  while ((m = ire.exec(html))) {
    const a = attrsOf(m[1]);
    if (a["data-in"] == null) continue;
    const el = mkEl("input", "input" + a["data-in"]);
    el.dataset = { in: a["data-in"] };
    el.value = a.value ? decode(a.value) : "";
    el.readOnly = /readonly/.test(m[1]);
    el.placeholder = a.placeholder ? decode(a.placeholder) : "";
    inputs.push(el);
  }
  const bre = /<button\b([^>]*?)>([\s\S]*?)<\/button>/g;
  while ((m = bre.exec(html))) {
    const a = attrsOf(m[1]);
    const el = mkEl("button", "button" + buttons.length);
    el.dataset = { forget: a["data-forget"] == null ? null : a["data-forget"] };
    el.textContent = m[2].trim();
    buttons.push(el);
  }
  inputs.sort((x, y) => Number(x.dataset.in) - Number(y.dataset.in));
  return { inputs, buttons };
}

const store = {};
store.cards = mkEl("main", "cards");
store.cards.track = true;
["meta", "prog", "copy", "hint2"].forEach((id) => { store[id] = mkEl("div", id); });

const document = {
  getElementById: (id) => store[id] || (store[id] = mkEl("div", id)),
  addEventListener: (t, fn) => { (docH[t] = docH[t] || []).push(fn); },
  fire: (t, ev) => { (docH[t] || []).forEach((fn) => fn(ev)); },
  createElement: (tag) => mkEl(tag, tag),
  body: { appendChild() {}, removeChild() {} },
  execCommand: () => true,
  querySelector: (sel) => {
    let m = /input\[data-in="(\d+)"\]/.exec(sel);
    if (m) return inputs.find((x) => Number(x.dataset.in) === Number(m[1])) || null;
    m = /button\[data-forget="(\d+)"\]/.exec(sel);
    if (m) return buttons.find((x) => Number(x.dataset.forget) === Number(m[1])) || null;
    return null;
  },
  querySelectorAll: (sel) => {
    if (/input\[data-in\]/.test(sel)) return inputs.slice();
    if (/button\[data-forget\]/.test(sel)) return buttons.slice();
    return [];
  },
};

const sandbox = {
  document,
  window: {},
  navigator: {
    clipboard: {
      writeText(t) { copied.push(t); return { then(f) { if (f) f(); } }; },
    },
  },
  console, JSON, String, Array, Object, Number, RegExp, Math,
  __copied: copied,
  __focus: focusState,
  __RAW__: raw,
};
const ctx = vm.createContext(sandbox);

/* ---------------- 测试脚本（与模板同作用域执行） ---------------- */
const test = `
const OUT = [];
function ok(name, cond, extra) { OUT.push((cond ? "PASS  " : "FAIL  ") + name + (extra ? "   [" + extra + "]" : "")); }
const ZW = ASK_CN;
const N = DATA.cards.length;
// 这套断言会驱动第 1/2/3 张卡（索引 0/1/2），并留一张不填来验「未作答」，故样本至少 4 张
if (N < 4) throw { __skip__: true, n: N };
const input = (i) => document.querySelector('input[data-in="' + i + '"]');
const forgetBtn = (i) => document.querySelector('button[data-forget="' + i + '"]');
function type(i, v){
  const el = input(i);
  el.value = v;
  document.fire("input", { target: el, preventDefault(){} });
  return el;
}
function clickForget(i){
  const b = forgetBtn(i);
  document.fire("click", { target: b, preventDefault(){} });
  return b;
}
function clickCopy(){
  globalThis.__copied.length = 0;
  document.getElementById("copy").fire("click");
  return globalThis.__copied[0];
}
function senseOf(meaning){ return String(meaning).split(/[；;，,、/|]/)[0].trim(); }
function cnt(s, re){ return (String(s).match(re) || []).length; }
const prompt = (i) => ZW ? DATA.cards[i].word : DATA.cards[i].meaning;

// ---------- 1) 结构：按钮只有「忘了」、正面不泄露答案 ----------
const html = document.getElementById("cards").innerHTML;
OUT.push("  · 每轮张数 N = " + N);
ok("每张卡刚好一个按钮", cnt(html, /<button/g) === N, cnt(html, /<button/g) + " 个");
ok("这个按钮就是「忘了」", cnt(html, /data-forget=/g) === N && cnt(html, />忘了<\\/button>/g) === N);
ok("没有别的动作按钮残留",
   ["data-save", "data-edit", "data-skip", "data-check"].every(a => html.indexOf(a) < 0));
ok("输入框不是只读", html.indexOf("readonly") < 0);
ok("N 张卡 = N 个输入框", document.querySelectorAll('input[data-in]').length === N);
if (ZW) {
  ok("正面出现英文单词", html.indexOf(DATA.cards[0].word) >= 0);
  ok("提示为“看英文写中文”", html.indexOf("看英文，写出中文意思") >= 0);
  const leak = DATA.cards.filter(c => html.indexOf(c.meaning) >= 0);
  ok("正面不泄露中文意思", leak.length === 0, leak.slice(0, 3).map(c => c.word + "=" + c.meaning).join(","));
} else {
  ok("正面出现中文意思", html.indexOf(DATA.cards[0].meaning) >= 0);
  ok("提示为“看中文写英文”", html.indexOf("看中文，写出英文单词") >= 0);
  const leak = DATA.cards.filter(c => html.indexOf(c.word) >= 0);
  ok("正面不泄露英文单词", leak.length === 0, leak.slice(0, 3).map(c => c.word).join(","));
  ok("给了首字母与字母数提示", html.indexOf("个字母") >= 0);
}

// ---------- 1.5) 例句 ----------
const withEx = DATA.cards.filter(c => (c.example || "").trim());
ok("卡片带例句区块", cnt(html, /class="eg"/g) >= withEx.length && cnt(html, /class="egtag"/g) >= withEx.length,
   cnt(html, /class="egtag"/g) + " 个例句 / 词库里有 " + withEx.length + " 条");
const c0 = DATA.cards[0];
if (withEx.length && ZW) {
  ok("word 模式例句原样显示", html.indexOf(c0.example) >= 0, c0.example);
} else if (withEx.length) {
  ok("cn 模式例句遮住答案（有 ______）", html.indexOf("______") >= 0);
}
if (DATA.cards.length > withEx.length) {
  ok("缺例句的卡显示占位提示", html.indexOf("egnone") >= 0);
}
if (!ZW) {
  const exLeak = DATA.cards.filter(c => (c.example || "").trim() && html.indexOf(c.word) >= 0);
  ok("cn 模式例句不泄露英文答案", exLeak.length === 0, exLeak.slice(0, 3).map(c => c.word).join(","));
}
// 遮词逻辑（纯函数，直接测边界）
OUT.push("  · maskWord('Many scientists advocate stricter limits.', 'advocate') -> " +
         maskWord("Many scientists advocate stricter limits.", "advocate"));
ok("maskWord 遮住原形", String(maskWord("Many scientists advocate change.", "advocate")).indexOf("@@BLANK@@") >= 0);
ok("maskWord 遮住 -s 形式", String(maskWord("Poor sleep hinders study.", "hinder")).indexOf("@@BLANK@@") >= 0);
ok("maskWord 遮住 -ed 形式", String(maskWord("Prices fluctuated wildly.", "fluctuate")).indexOf("@@BLANK@@") >= 0);
ok("maskWord 遮住 -ing 形式", String(maskWord("Air is deteriorating fast.", "deteriorate")).indexOf("@@BLANK@@") >= 0);
ok("maskWord 对无关词原样返回",
   maskWord("The weather is fine today.", "curb") === "The weather is fine today.",
   String(maskWord("The weather is fine today.", "curb")));
// 保守策略：只要遮完还残留答案（含 children 这种不规则/派生形式），整句就不显示
ok("遮不住不规则形式 -> null", maskWord("The children ran away.", "child") === null,
   String(maskWord("The children ran away.", "child")));
ok("遮不住派生形式 -> null", maskWord("A considerable amount.", "consider") === null,
   String(maskWord("A considerable amount.", "consider")));
ok("无例句时给占位提示", exampleHtml({ word: "foo", example: "" }).indexOf("还没例句") >= 0);
if (!ZW) {   // 只有「看中文写英文」需要遮词
  ok("遮不住时例句区显示隐藏提示",
     exampleHtml({ word: "child", example: "The children ran." }).indexOf("藏起来") >= 0);
  ok("遮得住时例句区显示空格而非答案",
     exampleHtml({ word: "advocate", example: "Many scientists advocate change." }).indexOf("advocate") < 0);
  ok("遮好的例句真的带 ______",
     exampleHtml({ word: "advocate", example: "Many scientists advocate change." }).indexOf("______") >= 0);
}

// ---------- 2) 页面上不能有判对错的痕迹（「忘了」按钮本身不算）----------
const banned = ["答对", "答错", "参考意思", "正确拼写", "沾点边", "认识", "已记录", "只读"];
const hit = banned.filter(w => html.indexOf(w) >= 0);
ok("卡片不含判对错/记录类文案", hit.length === 0, hit.join("|"));
const badge = ["正确", "模糊", "错误", "❌", "✅"];
const hit2 = badge.filter(w => html.indexOf(w) >= 0);
ok("卡片不含对错徽标", hit2.length === 0, hit2.join("|"));

// ---------- 3) 空态 ----------
ok("没填时复制按钮禁用", document.getElementById("copy").disabled === true);
ok("页面没有回执预览区", __RAW__.indexOf('id="summary"') < 0 && __RAW__.indexOf("回执预览") < 0);
ok("首张输入框自动聚焦", globalThis.__focus.i === 0);

// ---------- 4) 输入后自动刷新 ----------
const w0 = DATA.cards[0];
const ans0 = ZW ? senseOf(w0.meaning) : w0.word;
OUT.push("  · 模式=" + MODE + "  词=" + w0.word + "  义=" + w0.meaning);
type(0, ans0);
ok("输入后进度更新", document.getElementById("prog").textContent === "已填写 1 / " + N,
   document.getElementById("prog").textContent);
ok("输入后复制按钮启用", document.getElementById("copy").disabled === false);
ok("输入后不产生任何回执预览", document.getElementById("summary").innerHTML === "");
type(1, "   ");
ok("只填空格不算已填", document.getElementById("prog").textContent === "已填写 1 / " + N,
   document.getElementById("prog").textContent);

// ---------- 5) 「忘了」按钮：自动填答案 + 跳下一张 ----------
clickForget(1);
ok("点「忘了」自动把答案填成「忘了」", input(1).value === "忘了", input(1).value);
ok("点「忘了」后进度 +1", document.getElementById("prog").textContent === "已填写 2 / " + N,
   document.getElementById("prog").textContent);
ok("点「忘了」后焦点跳到下一张", globalThis.__focus.i === 2, "焦点=" + globalThis.__focus.i);
ok("「忘了」也不产生回执预览", document.getElementById("summary").innerHTML === "");
clickForget(1);
ok("「忘了」不重复计数", document.getElementById("prog").textContent === "已填写 2 / " + N,
   document.getElementById("prog").textContent);

// ---------- 6) 复制 = 现取全部输入框 ----------
type(2, "火车票订票系统");
let got = clickCopy();
OUT.push("  · 回执内容（前 5 行）：\\n" +
  String(got).split("\\n").slice(0, 5).map(l => "      " + l).join("\\n"));
ok("点复制拿到了回执", !!got && got.length > 0);
ok("回执含第 1 张的题干与答案", got.indexOf("1. " + prompt(0) + " → 我答：" + ans0) >= 0);
ok("回执含手写的答案", got.indexOf("我答：火车票订票系统") >= 0);
ok("回执含「忘了」那条", got.indexOf("2. " + prompt(1) + " → 我答：忘了") >= 0);
ok("没填的记成未作答", got.indexOf("我答：（未作答）") >= 0);
ok("回执一共 N 条", cnt(got, /我答：/g) === N, cnt(got, /我答：/g) + " / " + N);
ok("复制后提示已更新", document.getElementById("hint2").textContent.indexOf("已复制") >= 0);

// ---------- 7) 核心：改输入框 → 回执自动同步 ----------
type(2, "波动起伏");
got = clickCopy();
ok("改输入框后回执自动同步", got.indexOf("我答：波动起伏") >= 0 && got.indexOf("火车票订票系统") < 0);
input(1).value = ans0;
document.fire("input", { target: input(1), preventDefault(){} });
got = clickCopy();
ok("手动覆盖「忘了」后回执同步", got.indexOf("2. " + prompt(1) + " → 我答：" + ans0) >= 0);

// ---------- 8) 回车跳下一张 ----------
input(0).focus();
document.fire("keydown", { key: "Enter", target: input(0), preventDefault(){} });
ok("回车把焦点跳到下一张", globalThis.__focus.i === 1, "焦点=" + globalThis.__focus.i);
input(N - 1).focus();
document.fire("keydown", { key: "Enter", target: input(N - 1), preventDefault(){} });
ok("最后一张回车不再乱跳", globalThis.__focus.i === N - 1, "焦点=" + globalThis.__focus.i);

// ---------- 9) 交棒给 Python ----------
type(2, "");
clickForget(N - 1);
const FINAL = receipt();
globalThis.__RECEIPT__ = FINAL;
globalThis.__EXPECT__ = values().map(v => v.trim());
globalThis.__FAILS__ = OUT.filter(l => l.indexOf("FAIL") === 0).length;

console.log("被测文件: " + __TARGET__);
console.log(OUT.join("\\n"));
console.log("\\n" + (globalThis.__FAILS__ ? "❌ " + globalThis.__FAILS__ + " 项未通过"
  : "✅ 全部通过") + "（共 " + OUT.filter(l => /^(PASS|FAIL)/.test(l)).length + " 项断言）");
`;

try {
  vm.runInContext("const __TARGET__ = " + JSON.stringify(target) + ";\n" + script + "\n" + test, ctx,
                  { filename: "quiz-card.js" });
  if (receiptOut && ctx.__RECEIPT__) fs.writeFileSync(receiptOut, ctx.__RECEIPT__, "utf8");
  if (expectOut && ctx.__EXPECT__) fs.writeFileSync(expectOut, JSON.stringify(ctx.__EXPECT__), "utf8");
  process.exit(ctx.__FAILS__ ? 1 : 0);
} catch (e) {
  if (e && e.__skip__) {
    console.log("被测文件: " + target);
    console.log("⚠️  样本只有 " + e.n + " 张卡，回归至少需要 4 张（用 make_sample_card.py --n 4+ 重出）。");
    process.exit(2);
  }
  console.error("运行出错:", e && e.stack || e);
  process.exit(1);
}
