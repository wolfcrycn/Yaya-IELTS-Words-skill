---
name: 丫丫雅思单词
description: 雅思背单词助手「丫丫雅思单词」（2026-09-14 从「丫丫单词」更名而来，用户说「丫丫单词」「丫丫」也指本技能）。当用户提到「丫丫雅思单词」「丫丫单词」，或说「开始背单词」「背单词」「雅思单词」「今日雅思任务」「今日童话」「今日散文诗」，或要求单词闪卡练习、雅思进度报告/周报、查看记忆曲线与掌握情况时使用。按艾宾浩斯遗忘曲线调度复习（每天 50 词、一轮 10 张 HTML 答题卡），新词永不重复，错词自动进强化池；**当天任务背完，用今天背过的所有单词写一篇模仿安徒生的英文哲理童话（每天题材/标题不重复），渲染成带插画和朗读的 HTML 绘本交付；每段配图由「故事分镜」引擎按该段真实出现的词现场拼（必须与标题/内容对得上），并靠 art-ledger.json 保证每天的配图都和以前不同**。
agent_created: true
---

# 丫丫雅思单词 · 雅思背单词助手

## 运行环境

```bash
SKILL=~/.workbuddy/skills/丫丫雅思单词
PY=/Users/nelson/.workbuddy/binaries/python/versions/3.13.12/bin/python3
[ -x "$PY" ] || PY=python3
DATA=~/.workbuddy/ielts-prep      # state.json / reports/
```

所有状态存在 `~/.workbuddy/ielts-prep/state.json`（数据目录可用 `IELTS_DATA_DIR` 覆盖）。
手动命令：`$PY $SKILL/scripts/ielts.py <子命令>`。

子命令：`init` `today` `start` `quiz` `submit` `reveal` `grade` `finish` `stats` `report`
`task` `example` `poem` `import` `reset`

答题卡模板：`assets/quiz-template.html`（纯内联 CSS/JS，无外部依赖，改样式只改这一个文件）。
生成的卡片落在 `~/.workbuddy/ielts-prep/quizzes/`，自动只保留最近 60 张。
每张卡带**例句**，输入框右边自带一个「**忘了**」按钮，点了自动把答案填成「忘了」。
卡片**不显示回执预览**——底栏只有「已填写 X / 10」，回执在点「复制回执」那一刻才现取生成。
`quiz` 出卡前有一道闸：本轮有词缺例句就**先让你造句、用退出码 2 拦下**，不留占位（见「例句」一节）。
改过模板后**务必跑一遍回归测试**（见文末「维护」）。

辅助脚本：`build_bank.py`（重建词库）、`verify_quiz_card.js`（答题卡回归）、
`verify_watercolor_book.py`（可爱水彩绘本回归：静态 + 分镜 + JS + 真机朗读行为，共 164 项）、
`tale_index.py`（每日童话题材台账：**标题/题材/主角防重复**，见「每日童话」一节）、
`art_storyboard.py`（**故事分镜画具**：17 个背景层 + 59 个主体物，按段落里真实出现的词现场配图，
见「每日童话 · 配图」一节）、
`make_sample_card.py`（重出示例卡）、`make_poem_poster.py`（把正文渲成一张卡片，见「每日童话」一节）、
`make_comic.py`（把同一个故事渲成卡通连环画，见「每日童话」一节）、
`make_picturebook.py`（把手写 SVG 做成可翻页、可点词查义、**可切英文/中文/双语**的 HTML 绘本，
见「每日童话」一节）、
`make_watercolor_book.py`（把同一个故事做成 **AI 水彩配图** 的滚动式动态绘本，同上）、
`make_watercolor_svg_book.py`（把同一个故事做成 **故事风手绘水彩 SVG** 的动态绘本，
**分镜式自动配图**（`art_storyboard.py`，背景 + 主体物按内容拼，跨天不重样）+
EN/中文/双语切换 + **英文朗读开关**，**童话默认用它**，同上）、
`make_watercolor_svg_cute_book.py`（把同一个故事做成 **可爱 chibi 造型手绘水彩 SVG** 的动态绘本，
圆头圆脑小人 + 腮红爱心 + 马卡龙色 + EN/中文/双语切换 + **英文朗读开关**，
但场景写死成城市/治理那一套，**只适合城市题材**，同上）、
`make_doodle_book.py`（**手写 SVG 水彩涂鸦** + 滚动动画 + 三语切换的绘本，同上）。

---

## 触发 A：用户说「开始背单词」（最高优先级）

**每天 50 个单词**（强化池 → 到期复习 → 新词），一轮 10 张，用 HTML 答题卡作答；
卡面显示英文单词，用户在输入框里写中文意思。一次只推进一轮，绝不提前泄露释义。

> 分工：**答题卡只负责收集答案，一个字都不判，也没有提交按钮**。
> 每张卡输入框右边有个「**忘了**」按钮，一点就自动把该卡答案填成「忘了」并跳到下一张。
> 用户写完点「复制回执」——按钮会**现取所有输入框的内容**拼成回执（**卡上不显示回执预览**）。
> 把回执贴回来，**由你来判对错、给解析，再写回进度**。

```bash
$PY $SKILL/scripts/ielts.py start --n 50 --per 10   # 组批：强化池 → 到期复习 → 新词
$PY $SKILL/scripts/ielts.py quiz                    # 生成本轮 HTML 答题卡，返回文件路径
```

1. `start` 会把本批（默认 50 张）分成若干个 10 张一轮，并告诉你总轮数。
2. `quiz` 生成答题卡 → **立刻用 `present_files` 打开它**，配一句话：
   「十张都在卡里：看清英文单词，直接在输入框写中文意思（回车跳到下一张），
     想不起来的点右边『忘了』；写完点右下『复制回执』发我，我来判对错。」
   - **卡片正面只有英文单词 + 音标 + 词性 + 例句**，中文意思绝不出现；
     卡片上只有「忘了」这一个按钮，**没有任何「对 / 错」反馈**。
     底栏只有一句「已填写 X / 10」，**没有回执预览**（回执只在点复制那一刻生成）。
     **不要**在对话里提前贴释义。
   - 例句就是语境提示。**出卡前引擎自带一道闸**：这一轮只要有词没例句，
     `quiz` 会**直接列出来并以退出码 2 结束、不出卡**（见下面「例句」一节）。
     你只管按它给的清单造好句子存进去，再重跑 `quiz` 即可——**卡面绝不会出现占位**。
   - 反向模式（看中文写英文）：`quiz --mode cn`；默认 `word`=看英文写中文。
     该选择会记进 `profile.ask_mode`，想切回默认再跑一次 `quiz --mode word`。
   - 每轮张数临时改动：`quiz --per N`（默认 10）。
   - 想要纯文字出题：`quiz --text`（只给正面，同样不泄露释义）。
