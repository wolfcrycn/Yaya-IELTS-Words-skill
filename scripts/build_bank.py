#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_bank.py — 从 ECDICT 开源词典构建雅思词库（可重复执行）

用法:
    python3 build_bank.py [--csv /tmp/ecdict.csv] [--target 5000] [--keep 9]

流程:
1. 读取 data/words/ 下已有的手工词表（前 N 个文件，默认 9 个）作为保留词，不覆盖
2. 流式读取 ECDICT CSV，按雅思相关度分层筛选:
     T0 tag 含 ielts
     T1 tag 含 ky/cet6/toefl/gre
     T2 collins>=3 或 oxford3000
     T3 collins>=1
     T4 其余（按词频兜底）
   每层内按 BNC 词频升序（越常用越靠前）
3. 清洗中文释义、推断词性、按关键词做主题分类
4. 输出 TSV 分片到 data/words/10-bank-*.tsv
5. 若 state.json 已存在，把新词追加进 new_queue（不影响已有学习进度）

数据格式: word | phonetic | pos | meaning | example | topic
"""
import argparse
import csv
import json
import os
import random
import re
import sys

csv.field_size_limit(10 ** 7)

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDS_DIR = os.path.join(SKILL_DIR, "data", "words")
DATA_DIR = os.environ.get("IELTS_DATA_DIR",
                          os.path.join(os.path.expanduser("~"), ".workbuddy", "ielts-prep"))
STATE_PATH = os.path.join(DATA_DIR, "state.json")

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"^[a-z][a-z']{2,19}$")
POS_PREFIX = re.compile(r"^\s*(?:n|v|vt|vi|adj|adv|prep|conj|pron|int|art|aux|num|abbr)\.\s*", re.I)
BAD_ENTRY = re.compile(r"(人名|地名|女子名|男子名|姓氏|河流|作家|诗人|画家|批评家|作曲家|政治家)")
# 纯屈折形式（"某某的过去式/复数"）不是独立词条，不占名额
INFLECT_ONLY = re.compile(r"(的过去式|的过去分词|的现在分词|的复数|的第三人称单数|的比较级|的最高级)")
NET_NOISE = re.compile(r"\[网络\]|网络释义")
BRACKET = re.compile(r"\[[^\]]*\]")
DEFN_PERSON = re.compile(
    r"\b(British|American|English|Scottish|Irish|Welsh|French|German|Italian|Spanish|"
    r"Russian|Chinese|Japanese|Dutch|Greek|Roman)\b[^.]{0,60}?\b(poet|novelist|writer|"
    r"painter|critic|philosopher|composer|politician|actor|actress|playwright|biographer|"
    r"essayist|artist|sculptor|statesman|theologian)\b", re.I)
DEFN_PLACE = re.compile(r"\b(river|lake|mountain|city|town|village|county|island|"
                        r"peninsula|district|province|region|bay|strait|desert)\s+(in|of)\b", re.I)

STOPWORDS = set("""
a an the and or but if then than so because although though whilst while whereas
in on at of to for with by from as into onto upon within without during through
i me my myself you your yours yourself he him his himself she her hers herself
it its itself we us our ours ourselves they them their theirs themselves
this that these those there here what which who whom whose when where why how
am is are was were be been being have has had having do does did done doing
will would shall should can could may might must ought need dare
all any some no nor not none every each either neither both few fewer fewest
many much more most less least own same other another such only even still
yet already ever never always often sometimes usually once twice very quite
rather too also just now again soon hence thus therefore however moreover
yes okay ok oh ah well let per via versus about above across after against
along among around before behind below beneath beside besides between beyond
down except inside near off out outside over past since till toward under
underneath until versus
one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty
sixty seventy eighty ninety hundred thousand million billion trillion dozen
first second third fourth fifth sixth seventh eighth ninth tenth half quarter
double triple somebody anybody everybody everybody nobody someone anyone
everyone everything something anything nothing whoever whatever whenever
wherever somebody get got go went gone come came say said see saw know knew
think thought take took make made want need like love hate good bad big small
""".split())

# 只有中考/高考标签 = 初中高中水平，不占 5000 个名额
EASY_TAGS = {"zk", "gk"}

# ECDICT pos 分布字段 -> 词性标记
POS_CODE = {"n": "n.", "v": "v.", "j": "adj.", "r": "adv.", "i": "prep.",
            "c": "conj.", "p": "pron.", "u": "int.", "a": "art.", "t": "prep."}

TOPIC_RULES = [
    ("environment", ["环境", "污染", "生态", "气候", "排放", "废弃", "碳", "物种",
                     "森林", "自然", "可再生", "温室", "垃圾",
                     "environment", "pollut", "ecolog", "climate", "emission",
                     "waste", "species", "forest", "carbon", "natural resource"]),
    ("education",   ["教育", "学校", "学生", "课程", "教学", "教师", "大学", "学术",
                     "学科", "考试", "培训", "学位",
                     "education", "school", "student", "course", "teach",
                     "academic", "university", "curriculum", "pedagog"]),
    ("technology",  ["技术", "计算机", "网络", "数据", "软件", "系统", "电子", "数字",
                     "机械", "工程", "程序", "互联", "设备", "算法", "自动",
                     "technology", "computer", "network", "software", "digital",
                     "electronic", "machine", "engineer", "algorithm", "internet"]),
    ("health",      ["健康", "疾病", "医疗", "药物", "治疗", "症状", "医院", "营养",
                     "心理", "精神", "免疫", "手术", "病人",
                     "health", "disease", "medical", "drug", "symptom", "hospital",
                     "nutrition", "illness", "therap", "mental"]),
    ("economy",     ["经济", "商业", "市场", "金融", "投资", "贸易", "公司", "价格",
                     "成本", "收入", "就业", "产业", "消费", "货币", "税收", "银行",
                     "econom", "business", "market", "financ", "invest", "trade",
                     "price", "cost", "income", "employ", "industry", "commerc"]),
    ("society",     ["社会", "政府", "法律", "政策", "人口", "城市", "社区", "犯罪",
                     "权利", "贫困", "移民", "福利", "制度", "居民", "公共",
                     "societ", "social", "government", "law", "polic", "population",
                     "urban", "community", "crime", "poverty", "immigra", "welfare"]),
    ("work",        ["工作", "职业", "员工", "管理", "劳动", "雇主", "职位", "技能",
                     "生产", "企业", "组织", "效率", "工资", "失业",
                     "occupation", "profession", "labor", "labour", "manage",
                     "career", "organiz", "organis", "efficien", "wage", "workplace"]),
    ("culture",     ["文化", "艺术", "历史", "传统", "媒体", "电影", "音乐", "语言",
                     "宗教", "习俗", "遗产", "旅游", "文学", "建筑",
                     "culture", "cultural", "art", "historic", "tradition", "media",
                     "music", "language", "religio", "heritage", "tourism",
                     "literat", "architect"]),
]


def slug(word):
    return re.sub(r"[^a-z0-9]+", "-", word.lower().strip()).strip("-")


ZERO_WIDTH = "\ufeff\u200b\u200c\u200d\u200e\u200f"


def load_curated(keep_prefixes):
    """读取手工维护的词表，返回 (已占用 id 集合, 去重后词数)。"""
    taken = set()
    if not os.path.isdir(WORDS_DIR):
        return taken, 0
    for fn in sorted(os.listdir(WORDS_DIR)):
        if not fn.endswith((".tsv", ".txt", ".csv")):
            continue
        if keep_prefixes and not any(fn.startswith(p) for p in keep_prefixes):
            continue
        # utf-8-sig 防 BOM：否则首行注释会被当成一个叫 "# word" 的词条
        with open(os.path.join(WORDS_DIR, fn), encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip().strip(ZERO_WIDTH)
                if not line or line.startswith("#"):
                    continue
                w = line.split("|")[0].strip().strip(ZERO_WIDTH).lower()
                if w and not w.startswith("#"):
                    taken.add(slug(w))
    return taken, len(taken)


def clean_meaning(trans):
    """把 ECDICT 的 translation 洗成适合闪卡背面的一句话释义。"""
    if not trans:
        return None
    # 网络释义是众包噪声，从它出现的位置整段截断
    t = NET_NOISE.split(trans.replace("\\n", "\n"))[0]
    t = t.replace("\n", " ; ")
    # 去掉开头的词性标记（可能有多个）
    for _ in range(3):
        t2 = POS_PREFIX.sub("", t)
        if t2 == t:
            break
        t = t2
    senses = []
    for part in re.split(r"[;；]", t):
        part = BRACKET.sub("", part).strip(" 　.,，")
        if not part or not CJK.search(part):
            continue
        if len(part) > 22:
            part = part[:22].rstrip("，, ")
        senses.append(part)
        if len(senses) >= 2:
            break
    if not senses:
        return None
    out = "；".join(senses)
    return out if len(out) <= 60 else out[:60]


def derive_pos(trans, pos_field):
    m = POS_PREFIX.match(trans or "")
    if m:
        tag = m.group(0).strip().lower()
        return "v." if tag in ("vt.", "vi.") else tag
    if pos_field:
        best, bestv = None, -1
        for item in pos_field.split("/"):
            if ":" not in item:
                continue
            code, val = item.split(":", 1)
            try:
                v = int(val)
            except ValueError:
                continue
            if v > bestv:
                bestv, best = v, code.strip()
        if best in POS_CODE:
            return POS_CODE[best]
    return ""


def classify(text):
    for topic, kws in TOPIC_RULES:
        if any(k in text for k in kws):
            return topic
    return "general"


def tier_of(tags, collins, oxford):
    """雅思相关度分层：数字越小越优先。"""
    t = set(tags.split())
    if "ielts" in t:
        return 0
    if t & {"ky", "cet6", "toefl"}:
        return 1
    if collins >= 3:
        return 2
    if "gre" in t:
        return 3
    return 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="/tmp/ecdict.csv")
    ap.add_argument("--target", type=int, default=5000)
    ap.add_argument("--keep", type=int, default=9,
                    help="保留前 N 个手工词表文件（按文件名排序）")
    ap.add_argument("--chunk", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--min-freq", type=int, default=1000,
                    help="牛津3000核心词若词频高于此值（更常用）则视为太简单，剔除")
    ap.add_argument("--max-freq", type=int, default=20000,
                    help="词频排名低于此值（更生僻）则剔除")
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        print("找不到词典文件: %s" % a.csv)
        print("下载: curl -sL -o /tmp/ecdict.csv "
              "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv")
        sys.exit(1)

    keep_prefixes = ["%02d-" % i for i in range(0, a.keep)]
    taken, curated_n = load_curated(keep_prefixes)
    print("手工词表: %d 词（文件前缀 %s），不覆盖" % (curated_n, keep_prefixes[:1]))
    need = max(0, a.target - curated_n)
    print("目标总量 %d，需从词典补充 %d 词" % (a.target, need))

    cand = []
    inflected = set()
    drop = {"stop": 0, "nodef": 0, "name": 0, "nofreq": 0, "dupe": 0}
    with open(a.csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = (row.get("word") or "").strip()
            ex = row.get("exchange") or ""
            if ex:
                for item in ex.split("/"):
                    if ":" in item:
                        v = item.split(":", 1)[1].strip()
                        if v and len(v) <= 24:
                            inflected.add(slug(v))
            if not WORD_RE.match(w):
                continue
            if w in STOPWORDS:
                drop["stop"] += 1
                continue
            sid = slug(w)
            if sid in taken:
                drop["dupe"] += 1
                continue
            trans = (row.get("translation") or "").strip()
            if not trans or not CJK.search(trans):
                continue
            tags = (row.get("tag") or "").strip()
            tset = set(tags.split())
            # 只有中考/高考标签 → 中学水平，太简单
            if tset and tset <= EASY_TAGS:
                drop["easy"] = drop.get("easy", 0) + 1
                continue
            defn = (row.get("definition") or "").strip()
            # 没有英文释义 / 释义是人物或地点 → 基本都是专有名词
            if len(defn) < 8 or DEFN_PERSON.search(defn) or DEFN_PLACE.search(defn):
                drop["nodef"] += 1
                continue
            if BAD_ENTRY.search(trans) or INFLECT_ONLY.search(trans):
                drop["name"] += 1
                continue
            try:
                collins = int(row.get("collins") or 0)
                oxford = int(row.get("oxford") or 0)
                bnc = int(row.get("bnc") or 0)
                frq = int(row.get("frq") or 0)
            except ValueError:
                collins = oxford = bnc = frq = 0
            freq = bnc if bnc > 0 else frq
            if freq <= 0:
                drop["nofreq"] += 1
                continue
            cand.append((tier_of(tags, collins, oxford), freq, w,
                         (row.get("phonetic") or "").strip(), trans,
                         row.get("pos") or "", defn[:300], sid, oxford))

    print("候选词条: %d（剔除 %s）" % (len(cand), drop))
    cand.sort(key=lambda x: (x[0], x[1], x[2]))

    def pick(min_f, max_f, easy_filter, max_tier=4):
        out, seen = [], set()
        for tier, freq, w, ph, trans, posf, defn, sid, oxf in cand:
            if len(out) >= need:
                break
            if tier > max_tier or freq > max_f:
                continue
            if easy_filter:
                # 牛津 3000 核心 + 极高频 = 早就会了，不占名额
                if oxf == 1 and freq < min_f:
                    continue
                if freq < 1500 and len(w) <= 4:
                    continue
            if sid in seen or sid in inflected:
                continue
            meaning = clean_meaning(trans)
            if not meaning:
                continue
            seen.add(sid)
            out.append((w, ph, derive_pos(trans, posf), meaning, sid, defn, tier))
        return out

    # 逐级放宽：优先保证「考试标签词 + 常用词」，实在不够才动用生僻词
    # 逐级放宽：先保「常用 + 有考试标签」，最后才动用生僻词兜底
    plan = [(a.min_freq, a.max_freq, True, 4),
            (a.min_freq, 30000, True, 1),
            (a.min_freq, 30000, True, 4),
            (a.min_freq, 50000, True, 1),
            (a.min_freq, 50000, True, 4),
            (a.min_freq, 10 ** 9, True, 1),
            (0, 10 ** 9, False, 4)]
    picked = []
    for i, (mf, xf, ef, mt) in enumerate(plan):
        picked = pick(mf, xf, ef, mt)
        if len(picked) >= need:
            if i:
                print("第 %d 级筛选达标（词频上限 %s，层级上限 T%s）" % (i + 1, xf, mt))
            break
    print("筛出 %d 词" % len(picked))
    tiers = {}
    for it in picked:
        tiers[it[6]] = tiers.get(it[6], 0) + 1
    print("分层构成 T0雅思/T1考研六级托福/T2柯林斯/T3-GRE/T4其他: %s"
          % [tiers.get(i, 0) for i in range(5)])

    os.makedirs(WORDS_DIR, exist_ok=True)
    # 清理旧的分片
    for fn in os.listdir(WORDS_DIR):
        if fn.startswith("10-bank-"):
            os.remove(os.path.join(WORDS_DIR, fn))

    random.seed(a.seed)
    written, files = 0, []
    for i in range(0, len(picked), a.chunk):
        part = picked[i:i + a.chunk]
        fn = "10-bank-%02d.tsv" % (i // a.chunk + 1)
        path = os.path.join(WORDS_DIR, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# word | phonetic | pos. | meaning | example | topic\n")
            for w, ph, pos, meaning, sid, defn, tier in part:
                phone = "/%s/" % ph if ph else ""
                topic = classify(meaning + " " + defn)
                line = "%s | %s | %s | %s | %s | %s" % (
                    w, phone, pos, meaning.replace("|", "/").replace("\n", " "),
                    "", topic)
                f.write(line + "\n")
        files.append(fn)
        written += len(part)
    print("已写入 %d 个分片，共 %d 词" % (len(files), written))

    # 合并进已有学习进度
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            st = json.load(f)
        have = set(st["words"].keys()) | set(st.get("new_queue", []))
        new_ids = [p[4] for p in picked if p[4] not in have]
        random.shuffle(new_ids)
        st.setdefault("new_queue", []).extend(new_ids)
        st["bank_size"] = curated_n + written
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        print("已把 %d 个新词追加进现有学习进度（不影响已学记录）" % len(new_ids))
    else:
        print("尚无 state.json，下次运行会自动载入全部 %d 词" % (curated_n + written))


if __name__ == "__main__":
    main()
