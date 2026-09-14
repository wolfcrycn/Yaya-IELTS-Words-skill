#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改完 assets/quiz-template.html 后，用它重新生成一张可独立打开的示例答题卡。

    python3 scripts/make_sample_card.py            # 10 张，默认 word 模式
    python3 scripts/make_sample_card.py --n 3 --mode cn

只读模板 + 写 assets/sample-quiz-card.html，不碰任何真实学习数据。
"""
import argparse
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POOL = [
    ("anticipate", "/ænˈtɪsɪpeɪt/", "v.", "预料，预期",
     "We anticipate a rise in demand next quarter.", "职场经济"),
    ("fluctuate", "/ˈflʌktʃueɪt/", "v.", "波动，起伏",
     "Oil prices fluctuated wildly last month.", "环境"),
    ("deteriorate", "/dɪˈtɪəriəreɪt/", "v.", "恶化，变坏",
     "Air quality deteriorated sharply after the fires.", "健康"),
    ("incorporate", "/ɪnˈkɔːpəreɪt/", "v.", "包含，纳入",
     "The plan incorporates feedback from local residents.", "社会"),
    ("advocate", "/ˈædvəkeɪt/", "v.", "提倡，主张",
     "Many scientists advocate stricter emission limits.", "环境"),
    ("sustainable", "/səˈsteɪnəbl/", "adj.", "可持续的",
     "Cities need sustainable transport systems.", "环境"),
    ("curb", "/kɜːb/", "v.", "抑制，控制",
     "New rules aim to curb plastic waste.", "环境"),
    ("assess", "/əˈses/", "v.", "评估，评定",
     "Teachers assess students on both essays and exams.", "教育"),
    ("hinder", "/ˈhɪndə(r)/", "v.", "阻碍",
     "Poor sleep hinders academic performance.", "健康"),
    ("eliminate", "/ɪˈlɪmɪneɪt/", "v.", "消除，排除",
     "The scheme eliminated most manual errors.", "科技"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="示例卡张数（默认 10，与 per_round 一致）")
    ap.add_argument("--mode", choices=["word", "cn"], default="word")
    ap.add_argument("--with-missing", action="store_true",
                    help="留一张没有例句的卡，用来预览占位提示")
    ap.add_argument("--out", default=os.path.join(SKILL_DIR, "assets", "sample-quiz-card.html"))
    a = ap.parse_args()

    tpl_path = os.path.join(SKILL_DIR, "assets", "quiz-template.html")
    tpl = open(tpl_path, encoding="utf-8").read()
    if "/*__DATA__*/" not in tpl:
        sys.exit("模板里找不到 /*__DATA__*/ 占位符，检查 quiz-template.html")

    cards = []
    for i in range(min(a.n, len(POOL))):
        w, phon, pos, meaning, ex, topic = POOL[i]
        cards.append({"id": "sample-%d" % (i + 1), "word": w, "phonetic": phon, "pos": pos,
                      "meaning": meaning, "example": ex, "topic": topic,
                      "is_new": i >= 7, "stage": (i % 4)})
    if len(cards) < a.n:
        sys.exit("POOL 只有 %d 个词，要 %d 张请先补充词条" % (len(POOL), a.n))
    if a.with_missing and cards:
        # 词库里 97% 的词没有例句，示例也留一张空的，好看到占位提示长什么样
        cards[-1]["example"] = ""

    payload = {
        "cards": cards,
        "meta": {"round": 3, "total": 30, "date": "2026-09-11", "mode": a.mode,
                 "progress": "累计已学 128 · 已掌握 47"},
    }
    open(a.out, "w", encoding="utf-8").write(
        tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False)))
    print("已写出 %s（%d 张，%s 模式）" % (a.out, len(cards), a.mode))


if __name__ == "__main__":
    main()