3. 用户贴回执。回执长这样（10 张就是 10 行）：
   ```
   丫丫雅思单词答题卡回执 · 2026-09-11 · 第1轮（看英文写中文）
   1. anticipate → 我答：预料
   2. fluctuate → 我答：忘了
   3. deteriorate → 我答：（未作答）
   ...
   ```
   - `我答：忘了` = 用户点了「忘了」按钮，**明确不会**，按 `wrong` 记，可以顺带给个助记。
   - `我答：（未作答）` = 没填也没点忘了，同样按 `wrong` 记。
   **两种记录方式，任选一种：**
   - **你自己判**（推荐，能给解析）：逐张对照用户答案和释义，判 `correct / fuzzy / wrong`，
     然后把结果告诉用户（对错 + 正确意思 + 例句 + 刚才为什么算错），再落库：
     ```bash
     $PY $SKILL/scripts/ielts.py submit --answers "c,f,w,c,w,c,c,f,w,w"
     ```
     回执里答案的顺序就是 `--answers` 的顺序，**必须给满当轮张数**。
   - **让引擎代判**：把回执原文丢给脚本，它用同一套中文语义匹配给建议，同时落库：
     ```bash
     $PY $SKILL/scripts/ielts.py submit --raw "<整段回执原文>"
     ```
     想先看建议、不写进度就加 `--dry-run`；对某张的判定不认同，随时
     `grade --result correct|fuzzy|wrong` 单张改。
  - 判分口径：命中任一义项（相等或互为子串）= `correct`；只沾到部分字词 = `fuzzy`；
    「忘了」/ 留空 / 完全不沾边 = `wrong`。
  - **你判得比引擎准，该改就改**（`submit --raw --dry-run` 先看建议，再自己定）：
    引擎是纯字符串匹配，**误判是常态、不是例外**，两头都会错：
    - **同义改写一律被低估**：既会把它们判 `fuzzy`（「极为宝贵的」(极宝贵的)、
      「预防性」(预防的)、「优先级」(优先事项)、「有益处的」(有益的)），
      **也会直接判 `❌ 忘了`**（「获取」(获得)、「减轻」(缓解)、「过度的」(过多的)、
      「下降」(减少)、「压倒性的」(压到性的)这类）——**凡是 `❌` 的条目都要自己复核，
      不能只挑 `fuzzy` 看**。核过是标准释义的另一种说法，一律改判 `correct`。
    - **答成另一个词却可能被评为 fuzzy**（inevitable→不可见的=invisible），
      这种**混词错误一律改判 `wrong`**（obtain→申请=apply、maintain→强调=emphasize、
      boost→加速=accelerate、distribute→发送=send 同理），即使字面沾边。
    - **词库里只收了词的某一个词性/义项时也会误判**：`narrow` 词条只写「狭窄的」(adj.)，
      用户答「收窄」(v.) 会被判错——这种按用户答的义项复核，对就改判 `correct`。
    粗线条规则：**同义近义算对，方向上对但不精确算 fuzzy，换成另一个词算错**。
    改完在回复里点明「我改了哪几处、为什么」，用户认这个判法。
  - ⚠️ **回执按「我答：」切分**：某一行漏了这三个字，后面所有答案会**整段串位**
    （引擎会少解析一张、且把答案错配到别的词上）。落库前先用 `--dry-run` 核对
    **解析出的词数 == 回执行数**，对不上就说明回执被截断/格式坏了，让用户重发，
    千万别直接 `submit --answers`。
4. 无论哪种方式，`submit` 都会回传整轮的**背面**（释义 + 例句）+ 记忆阶段变化 + 本轮小结。
   把背面和阶段变化一起展示给用户（这一步才揭示答案）。10 张一次别啰嗦，逐张一行最清爽。
5. 队列没跑完就问「继续下一轮吗」，跑完脚本自动 `finish` 并输出整批小结。
6. **今日任务全部完成后 → 写一篇英文哲理童话（模仿安徒生），做成绘本送给他**（见下一节「每日童话」）。

规则：
- 回执张数必须与当轮卡数一致；收到 `-` 说明有卡没答，提醒补完
- 用户说「停」「结束」「不背了」→ `finish`
- 用户说「继续」→ 再跑一次 `quiz`
- 出现顽固词（累计错 ≥5 次）时，主动给一个助记：词根拆解 / 谐音 / 一句自造句

## 每日童话：今日任务的收尾（做完必须写）

**当今天最后一批背完（`finish` 输出整批小结）之后，用「今天背过的所有单词」写一篇
英文哲理童话（fairy tale），做成带插画 + 朗读的 HTML 绘本交付。** 这是每天背单词的固定收尾，
不是可选彩蛋——用户就是靠它把当天这一批词再串一遍。

> **2026-09-13 起：不再写散文诗。** 用户明确说「不要写优美的散文诗」，要**模仿安徒生
> （H. C. Andersen）的哲理童话**。想要诗的时候他会明说；默认一律童话。
> **每天的名称与题材必须不同**——见下面「防重复」一节，有工具，别靠记性。

```bash
$PY $SKILL/scripts/ielts.py poem                      # 列出今天背过的所有词（只读）
$PY $SKILL/scripts/ielts.py poem --json               # 注意是对象不是数组：{"date":...,"count":N,"words":[{word,pos,meaning,example},...]}
#   取词表要写 d["words"]；直接 for w in data 会报 "string indices must be integers"
$PY $SKILL/scripts/tale_index.py                      # 动笔前：先看已用过的标题/题材/主角
$PY $SKILL/scripts/tale_index.py --suggest            # 没灵感时，从没写过的题材池里挑几个
```

### 怎么写：安徒生的那几手

- **叙述声音**：朴素、口语，像一个人在炉边慢慢讲。以短句为主，故意留一点笨拙的重复。
  **不要**华丽辞藻、不要排比、不要意象堆叠、**不要分行**——那些是诗的写法，用户要的正是**别这样写**。
- **主角**：日常小物件，或不起眼的小人物。安徒生的卡司是：一把钥匙、一只茶壶、一根缝衣针、
  一枚银币、一株云杉、一盏街灯、一个雪人、一只夜莺。**要给物件一个执拗的自我认知**
  （缝衣针以为自己是胸针、茶壶以壶嘴为傲）——这是安徒生大部分反讽的来源。
- **结构**：起（主角和它的小世界）→ 承（一件小事打断它）→ 转（被误解、被摆布，或被一群人
  开会讨论）→ 合（一个安静的、略带苦味的领悟）。**要有情节**，不能只是抒情。
- **反讽**：锋芒藏在平铺直叙里，让读者自己笑一下、疼一下。**不许说教**——
  不许出现「这个故事告诉我们」「所以我们应该」。
- **结尾**：收在一句格言式的句子上，但要含蓄，甚至可以被反着读
  （例：「没有一个人能把钥匙上那点光泽归功于天气」）。
- **哲理**：全文要有**一处**真正的思考支点（关于价值、时间、被看见、用处、限度……），
  但只能让它在情节里自己长出来，不能宣布出来。
- **长度**：5–7 段，每段 4–8 句，全文 500–800 词（约 3000–4500 字符）。

### 用词（硬要求）

- **必须把今天背过的每个词都用进去**（可以变形）。写完自己核一遍，词表里漏掉任何一个都不算完成。
- 但变形**只能落在渲染器认的那几种**（`word_forms()` 的规则）：
  `w` / `w+s` / `w+es` / `w+d` / `w+ed` / 去尾 e + `ing` / 去尾 e + `ies` / 去尾 e + `ied` / `w+ied`。
  于是有两个常见坑：
  - **不规则过去式不算**：`undertook` / `drew` / `felt` / `bought` 都不会被高亮 → 换成规则形式
    （写 `determined to undertake the search`，别写 `undertook`）。
  - **派生副词不算**：`gradually` 命不中 `gradual` → 用形容词（`a gradual quiet`）；
    同理 `notably` ✗ / `notable` ✓。

### 防重复：标题、题材、主角三个轴都要换

`tale_index.py` 会把 `tales/*.json`（童话）和 `poems/*.json`（旧诗）连同手工登记的历史题材
一起扫出来，所以第一篇童话也不会重蹈「城市规划 / 议会 / 税收 / 政策 / 学校」那一套。

```bash
$PY $SKILL/scripts/tale_index.py                 # 台账：日期 · 标题 · 题材 · 主角
$PY $SKILL/scripts/tale_index.py --suggest -n 5  # 从 40 个没用过的题材里推荐
$PY $SKILL/scripts/tale_index.py --check "The Teapot's Confession" --theme "一只自命不凡的旧茶壶" --hero "旧茶壶"
#   撞车（标题/题材/主角与历史完全相同）→ 退出码 2，换一个再来
#   「很像」（一方是另一方的子串，或 2-gram 相似度 ≥ 0.45）→ 只警告，不拦你
```

**动笔前**跑一次台账、**写完**跑一次 `--check`。这是用户点名的要求，别省这一步。

### 数据与渲染

把童话写进 `~/.workbuddy/ielts-prep/tales/tale-<日期>.json`（用文件，别塞进命令行参数）：

```json
{
  "title": "The Key That Opened Only One Door",
  "title_zh": "只开一扇门的钥匙",
  "date": "2026-09-13",
  "subtitle": "第 3 天 · 用今天背过的 53 个词写的安徒生式童话",
  "theme": "一把只开一扇门的钥匙 · 价值与专属",
  "hero": "一把旧钥匙",
  "words": ["feasible", "gradual", "..."],
  "story": ["第一段整段写在这里", "", "第二段整段写在这里", "", "..."],
  "zh": ["第一段中文", "第二段中文", "..."]
}
```

