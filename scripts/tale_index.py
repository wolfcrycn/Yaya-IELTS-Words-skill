#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日童话 · 题材台账（防重复）

用户要求「每天童话故事的**名称、内容题材要不同**」，光靠记忆做不到，
所以把历史写过的童话/诗全部扫出来，写成可以查、可以自检的台账。

用法：
  # 1) 动笔前先看已用过的：日期 · 标题 · 题材 · 主角 · 出处
  $PY scripts/tale_index.py

  # 2) 想不出题材时，从没用过的题材池里随机推荐几个
  $PY scripts/tale_index.py --suggest
  $PY scripts/tale_index.py --suggest -n 5

  # 3) 写完之后自检：撞车就退出码 2（撞车 = 标题/题材/主角与历史重复）
  $PY scripts/tale_index.py --check "The Teapot's Confession" \
      --theme "一只自命不凡的旧茶壶" --hero "旧茶壶"

  # 4) 台账本身也可以机读
  $PY scripts/tale_index.py --json

数据来源：<数据目录>/tales/tale-*.json（新的童话）与 <数据目录>/poems/poem-*.json（旧的诗），
外加 LEGACY_THEMES 里手工登记的历史题材（那些没留下 json 的）。
"""
import argparse
import glob
import json
import os
import random
import re
import sys

HOME = os.path.expanduser("~")
DATA_DIR = os.environ.get("IELTS_DATA_DIR", os.path.join(HOME, ".workbuddy", "ielts-prep"))
TALES_DIR = os.path.join(DATA_DIR, "tales")
POEMS_DIR = os.path.join(DATA_DIR, "poems")

# 旧诗（散文诗时代）用过的题材，手工登记，免得第一篇小说就重蹈覆辙。
# 格式：(日期, 标题, 题材)
LEGACY_THEMES = [
    ("<2026-09-12", "The Foundation of Small Hours", "城市清晨 · 城市生活/公共事务"),
    ("<2026-09-12", "（第 1 天）城市规划与治理", "城市规划 · 议会/税收/政策/学校"),
    ("2026-09-13", "What the Salt House Knows", "海边盐屋 · 潮水与遗产"),
]

# 没写过的题材池：安徒生那一脉「日常物件 + 小人物 + 一点苦味」的领域。
# theme 是领域描述，hero 是主角，两个轴都要轮着换，不然还是会同质化。
POOL = [
    ("深海与人鱼", "一条小人鱼"),
    ("一棵树的一年", "一株云杉"),
    ("一盏街灯的记忆", "老路灯"),
    ("一枚银币的旅行", "银币"),
    ("一双旧舞鞋", "舞鞋"),
    ("风与窗", "北风"),
    ("雪人", "雪人"),
    ("蝴蝶选亲", "蝴蝶"),
    ("影子的背叛", "影子"),
    ("夜莺与皇帝", "夜莺"),
    ("一只自命不凡的旧茶壶", "旧茶壶"),
    ("织补针", "缝衣针"),
    ("教堂钟的最后一声", "钟"),
    ("卖火柴的小女孩", "小女孩"),
    ("沼泽王的女儿", "沼泽王"),
    ("一只瓶子的漂流", "瓶子"),
    ("魔镜的碎片", "镜子碎片"),
    ("一封没有寄到的信", "邮差"),
    ("园丁与四季", "园丁"),
    ("钟表匠与走失的时间", "钟表匠"),
    ("五颗豌豆", "豌豆"),
    ("小锡兵", "锡兵"),
    ("花国里的拇指姑娘", "拇指姑娘"),
    ("一滴水在显微镜下", "水珠"),
    ("亚麻的一生", "亚麻"),
    ("天使与孩子", "天使"),
    ("坟上的玫瑰", "玫瑰"),
    ("风筝与线", "风筝"),
    ("陀螺与球", "陀螺"),
    ("蜗牛与玫瑰树", "蜗牛"),
    ("一朵云的重量", "云"),
    ("一把只开一扇门的钥匙", "钥匙"),
    ("蜡烛的两半", "蜡烛"),
    ("阴沟里的纸船", "纸船"),
    ("沙与珍珠", "珍珠"),
    ("老橡树的梦", "老橡树"),
    ("候鸟与留鸟", "麻雀"),
    ("石头与河", "石头"),
    ("图书馆里没人读的那本书", "书"),
    ("一只会算数的喜鹊", "喜鹊"),
]


def norm(s):
    """归一化：去空白/标点、转小写，用来判重。"""
    if not s:
        return ""
    return re.sub(r"[\s·・,，。.、;；:：!！?？\-—_/／'\"“”‘’()（）\[\]【】]+", "", str(s)).lower()


def bigrams(s):
    s = norm(s)
    if len(s) < 2:
        return set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def sim(a, b):
    """2-gram Jaccard，用来抓「换了个说法但其实还是同一件事」。"""
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / float(len(A | B))


def relate(a, b):
    """→ (是否同一, 是否很近)。同一 = 归一化后完全相同；很近 = 一方是另一方的一部分，
    或 Jaccard ≥ 0.45。后者专治「海边盐屋」vs「海边盐屋 · 潮水与遗产」这种加了个尾巴的。"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False, False
    if na == nb:
        return True, True
    A, B = bigrams(a), bigrams(b)
    subset = bool(A) and bool(B) and (A <= B or B <= A)
    return False, subset or sim(a, b) >= 0.45


