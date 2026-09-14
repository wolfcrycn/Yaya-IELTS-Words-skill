#!/usr/bin/env bash
# 把本机技能目录的内容同步到本仓库，并提交。
# 用法：
#   tools/sync-from-skill.sh "更新说明"        # 同步 + 提交
#   tools/sync-from-skill.sh "更新说明" --push # 同步 + 提交 + 推送
#
# 源（唯一事实来源）：~/.workbuddy/skills/丫丫雅思单词
# 目标：本仓库根目录（README / LICENSE / .gitignore / tools 由本仓库自己维护，不会被删除）

set -euo pipefail

SRC="${SKILL_SRC:-$HOME/.workbuddy/skills/丫丫雅思单词}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MSG="${1:-chore: 同步技能目录}"
DO_PUSH="${2:-}"

if [ ! -d "$SRC" ]; then
  echo "✗ 找不到技能目录：$SRC（可用 SKILL_SRC=... 指定）" >&2
  exit 1
fi

echo "→ 同步  $SRC"
echo "      → $REPO"

# 只同步技能本体的四块，剔除缓存与 macOS 垃圾文件
cd "$SRC"
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
    -cf - SKILL.md assets data references scripts | (cd "$REPO" && tar -xf -)

cd "$REPO"
git add -A
if git diff --cached --quiet; then
  echo "· 没有变化，跳过提交"
else
  git commit -m "$MSG"
  echo "✓ 已提交：$(git log -1 --format='%h %s')"
fi

if [ "$DO_PUSH" = "--push" ]; then
  git push
  echo "✓ 已推送"
fi