- `story`：**一段一行**（整段散文，不要按行折断），`""` 表示段与段之间的空行。
- `zh`：**一段一条**，紧凑写法（中间不放 `""`）。渲染器认的译文键：`zh` / `zh_stanzas` /
  `translation`；位图绘本与翻页绘本那边历史键名是 `poem_zh`，两个脚本现在都已兼容 `zh`。
- `theme` / `hero`：给 `tale_index.py` 用的**防重复标签**，渲染器会忽略，但一定要写。
- `words`：来自 `poem --json` 的 `word` 字段，**务必传全**——它们会在绘本里被金色高亮。
- 键名用 `story`（渲染器同时兼容 `tale` 和旧的 `poem`，6 个渲染器都改了）。

**默认渲染**（故事分镜引擎自动配图，见下面「配图」小节）：

```bash
$PY $SKILL/scripts/make_watercolor_svg_book.py \
    --json ~/.workbuddy/ielts-prep/tales/tale-2026-09-13.json \
    --out  ~/.workbuddy/ielts-prep/tales/book-2026-09-13.html \
    --date 2026-09-13
```

- **一定要带 `--date`**：配图台账按日期记账，没日期就没法「跨天不重样」。
- 交付：`present_files` 打开 HTML（自带**英文 / 中文 / 双语切换**和**朗读开关**），
  并把童话正文**贴进回复**（图是给人分享的，文字是给人读的）。
- 出图后会打印一行 `🎬 分镜配图（N 段）：…`，逐段列出「背景 → 主体物(触发词)」，
  这就是自检凭据：**每段的主体物必须和标题/该段内容对得上**。
- 想要 chibi 可爱版就换 `make_watercolor_svg_cute_book.py`——但它的场景是**写死的**
  `city / council / policy / build / school / sky`，**只适合城市/治理题材**；
  童话题材杂，默认走上面那个分镜引擎的。
- 其他版本（`make_picturebook.py` 翻页可点词、`make_doodle_book.py`、`make_comic.py` 连环画、
  `make_poem_poster.py` 单张卡）都能吃这份 JSON。**但童话是散文、段落很长**，
  `make_poem_poster.py` / `make_comic.py` 那套版面是按「一行一句短诗」排的，
  长段会被折成一堆短行，**只在你确实要一张长卡片时用**，且先加 `--no-png` 看 HTML。

#### 配图：每段都必须贴题，且每天都不能一样（用户 2026-09-14 点名要求）

旧的 9 个 `SCENES` 是「整套画好的场景」——通用，但**必然不贴题**（讲钥匙的童话会配上水壶 +
山丘），而且一共只有 9 张，**连着写几天必然重样**。现在换成 `art_storyboard.py` 的**分镜式**拼图：

    plan = {"bg": 背景名, "parts": [主体物…], "why": {主体物: 引出它的那个词}}

- **背景层 17 个**（`dawn/day/night_sky/night_house/room/attic/corridor/street/street_night/
  forest/sea/snow/garden/shop/rain/market/plain`）：只画「在哪里、什么气氛」，由段落里的场景词决定。
- **主体物 59 个**（`key/door/chest/clock/coin/candle/jar/well/wheel/book/person/cat/…`）：
  由**这一段真实出现的词**决定。每个主体物都要能说出它是被哪个词引出来的（`why`），
  **而且那个词确实出现在段/标题/正文里**——回归测试会逐个断言。这就是「贴题」的硬标准。
- 只为好看而加的填充物（云、花）`why` 为空、标 `decor`，不算贴题，也不参与防重。
- **跨天不重样**：`~/.workbuddy/ielts-prep/art-ledger.json` 记下每天用过的**背景**和
  「背景|主体物」组合，最近 3 天的会被主动避开；重出同一天时会先剔除那天的旧记录，不会被自己挡住。
- 封面用「标题 + 全文」排片，所以**标题里的东西一定会上封面**。

调试用：

```bash
# 只看排片结果，不写文件（把每段的「背景 → 主体物(触发词)」打出来）
$PY -c "import importlib.util,json,sys; spec=importlib.util.spec_from_file_location('m','$SKILL/scripts/make_watercolor_svg_book.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); d=json.load(open(sys.argv[1])); ps=[' '.join(s) for s in m.split_stanzas(d['story'])]; print('\n'.join(m.ART.describe(p) for p in m.ART.plan_book(ps, d['title'])))" <tale.json>

# 回退到老的成品场景（只有你要对比时才用）
$PY $SKILL/scripts/make_watercolor_svg_book.py --json <tale.json> --out /tmp/x.html --art scene

# 临时不读台账（测试用，不会污染 art-ledger.json）
$PY $SKILL/scripts/make_watercolor_svg_book.py --json <tale.json> --out /tmp/x.html --no-ledger
```

> 想加主体物：在 `art_storyboard.py` 里写一个 `def d_xxx(x, y, s, ctx)`（`(x, y)` 是**底面中点**，
> 贴地），再在 `PARTS` 里 `_p("xxx", "触发词1 触发词2 …", "ground", d_xxx, 造型高度)`。
> **触发词要写全词形**（`key keys`，不是 `key` 靠词干推），也**绝不写 a/the/he 这种通用词**——
> 否则每段都会瞎命中。缩放不用手调：`h` 给了就按「目标高 232px」自动算。
> 加完跑 `verify_watercolor_book.py`，它会逐个试画所有背景和主体物（专抓 %-占位符数错）。

> ⚠️ 不要再往任何一个渲染器里写死默认译文。曾经在 cute 版里内置过「城市规划」那首诗的 6 段中文，
> 新内容段数一对不上就会**串上城市那套旧译文**——用户抱怨「题材老是城市那一套」，这是原因之一。

### 同一个故事的「卡通连环画」版（用户要卡通/漫画时走这条）

`make_comic.py` 吃**同一份故事 JSON**，把正文按空行切成段，一段一格，画成哆啦 A 梦风格的
**上图下文小人书**（宽 1200 逻辑像素，封面 + N 格 + 词表）。

```bash
$PY $SKILL/scripts/make_comic.py --json /tmp/story.json            # 出 comic-<日期>.html/.png
$PY $SKILL/scripts/make_comic.py --json /tmp/story.json --scenes city,council,policy,build,school,sky
$PY $SKILL/scripts/make_comic.py --json /tmp/story.json --no-png   # 只要 HTML
```

- `poem` 里的 `""` 空行 = 分格；指定 `--scenes` 或 JSON 里给 `panels:[{scene,lines}]` 可自定义。
- 内置场景（都是手写 SVG，viewBox 0 0 1200 400）：
  `city`（车流尾气）、`council`（议会争执 + 10:9 投票）、`policy`（征税/补贴/种树/加宽马路）、
  `build`（太阳能板/河流传感器/公交/商店）、`school`（黑板写词）、`sky`（晴朗市场）、`cover`（封面）。
  新增场景 = 在 `SCENES` 里加一个返回 SVG 字符串的函数。
- 角色是手绘 SVG（`dora()` / `kid()` / `adult()`），不是位图，缩放不糊，改配色改常量即可。
- **同样用 `present_files` 把 PNG 打开**，正文照旧贴进回复。
- ⚠️ `word_forms()` 三个脚本里各有一份，**改一处就要改另一处**（已知坑：以 s/x/z/ch/sh 结尾的
  词要额外补 `-es`，否则 `diminish → diminishes` 高亮不上）。

### 同一个故事的「可交互 HTML 绘本」版（要绘本 / 要给孩子看时走这条）

`make_picturebook.py` 同样吃 poem.json，**再喂一份词表**（`ielts.py poem --json` 的输出）
就能做出一本能翻页、能点词查义的绘本：

```bash
$PY $SKILL/scripts/ielts.py poem --json > /tmp/vocab.json
$PY $SKILL/scripts/make_picturebook.py --json /tmp/story.json --vocab /tmp/vocab.json
```

