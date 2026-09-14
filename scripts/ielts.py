#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ielts.py — 雅思备考引擎（艾宾浩斯记忆调度 + 闪卡 + 周报）

子命令:
  init        初始化学习者档案与词库队列
  today       今日任务卡（到期复习 / 新词额度 / 强化池 / 四项技能建议）
  start       开始一次闪卡会话
  quiz        生成本轮 HTML 答题卡（只收集答案，不判定对错）
              本轮有词缺例句时会先拦下来（退出码 2）并列出清单，
              造好例句存进去再跑一次；--allow-missing 可跳过这道闸
  submit      提交本轮回执：--raw 传回执原文（引擎代判）或 --answers 传判好的 c,w,f
  reveal      偷看当前卡片背面
  grade       批改当前卡片 (correct|fuzzy|wrong)
  finish      结束会话并写入当日日志
  stats       统计概览
  report      生成 HTML 周报（含可视化）
  task        记录一项听说读写训练
  example     给词补例句（存 examples.tsv，卡片自动带上）或列出缺例句的词
  poem        列出今天背过的所有单词（写每日童话用；命令名是历史遗留，别改）
  import      导入自定义词表 (CSV/TSV: word|phonetic|pos|meaning|example|topic)
  reset       清空学习进度（需 --yes）

