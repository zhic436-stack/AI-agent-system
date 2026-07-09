#!/bin/bash
# 启动决策层 — 自动加载 0_决策层/【只读】永久记忆.md 作为系统提示词
#
# 方式一（推荐）：已在 ~/.deepseek/config.toml 中配置 Memory 自动加载
#   直接运行 deepseek 即可自动注入系统提示词
#
# 方式二（手动传参）：如果 Memory 未生效，使用本脚本显式加载
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_FILE="$SCRIPT_DIR/0_决策层/【只读】永久记忆.md"

echo "📂 加载决策层提示词: $MEMORY_FILE"
echo "═══════════════════════════════════════════"
cat "$MEMORY_FILE"
echo ""
echo "═══════════════════════════════════════════"
echo ""

deepseek --system "$(cat "$MEMORY_FILE")"