- 结构：**封面 → 每段一页（上图下文）→ 词汇表页**，共 段数+2 页。
- 交互：左右按钮 / ←→ 方向键 / 底部页码点跳转；翻页是 3D 翻书动画（perspective + rotateY）。
- **动态插画**：每页翻到时才「画出来」——SVG 顶层子元素逐个淡入上浮（JS 按顺序写
  `animationDelay`，CSS 用 `animation-play-state:paused → running` 控制起跑时机，
  翻回来会**重播**）；画面上还叠了飘云、上升颗粒、呼吸光晕（`.fx` 层，不碰 SVG 本身）。
- **语言切换：英文 / 中文 / 双语**（右上角）。中文译文走 `poem_zh`，与 `poem` **行数必须一致**
  （空行分段位置也要对齐），脚本会校验并在不一致时 warn：
  ```bash
  # poem.json 里直接带 poem_zh: [...]
  $PY $SKILL/scripts/make_picturebook.py --json /tmp/story.json --vocab /tmp/vocab.json
  # 或单独一份译文
  $PY $SKILL/scripts/make_picturebook.py --json /tmp/story.json --zh /tmp/story-zh.json --vocab /tmp/vocab.json
  ```
  切换靠 `html[data-lang]` + CSS 显隐，默认「双语」（英文在上，中文小字在下）；
  **中文模式下 `.en` 被隐藏，所以金色可点词只在英文/双语模式下能点**，这是预期行为。
- **正文里每个目标词都可点**，点开底部词条卡显示 词性 / 释义 / 例句；词汇表页带搜索框。
- 每页一条「**观察**」提示（`NOTES` 字典按场景配，也可在 JSON 的 `panels[].note` 里覆盖），
  先让青少年在画面里找线索，再看词——这是绘本相对连环画多出来的教学层。
- 插画仍复用 `make_comic.SCENES`（`from make_comic import SCENES`），**别重复抄一份 SVG**。
- 只出 HTML（默认）。想再要一张封面缩略图就加 `--png`。
- 交付：`present_files` 打开 HTML（会在内置浏览器里直接翻页），
  并在回复里说明「可以点金色单词查意思」、右上角能切英文/中文/双语。
- 踩过的坑（都修了，别改回去）：
  1. `CSS_TMPL` 里的 `%%` 是历史遗留转义，**生成时必须 `.replace("%%","%")` 还原**，
     否则 CSS 里留下 `height:100%%` 这类非法值，浏览器整条规则丢掉（旧产物就这样坏过）；
  2. `out_dir` 必须 `abspath`——`--png` 会用 `file://` 打开，相对路径直接 ERR_INVALID_URL；
  3. 环境动画的位移要用**容器的百分比**（`left`/`bottom`），用 `translateX/Y` 的百分比是相对
     元素自身尺寸，宽度只有 20%% 的云走不完全程；
  4. `.lang button` 要 `white-space:nowrap`，否则窄屏把「英文」拆成两行。

### 同一个故事的「水彩配图动态绘本」版（要**AI 生成的水彩插画**时走这条）

`make_watercolor_book.py` 用**真实的水彩位图**（ImageGen 出的图）做素材，滚动式排版，
和上面两个手写 SVG 的脚本完全不是一条路子——**用户点名要「水彩风 / 精致插画 / 动态效果」时用它**。

```bash
# 1) 先按段落出图（一段一张 + 一张封面），横向 1536x1024、封面竖版 1024x1536
#    prompt 骨架固定为：
#    「精致水彩风格插画，湿画法晕染，可见细腻纸张纹理：<画面>。<配色>，
#      克制优雅，绘本插画，青少年向，纯插画无文字，无边框」
# 2) 压一下，1290KB 一张太重：
sips -s format jpeg -s formatOptions 84 --resampleWidth 1300 x.png --out x.jpg
# 3) 生成绘本（images/cover.* 作封面，其余按文件名排序对应第 1、2… 段）
$PY $SKILL/scripts/make_watercolor_book.py --json /tmp/story.json --images-dir ./images --out ./index.html
```

- 效果：漂动的水彩色斑底 + 纸纹（SVG turbulence）、封面逐字浮现、图片视差 + 缓慢推镜、
  正文行错峰去模糊上浮、**进入视口时金色词依次点亮**、顶部一条水彩进度笔触、右下词高亮开关。
- 已有的课本 wellness：自动把 `-s/-es/-ed/-ing/-ied` 变形也算进高亮
  （这里自带 `forms()`，**和上面三个脚本的 `word_forms()` 是分开的**，别混为一谈）。
- 改样式只改脚本里的 `CSS` 常量；改交互改 `JS` 常量。
- 交付：`present_files` 打开 `index.html`（**HTML 必须和 images/ 目录一起分发**，图片是相对路径）。
- 已知三个坑：
  1. 本机**没有 PIL**，压缩别指望它，用 macOS 自带的 `sips`；
  2. 7 张图原图约 21MB，不压缩本地预览也卡，**务必先压到 ~500KB/张**；
  3. `--out` 换目录也没关系，图片路径会自动算成相对路径（所以 HTML 和 images/ 要一起搬）。

### 同一个故事的「可爱水彩 SVG 绘本」版（要**手画 SVG + 可爱水彩插画 + 三档语言**时走这条）

`make_watercolor_svg_book.py` 和上面的位图绘本**同属水彩风，但插画是手写 SVG**
（feTurbulence 水彩抖动边缘 + 手抖笔触的涂鸦线），**不依赖任何外部图片**；
顶部有 English / 双语 / 中文 三档文字切换，纯自包含单文件。
▼ 2026-09-12 重写：插画从「方块楼 + 火柴人」换成**可爱造型的通用水彩场景**，
每段正文自动配一张贴题的图（不再需要人工指定场景）。

```bash
$PY $SKILL/scripts/make_watercolor_svg_book.py --json /tmp/story.json --out ./book-svg/index.html
# 中文优先读 poem.json 自带的 zh / zh_stanzas / translation；再用 --zh-file 覆盖
# --zh-file 支持 {"1":"...","2":"..."} / {"zh":["段1",...]} / ["段1",...] 三种写法
# --rate 调朗读语速（默认 0.92，比常速慢一点方便跟读；0.5–1.5 之间）
```

- **默认出图 = 故事分镜引擎**（`art_storyboard.py`，见前面「配图」小节）：17 个背景层 + 59 个主体物，
  按每段**真实出现的词**现场拼，所以讲钥匙就出钥匙/门/箱子，讲陶罐就出陶罐/井/水桶，且跨天不重样。
- **备用（`--art scene`）= 9 个成品场景**（画布 1200×900）：`cover`（摊开的书 + 小芽 + 小猫）、
  `dawn`（暖霞朝阳）、`night`（月牙 + 星子 + 亮灯小屋 + 睡猫）、`study`（台灯 + 书 + 冒热气的杯子）、
  `rain`（仰头笑的云 + 雨丝 + 水洼 + 撑伞小孩）、`field`（草地野花大树）、`home`（水壶/杯子/盆栽）、
  `town`（三间小屋 + 街）、`sea`（小船 + 水波 + 沙滩上的猫）。
  每个场景都有**圆润的小角色**（有眼睛/笑弧/腮红）和**会动的部件**。
  这套仍然保留，也可以单独用（`--art scene`），或在 panel 里塞 `"scene": "sea"` 指定。
- **自动选景** `assign_scenes()`（只服务于 `--art scene`）：按每段正文的关键词命中数挑场景
  （`SCENE_HINTS`），同一场景不重复；没命中就按 `ORDER` 补位。
- 积木式生成器（想加场景直接拼）：`face / cloud / star / sparkle / moon / bird / cat /
  sprout / book_open / kettle / mug / lamp / boat / flower / hills / drops / puddle /
  pane / house / kid / tree / sun / mottle`。
  `mottle()` 是「在同一区域撒几团同色系色块」做水彩晕染层次，**必须在主体物之前画**。