数据目录: ~/.workbuddy/ielts-prep/state.json
词库目录: <skill>/data/words/*.tsv  分隔符 "|"
"""
import argparse
import csv
import html
import json
import os
import random
import re
import sys
from datetime import date, datetime, timedelta

HOME = os.path.expanduser("~")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_DIR = os.path.join(SKILL_DIR, "data", "words")
DATA_DIR = os.environ.get("IELTS_DATA_DIR", os.path.join(HOME, ".workbuddy", "ielts-prep"))
STATE_PATH = os.path.join(DATA_DIR, "state.json")
REPORT_DIR = os.path.join(DATA_DIR, "reports")
EXAMPLES_PATH = os.path.join(DATA_DIR, "examples.tsv")   # 自己的例句缓存（word<TAB>句子）
CUSTOM_DIR = os.path.join(DATA_DIR, "custom-words")      # import 进来的自建词表（也是词库）

# 艾宾浩斯复习间隔（天）：索引 = 升级后的 stage
INTERVAL_BY_STAGE = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15, 6: 30, 7: 60}
MASTER_STAGE = 8          # stage >= 8 视为已掌握，退出复习循环
LEECH_THRESHOLD = 5       # 错误次数达到该值 -> 顽固词
MAX_HISTORY = 30

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 词表里可能混入的零宽字符（BOM 等），必须在解析前清掉
ZERO_WIDTH = "\ufeff\u200b\u200c\u200d\u200e\u200f"

# 每周技能轮换（听说读写）
WEEKLY_PLAN = {
    0: [("listening", "剑桥真题 Section 1+2 精听，逐句听写 1 个 section", 40),
        ("reading",   "限时 20 分钟完成 1 篇 True/False/Not Given 专项", 25)],
    1: [("reading",   "限时 20 分钟 1 篇 Passage，做 Matching Headings", 25),
        ("vocab",     "整理今日错题本，用 5 个新词造句", 15)],
    2: [("writing",   "Task 1 图表作文（动态图）1 篇，限时 20 分钟", 30),
        ("listening", "Section 3 学术对话精听 + 跟读", 20)],
    3: [("speaking",  "Part 2 话题卡 ×3，每题录音 2 分钟并回听", 30),
        ("vocab",     "话题词汇整理：把口语高频搭配写成清单", 15)],
    4: [("writing",   "Task 2 大作文 1 篇，限时 40 分钟，写完必须批改", 50),
        ("reading",   "错题复盘：把上周错的 5 题逐题写出定位句", 20)],
    5: [("mock",      "完整模考一套（听+读+写），严格计时", 170),
        ("speaking",  "Part 1+3 模拟问答，找人对话或用录音自评", 20)],
    6: [("review",    "本周词汇总复习：只练强化池 + 顽固词", 30),
        ("review",    "看周报，定下周目标，重做本周写跑题的作文提纲", 25)],
}

SKILL_CN = {"listening": "听力", "reading": "阅读", "writing": "写作",
            "speaking": "口语", "vocab": "词汇", "mock": "模考", "review": "复盘"}

RESULT_ICON = {"correct": "✅ 认识", "fuzzy": "🤔 模糊", "wrong": "❌ 忘了"}
RESULT_CN = {"correct": "认识", "fuzzy": "模糊", "wrong": "忘了"}

# 答题卡回执的简写：c=认识 f=模糊 w=忘了
ALIAS = {
    "c": "correct", "correct": "correct", "对": "correct", "认识": "correct",
    "会": "correct", "y": "correct", "o": "correct", "1": "correct",
    "f": "fuzzy", "fuzzy": "fuzzy", "模糊": "fuzzy", "半": "fuzzy", "~": "fuzzy",
    "w": "wrong", "wrong": "wrong", "错": "wrong", "忘了": "wrong", "忘": "wrong",
    "n": "wrong", "x": "wrong", "0": "wrong",
}

DEFAULT_PER_ROUND = 10
DEFAULT_ASK_MODE = "word"   # "word"=看英文写中文（默认）; "cn"=看中文写英文
DEFAULT_DAILY_NEW = 50      # 每日新词额度（每日任务总量）
DEFAULT_SESSION_SIZE = 50   # 一批（=一天）放多少张卡
QUIZ_TEMPLATE = "quiz-template.html"
QUIZ_KEEP = 60


def parse_answers(raw):
    """把回执解析成结果列表。支持 'c,w,f' 或 '认识 模糊 忘了' 等写法。"""
    tokens = [t for t in re.split(r"[,\s|/，、]+", (raw or "").strip()) if t]
    out = []
    for t in tokens:
        key = t.strip().lower()
        if key in ALIAS:
            out.append(ALIAS[key])
        elif key in ("-", "?", "_", "跳过"):
            out.append(None)
        else:
            return None, "看不懂的回执片段：%s（可用 c=认识 / f=模糊 / w=忘了）" % t
    return out, None


# ----------------------------------------------------------------------------
# 中文自由输入的语义判分（答题卡只收数据，判分在这里；AI 可作参考或自行覆盖）
# ----------------------------------------------------------------------------
RAW_MARK = "我答："
_CN_POS_RE = re.compile(r"^(n|v|vt|vi|adj|adv|prep|conj|pron|int|art|aux|num|abbr)\.\s*", re.I)
_SENSE_RE = re.compile(r"[；;，,、/|\u3001]")


def norm_cn(s):
    """全角转半角 + 去掉标点空格 + 小写。"""
    buf = []
    for ch in (s or ""):
        o = ord(ch)
        buf.append(chr(o - 0xFEE0) if 0xFF01 <= o <= 0xFF5E else ch)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", "".join(buf)).lower()


def sense_list(meaning):
    """把释义切成义项并归一化（剥掉词性前缀）。"""
    out = []
    for part in _SENSE_RE.split(meaning or ""):
        n = norm_cn(_CN_POS_RE.sub("", part.strip()))
        if n:
            out.append(n)
    return out


def _bigrams(s):
    return [s[i:i + 2] for i in range(len(s) - 1)]


def judge_cn(meaning, raw):
    """中文自由输入 -> correct / fuzzy / wrong。

    命中任一义项（相等或互为子串）=> correct；只沾到部分字词 => fuzzy；
    留空或完全不沾边 => wrong。
    """
    u = norm_cn(raw)
    if not u:
        return "wrong"
    senses = sense_list(meaning)
    if not senses:
        return "correct"
    for s in senses:
        if s == u:
            return "correct"
        if len(s) >= 2 and len(u) >= 2 and (u in s or s in u):
            return "correct"
    for s in senses:
        for g in _bigrams(u):
            if g in s:
                return "fuzzy"
    return "wrong"


def norm_en(s):
    """归一化英文拼写，容忍英美拼写差异（analyse/analyze、colour/color…）。"""
    s = re.sub(r"[^a-z]", "", (s or "").lower())
    s = s.replace("isation", "ization")
    s = re.sub(r"ise$", "ize", s)
    s = re.sub(r"yse$", "yze", s)
    s = re.sub(r"our$", "or", s)
    return s


def judge_en(word, raw):
    """英文拼写比对 -> correct / wrong（拼错了就是 wrong，没有模糊档）。"""
    u = norm_en(raw)
    if not u:
        return "wrong"
    return "correct" if u == norm_en(word) else "wrong"


def parse_raw_answers(raw):
    """解析答题卡回执里的用户答案（按顺序）。

    优先认 `我答：xxx` 标记（回执就是这格式，最稳）；
    没有标记时退化成按 `|` / 换行切分。
    空/未作答会返回 ""，由 judge_cn 判为 wrong。
    """
    txt = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"我答\s*[:：]", RAW_MARK, txt)
    if RAW_MARK in txt:
        out = []
        for seg in txt.split(RAW_MARK)[1:]:
            line = seg.split("\n")[0].strip().strip("|").strip()
            out.append("" if line in ("", "-", "/", "（未作答）", "(未作答)") else line)
        return out
    toks = [t.strip() for t in re.split(r"[|\uff5c\n]+", txt.strip()) if t.strip()]
    return ["" if t in ("-", "/", "（未作答）", "(未作答)") else t for t in toks]


# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------
def today_str():
    return date.today().isoformat()


def d(s):
    return date.fromisoformat(s)


def slug(word):
    s = re.sub(r"[^a-z0-9]+", "-", word.lower().strip()).strip("-")
    return s or "word"


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)


_EX_CACHE = None


def load_examples(force=False):
    """读学习者自己的例句缓存 ~/.workbuddy/ielts-prep/examples.tsv -> {id: 句子}。
    这份缓存是权威的：写了就覆盖词库自带的那句。"""
    global _EX_CACHE
    if _EX_CACHE is not None and not force:
        return _EX_CACHE
    out = {}
    if not os.path.exists(EXAMPLES_PATH):
        _EX_CACHE = out
        return out
    with open(EXAMPLES_PATH, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip().strip(ZERO_WIDTH)
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"\t|\|", line, maxsplit=1)
            if len(parts) < 2:
                continue
            wid, ex = slug(parts[0].strip()), parts[1].strip()
            if wid and ex:
                out[wid] = ex
    _EX_CACHE = out
    return out


_BANK_CACHE = None


def load_bank(force=False):
    """读取 data/words/*.tsv，返回 {id: word_record_template}，按文件顺序去重。
    自动补上 examples.tsv 里自己攒的例句；结果做进程内缓存（10000 词不要反复解析）。"""
    global _BANK_CACHE
    if _BANK_CACHE is not None and not force:
        return _BANK_CACHE
    bank, seen = {}, set()
    # 官方词库 + 用户 import 进来的词表：都是词库，一起读（自建词排在后面，重复的以官方为准）
    for d in (BANK_DIR, CUSTOM_DIR):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith((".tsv", ".txt", ".csv")):
                continue
            path = os.path.join(d, fn)
            # utf-8-sig：带 BOM 的文件不能让注释行被当成词条
            with open(path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip().strip(ZERO_WIDTH)
                    if not line or line.startswith("#"):
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 4:
                        continue
                    word, phonetic, pos, meaning = parts[:4]
                    example = parts[4] if len(parts) > 4 else ""
                    topic = parts[5] if len(parts) > 5 and parts[5] else "general"
                    wid = slug(word)
                    if not word or word.startswith("#") or wid in seen:
                        continue
                    seen.add(wid)
                    bank[wid] = {
                        "id": wid, "word": word, "phonetic": phonetic, "pos": pos,
                        "meaning": meaning, "example": example, "topic": topic,
                    }
    for wid, ex in load_examples().items():
        if wid in bank and ex:
            bank[wid]["example"] = ex
    _BANK_CACHE = bank
    return bank


def bank_lookup(wid):
    """按 id 或原词找词库条目。"""
    bank = load_bank()
    return bank.get(wid) or next((v for v in bank.values() if v["word"] == wid), None)


def peek_word(st, wid):
    """只读取词：绝不往 st["words"] 里写。凡是「扫一遍看看」的场景都要用这个，
    否则 get_word() 会把整库都灌进 state。"""
    return st.get("words", {}).get(wid) or bank_lookup(wid)


def block_shuffle(ids, block=50):
    """按词库文件的自然顺序分块打散：整体保持由易到难，局部不连续。"""
    out = []
    for i in range(0, len(ids), block):
        blk = list(ids[i:i + block])
        random.shuffle(blk)
        out.extend(blk)
    return out


def blank_state():
    bank = load_bank()
    ids = list(bank.keys())
    ids = block_shuffle(ids)
    return {
        "version": 1,
        "created": today_str(),
        "profile": {"target_score": 7.0, "exam_date": None,
                    "daily_new": DEFAULT_DAILY_NEW, "session_size": DEFAULT_SESSION_SIZE,
                    "per_round": DEFAULT_PER_ROUND,
                    "ask_mode": DEFAULT_ASK_MODE},
        "bank_size": len(bank),
        "words": {},
        "new_queue": ids,
        "reinforcement": [],           # [{"id":.., "need":2}, ...]
        "daily": {},                   # date -> log
        "session": None,
        "migrations": {"per_round": DEFAULT_PER_ROUND,
                       "daily_new": DEFAULT_DAILY_NEW,
                       "session_size": DEFAULT_SESSION_SIZE},
    }


def load_state():
    if not os.path.exists(STATE_PATH):
        st = blank_state()
        save_state(st)
        return st
    with open(STATE_PATH, encoding="utf-8") as f:
        st = json.load(f)
    st.setdefault("words", {})
    st.setdefault("reinforcement", [])
    st.setdefault("daily", {})
    st.setdefault("profile", {"target_score": 7.0, "exam_date": None,
                              "daily_new": DEFAULT_DAILY_NEW,
                              "session_size": DEFAULT_SESSION_SIZE})
    st["profile"].setdefault("per_round", DEFAULT_PER_ROUND)
    st["profile"].setdefault("ask_mode", DEFAULT_ASK_MODE)
    if "new_queue" not in st:
        st["new_queue"] = [i for i in load_bank() if i not in st["words"]]
        random.shuffle(st["new_queue"])
    if migrate(st):
        save_state(st)      # 迁移只在第一次改到东西时写盘
    return st


def migrate(st):
    """老存档的一次性升级。只在确实是从未改过的旧默认值上动手，不覆盖用户的选择。
    返回 True 表示改动过、需要落盘。"""
    changed = False
    mig = st.setdefault("migrations", {})
    if mig.get("per_round") != DEFAULT_PER_ROUND:
        # 3 是历史上的默认值，不可能是用户特意选的 → 升到新的每轮 10 张
        if st["profile"].get("per_round") == 3:
            st["profile"]["per_round"] = DEFAULT_PER_ROUND
            changed = True
        sess = st.get("session")
        if sess and sess.get("per_round") == 3:
            sess["per_round"] = DEFAULT_PER_ROUND   # 之后的轮次立刻按新张数走
            changed = True
        mig["per_round"] = DEFAULT_PER_ROUND
        changed = True
    if mig.get("daily_new") != DEFAULT_DAILY_NEW:
        # 30 是历史上的新词额度默认值；用户从没改过 → 升到新的每日任务 50
        if st["profile"].get("daily_new") == 30:
            st["profile"]["daily_new"] = DEFAULT_DAILY_NEW
            changed = True
        mig["daily_new"] = DEFAULT_DAILY_NEW
        changed = True
    if mig.get("session_size") != DEFAULT_SESSION_SIZE:
        # 20 同理：一批（一天）的卡片数升到 50
        if st["profile"].get("session_size") == 20:
            st["profile"]["session_size"] = DEFAULT_SESSION_SIZE
            changed = True
        mig["session_size"] = DEFAULT_SESSION_SIZE
        changed = True
    return changed


def save_state(st):
    ensure_dirs()
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)


def day_log(st, day=None):
    day = day or today_str()
    return st["daily"].setdefault(day, {
        "new_issued": 0, "review_done": 0, "correct": 0, "fuzzy": 0,
        "wrong": 0, "minutes": 0, "mastered": 0, "tasks": [], "words": [],
    })


def today_word_ids(st, day=None):
    """某天背过的词 id，按当天首次出现顺序。优先用 day_log 里记的顺序，
    没有的话（老数据）回退到扫 words[*].history。"""
    day = day or today_str()
    ids = (st.get("daily", {}).get(day) or {}).get("words") or []
    if ids:
        return list(dict.fromkeys(ids))
    out = []
    for wid, w in st.get("words", {}).items():
        for entry in (w.get("history") or []):
            if entry and entry[0] == day:
                out.append(wid)
                break
    return out


def get_word(st, wid):
    w = st["words"].get(wid)
    if w is None:
        tpl = bank_lookup(wid)
        if tpl is None:
            return None
        w = dict(tpl)
        w.update({"status": "new", "stage": 0, "due": today_str(), "wrong": 0,
                  "right": 0, "streak": 0, "first_seen": today_str(),
                  "last_seen": None, "graduated": None, "leech": False,
                  "history": []})
        st["words"][wid] = w
    elif not (w.get("example") or "").strip():
        # 词库里后来补了例句（examples.tsv 新加），已经学过的词也要跟上
        tpl = bank_lookup(wid)
        if tpl and (tpl.get("example") or "").strip():
            w["example"] = tpl["example"]
    own = load_examples().get(wid)
    if own and w.get("example") != own:
        w["example"] = own      # 自己攒的例句永远优先，哪怕词库自带一句
    return w


def issue_new(st, n):
    """从新词队列发放 n 个从未出现过的词。"""
    out = []
    for _ in range(n):
        if not st["new_queue"]:
            break
        wid = st["new_queue"].pop(0)
        w = get_word(st, wid)
        w["status"] = "learning"
        w["stage"] = 0
        w["due"] = today_str()
        w["first_seen"] = today_str()
        out.append(wid)
    if out:
        day_log(st)["new_issued"] += len(out)
    return out


def due_review_ids(st, today):
    out = []
    for wid, w in st["words"].items():
        if w["status"] not in ("learning", "leech"):
            continue
        if w.get("due") and d(w["due"]) <= d(today):
            out.append(wid)
    out.sort(key=lambda i: (st["words"][i].get("due") or "", -st["words"][i]["stage"]))
    return out


def pool_ids(st):
    return [p["id"] for p in st["reinforcement"] if p["need"] > 0]


def bump_pool(st, wid, result):
    """强化池维护：correct 削减、wrong 需答对 2 次、fuzzy 需答对 1 次。"""
    for p in st["reinforcement"]:
        if p["id"] == wid:
            if result == "correct":
                p["need"] -= 1
            elif result == "wrong":
                p["need"] = 2
            else:
                p["need"] = max(p["need"], 1)
            break
    else:
        if result == "wrong":
            st["reinforcement"].append({"id": wid, "need": 2})
        elif result == "fuzzy":
            st["reinforcement"].append({"id": wid, "need": 1})
    st["reinforcement"] = [p for p in st["reinforcement"] if p["need"] > 0]


def schedule_after_grade(w, result, today):
    """按艾宾浩斯曲线更新 stage / due / status，返回描述文本。"""
    old = w["stage"]
    if result == "correct":
        new = min(old + 1, MASTER_STAGE)
        w["stage"] = new
        w["right"] += 1
        w["streak"] += 1
        if new >= MASTER_STAGE:
            w["status"] = "mastered"
            w["due"] = None
            w["graduated"] = today
            return "🎉 毕业！已移出复习循环"
        w["due"] = (d(today) + timedelta(days=INTERVAL_BY_STAGE[new])).isoformat()
        return "📈 阶段 %d → %d，%d 天后再复习（%s）" % (
            old, new, INTERVAL_BY_STAGE[new], w["due"])
    if result == "fuzzy":
        gap = max(1, INTERVAL_BY_STAGE.get(w["stage"], 1))
        w["due"] = (d(today) + timedelta(days=gap)).isoformat()
        w["streak"] = 0
        return "🤔 阶段保持 %d，%d 天后再复习（%s）" % (w["stage"], gap, w["due"])
    # wrong
    new = max(0, old - 2)
    w["stage"] = new
    w["wrong"] += 1
    w["streak"] = 0
    w["due"] = today
    if w["wrong"] >= LEECH_THRESHOLD:
        w["leech"] = True
    return "⬇️ 阶段 %d → %d，已加入强化池，今天会再考你" % (old, new)


def fmt_front(w):
    return "%s   %s   %s" % (w["word"], w["phonetic"], w["pos"])


def fmt_back(w):
    s = "   %s  %s" % (w["pos"], w["meaning"])
    if w.get("example"):
        s += "\n   e.g. %s" % w["example"]
    return s


# ----------------------------------------------------------------------------
# 命令
# ----------------------------------------------------------------------------
def cmd_init(a):
    ensure_dirs()
    st = load_state()
    if a.daily_new:
        st["profile"]["daily_new"] = a.daily_new
        # 「每日任务量」＝一批的张数，一起改，否则 start 会被旧的 session_size 卡住
        st["profile"]["session_size"] = a.daily_new
    if a.target:
        st["profile"]["target_score"] = a.target
    if a.exam_date:
        st["profile"]["exam_date"] = a.exam_date
    save_state(st)
    print("✅ 雅思备考档案已就绪")
    print("   数据目录: %s" % DATA_DIR)
    print("   词库总量: %d 词 | 每日新词: %d | 目标分: %s | 考试日: %s"
          % (st["bank_size"], st["profile"]["daily_new"],
             st["profile"]["target_score"], st["profile"]["exam_date"] or "未设置"))
    print("\n下一步：说「开始背单词」即可进入闪卡练习。")


def build_today(st, size=None):
    today = today_str()
    log = day_log(st)
    size = size or st["profile"].get("session_size", DEFAULT_SESSION_SIZE)
    daily_new = st["profile"]["daily_new"]
    remain_new = max(0, daily_new - log["new_issued"])
    due = due_review_ids(st, today)
    pool = pool_ids(st)
    wd = date.today().weekday()
    tasks = [{"skill": s, "name": n, "minutes": m} for s, n, m in WEEKLY_PLAN[wd]]
    countdown = None
    if st["profile"].get("exam_date"):
        try:
            countdown = (d(st["profile"]["exam_date"]) - d(today)).days
        except Exception:
            countdown = None
    return {
        "date": today, "weekday": WEEKDAY_CN[wd],
        "exam_countdown": countdown,
        "due_review": due, "due_review_count": len(due),
        "pool": pool, "pool_count": len(pool),
        "new_quota": remain_new, "session_size": size,
        "suggested_tasks": tasks,
        "today_log": log,
        "totals": summarize(st),
    }


def summarize(st):
    words = st["words"]
    mastered = sum(1 for w in words.values() if w["status"] == "mastered")
    learning = sum(1 for w in words.values() if w["status"] == "learning")
    leech = sorted([w for w in words.values() if w.get("leech")],
                   key=lambda w: -w["wrong"])
    return {
        "seen": len(words), "mastered": mastered, "learning": learning,
        "bank_total": st.get("bank_size", len(load_bank())),
        "new_remaining": len(st["new_queue"]),
        "leech_count": len(leech),
        "leech_top": [{"word": w["word"], "meaning": w["meaning"], "wrong": w["wrong"]}
                      for w in leech[:10]],
    }


def streak_days(st):
    n, cur = 0, date.today()
    while True:
        log = st["daily"].get(cur.isoformat())
        active = log and (log.get("new_issued", 0) + log.get("review_done", 0)) > 0
        if active:
            n += 1
            cur -= timedelta(days=1)
        else:
            if n == 0 and cur == date.today():
                cur -= timedelta(days=1)
                continue
            break
    return n


def cmd_today(a):
    st = load_state()
    t = build_today(st)
    if a.json:
        print(json.dumps(t, ensure_ascii=False, indent=1))
        return
    tot = t["totals"]
    print("📅 %s %s%s" % (t["date"], t["weekday"],
                         "　·　距考试 %d 天" % t["exam_countdown"]
                         if t["exam_countdown"] is not None else ""))
    print("────────────────────────────────")
    print("📚 单词：到期复习 %d 张　|　强化池 %d 张　|　可发新词 %d 个"
          % (t["due_review_count"], t["pool_count"], t["new_quota"]))
    print("   进度：已学 %d / 掌握 %d / 顽固 %d / 词库剩余 %d"
          % (tot["seen"], tot["mastered"], tot["leech_count"], tot["new_remaining"]))
    print("\n🎯 今日训练（%s）" % t["weekday"])
    for i, tsk in enumerate(t["suggested_tasks"], 1):
        print("  %d. [%s·%dmin] %s" % (i, SKILL_CN.get(tsk["skill"], tsk["skill"]),
                                       tsk["minutes"], tsk["name"]))
    if t["pool_count"]:
        pw = [st["words"][i]["word"] for i in t["pool"] if i in st["words"]]
        print("\n🔥 强化池待清：%s" % "、".join(pw[:12]))
    print("\n💬 说「开始背单词」进入闪卡。")


def cmd_start(a):
    st = load_state()
    if st.get("session"):
        print("⚠️ 已有进行中的会话（%s），继续用 grade，或先 finish。" % st["session"]["date"])
        return
    today = today_str()
    size = a.n or st["profile"].get("session_size", DEFAULT_SESSION_SIZE)
    due = due_review_ids(st, today)
    pool = pool_ids(st)
    # 强化池优先，其次到期复习，最后新词
    ordered = []
    seen = set()
    for wid in pool + due:
        if wid not in seen:
            seen.add(wid)
            ordered.append(wid)
    n_rev = len(ordered)
    take_new = max(0, size - n_rev)
    take_new = min(take_new, max(0, st["profile"]["daily_new"] - day_log(st)["new_issued"]))
    new_ids = issue_new(st, take_new)
    ordered += new_ids
    if not ordered:
        print("✅ 今天没有到期卡片，新词额度也用完了。可以休息，或用 report 看进度。")
        save_state(st)
        return
    random.shuffle(ordered[:n_rev])
    per = a.per or st["profile"].get("per_round") or DEFAULT_PER_ROUND
    st["session"] = {"date": today, "queue": ordered, "idx": 0, "per_round": per,
                     "results": [], "new_ids": new_ids, "start": datetime.now().isoformat()}
    save_state(st)
    rounds = (len(ordered) + per - 1) // per
    if a.json:
        print(json.dumps({"count": len(ordered), "review": n_rev, "new": len(new_ids),
                          "per_round": per, "rounds": rounds,
                          "cards": build_round(st, per)},
                         ensure_ascii=False, indent=1))
        return
    print("🎯 本批 %d 张　（复习 %d / 强化 %d / 新词 %d）　每轮 %d 张，共 %d 轮"
          % (len(ordered), n_rev - len(pool), len(pool), len(new_ids), per, rounds))
    print("   下一步：运行 quiz 生成本轮答题卡。")


def current_card(st, reveal=False):
    s = st.get("session")
    if not s or s["idx"] >= len(s["queue"]):
        return None
    w = get_word(st, s["queue"][s["idx"]])
    card = {"id": w["id"], "index": s["idx"] + 1, "total": len(s["queue"]),
            "is_new": w["id"] in s["new_ids"], "front": fmt_front(w)}
    if reveal:
        card.update({"meaning": w["meaning"], "example": w["example"],
                     "topic": w["topic"], "stage": w["stage"],
                     "wrong": w["wrong"], "status": w["status"]})
    return card


def print_card(st, reveal=False):
    c = current_card(st, reveal)
    if not c:
        print("本批已结束，运行 finish 查看总结。")
        return
    tag = "🆕 新词" if c["is_new"] else "🔁 复习"
    print("\n[%d/%d] %s" % (c["index"], c["total"], tag))
    print("   " + c["front"])
    if reveal:
        print(fmt_back(get_word(st, c["id"])))


def cmd_reveal(a):
    st = load_state()
    if not st.get("session"):
        print("没有进行中的会话，先说「开始背单词」。")
        return
    c = current_card(st, True)
    print(json.dumps(c, ensure_ascii=False, indent=1) if a.json else
          "\n" + c["front"] + "\n" + fmt_back(get_word(st, c["id"])))


def apply_grade(st, wid, result, insert_at=None):
    """更新一个词的状态。不推进 idx、不落盘，由调用方决定。"""
    s = st["session"]
    w = get_word(st, wid)
    today = today_str()
    w["last_seen"] = today
    w["history"].append([today, result])
    w["history"] = w["history"][-MAX_HISTORY:]
    note = schedule_after_grade(w, result, today)
    bump_pool(st, wid, result)
    log = day_log(st)
    log[result] = log.get(result, 0) + 1
    tw = log.setdefault("words", [])
    if wid not in tw:
        tw.append(wid)          # 当天背过的词，按首次出现顺序（写每日童话要用）
    if wid not in s["new_ids"]:
        log["review_done"] += 1
    if w["status"] == "mastered":
        log["mastered"] += 1
    s["results"].append({"id": wid, "result": result})
    # 答错/模糊 -> 若干张之后回插重考
    if result != "correct":
        pos = len(s["queue"]) if insert_at is None else min(insert_at, len(s["queue"]))
        if wid not in s["queue"][pos:]:
            s["queue"].insert(pos, wid)
    return w, note


def round_slice(st, per):
    """返回当前这一轮的词 id 列表。"""
    s = st.get("session") or {}
    start = s.get("idx", 0)
    return list(s.get("queue", [])[start:start + per])


def write_quiz_html(st, cards, per, mode=None):
    """用 assets/quiz-template.html 渲染一张答题卡，返回文件路径。

    mode: "word" = 卡面显示英文单词、让用户输入中文（默认）
          "cn"   = 卡面显示中文意思、让用户输入英文单词
    """
    tpl_path = os.path.join(SKILL_DIR, "assets", QUIZ_TEMPLATE)
    if not os.path.exists(tpl_path):
        return None
    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    qdir = os.path.join(DATA_DIR, "quizzes")
    os.makedirs(qdir, exist_ok=True)
    s = st.get("session") or {}
    tot = summarize(st)
    rnd = (s.get("idx", 0) // max(1, per)) + 1
    payload = {
        "cards": [{"id": c["id"], "word": c["word"], "phonetic": c["phonetic"],
                   "pos": c["pos"], "meaning": c["meaning"], "example": c["example"],
                   "topic": c["topic"], "is_new": c["is_new"], "stage": c["stage"]}
                  for c in cards],
        "meta": {"round": rnd, "total": len(s.get("queue", [])), "date": today_str(),
                 "mode": mode or st["profile"].get("ask_mode") or DEFAULT_ASK_MODE,
                 "progress": "累计已学 %d · 已掌握 %d" % (tot["seen"], tot["mastered"])},
    }
    path = os.path.join(qdir, "round-%s.html" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False)))
    old = sorted(x for x in os.listdir(qdir) if x.endswith(".html"))
    for x in old[:-QUIZ_KEEP]:
        try:
            os.remove(os.path.join(qdir, x))
        except OSError:
            pass
    return path


def build_round(st, per):
    s = st["session"]
    ids = round_slice(st, per)
    cards = []
    for i, wid in enumerate(ids):
        w = get_word(st, wid)
        cards.append({"id": w["id"], "index": s["idx"] + i + 1, "total": len(s["queue"]),
                      "is_new": wid in s["new_ids"], "word": w["word"],
                      "phonetic": w["phonetic"], "pos": w["pos"], "meaning": w["meaning"],
                      "example": w["example"], "topic": w["topic"], "stage": w["stage"]})
    return cards


def missing_examples(cards):
    return [c for c in cards if not (c.get("example") or "").strip()]


def quiz_blocked_json(miss, cards):
    return {"needs_examples": [{"id": c["id"], "word": c["word"], "pos": c["pos"],
                                "meaning": c["meaning"], "topic": c["topic"]} for c in miss],
            "round_size": len(cards), "html": None,
            "hint": "先造例句再出卡：ielts.py example --json '{\"词\":\"句子\"}'，然后重跑 quiz"}


def report_missing_examples(miss, cards):
    """出卡前的闸口：把缺例句的词列清楚，让 AI 先造句。"""
    print("🖊️ 本轮 %d 张里有 %d 个词还没有例句，先给它们造句，再出卡："
          % (len(cards), len(miss)))
    for c in miss:
        print("   %-18s %-6s %s" % (c["word"], c["pos"], c["meaning"]))
    print("\n   要求：一句 8–16 词的雅思场景句（教育 / 环境 / 科技 / 社会 / 职场经济 / 健康），"
          "让词义能从语境里猜出来；不要写 This is a good word. 这类废话。")
    demo = ", ".join('"%s": "..."' % c["word"] for c in miss[:2])
    if len(miss) > 2:
        demo += ", …"
    print("\n   造好后一次写进去（句子会存进 examples.tsv，以后这个词就不用再造）：")
    print("     ielts.py example --json '{%s}'" % demo)
    print("   然后重新跑 quiz。确实想先出卡（卡面显示虚线占位）就加 --allow-missing。")


def cmd_quiz(a):
    st = load_state()
    s = st.get("session")
    if not s:
        print("没有进行中的会话，先说「开始背单词」。")
        return
    if s["idx"] >= len(s["queue"]):
        print("本批已结束，运行 finish 查看总结。")
        return
    per = a.per or s.get("per_round") or st["profile"].get("per_round") or DEFAULT_PER_ROUND
    mode = getattr(a, "mode", None)
    if mode:
        st["profile"]["ask_mode"] = mode
        save_state(st)
    cards = build_round(st, per)
    # 出卡闸口：卡面要显示例句，缺例句的词必须先由 AI 造好（除非显式 --allow-missing）
    miss = missing_examples(cards)
    if miss and not getattr(a, "allow_missing", False):
        if a.json:
            print(json.dumps(quiz_blocked_json(miss, cards), ensure_ascii=False, indent=1))
        else:
            report_missing_examples(miss, cards)
        sys.exit(2)          # 2 = 需要先造句，不是报错
    path = None if a.text else write_quiz_html(st, cards, per, mode)
    if a.json:
        print(json.dumps({"cards": cards, "html": path,
                          "answered": len(s["results"]), "queue_left":
                          len(s["queue"]) - s["idx"]}, ensure_ascii=False, indent=1))
        return
    if path:
        ask = "看英文单词 → 输入中文意思" if (mode or st["profile"].get("ask_mode")) != "cn" \
            else "看中文意思 → 输入英文单词"
        print("🃏 本轮 %d 张答题卡已生成：%s" % (len(cards), path))
        print("   模式：%s。" % ask)
        print("   卡片只负责收集答案、不做判定，也没有提交按钮；"
              "%d 个输入框写完点「复制回执」（现取输入框内容，空的记「未作答」），"
              "把回执发我，我来判对错并记录进度。" % len(cards))
        return
    why = "文字模式" if a.text else "未找到 assets/%s" % QUIZ_TEMPLATE
    print("🃏 本轮 %d 张（%s，只显示正面）：" % (len(cards), why))
    for c in cards:
        print("   [%d] %s  %s" % (c["index"], fmt_front(get_word(st, c["id"])),
                                  "🆕" if c["is_new"] else "🔁"))
    print("   把 %d 张的答案按顺序发我（一行一个即可），我来判对错；" % len(cards))
    print("   也可直接走 submit --raw \"答案1|答案2|答案3\" 让引擎先判。")


def cmd_submit(a):
    st = load_state()
    s = st.get("session")
    if not s:
        print("没有进行中的会话，先说「开始背单词」。")
        return
    if s["idx"] >= len(s["queue"]):
        print("本批已结束，运行 finish 查看总结。")
        return
    raw_mode = getattr(a, "raw", None) is not None
    if raw_mode:
        raws = parse_raw_answers(a.raw)
        if not raws:
            print("⚠️ 回执里没解析出答案。")
            return
        ids = round_slice(st, len(raws))
        if len(ids) != len(raws):
            print("⚠️ 本轮只有 %d 张卡，收到 %d 个答案，数量对不上。" % (len(ids), len(raws)))
            return
        # 每题各自判分（引擎给的只是建议，AI 可以用 grade/answers 覆盖）
        ask_cn = (st["profile"].get("ask_mode") or DEFAULT_ASK_MODE) != "cn"
        if ask_cn:      # 看英文写中文 -> 比中文释义
            results = [judge_cn(get_word(st, wid)["meaning"], r) for wid, r in zip(ids, raws)]
        else:           # 看中文写英文 -> 比英文拼写
            results = [judge_en(get_word(st, wid)["word"], r) for wid, r in zip(ids, raws)]
        if not a.json:
            for wid, r, res in zip(ids, raws, results):
                w = get_word(st, wid)
                print("\n%s　%s   %s" % (RESULT_ICON[res], w["word"], w["phonetic"] or ""))
                print("   你写的是「%s」" % (r if r else "（未作答）"))
                print(fmt_back(w))
    else:
        par = getattr(a, "answers", None)
        if not par:
            print("⚠️ 请给 --answers \"c,c,c\"（你自己判好的）或 --raw \"<回执原文>\"。")
            return
        results, err = parse_answers(par)
        if err:
            print("⚠️ " + err)
            return
        if not results:
            print("⚠️ 没解析出任何答案。")
            return
        ids = round_slice(st, len(results))
        if len(ids) != len(results):
            print("⚠️ 本轮只有 %d 张卡，收到 %d 个答案，数量对不上。" % (len(ids), len(results)))
            return
        if any(r is None for r in results):
            print("⚠️ 有卡片没作答（回执里的 -），请每张都给个结果再提交"
                  "（不会就写 w，别留 -）。")
            return
    if getattr(a, "dry_run", False):
        out = []
        for k, (wid, res) in enumerate(zip(ids, results)):
            w = get_word(st, wid)
            out.append({"id": wid, "word": w["word"], "phonetic": w["phonetic"],
                        "meaning": w["meaning"], "example": w["example"],
                        "answer": raws[k] if raw_mode else None, "suggest": res})
        if a.json:
            print(json.dumps({"dry_run": True, "graded": out}, ensure_ascii=False, indent=1))
        else:
            print("\n（--dry-run：以上只是建议，未写入进度）")
        return
    insert_at = s["idx"] + len(results) + 3
    graded = []
    for wid, res in zip(ids, results):
        w, note = apply_grade(st, wid, res, insert_at=insert_at)
        graded.append({"id": wid, "word": w["word"], "phonetic": w["phonetic"],
                       "pos": w["pos"], "meaning": w["meaning"], "example": w["example"],
                       "result": res, "note": note, "stage": w["stage"],
                       "status": w["status"], "history": w["history"]})
    s["idx"] += len(results)
    done = s["idx"] >= len(s["queue"])
    save_state(st)
    summary = finish_session(st) if done else None
    if a.json:
        print(json.dumps({"graded": graded, "done": done,
                          "queue_left": len(s["queue"]) - s["idx"],
                          "summary": summary}, ensure_ascii=False, indent=1))
        return
    for g in graded:
        print("\n%s　%s   %s" % (RESULT_ICON[g["result"]], g["word"], g["phonetic"]))
        print(fmt_back(g))
        print("   " + g["note"])
    print("\n📊 本轮：%d 张 ✅%d 🤔%d ❌%d"
          % (len(graded), sum(1 for g in graded if g["result"] == "correct"),
             sum(1 for g in graded if g["result"] == "fuzzy"),
             sum(1 for g in graded if g["result"] == "wrong")))
    if summary:
        tot = summary["totals"]
        print("\n── 本批结束 ──")
        print("📊 本批总结：%d 张 | 正确率 %.0f%% | 用时 %d 分钟"
              % (summary["total"], summary["accuracy"], summary["minutes"]))
        print("   累计：已学 %d 词 · 已掌握 %d 词 · 顽固词 %d · 连续打卡 %d 天"
              % (tot["seen"], tot["mastered"], tot["leech_count"], summary["streak"]))
        if summary["pool"]:
            print("   🔥 强化池还剩：%s" % "、".join(summary["pool"][:12]))
    else:
        print("   还剩 %d 张，说「继续」出下一轮。" % (len(s["queue"]) - s["idx"]))


def cmd_grade(a):
    st = load_state()
    s = st.get("session")
    if not s:
        print("没有进行中的会话，先说「开始背单词」。")
        return
    if s["idx"] >= len(s["queue"]):
        print("本批已结束，运行 finish。")
        return
    wid = a.id or s["queue"][s["idx"]]
    result = a.result
    w, note = apply_grade(st, wid, result, insert_at=s["idx"] + 4)
    s["idx"] += 1
    save_state(st)
    icon = RESULT_ICON[result]
    if a.json:
        print(json.dumps({"graded": {"id": wid, "word": w["word"], "result": result,
                                     "back": fmt_back(w), "note": note},
                          "next": current_card(st, False),
                          "done": s["idx"] >= len(s["queue"])},
                         ensure_ascii=False, indent=1))
        return
    print("\n%s　%s" % (icon, w["word"]))
    print(fmt_back(w))
    print("   " + note)
    if result == "wrong":
        print("   🔥 已进入强化池，需连续答对 2 次才放行")
    elif result == "fuzzy":
        print("   🔁 已标记模糊，稍后再考一次")
    if s["idx"] >= len(s["queue"]):
        print("\n── 本批结束 ──")
        cmd_finish(argparse.Namespace(json=False))
    else:
        print_card(st, reveal=False)


def finish_session(st):
    """结束当前会话，返回小结字典（不打印）。"""
    s = st.get("session")
    if not s:
        return None
    res = s["results"]
    c = sum(1 for r in res if r["result"] == "correct")
    f = sum(1 for r in res if r["result"] == "fuzzy")
    wg = sum(1 for r in res if r["result"] == "wrong")
    total = len(res) or 1
    started = datetime.fromisoformat(s["start"])
    mins = max(1, round((datetime.now() - started).total_seconds() / 60))
    day_log(st)["minutes"] += mins
    st["session"] = None
    save_state(st)
    tot = summarize(st)
    return {"total": len(res), "correct": c, "fuzzy": f, "wrong": wg, "minutes": mins,
            "accuracy": round(c / total * 100, 1), "totals": tot,
            "streak": streak_days(st),
            "pool": [st["words"][p["id"]]["word"] for p in st["reinforcement"]
                     if p["id"] in st["words"]]}


def cmd_finish(a):
    st = load_state()
    if not st.get("session"):
        print("没有进行中的会话。")
        return
    summary = finish_session(st)
    if a.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return
    tot = summary["totals"]
    print("\n📊 本批总结：%d 张 | ✅%d 🤔%d ❌%d | 正确率 %.0f%% | 用时 %d 分钟"
          % (summary["total"], summary["correct"], summary["fuzzy"], summary["wrong"],
             summary["accuracy"], summary["minutes"]))
    print("   累计：已学 %d 词 · 已掌握 %d 词 · 顽固词 %d · 连续打卡 %d 天"
          % (tot["seen"], tot["mastered"], tot["leech_count"], summary["streak"]))
    if summary["pool"]:
        print("   🔥 强化池还剩：%s" % "、".join(summary["pool"][:12]))


def cmd_stats(a):
    st = load_state()
    days = a.days
    end = date.today()
    rows = []
    for i in range(days - 1, -1, -1):
        day = (end - timedelta(days=i)).isoformat()
        log = st["daily"].get(day)
        if log:
            tot = log.get("correct", 0) + log.get("fuzzy", 0) + log.get("wrong", 0)
            rows.append({"date": day, "cards": tot,
                         "accuracy": round(log.get("correct", 0) / tot * 100, 1) if tot else 0,
                         "minutes": log.get("minutes", 0),
                         "mastered": log.get("mastered", 0)})
    stage_dist = {i: 0 for i in range(0, MASTER_STAGE + 1)}
    for w in st["words"].values():
        stage_dist[min(w["stage"], MASTER_STAGE)] += 1
    out = {"totals": summarize(st), "streak": streak_days(st),
           "stage_distribution": stage_dist, "daily": rows,
           "pool": pool_ids(st)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    t = out["totals"]
    print("📈 雅思备考概览")
    print("   已学 %d / 掌握 %d / 学习中 %d / 顽固 %d / 词库剩余 %d"
          % (t["seen"], t["mastered"], t["learning"], t["leech_count"], t["new_remaining"]))
    print("   连续打卡 %d 天 | 强化池 %d 词" % (out["streak"], len(out["pool"])))
    print("\n   记忆阶段分布：")
    labels = {0: "新学", 1: "1天", 2: "2天", 3: "4天", 4: "7天", 5: "15天",
              6: "30天", 7: "60天", 8: "✅已掌握"}
    for k in range(0, MASTER_STAGE + 1):
        v = stage_dist[k]
        if v:
            print("     %-8s %s %d" % (labels[k], "█" * min(v, 40), v))


def cmd_task(a):
    st = load_state()
    log = day_log(st)
    log["tasks"].append({"skill": a.skill, "name": a.name,
                         "minutes": a.minutes, "done": True,
                         "note": a.note or ""})
    log["minutes"] += a.minutes
    save_state(st)
    print("✅ 已记录：%s · %s（%d 分钟）" % (SKILL_CN.get(a.skill, a.skill),
                                            a.name, a.minutes))


def cmd_import(a):
    st = load_state()
    bank = load_bank()
    rows = []                     # (wid, 原始 TSV 行)
    seen_here = set()
    with open(a.file, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip().strip(ZERO_WIDTH)
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in re.split(r"[|\t,]", line, maxsplit=5)]
            if len(parts) < 4:
                continue
            word = parts[0]
            if not word:
                continue
            wid = slug(word)
            # 已学过的、词库里已有的、本文件里重复的，都不再导入
            if wid in st["words"] or wid in bank or wid in seen_here:
                continue
            seen_here.add(wid)
            fields = (parts + ["", "", "", "", ""])[:6]
            fields[5] = fields[5] or "custom"
            rows.append((wid, "|".join(fields)))
    added = len(rows)
    # 写进 DATA_DIR/custom-words/（这是词库的一部分，load_bank 会读），
    # 只把 id 追加到 new_queue；**不要**在 st["words"] 里塞空记录，
    # 否则 due_review_ids() 读 w["status"] 会 KeyError，卡片也是空的。
    if added:
        ensure_dirs()
        os.makedirs(CUSTOM_DIR, exist_ok=True)
        dst = os.path.join(CUSTOM_DIR, os.path.basename(a.file) or "custom.tsv")
        existing = []
        if os.path.exists(dst):
            with open(dst, encoding="utf-8-sig") as g:
                existing = [ln.rstrip("\n") for ln in g if ln.strip()]
        with open(dst, "w", encoding="utf-8") as o:
            o.write("# 由 `ielts.py import` 导入的自建词表：word|音标|词性|释义|例句|话题\n")
            for ln in existing:
                if not ln.startswith("#"):
                    o.write(ln + "\n")
            for _, ln in rows:
                o.write(ln + "\n")
        st["new_queue"].extend(wid for wid, _ in rows)
        st["bank_size"] = st.get("bank_size", 0) + added
        save_state(st)
        load_bank(force=True)     # 本次进程立刻看得到新词
    print("✅ 导入 %d 个新词（已去重），当前待发新词 %d" % (added, len(st["new_queue"])))


def save_examples(pairs):
    """把 {id: 句子} 合并进 examples.tsv（后写的覆盖先写的），返回 (新增, 覆盖) 数。"""
    ensure_dirs()
    cur = load_examples()
    added = sum(1 for k in pairs if k not in cur)
    upd = len(pairs) - added
    cur.update(pairs)
    with open(EXAMPLES_PATH, "w", encoding="utf-8") as f:
        f.write("# 例句缓存：词<TAB>例句（由 `ielts.py example` 维护，可手改）\n")
        for k in sorted(cur):
            f.write("%s\t%s\n" % (k, cur[k]))
    # 让本进程立刻看到新例句，不用重读整个词库
    global _EX_CACHE
    _EX_CACHE = cur
    if _BANK_CACHE:
        for wid, ex in pairs.items():
            if wid in _BANK_CACHE:
                _BANK_CACHE[wid]["example"] = ex
    return added, upd


def parse_example_pairs(items):
    """把 ['advocate=Many people advocate...'] 解析成 {id: 句子}。"""
    out = {}
    for it in items or []:
        parts = re.split(r"[=|\t]", it, maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            print("⚠️ 跳过格式不对的一条：%s（应为 词=句子）" % it)
            continue
        wid = slug(parts[0].strip())
        if wid:
            out[wid] = parts[1].strip()
    return out


def cmd_example(a):
    """维护例句，或者列出还缺例句的词。"""
    if a.missing:
        st = load_state()
        sess = st.get("session")
        if a.all or not sess:
            ids = [i for i in st.get("new_queue", [])] + list(st.get("words", {}).keys())
        elif a.queue:
            ids = sess["queue"][sess["idx"]:]          # 本批还没背的全部
        else:
            per = sess.get("per_round") or st["profile"].get("per_round") or DEFAULT_PER_ROUND
            ids = sess["queue"][sess["idx"]:sess["idx"] + per]
        miss, seen = [], set()
        for wid in ids:
            if wid in seen:
                continue
            seen.add(wid)
            w = peek_word(st, wid)          # 只读，别把整库灌进 state
            if w and not (w.get("example") or "").strip():
                miss.append(w)
        miss = miss[:a.limit] if a.limit else miss
        if a.json:
            print(json.dumps([{"id": w["id"], "word": w["word"], "meaning": w["meaning"],
                               "pos": w["pos"]} for w in miss], ensure_ascii=False, indent=1))
            return
        if not miss:
            print("✅ 这些词都已有例句，不用补。")
            return
        print("📝 下面 %d 个词还没有例句（照着词性和释义各造一句雅思场景句）：" % len(miss))
        for w in miss:
            print("   %-16s %s  %s" % (w["word"], w["pos"], w["meaning"]))
        print('\n   补完存进去： ielts.py example --set "词=句子" --set "..."')
        return

    pairs = {}
    if a.json:
        try:
            pairs.update({slug(k): v.strip() for k, v in json.loads(a.json).items() if v and v.strip()})
        except Exception as e:
            print("⚠️ --json 解析失败：%s" % e)
            return
    pairs.update(parse_example_pairs(a.sets))
    if a.file:
        with open(a.file, encoding="utf-8-sig") as f:
            pairs.update(parse_example_pairs(
                [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]))
    if not pairs:
        if a.file:
            print("⚠️ %s 里没解析出有效条目（每行应为 词<TAB>句子）。" % a.file)
            return
        print("用法：")
        print('  example --set "advocate=Many scientists advocate stricter limits."')
        print("  example --json '{\"curb\":\"New rules aim to curb plastic waste.\"}'")
        print("  example --file 例句.tsv        # 每行 词<TAB>句子")
        print("  example --missing              # 看当前这一轮里哪些词还缺例句")
        return

    bank = load_bank()
    unknown = [k for k in pairs if k not in bank]
    added, upd = save_examples(pairs)
    load_bank(force=True)          # 让本次进程立刻看到新例句
    print("✅ 例句已写入 %s（新增 %d / 覆盖 %d）" % (EXAMPLES_PATH, added, upd))
    if unknown:
        print("   注意：这 %d 个词不在词库里，句子先存着，等词出现了就会带上：%s"
              % (len(unknown), "、".join(unknown[:8])))
    print("   ✅ 例句已生效：现在重跑 quiz 就能出卡（卡面直接带这些句子）。")


def cmd_poem(a):
    """列出「今天背过的所有单词」，供接着写每日童话。只读，不改进度。"""
    st = load_state()
    day = getattr(a, "date", None) or today_str()
    words, seen = [], set()
    for wid in today_word_ids(st, day):
        if wid in seen:
            continue
        seen.add(wid)
        w = peek_word(st, wid)      # 只读，别把整库灌进 state
        if not w:
            continue
        words.append({"id": w["id"], "word": w["word"], "pos": w.get("pos", ""),
                      "meaning": w.get("meaning", ""), "example": w.get("example", "")})
    if a.json:
        print(json.dumps({"date": day, "count": len(words), "words": words},
                         ensure_ascii=False, indent=1))
        return
    if not words:
        print("📭 %s 还没有背过单词。先「开始背单词」，背完再来写童话。" % day)
        return
    print("📝 %s 背过的 %d 个词（今天的童话要把这些词全用上）：" % (day, len(words)))
    for w in words:
        print("   %-18s %-6s %s" % (w["word"], w["pos"], w["meaning"]))
    print("\n   下一步：用上面每个词写一篇安徒生式英文哲理童话，"
          "先跑 scripts/tale_index.py 看已用过的题材，再渲染成绘本"
          "（scripts/make_watercolor_svg_book.py）。")


def cmd_reset(a):
    """清空进度。有真实进度时需额外 --force，避免误删。"""
    learned = 0
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                st = json.load(f)
            learned = len(st.get("words", {}))
        except Exception:
            learned = 0
    if learned and not getattr(a, "force", False):
        print("🛑 检测到 %d 个已学单词，reset 会全部清空。" % learned)
        print("   如果确实要清空，请加 --force；否则用其他子命令继续学习。")
        return
    if not a.yes:
        print("⚠️ 这会清空所有学习进度，确认请加 --yes")
        return
    if os.path.exists(STATE_PATH):
        import shutil
        bak = STATE_PATH + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(STATE_PATH, bak)
        os.remove(STATE_PATH)
        print("💾 已备份到：%s" % bak)
    print("🗑️ 进度已清空，下次运行将自动重建。")


def cmd_report(a):
    st = load_state()
    end = date.today()
    start = end - timedelta(days=6)
    if a.start:
        start = d(a.start)
        end = d(a.end) if a.end else start + timedelta(days=6)
    path = generate_report(st, start, end)
    if a.json:
        print(json.dumps({"path": path}, ensure_ascii=False))
    else:
        print("📄 周报已生成：%s" % path)


# ----------------------------------------------------------------------------
# HTML 周报
# ----------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s or ""))


def svg_bars_line(rows, w=620, h=200, pad=32):
    if not rows:
        return "<p style='color:#8a8f98'>本周暂无数据</p>"
    n = len(rows)
    bw = (w - pad * 2) / n * 0.55
    step = (w - pad * 2) / n
    maxv = max([r["cards"] for r in rows] + [1])
    base = h - 26
    bars, labels, pts = [], [], []
    for i, r in enumerate(rows):
        x = pad + step * i + (step - bw) / 2
        bh = (r["cards"] / maxv) * (base - 20)
        bars.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="#3b6ef6" opacity="0.85"/>'
                    % (x, base - bh, bw, max(bh, 1)))
        bars.append('<text x="%.1f" y="%.1f" font-size="11" fill="#5b6472" text-anchor="middle">%d</text>'
                    % (x + bw / 2, base - bh - 5, r["cards"]))
        labels.append('<text x="%.1f" y="%d" font-size="11" fill="#8a8f98" text-anchor="middle">%s</text>'
                      % (x + bw / 2, h - 8, r["date"][5:]))
        cx = pad + step * i + step / 2
        cy = base - (r["accuracy"] / 100) * (base - 20)
        pts.append("%.1f,%.1f" % (cx, cy))
    line = ('<polyline points="%s" fill="none" stroke="#e05252" stroke-width="2"/>'
            % " ".join(pts))
    dots = "".join('<circle cx="%s" cy="%s" r="3" fill="#e05252"/>' % tuple(p.split(","))
                   for p in pts)
    return ('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">'
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#e3e6ec"/>'
            '%s%s%s%s'
            '<text x="%d" y="16" font-size="11" fill="#8a8f98">■ 词卡量　— 正确率%%</text>'
            '</svg>') % (w, h, w, pad, base, w - pad, base,
                         "".join(bars), line, dots, "".join(labels), pad)


def svg_stage(dist, w=620, h=190, pad=30):
    labels = ["新学", "1天", "2天", "4天", "7天", "15天", "30天", "60天", "已掌握"]
    keys = list(range(0, MASTER_STAGE + 1))
    maxv = max([dist.get(k, 0) for k in keys] + [1])
    step = (w - pad * 2) / len(keys)
    bw = step * 0.5
    out = []
    for i, k in enumerate(keys):
        v = dist.get(k, 0)
        x = pad + step * i + (step - bw) / 2
        bh = (v / maxv) * (h - 60)
        color = "#2f9e6e" if k == MASTER_STAGE else "#3b6ef6"
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s" opacity="0.85"/>'
                   % (x, h - 40 - bh, bw, max(bh, 1), color))
        out.append('<text x="%.1f" y="%.1f" font-size="11" fill="#5b6472" text-anchor="middle">%d</text>'
                   % (x + bw / 2, h - 44 - bh, v))
        out.append('<text x="%.1f" y="%d" font-size="10" fill="#8a8f98" text-anchor="middle">%s</text>'
                   % (x + bw / 2, h - 22, labels[i]))
    return ('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">%s'
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#e3e6ec"/></svg>'
            % (w, h, w, "".join(out), pad, h - 40, w - pad, h - 40))


def svg_cumulative(rows, w=620, h=160, pad=30):
    if not rows:
        return ""
    vals, cum = [], 0
    for r in rows:
        cum += r.get("mastered", 0)
        vals.append(cum)
    maxv = max(vals + [1])
    step = (w - pad * 2) / max(len(vals) - 1, 1)
    pts = " ".join("%.1f,%.1f" % (pad + step * i, h - 30 - (v / maxv) * (h - 60))
                   for i, v in enumerate(vals))
    return ('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">'
            '<polyline points="%s" fill="none" stroke="#2f9e6e" stroke-width="2.5"/>'
            '<text x="%d" y="16" font-size="11" fill="#8a8f98">累计掌握词数：%d</text></svg>'
            % (w, h, w, pts, pad, cum))


def generate_report(st, start, end):
    ensure_dirs()
    rows, tot_c, tot_f, tot_w, tot_min, active_days, skill_min = [], 0, 0, 0, 0, 0, {}
    cur = start
    while cur <= end:
        day = cur.isoformat()
        log = st["daily"].get(day, {})
        c, f, w = log.get("correct", 0), log.get("fuzzy", 0), log.get("wrong", 0)
        n = c + f + w
        rows.append({"date": day, "cards": n,
                     "accuracy": round(c / n * 100, 1) if n else 0,
                     "minutes": log.get("minutes", 0),
                     "mastered": log.get("mastered", 0)})
        tot_c += c; tot_f += f; tot_w += w; tot_min += log.get("minutes", 0)
        if n:
            active_days += 1
        for t in log.get("tasks", []):
            skill_min[t["skill"]] = skill_min.get(t["skill"], 0) + t.get("minutes", 0)
        cur += timedelta(days=1)
    total_cards = tot_c + tot_f + tot_w
    acc = round(tot_c / total_cards * 100, 1) if total_cards else 0.0

    dist = {i: 0 for i in range(0, MASTER_STAGE + 1)}
    for w in st["words"].values():
        dist[min(w["stage"], MASTER_STAGE)] += 1
    tot = summarize(st)
    leech = tot["leech_top"]
    pool = pool_ids(st)

    cd = ""
    if st["profile"].get("exam_date"):
        try:
            left = (d(st["profile"]["exam_date"]) - date.today()).days
            cd = ("　·　距考试 <b>%d</b> 天" % left) if left >= 0 else "　·　考试日已过"
        except Exception:
            pass

    skill_rows = "".join(
        "<tr><td>%s</td><td>%d 分钟</td><td><div class='bar'><i style='width:%d%%'></i></div></td></tr>"
        % (esc(SKILL_CN.get(k, k)), v, min(100, round(v / max(skill_min.values() or [1]) * 100)))
        for k, v in sorted(skill_min.items(), key=lambda x: -x[1])) or \
        "<tr><td colspan='3' style='color:#9aa0a8'>本周未记录听说读写训练</td></tr>"

    leech_rows = "".join(
        "<tr><td><b>%s</b></td><td>%s</td><td class='bad'>%d</td></tr>"
        % (esc(x["word"]), esc(x["meaning"]), x["wrong"]) for x in leech[:10]) or \
        "<tr><td colspan='3' style='color:#9aa0a8'>暂无顽固词，保持住 👍</td></tr>"

    pool_txt = "、".join(esc(st["words"][i]["word"]) for i in pool[:20]
                        if i in st["words"]) or "空"

    new_mastered = sum(r["mastered"] for r in rows)
    if acc >= 85 and active_days >= 5:
        advice = "正确率和出勤都很稳。下周把重点从「认词」转到「输出」：每个新词必须造一个雅思句式，并塞进 Task 2 作文里。"
    elif acc >= 70:
        advice = "正确率尚可但有波动。建议把每日新词降到 %d 个，先把强化池清空，避免边学边忘。" % max(10, st["profile"]["daily_new"] - 10)
    else:
        advice = "错误率偏高，典型原因是新词发太快、复习没跟上。下周建议：每日新词减半、每天先清强化池再发新词、错词当天手写 3 遍并造句。"
    if tot["leech_count"] >= 5:
        advice += " 另外有 %d 个顽固词，建议用词根/联想/例句卡片单独攻克。" % tot["leech_count"]
    if st["profile"].get("daily_new") and active_days == 0:
        advice = "本周零打卡。先从每天 10 张卡、10 分钟开始，把连续性建立起来再谈强度。"

    iso = end.isocalendar()
    fname = "weekly-%d-W%02d.html" % (iso[0], iso[1])
    path = os.path.join(REPORT_DIR, fname)

    body = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>雅思备考周报 %(week)s</title>
<style>
*{box-sizing:border-box}
body{margin:0;padding:32px;background:#f6f7f9;color:#1f2430;
 font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",Arial,sans-serif}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:24px;margin:0 0 6px}
.sub{color:#6b7280;font-size:13px;margin-bottom:24px}
.card{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px;margin-bottom:16px}
.card h2{font-size:15px;margin:0 0 16px;color:#1f2430;display:flex;align-items:center;gap:8px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.kpi{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:16px;text-align:center}
.kpi .v{font-size:26px;font-weight:600;line-height:1.2}
.kpi .l{font-size:12px;color:#6b7280;margin-top:4px}
.kpi.blue .v{color:#3b6ef6}.kpi.green .v{color:#2f9e6e}
.kpi.red .v{color:#e05252}.kpi.gray .v{color:#4b5563}
table{width:100%%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #f0f2f5}
th{color:#6b7280;font-weight:500;font-size:12px}
td.bad{color:#e05252;font-weight:600}
.bar{background:#f0f2f5;border-radius:6px;height:8px;overflow:hidden}
.bar i{display:block;height:100%%;background:#3b6ef6;border-radius:6px}
.note{font-size:13px;line-height:1.7;color:#374151;background:#f9fafb;
 border-left:3px solid #3b6ef6;padding:12px 14px;border-radius:0 8px 8px 0}
.tag{display:inline-block;font-size:12px;color:#6b7280;background:#f0f2f5;
 border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0}
.chart{overflow-x:auto}
</style></head><body><div class="wrap">
<h1>雅思备考周报</h1>
<div class="sub">%(start)s ~ %(end)s　·　第 %(week)s 周%(cd)s</div>

<div class="kpis">
<div class="kpi blue"><div class="v">%(days)d</div><div class="l">打卡天数 / 7</div></div>
<div class="kpi gray"><div class="v">%(cards)d</div><div class="l">本周词卡</div></div>
<div class="kpi green"><div class="v">%(acc).1f%%</div><div class="l">正确率</div></div>
<div class="kpi red"><div class="v">%(mins)d</div><div class="l">学习分钟</div></div>
</div>

<div class="card"><h2>📊 每日词卡量与正确率</h2><div class="chart">%(chart1)s</div></div>

<div class="card"><h2>🧠 艾宾浩斯记忆阶段分布</h2><div class="chart">%(chart2)s</div>
<div style="margin-top:12px;font-size:12px;color:#6b7280">
已掌握 <b>%(mastered)d</b> 词　·　学习中 <b>%(learning)d</b> 词　·　累计接触 <b>%(seen)d</b> 词　·　词库剩余 <b>%(remain)d</b> 词</div>
</div>

<div class="card"><h2>📈 累计掌握词数</h2><div class="chart">%(chart3)s</div>
<div style="margin-top:8px;font-size:12px;color:#6b7280">本周新增掌握 <b>%(newm)d</b> 词　·　连续打卡 <b>%(streak)d</b> 天</div></div>

<div class="card"><h2>🎧 听说读写训练</h2><table>%(skills)s</table></div>

<div class="card"><h2>🔥 顽固词 TOP 10</h2><table>
<tr><th>单词</th><th>释义</th><th>错误次数</th></tr>%(leech)s</table>
<div style="margin-top:12px;font-size:12px;color:#6b7280">强化池待清：%(pool)s</div></div>

<div class="card"><h2>💡 下周建议</h2><div class="note">%(advice)s</div></div>
</div></body></html>""" % {
        "start": start.isoformat(), "end": end.isoformat(),
        "week": "W%02d" % iso[1], "cd": cd,
        "days": active_days, "cards": total_cards, "acc": acc, "mins": tot_min,
        "chart1": svg_bars_line(rows), "chart2": svg_stage(dist),
        "chart3": svg_cumulative(rows),
        "mastered": tot["mastered"], "learning": tot["learning"],
        "seen": tot["seen"], "remain": tot["new_remaining"],
        "newm": new_mastered, "streak": streak_days(st),
        "skills": skill_rows, "leech": leech_rows, "pool": pool_txt,
        "advice": esc(advice),
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return path


# ----------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="雅思备考引擎")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("init")
    c.add_argument("--daily-new", type=int)
    c.add_argument("--target", type=float)
    c.add_argument("--exam-date")
    c.set_defaults(fn=cmd_init)

    c = sub.add_parser("today")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_today)

    c = sub.add_parser("start")
    c.add_argument("--n", type=int)
    c.add_argument("--per", type=int, help="每轮几张卡（默认 %d）" % DEFAULT_PER_ROUND)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_start)

    c = sub.add_parser("quiz", help="出本轮答题卡（默认生成 HTML）")
    c.add_argument("--per", type=int)
    c.add_argument("--mode", choices=["word", "cn"],
                   help="word=看英文写中文（默认）；cn=看中文写英文")
    c.add_argument("--text", action="store_true", help="只输出文字，不生成 HTML")
    c.add_argument("--allow-missing", action="store_true",
                   help="缺例句也照样出卡（卡面会显示虚线占位），默认会先拦下来让你造句")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_quiz)

    c = sub.add_parser("submit", help="提交本轮回执：--raw 传回执原文（引擎判分）或 --answers 传判好的 c,w,f")
    c.add_argument("--raw", help="答题卡回执原文（含「我答：xxx」），按顺序取出用户答案并判分")
    c.add_argument("--answers", help="已判好的结果，如 c,w,f（AI 自己判完用这个）")
    c.add_argument("--dry-run", action="store_true", help="只给判分建议，不写进度")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_submit)

    c = sub.add_parser("reveal")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_reveal)

    c = sub.add_parser("grade")
    c.add_argument("--result", required=True, choices=["correct", "fuzzy", "wrong"])
    c.add_argument("--id")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_grade)

    c = sub.add_parser("finish")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_finish)

    c = sub.add_parser("stats")
    c.add_argument("--days", type=int, default=7)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_stats)

    c = sub.add_parser("report")
    c.add_argument("--start")
    c.add_argument("--end")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_report)

    c = sub.add_parser("task")
    c.add_argument("--skill", required=True,
                   choices=list(SKILL_CN.keys()))
    c.add_argument("--name", required=True)
    c.add_argument("--minutes", type=int, default=0)
    c.add_argument("--note")
    c.set_defaults(fn=cmd_task)

    c = sub.add_parser("example", help="给词补例句（存进 examples.tsv，卡片会自动带上）")
    c.add_argument("--set", dest="sets", action="append", metavar="词=句子")
    c.add_argument("--json", help='一次给多条，如 \'{"curb":"New rules aim to curb waste."}\'')
    c.add_argument("--file", help="每行 词<TAB>句子")
    c.add_argument("--missing", action="store_true", help="列出还缺例句的词（只读）")
    c.add_argument("--queue", action="store_true", help="配合 --missing：看本批剩余全部，而不只是当前一轮")
    c.add_argument("--all", action="store_true", help="配合 --missing：扫全库（只用来看看，别用来批量补）")
    c.add_argument("--limit", type=int, default=20)
    c.set_defaults(fn=cmd_example)

    c = sub.add_parser("poem", help="列出今天背过的所有单词（供写每日童话用，只读）")
    c.add_argument("--date", help="指定日期 YYYY-MM-DD，默认今天")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_poem)

    c = sub.add_parser("import")
    c.add_argument("--file", required=True)
    c.set_defaults(fn=cmd_import)

    c = sub.add_parser("reset")
    c.add_argument("--yes", action="store_true")
    c.add_argument("--force", action="store_true",
                   help="已有学习进度时，必须再加这个才会真的清空")
    c.set_defaults(fn=cmd_reset)

    a = p.parse_args()
    if not a.cmd:
        p.print_help()
        return
    a.fn(a)


if __name__ == "__main__":
    main()
