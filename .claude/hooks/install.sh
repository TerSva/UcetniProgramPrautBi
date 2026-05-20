#!/bin/bash
# PRAUT git hooks installer
#
# Aktivuje hooky z .claude/hooks/ jako symlinky v .git/hooks/.
# Spustit po klonu repa:
#     bash .claude/hooks/install.sh

set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "❌ Nejsem v git repu."
    exit 1
fi

HOOKS_DIR="$REPO_ROOT/.git/hooks"
SOURCE_DIR="$REPO_ROOT/.claude/hooks"

mkdir -p "$HOOKS_DIR"

# post-commit
ln -sf "$SOURCE_DIR/post-commit" "$HOOKS_DIR/post-commit"
chmod +x "$SOURCE_DIR/post-commit"

echo "✅ Git hooks aktivovány:"
echo "   $HOOKS_DIR/post-commit → $SOURCE_DIR/post-commit"
echo ""
echo "Po každém git commitu se automaticky:"
echo "   1. Spustí .claude/hooks/update_kontext.py"
echo "   2. Aktualizuje PRAUT_kontext.md (auto sekce)"
echo "   3. Pokud se kontext změnil, amend do commitu"