- 效果：漂动色斑底 + 纸纹颗粒（`.pgrain`，mix-blend-mode:multiply）、封面逐字浮现、
  段图视差、正文行错峰去模糊上浮、金色词进入视口**依次点亮**；每张段图本身也有动画
  （太阳转、云漂、树/花摇、雨滴落、蒸汽升、小猫浮）。
- **语言切换**：`English` 只显英文、`中文` 只显译文（缺译文的那段自动跳过）、`双语` 上英下中。
- **英文朗读**（Web Speech API，无需音频文件、无需联网）：
  - 两个入口，**都是「点一次开始 / 再点一次停止」的开关**：顶部语言栏的 `🔊 朗读`（全文，
    一段读完自动接下一段）、每段右上角的小圆 `🔊`（只读本段）。朗读中原位变成 `⏹` 并金色脉动。
  - 朗读时**逐词高亮**（`onboundary` 给当前词加 `.speaking`），当前段落也整体提亮。
  - 中文/双语模式下点朗读会**自动切到英文**显示；停止后**还原回原来的语言**。
  - 声音：优先 `en-US` → `en-GB` → 其它 `en`，再加分挑 natural/neural/premium/Siri 等优质音色；
    浏览器不支持语音合成时**按钮自动隐藏**（别留个点了没反应的按钮）。
  - 语速 `--rate`（默认 `0.92`，可 0.5–1.5）。
- 响应式：桌面图文左右交替、≤860px 上下堆叠、≤480px 收紧语言药丸。
  `prefers-reduced-motion` 全关动画。
- 交付：`present_files` 打开 `index.html`（纯单文件，无外部依赖，可直接发、可发到站点）。
- 踩过的坑（都修了，别改回去）：
  1. **`filter` 用 `objectBoundingBox` 会吃掉直线**：`<line>` / `M..V..` / `M..H..` 的包围盒
     宽或高为 0 → 滤镜区域退化成 0×0 → **整条线被裁掉**。症状是太阳光芒、花茎、书页字行、
     灯杆统统消失。修法：`#rough` 改成 `filterUnits="userSpaceOnUse"` + 一块覆盖画布的区域。
  2. **`place-items:center` 会让网格子项按 max-content 撑宽**，窄屏上封面标题会溢出被裁。
     只留 `align-items:center`，水平居中交给 `text-align`。
  3. 重绘正文不要 `box.innerHTML=...` 直接拼（`.copy` 里还有序号 `<span class="num">`），
     正文写在 `.copy > .lines` 里；中文用 `textContent`，否则标点会被正则转义出反斜杠。
  4. 手写 `%` 格式化路径时占位符极易数错（`hills` / `book_open` 都踩过），
     多段贝塞尔一律用 `curve([(x,y),...])` 拼，别手数。
  5. 无头 Chrome 有 **500px 最小窗口宽度**，想验窄屏别只把 `--window-size` 调小，
     那只会把截图裁掉；用 `<iframe width="360">` 套一层才准。
  6. **`JS` 这个字符串必须是普通字符串 `"""`，不能写成 `r"""`**。写成 raw 之后 Python
     会把 `\\b` 原样吐成 `\\\\b`，JS 侧 `\b` 就变成「字面反斜杠 + b」——正则一个词都匹配不上、
     `esc()` 退化成空操作，**金色词高亮整体静默消失**（页面照常打开，不报任何错，极难发现）。
     代价是普通字符串里正则反斜杠要写双份（`\\s` / `\\b`），否则 Python 3.12+ 会报 SyntaxWarning。
  7. **`speechSynthesis.cancel()` 会给当前这条 utterance 抛 `canceled`（或 `onend`）**，
     而朗读是靠回调递归「念下一句」的 → 点了「停止」还会接着念下去。修法：`narrGen` 代次令牌，
     `stopNarration()` / `startNarration()` 里都 `narrGen++`，每个回调开头先
     `if(!narrating || g !== narrGen) return;`，并忽略 `error === 'canceled' | 'interrupted'`。
  8. **「朗读」按钮和语言按钮同在一个 `.lang` 容器里**：语言切换千万别绑 `.lang button`，
     要点名 `.lang button[data-mode]`。否则点一次「朗读」就把 `mode` 覆盖成 `undefined`，
     双语会同时显示、`ensureEnVisible`（中文模式下先切英文）也彻底失效。
     同理 `ensureEnVisible` 直接看 DOM（有没有 `.copy p.en`）比判 `mode === 'zh'` 稳。
- 改样式改 `CSS`、改动画改 `@keyframes`、改画改 `SCENES` 里的场景函数。
- 改完**跑一遍回归**：`$PY $SKILL/scripts/verify_watercolor_book.py`（见文末「维护」）。

### 同一个故事的「可爱 chibi 造型水彩 SVG 绘本」版（要**圆头圆脑 + 马卡龙色 + 故事配图**时走这条）

`make_watercolor_svg_cute_book.py` 和上面的水彩 SVG 绘本**共用同一套引擎**（CSS、动画、
语言切换、金色词高亮、响应式），但插画换成更 Q 的 chibi 水彩风：大圆脑袋、小身子、
腮红笑脸、漂浮小爱心；场景也按这个故事的情节定制——`cover` / `city` / `council` /
`policy` / `build` / `school` / `sky`。

```bash
$PY $SKILL/scripts/make_watercolor_svg_cute_book.py --json /tmp/story.json --out ./book-cute/index.html
# 换中文译文：--zh-file zh.json（{"1":"...",...} / {"zh":["...",...]} / ["...",...]）
# 朗读语速：--rate（默认 0.92）
```

- 每段正文**自动匹配故事场景**：`assign_cute_scenes()` 按关键词命中数挑选，优先映射到
  城市清晨、议会、政策、建设、学校、天空；没命中就按 `ORDER_CUTE` 补位。
- 场景里是马卡龙色块 + 软棕描边 + `feTurbulence` 水彩抖动；太阳会转、树叶会摇、
  人会轻轻上下浮动、小爱心会飘。
- 语言切换、响应式、金色词高亮、进度条、词汇云、**英文朗读（点一次开始 / 再点一次停止）
  + 逐词高亮**与 `make_watercolor_svg_book.py` 完全一致（共用 `build_html`，改主文件即同步生效）。
- 纯单文件，无外部依赖。

### 同一个故事的「手写 SVG 水彩涂鸦动态绘本」（要**矢量水彩 + 三语**时走这条）

`make_doodle_book.py` 不出位图、也不复用 `make_comic` 的卡通场景，而是**用几何生成器现场画 SVG**：
抖动顶点 + Catmull-Rom 转贝塞尔 = 每一笔都手抖，叠两三层半透明色 = 水彩积色，再叠一层深一点的
边缘描边 = 颜料堆积。放大不糊、体积极小（6 段 50 词约 420KB，**零外部依赖**）。

```bash
$PY $SKILL/scripts/make_doodle_book.py --json /tmp/story-bi.json --vocab /tmp/vocab.json \
    --out ./index.html
# 也可以换场景顺序：--scenes city,road,market,...
```

输入 JSON 用**分段 + 双语**结构（比旧 `poem` 行数组更好用，脚本仍兼容旧格式）：

```json
{"title":"...", "title_zh":"...", "subtitle":"...", "subtitle_zh":"...", "words":[...],
 "stanzas":[{"scene":"city", "caption_en":"...", "caption_zh":"...",
             "lines":[{"en":"...","zh":"..."}, ...]}]}
```

- **三种语言**（右上角切换，默认双语）：`English` / `中文` / `双语`。双语是英文在上、中文小字在下；
  中文模式下英文行整行隐藏（所以金色词只在英文/双语下可见）。选择记进 localStorage，
  也支持 **`#en` / `#zh` / `#bi` 深链**直接分享指定语言。
- **动态效果**（纯 CSS，无 JS 定时器）：水彩色斑漂移、烟/雾升腾、云飘、树摇、太阳呼吸、
  光束闪烁、尘埃上浮、落叶、屋檐滴水、公交行驶、浮标点头、秒针走、串灯闪烁、纸飞机飞过、
  正文行错峰去模糊上浮、图片视差、**进视口时金色词依次点亮**、顶部水彩进度笔触。
  `prefers-reduced-motion` 下全部关闭。
