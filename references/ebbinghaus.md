# 艾宾浩斯调度表

引擎用「阶段（stage）+ 间隔（天）」实现遗忘曲线，而不是固定复习表。

## 阶段 → 间隔

| stage | 下次复习间隔 | 含义 |
|---|---|---|
| 0 | 当天 | 刚发放的新词，当天必须过一遍 |
| 1 | +1 天 | 第一次巩固 |
| 2 | +2 天 | |
| 3 | +4 天 | |
| 4 | +7 天 | 一周线 |
| 5 | +15 天 | 半月线 |
| 6 | +30 天 | 月线 |
| 7 | +60 天 | 长时记忆线 |
| 8 | — | 毕业（mastered），移出循环 |

## 状态转移

```
correct : stage = min(stage+1, 8)      8 即为毕业
fuzzy   : stage 不变，due = today + max(1, interval[stage])，进强化池(need=1)
wrong   : stage = max(0, stage-2)，due = today，进强化池(need=2)
```

- 强化池条目答对一次 `need -= 1`，归零则出池；答错 `need` 重置为 2。
- 答错/模糊的词会在**同一批**里往后插 3–4 张再考一次（即时回炉），并在**第二天**优先出现。
- 累计错 ≥5 次 → `leech=True`，进入顽固词名单，周报单独列出。

## 为什么这样设计

- 直接把答错的 stage 归零会浪费此前的记忆投入，因此只退 2 级。
- 「模糊」单独一档很关键：它通常意味着被动认得、主动想不出来，
  这类词如果不额外练，会在 7 天线上集中崩盘。
- 毕业线设在 60 天后：雅思备考周期通常 2–6 个月，再长没有边际收益。

## 调参建议

| 场景 | 调整 |
|---|---|
| 正确率 < 70% | `daily_new` 减半（`init --daily-new 15`），先清空强化池 |
| 正确率 > 90% 且稳定 | `daily_new` +10，把 `session_size` 提到 30 |
| 距考试 < 30 天 | 停止发新词，只跑复习池 + 顽固词；新词改从真题里捞 |
| 每天时间 < 15 分钟 | `daily_new` 10、`session_size` 15，保住连续性优先于量 |

## 数据字段

`state.json` 中每个词：
```
id, word, phonetic, pos, meaning, example, topic,
status   : new | learning | mastered
stage    : 0..8
due      : YYYY-MM-DD | null（毕业）
wrong, right, streak, leech, first_seen, last_seen, graduated, history[]
```

顶层还有：`new_queue`（未发放新词，洗过牌）、`reinforcement`（强化池）、
`daily[date]`（当日计数与训练记录）、`session`（进行中的闪卡会话）。