def _date_from_path(path):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    return m.group(1) if m else ""


def load_history():
    """→ [{date,title,theme,hero,src,kind}]，按日期排序。"""
    rows = []
    for d, kind in ((TALES_DIR, "tale"), (POEMS_DIR, "poem")):
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            base = os.path.basename(p)
            if ".zh" in base:          # 译文文件不是正文
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:          # noqa: BLE001
                continue
            if not isinstance(data, dict):
                continue
            rows.append({
                "date": _date_from_path(p) or data.get("date") or "",
                "title": data.get("title") or "(无标题)",
                "theme": data.get("theme") or "",
                "hero": data.get("hero") or "",
                "src": base,
                "kind": kind,
            })
    for date, title, theme in LEGACY_THEMES:
        # 已经留下 json 的（标题能对上）就别再登记一遍，否则台账会出现重复行；
        # 但 json 里没写 theme 的，把这里登记的题材补进去，信息不丢。
        hit = next((r for r in rows if norm(r["title"]) == norm(title)), None)
        if hit:
            if not hit["theme"]:
                hit["theme"] = theme
                hit["src"] += " + 历史登记"
            continue
        rows.append({"date": date, "title": title, "theme": theme,
                     "hero": "", "src": "(历史登记)", "kind": "legacy"})
    rows.sort(key=lambda r: (r["date"], r["src"]))
    return rows


def used_themes(rows):
    out = []
    for r in rows:
        if r["theme"]:
            out.append(r["theme"])
        if r["hero"]:
            out.append(r["hero"])
    return out


def cmd_list(rows, as_json):
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print("📭 台账是空的——这会是第一篇童话。")
        return 0
    print("📖 已写过的题材台账（%d 条）" % len(rows))
    print("-" * 78)
    for r in rows:
        print("%-12s %-38s %s" % (r["date"], r["title"][:38], r["theme"] or "—"))
        if r["hero"]:
            print("%-12s   └ 主角：%s   [%s]" % ("", r["hero"], r["src"]))
    print("-" * 78)
    th = sorted({r["theme"] for r in rows if r["theme"]})
    hr = sorted({r["hero"] for r in rows if r["hero"]})
    print("已用题材领域 %d 个：%s" % (len(th), "、".join(th) or "—"))
    print("已用主角 %d 个：%s" % (len(hr), "、".join(hr) or "—"))
    print("\n※ 新的一篇：标题、题材、主角三者都要和上面不一样。写完用 --check 自检。")
    return 0


def cmd_suggest(rows, n):
    used = used_themes(rows)
    fresh = []
    for theme, hero in POOL:
        if any(relate(theme, u)[1] or relate(hero, u)[1] for u in used):
            continue
        fresh.append((theme, hero))
    if not fresh:
        print("题材池已用尽，得自己另想一个了。")
        return 0
    random.seed()
    picks = random.sample(fresh, min(n, len(fresh)))
    print("🎲 没用过的题材（还剩 %d 个）：" % len(fresh))
    for theme, hero in picks:
        print("   · 题材：%s ｜ 主角：%s" % (theme, hero))
    print("\n※ 挑一个，然后写标题（英文、有画面感，别和上面的标题撞）。")
    return 0


def cmd_check(rows, title, theme, hero):
    bad, warn = [], []
    for r in rows:
        for label, mine, theirs in (("标题", title, r["title"]),
                                    ("题材", theme, r["theme"]),
                                    ("主角", hero, r["hero"])):
            if not mine or not theirs:
                continue
            same, close = relate(mine, theirs)
            if same:
                bad.append("%s撞车：「%s」＝ %s 的「%s」（%s）"
                           % (label, mine, r["date"], theirs, r["src"]))
            elif close:
                warn.append("%s很像：「%s」≈ %s 的「%s」（相似度 %.2f）"
                            % (label, mine, r["date"], theirs, sim(mine, theirs)))
    for w in warn:
        print("⚠️  " + w)
    for b in bad:
        print("✗ " + b)
    if bad:
        print("\n✗ 撞车了，换个标题/题材/主角再来。")
        return 2
    print("✓ 标题 / 题材 / 主角都没和历史重复，可以写。")
    if warn:
        print("  （上面带 ⚠️ 的更接近，建议微调，但不拦你）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="每日童话题材台账（防重复）")
    ap.add_argument("--check", metavar="TITLE", help="自检新标题是否与历史重复")
    ap.add_argument("--theme", default="", help="新童话的题材（配合 --check）")
    ap.add_argument("--hero", default="", help="新童话的主角（配合 --check）")
    ap.add_argument("--suggest", action="store_true", help="从没用过的题材池里推荐")
    ap.add_argument("-n", type=int, default=3, help="--suggest 推荐几个（默认 3）")
    ap.add_argument("--json", action="store_true", help="台账以 JSON 输出")
    a = ap.parse_args()

    rows = load_history()
    if a.check:
        return cmd_check(rows, a.check, a.theme, a.hero)
    if a.suggest:
        return cmd_suggest(rows, a.n)
    return cmd_list(rows, a.json)


if __name__ == "__main__":
    sys.exit(main())