- 7 个内置场景：`cover` `city` `council` `road` `rooftop` `school` `market`。
  新增场景 = 往 `SCENES` 加一个函数返回 SVG 字符串。
- 交付：`present_files` 打开 `index.html`（单文件自包含，可以直接发给人看）。
- 踩过的坑（都修了，别改回去）：
  1. **顶点太少的矩形必须先 `densify()` 补点**，否则 Catmull-Rom 把楼、桌子、马路揉成胶囊；
  2. **CSS `transform` 会覆盖 SVG 的 `transform` 属性**——同一个 `<g>` 上既有 `transform="translate()"`
     又有带动画的 class，元素会飞回原点。定位放外层 `<g>`、动画放内层 `<g>`；
  3. 旋转动画的 `transform-origin`：**竖线的 bbox 宽度是 0**，`transform-box:fill-box` 会转飞，
     秒针这类要用 `transform-box:view-box` + `--ox/--oy` 显式给 viewBox 坐标；
  4. 三语切换的 CSS 要**成对写**（`x .t-en{display:none}` 和 `x .t-zh{display:block}` 一起），
     漏一半就会出现"中文模式还挂着英文大标题"；
  5. headless Chrome 有 **500px 最小视口**，`--window-size=430` 截出来的图其实是被裁的 500px 宽，
     别拿它判断窄屏有没有溢出（用 `--dump-dom` 打印 `scrollWidth` 才算数）。

## 例句：卡片上的语境（缺例句由 AI 先补，再出卡）

卡片正面会显示该词的例句。但词库里 **10000 词只有 298 条手工例句**，
`10-bank-*`（ECDICT 自动生成那 9702 个）**全都没有例句**。

**所以「缺例句就用 AI 现造」不是一个可选动作，而是出卡前的硬闸：**

```bash
$PY $SKILL/scripts/ielts.py quiz          # 本轮有词缺例句 → 列出清单，退出码 2，不出卡
$PY $SKILL/scripts/ielts.py quiz --json   # 同上，输出 {"needs_examples":[{word,meaning,pos},...], "html":null}
```

**标准流程（照着做，用户永远看不到占位）：**

1. 跑 `quiz`。若本轮缺例句，它会打印「本轮 N 张里有 M 个词还没有例句，先给它们造句」并 **exit 2**；
   这**不是报错**，是本轮的正常下一步。
2. 你**自己给每个词造一句雅思场景句**（8–16 词，教育 / 环境 / 科技 / 社会 / 职场经济 / 健康，
   让词义能从语境猜出来；别写 "This is a good word."），一次写进去：
   ```bash
   $PY $SKILL/scripts/ielts.py example --json '{"zealous":"She is zealous about protecting the coastal wetlands.","curb":"New rules aim to curb plastic waste."}'
   # 也可以：example --set "词=句子"  /  example --file 例句.tsv（每行 词<TAB>句子）
   ```
3. **重跑 `quiz`**——这次会 exit 0 并生成卡片，例句已经在卡面上。然后照常 `present_files` 打开。

其它：

```bash
$PY $SKILL/scripts/ielts.py example --missing             # 只看本轮缺哪些（只读，不拦）
$PY $SKILL/scripts/ielts.py example --missing --queue     # 看本批剩余全部（提前批量把例句备好）
$PY $SKILL/scripts/ielts.py quiz --allow-missing          # 逃生门：确实想先出卡（卡面显示虚线占位）
```

规则：
- 例句存在 `~/.workbuddy/ielts-prep/examples.tsv`，**你写进去的永远优先于词库自带的**；
  已学过的词也会跟着更新（`get_word()` 每次都会套用这份缓存）。
- 造句要求：**一句 8–16 词的雅思场景句**，让词义能从语境里猜出来。
- 别一次扫全库补例句（`example --missing --all` 只是看看），**只补用户这一轮要背的词**，一轮 10 条封顶。
- `example --missing` 是只读的，放心跑，它不会把整库灌进 `state.json`。
- 反向模式（`--mode cn`）下，**卡片会自动把例句里的目标词遮成 `______`**，
  遮不住（不规则变形等）就整句不显示。这是刻意设计，别去「修好」它。
- 只有在你用 `--allow-missing` 时才会出现 `.egnone` 虚线占位（上面写着「这个词还没例句」）。

## 触发 B：每日 7 点推送当日任务

```bash
$PY $SKILL/scripts/ielts.py today
```

把输出改写成一条清爽的晨间消息：倒计时 → 单词量（到期复习 / 强化池 / 新词额度）→
今日听说读写训练（脚本按周一至周日自动轮换）→ 一句提示「回复『开始背单词』开始」。
**不要**把 JSON 原样丢给用户。

## 触发 C：每周日进度报告

```bash
$PY $SKILL/scripts/ielts.py report
```

生成自包含 HTML（内联 SVG 图表，无外部依赖），路径在 `~/.workbuddy/ielts-prep/reports/`。
必须用 `present_files` 打开它，并在回复里补 3 句话：本周最大亮点、最大问题、下周唯一要改的一件事。
用户问「我的进度怎么样」时，用 `stats --days 30 --json` + `show_widget` 出一张进度图。

## 触发 D：记录训练

用户报告做了听力/阅读/写作/口语练习时：
`$PY $SKILL/scripts/ielts.py task --skill listening|reading|writing|speaking|vocab|mock|review --name "剑桥17 T1S1" --minutes 30`

## 触发 E：初次使用 / 调整参数

```bash
$PY $SKILL/scripts/ielts.py init --daily-new 50 --target 7.0 --exam-date 2026-12-12
```
首次使用先问目标分和考试日期，再 init。**默认每日 50 个单词**（`daily_new=50`，
一批也是 50 张），一轮 10 张。
调小/调大：`init --daily-new N`（只改档案参数，**不清进度**）。

---

## 记忆机制（不要自己另发明一套）

| 事件 | 处理 |
|---|---|
| 答对 | stage +1，间隔 1→2→4→7→15→30→60 天（艾宾浩斯） |
| 答对到 stage 8 | 毕业，移出复习循环，计入「已掌握」 |
| 模糊 | stage 不变，1 天后重考，进强化池（答对 1 次放行） |
| 答错 | stage −2，当天重考，进强化池（需连续答对 2 次） |
| 累计错 ≥5 | 标记为顽固词，用助记法单独攻克 |

- **新词不重复**：每个词从 `new_queue` 弹出一次即进入 `words`，永不回到新词池。
- **强化池**：跨天保留，第二天优先出，清空前不罢休。
- 细读 `references/ebbinghaus.md` 可看完整调度表与调参建议。

## 词库：10000 词

`data/words/*.tsv`，分隔符 `|`，字段：
`word | phonetic | pos | meaning | example | topic`

| 分片 | 数量 | 来源 | 特点 |
|---|---|---|---|
| `01-`~`09-*.tsv` | 299 | 手工编写 | 核心动词/形容词/学术名词 + 教育、科技、环境、社会、职场经济、健康文化 8 大话题，**几乎全部带例句** |
| `10-bank-01`~`10-bank-20` | 9701 | ECDICT 自动筛选 | 按雅思相关度分层，按词频排序，**没有例句** |

例句只有 298 条（手工那批）。补例句走 `example` 子命令写进
`~/.workbuddy/ielts-prep/examples.tsv`，见上文「例句」一节。

### 难度梯度（重要）

`10-bank-01` → `10-bank-20` 是**由易到难**排列的，`ielts.py` 按文件顺序分 50 词一块局部打散后发牌。
所以用户先遇到的是 `anticipate / incorporate / fluctuate` 这类高频学术词，
`10-bank-20` 里那些低频派生词（unmemorable、overlarge 之类）要练到很后面才会出现。

分层依据：T0 ECDICT 标了 ielts → T1 考研/六级/托福 → T2 柯林斯 3 星以上 → T3 GRE → T4 其余。
同时剔除了功能词、数字、代词、人名地名、纯屈折形式，以及牛津 3000 里最常用的那些（早就认识的词）。

### 重新生成 / 扩充

