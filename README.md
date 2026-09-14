# 丫丫雅思单词 · Yaya IELTS Words Skill

一个给 AI 助手用的**雅思背单词技能包**（Agent Skill）。装上之后，你只要对助手说「开始背单词」，
它就会按艾宾浩斯遗忘曲线给你派词、出 HTML 答题卡、判分、记录错词；**当天任务背完，
它会用今天背过的所有单词写一篇模仿安徒生的英文哲理童话，做成带插画和朗读的 HTML 绘本**收尾。

- 词库 **10000 词**（9 个主题词表 + 20 个自动生成的大词库分片）
- 每天 **50 词**，一轮 **10 张**答题卡，新词永不重复，错词自动进强化池
- 复习间隔：1 / 2 / 4 / 7 / 15 / 30 / 60 天（stage 0–8）
- 每日童话：**每天标题、题材、主角都不重样**；**每段配图由内容现场拼出来，且跨天不重样**

> 2026-09-14 起由「丫丫单词」更名为「丫丫雅思单词」。旧名仍是触发别名。

---

## 安装

这是一个标准的 Agent Skill 目录（`SKILL.md` + `scripts/` + `assets/` + `data/`）。
把整个目录放到你的技能目录下即可：

```bash
# WorkBuddy / 同类 Agent
SKILLS=~/.workbuddy/skills

git clone https://github.com/wolfcrycn/Yaya-IELTS-Words-skill.git /tmp/yaya-ielts
mkdir -p "$SKILLS/丫丫雅思单词"
cp -R /tmp/yaya-ielts/. "$SKILLS/丫丫雅思单词/"
```

⚠️ **目录名必须是 `丫丫雅思单词`** —— 与 `SKILL.md` 顶部的 `name:` 一致，助手才认得出来。
直接把克隆下来的 `Yaya-IELTS-Words-skill/` 丢进 skills 目录是不行的（名字对不上）。

学习数据默认写在 `~/.workbuddy/ielts-prep/`（`state.json` 是唯一事实来源，别手改）；
想换地方就设环境变量 `IELTS_DATA_DIR`。

## 依赖

| 依赖 | 是否必需 | 用途 |
|---|---|---|
| Python 3.9+ | ✅ 必需 | 全部脚本（只用来跑脚本，无需装任何三方包） |
| Node 18+ | 可选 | 跑答题卡模板的回归测试 |
| Google Chrome / Chromium | 可选 | 绘本转 PNG、朗读按钮的真机实测 |

## 快速开始

```bash
SKILL=~/.workbuddy/skills/丫丫雅思单词
PY=python3            # 或你的 python3 绝对路径

$PY $SKILL/scripts/ielts.py init                  # 首次使用：建档（目标分、每日新词量）
$PY $SKILL/scripts/ielts.py today                 # 看今日任务
$PY $SKILL/scripts/ielts.py start --n 50 --per 10 # 组批：强化池 → 到期复习 → 新词
$PY $SKILL/scripts/ielts.py quiz                  # 生成本轮 10 张 HTML 答题卡
```

答题卡**只收答案、不显示答案**（卡面只有英文 + 音标 + 词性 + 例句，一个「忘了」按钮，
没有对/错反馈，底栏也没有回执预览）。填完点「复制回执」，把回执贴回对话，由 AI 判分
（同义近义算对、方向对但不精确算模糊、换成另一个词算错），再落库：

```bash
# 自己判（推荐，能给解析）：c=correct / f=fuzzy / w=wrong，顺序对齐回执，给满当轮张数
$PY $SKILL/scripts/ielts.py submit --answers "c,f,w,c,w,c,c,f,w,w"

# 或让引擎代判（同义改写会被低估，❌ 条目务必人工复核）
$PY $SKILL/scripts/ielts.py submit --raw "<整段回执原文>" --dry-run

$PY $SKILL/scripts/ielts.py finish   # 收尾：结算本日、更新记忆曲线
```

常用子命令：`init` `today` `start` `quiz` `submit` `reveal` `grade` `finish`
`stats` `report` `task` `import` `example` `poem` `reset`。

> `quiz` 遇到「没有例句」的词会**退出码 2** 并列出清单——这不是报错，
> 是「先造句再出卡」的硬闸。按清单用 `example --json` 补例句后重跑即可。

## 每日童话（收尾仪式）

```bash
# 1) 取今天背过的词，写一篇安徒生式英文哲理童话（5–7 段、500–800 词）
$PY $SKILL/scripts/ielts.py poem

# 2) 存成 JSON（键：story / zh / theme / hero / words），写之前先查台账防重样
$PY $SKILL/scripts/tale_index.py                      # 台账：日期 · 标题 · 题材 · 主角
$PY $SKILL/scripts/tale_index.py --suggest -n 5       # 从没写过的题材里推荐
$PY $SKILL/scripts/tale_index.py --check "The Teapot's Confession" \
        --theme "一只自命不凡的旧茶壶" --hero "旧茶壶"   # 撞车 → 退出码 2

# 3) 渲染成 HTML 绘本（默认手绘 SVG 水彩风 + 朗读 + 中英双语切换）
$PY $SKILL/scripts/make_watercolor_svg_book.py \
    --json ~/.workbuddy/ielts-prep/tales/tale-2026-09-14.json \
    --date 2026-09-14 \
    --out  ~/.workbuddy/ielts-prep/tales/book-2026-09-14.html
```

绘本的**每段配图**由 `scripts/art_storyboard.py` 现场拼：17 个背景层 × 59 个主体物，
每个主体物都必须有「从这段/标题里引出的那个词」当凭据（`--art scene` 可回退到旧的成品场景）。
跨天防重靠 `~/.workbuddy/ielts-prep/art-ledger.json`。

其他渲染器：`make_comic.py`（连环画）、`make_picturebook.py`（翻页点词）、
`make_poem_poster.py`（单张卡）、`make_doodle_book.py`（涂鸦风）、
`make_watercolor_book.py`（AI 位图水彩）、`make_watercolor_svg_cute_book.py`（chibi）。

## 目录结构

```
.
├── SKILL.md                      # 技能本体：触发词、完整工作流、命令示例
├── assets/
│   ├── quiz-template.html        # 答题卡模板（自包含，无外链）
│   ├── sample-quiz-card.html     # 样板卡
│   └── sample-weekly-report.html # 周报样板
├── data/words/*.tsv              # 10000 词库（9 主题表 + 20 个 bank 分片）
├── references/
│   ├── ebbinghaus.md             # 记忆曲线调度规则
│   └── weekly-plan.md            # 听说读写周计划
└── scripts/
    ├── ielts.py                  # 主程序（状态机 + 全部子命令）
    ├── art_storyboard.py         # 童话配图「故事分镜」引擎
    ├── tale_index.py             # 童话题材台账（防重复）
    ├── build_bank.py             # 词库生成
    ├── make_*.py                 # 7 个 HTML 绘本 / 卡片渲染器
    ├── verify_quiz_card.js       # 答题卡模板回归（Node）
    └── verify_watercolor_book.py # 绘本回归（Python + Chrome 实测）
```

## 自检

```bash
$PY $SKILL/scripts/verify_watercolor_book.py   # 绘本四段回归，C 段要 Chrome
NODE=${NODE:-$(command -v node)} node $SKILL/scripts/verify_quiz_card.js
```

## License

MIT — 见 [LICENSE](./LICENSE)。词库内容来自公开词表整理，可自由使用；
`data/words/` 下由 ECDICT 派生的部分遵循其原始许可。