```bash
$PY $SKILL/scripts/build_bank.py --csv /tmp/ecdict.csv --target 10000 --keep 10
```
- `--target` 总词量、`--keep 10` 保留前 10 个手工文件、`--max-freq` 控制生僻上限（默认 20000）
- 可重复执行；已学进度不受影响，新词会追加进队列末尾
- 词典下载：`curl -sL -o /tmp/ecdict.csv https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv`

补充自己的词表：`$PY $SKILL/scripts/ielts.py import --file 我的词表.csv`

- 行格式与词库一致：`词|音标|词性|释义[|例句|话题]`（分隔符 `|`、Tab 或逗号都能认，至少 4 列）。
- 自动去重（已在词库/已学过/文件内重复的跳过）；导入的词写进 `~/.workbuddy/ielts-prep/custom-words/`，
  **这份目录也是词库**，`load_bank()` 会和 `data/words/` 一起读，所以导入的词有完整词条、能正常出卡。
  （不要再往 `state.json` 的 `words` 里塞空记录——那样 `due_review_ids()` 读 `status` 会崩、
  卡片也是空的；`import` 现在只把 id 追加进 `new_queue`。）

## 维护：改完答题卡模板后跑回归

```bash
NODE=/Users/nelson/.workbuddy/binaries/node/versions/22.22.2-3/bin/node
"$NODE" $SKILL/scripts/verify_quiz_card.js                       # 默认测 assets/sample-quiz-card.html
"$NODE" $SKILL/scripts/verify_quiz_card.js <某张生成的卡片.html>    # 也可测真实卡片
"$NODE" $SKILL/scripts/verify_quiz_card.js <卡片.html> /tmp/rcpt.txt /tmp/expect.json
```

它用最小 DOM 桩**真实执行卡片里的 JS**（会解析渲染出的 `<input>` / `<button>`、模拟输入与点击），
断言约 **43 项（word）/ 48 项（cn）**（10 张示例；含「缺例句占位卡」的样本为 44 项），
全部按 `DATA.cards.length` 自适应：正面不泄露答案、
**卡片上只有「忘了」这一个按钮、没有任何判对错的痕迹**、输入框可编辑、
输入后底栏进度自动刷新、**卡片不做回执预览**、**点「忘了」自动填答案并跳下一张**、
**「复制回执」现取全部输入框的内容**、改了输入框回执跟着变、空的记「未作答」、回车跳下一张、
**卡面带例句**、**cn 模式下例句里的答案被遮成 `______`**（含 `maskWord` 的
原形/-s/-ed/-ing/不规则形式、以及「遮不住就返回 null 不显示」这些边界）。
自动识别 `word` / `cn` 两种模式。退出码非 0 就是有回归。
**样本至少 4 张**（少于 4 张会打印提示并以退出码 2 跳过，那不算回归失败）。

给了后两个参数时，还会把回执和期望答案落盘，可以再喂给 Python 侧做跨语言一致性校验：

```bash
"$PY" -c "import importlib.util,json,os;
spec=importlib.util.spec_from_file_location('ielts',os.path.expanduser('$SKILL/scripts/ielts.py'));
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);
print(m.parse_raw_answers(open('/tmp/rcpt.txt',encoding='utf-8').read())==json.load(open('/tmp/expect.json')))"
```

改动卡片模板后重出示例（10 张，与 `per_round` 对齐）：

```bash
$PY $SKILL/scripts/make_sample_card.py                    # 默认 10 张 word 模式
$PY $SKILL/scripts/make_sample_card.py --n 3 --mode cn
$PY $SKILL/scripts/make_sample_card.py --n 5 --with-missing   # 留一张没例句的，看虚线占位长啥样
```

## 维护：改完可爱水彩绘本后跑回归

```bash
$PY $SKILL/scripts/verify_watercolor_book.py     # 四段全跑，约十几秒（C 段要 Chrome）
$PY $SKILL/scripts/verify_watercolor_book.py --no-browser   # 只跑静态 + 分镜 + JS 语法，秒出
```

共 **164 项断言**（A 静态 / A2 分镜 / B node / C Chrome 真机）：

- **A 段（纯 Python，静态）**：9 个场景都能渲染、每个场景里至少有一张带脸的小角色、
  每个场景不含 `None`/`nan`（百分号格式化数错占位符的典型症状）、
  `#rough` 必须是 `userSpaceOnUse` + 固定尺寸区域（不然太阳光芒/花茎/书页字行会被 0×0 的滤镜区域整条裁掉）、
  太阳 12 道光、花 6 瓣 + 1 叶 + 竖直花茎、书 = 封皮 + 两页 + 字行且只有一个动画组、
  `hills` 层数 = 输入层数、`mottle` 撒够团数、6 组关键词选景、场景不重复 + 未命中按 ORDER 补位、
  HTML 含三档语言按钮 / `.lines` 容器 / `.pgrain` 纸纹 / 四种动画类 / IntersectionObserver /
  `prefers-reduced-motion` / 窄屏媒体查询、插画数 = 封面 + 段数、JS 占位符全替换、中文走 `textContent`、
  `.hero` 规则里没有 `place-items:center`；
  以及朗读相关的静态项：按钮数量与 `data-start/data-stop/.btxt/aria-pressed` 齐全、
  `narrGen` 代次令牌、`g !== narrGen` 守卫、忽略 `canceled/interrupted`、
  `render(narrPrevMode || mode)` 复原高亮、`.lang button[data-mode]` 只绑语言按钮、
  `--rate` 能注入；
  **童话契约**：本文件认 `story`/`tale` 键（旧 `poem` 仍兼容）、chibi 版同样认 `story`、
  且 chibi 版**不得**再内置硬编码译文（`DEFAULT_ZH = {` 一出现就报错，那正是「串上城市那套中文」的源头）。
- **A2 段（故事分镜，2026-09-14 加）**：17 个背景层 + 59 个主体物**逐个试画**
  （专抓手写 `%` 占位符数错——`bell/loaf/teapot/nest/violin/chest` 都中过）、
  `hits()` 必须按**单词**匹配（传字符串会被拆成字符 → 整篇配图乱套，踩过）、
  触发词里不许有 `a/the/he` 这类通用虚词、
  **贴题**：每段每个主体物都要有非空 `why` 且那个词真在段/标题/正文里，装饰物不许有 `why`；
  换题材必须换主体物（钥匙篇配 `key/door`、陶罐篇配 `jar/well`，且两篇几乎不重叠）；
  一篇之内组合不重样；**跨天防重**：同一篇童话第二天重排，`背景|主体物` 组合全部换掉；
  台账读写（写在临时目录，绝不碰真实 `ielts-prep` 数据）；封面必须包含标题里的主体物；
  老的 9 个成品场景仍可用（`--art scene`）；`build_html(art_fn=…)` 能整体切成故事分镜。
- **B 段（node）**：`new Function(js)` 语法能编译；**真跑一遍生成的正则**，验证 `esc('a.b') === 'a\\.b'`、
  `re.source` 以 `\b` 开头、样例句能命中 ≥3 个金色词。**这段专治「`JS` 被误改成 `r"""`」**。
- **C 段（Chrome，真机行为）**：在页面里塞一个假 `speechSynthesis`，然后**真点按钮**：
  点一次要真发声（≥1）、语速是注入的 0.92、用 en 声音；**再点一次必须 `cancel()` 且此后 0 次发声**
  （这条是「代次令牌」的看门狗）；停止后 `.word` 金色高亮复原、`.wd` 外壳清掉；
  单段按钮同样能开能关；**中文模式下点朗读会自动切英文、停止后还原回中文**；全程 0 个 JS 报错。

> 桩件必须用 `Object.defineProperty(window, 'speechSynthesis', {...})` 遮蔽：
> `speechSynthesis` 是 `Window.prototype` 上的只读 getter，直接赋值会被**静默忽略**，
> 于是页面调到真合成器、报 `parameter 1 is not of type 'SpeechSynthesisUtterance'`，
> 量出来的「0 次发声」全是假的。桩件里 `speak()` 要**同步**记一笔，
> 所以「点击前」的基线必须在 `click()` **之前**取，否则增量恒为 0；
> 每句的 `onend` 延迟给 **250ms**，太快的话短段落会在你点「停止」之前就自然读完，
> 第二次点击变成「重新开始」，测不出 toggle 语义。

退出码非 0 就是有回归。

改了插画想**肉眼看效果**，生成一张九宫格接触印相图最快：

```bash
$PY - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location('m', '$SKILL/scripts/make_watercolor_svg_book.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cards = "".join('<figure><div class="bx">%s</div><figcaption>%s</figcaption></figure>' % (m.svg(k), k)
                for k in m.SCENES)
open('/tmp/sheet.html','w',encoding='utf-8').write(
  '<!DOCTYPE html><meta charset="utf-8"><style>body{margin:0;background:#efe7d6}'
  '.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:14px}'
  '.bx{aspect-ratio:4/3}.bx svg{width:100%%;height:100%%}'
  'figure{margin:0;background:#fffaf0;border-radius:10px;overflow:hidden}'
  'figcaption{text-align:center;font:600 15px sans-serif;padding:6px}'
  '.pgrain{mix-blend-mode:multiply;opacity:.55}'
  '.wx-float,.wx-sway,.wx-spin,.wx-rain,.wx{animation:none!important}</style>'
  '<div class="grid">%s</div>' % cards)
EOF
# 然后两趟无头截图（先 --dump-dom 读高度，再按高度 --screenshot）
```

⚠️ 想验**窄屏**别只把 `--window-size` 调小——无头 Chrome 有 **500px 最小窗口宽度**，
调小只会把截图裁掉、看着像溢出。用 `<iframe width="360" src="...">` 套一层才准。

张数相关：**每天 50 张**（`profile.session_size`，一批=一天）、`profile.daily_new`（新词额度，同为 50）；
**每轮 10 张**（`profile.per_round`，临时改一次用 `quiz --per N`）。
`load_state()` 里有个一次性 `migrate()`，只动「历史上从没被改过」的旧默认值：
`per_round == 3` → 10（`session.per_round` 一起升，进行中的会话下一轮就生效）；
`daily_new == 30` → 50、`session_size == 20` → 50。用户自己设过的值不会被覆盖。
`init --daily-new N` 会把 `session_size` 一起设成 N（每天任务量就是一个概念）。

## 维护：改了童话题材台账 / 渲染器后自检

`tale_index.py` 只读 `tales/` + `poems/` + 内置题材池，不会写任何东西，可以放心跑：

```bash
$PY $SKILL/scripts/tale_index.py                     # 列台账（空库会提示「这会是第一篇童话」）
$PY $SKILL/scripts/tale_index.py --suggest -n 3      # 从池子里推荐没用过的题材
$PY $SKILL/scripts/tale_index.py --check "已用过的标题" --theme "已用过的题材"   # 必须退出码 2
$PY $SKILL/scripts/tale_index.py --json              # 机读
```

判重口径（改之前先想清楚，别把唯一能挡重复的东西改松了）：
标题/题材/主角**归一化后完全相同** → 撞车（退出码 2）；
一方是另一方的**子串**，或 2-gram **Jaccard ≥ 0.45** → 只警告。
`LEGACY_THEMES` 里手工登记了散文诗时代用过的题材（城市清晨、城市规划/议会/税收/政策/学校），
**别删**——删了第一篇小说就会又写回城市那套（用户就是这么抱怨的）。

改了任何一个渲染器之后，拿一篇真童话把整条链路跑一遍（每篇都能吃同一份 JSON）：

```bash
T=$HOME/.workbuddy/ielts-prep/tales/tale-2026-09-13.json
$PY $SKILL/scripts/make_watercolor_svg_book.py --json $T --out /tmp/t.html          # 默认交付物
$PY $SKILL/scripts/make_watercolor_svg_cute_book.py --json $T --out /tmp/c.html
$PY $SKILL/scripts/make_poem_poster.py  --json $T --out /tmp --name t --no-png      # 退出码应为 0
$PY $SKILL/scripts/make_comic.py        --json $T --out /tmp --name t --no-png      # 退出码应为 0
$PY $SKILL/scripts/make_picturebook.py  --json $T --vocab /tmp/vocab.json --out /tmp --name t
$PY $SKILL/scripts/make_doodle_book.py  --json $T --out /tmp/t-doodle.html
```

改完绘本的插画/样式/JS 还要再跑 `verify_watercolor_book.py`（四段 164 项，见上一节）。

## 注意

- 状态文件是唯一事实来源，禁止手写编辑 `state.json`。
- 🛑 **绝对不要对真实数据目录执行 `reset`**。用户可能已经有几十上百个已学单词，
  清掉就找不回来了。真要重置必须先征得用户明确同意，且 reset 本身就带二次确认闸
  （有进度时必须再加 `--force`），被拦住是**预期行为**，不要绕过。
- `build_bank.py`、`report`、`today`、`quiz` 都是非破坏性的，可以放心跑；
  `quiz` 只生成卡片、不推进 `idx`、不写 `words`（只有 `--mode` 会更新
  `profile.ask_mode`）。真正改进度的是 `submit` / `grade`。
- `reset --yes` 会整体清空进度（会自动留一份 `state.json.bak-<时间戳>` 备份）；
  换词库后重跑 `init` 不会清进度，**只有 reset 会**。
- `10-bank-*` 是生成物，别手改；要改就改筛选规则重跑 `build_bank.py`。
- 自动生成的词条**没有例句**（ECDICT 无此字段）。`quiz` 出卡前会**自动拦下**缺例句的轮次
  （退出码 2），让 AI 先用 `example --json` 造句再重跑，所以正常流程不会露出占位
  （见「例句」一节）。真要先出卡才用 `quiz --allow-missing`。
- 示例文件：`assets/sample-weekly-report.html`（周报，示意数据）、
  `assets/sample-quiz-card.html`（答题卡，真实结构，由 `make_sample_card.py` 生成）。
  两者都不参与运行，只作样子。
- `examples.tsv` 是**学习者自己的数据**，跟 `state.json` 一样别删；
  它只影响卡片上显示哪句例句，删了不会丢进度，但造过的句子就没了。
- `poem` 是**只读**的（不会动进度）；写童话渲染只往 `~/.workbuddy/ielts-prep/tales/` 里放文件。
  童话正文 JSON 用 `story` 键（一段一行、`""` 分段），`zh` 放中文（一段一条）；
  旧的 `poems/*.json` 和 `poem` 键仍然能读，别删。
  `make_poem_poster.py` 依赖本机 Chrome 做无头截图（两趟：量高 → 截屏）。
  它支持 `--json-out`（返回 `{html,png,size,note}`，便于脚本取值）和 `--no-png`
  （**`--no-png` 的退出码是 0**，那是「只出 HTML」不是失败）。
- 写完童话**必须**跑 `tale_index.py --check`：标题 / 题材 / 主角任一与历史撞车都会退出码 2
  （「很像」只警告）。这个是用户点名的「每天要不同」，别跳过。
- **配图也有自己的台账**：`~/.workbuddy/ielts-prep/art-ledger.json`（记每天用过的背景 +
  「背景|主体物」组合，最近 3 天自动避开）。它是**生成物**，可以删（删了就从「没有配图历史」
  重新开始，配图仍会贴题，只是可能和前两天重样）。重出同一天时 `--date` 会自动剔除那天的旧记录。
- 童话渲染的**默认**是分镜引擎（`art_storyboard.py`）；`--art scene` 才回到老的 9 个成品场景。
  改分镜画法/触发词后，除了跑 `verify_watercolor_book.py`，最好**肉眼看一遍**：
  用 `m.ART.plan_book(...)` 打出排片表，再按上面「生成一张接触印相图」的方法把新造型铺开看。
- 卡片模板改动后：先重出示例卡 → 跑 `verify_quiz_card.js` → 再交付；
  改了 `make_poem_poster.py` 的版式后，用 `/tmp` 里的样例 JSON 渲染一张，**亲眼看一遍**再收工。
- 周报 HTML 为浅色主题、内联 SVG，可直接双击打开或分享。
