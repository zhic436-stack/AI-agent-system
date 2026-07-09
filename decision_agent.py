#!/usr/bin/env python3
"""
决策层自动轮询脚本
功能：
- 监听 0_决策层/当前任务目标.md 的变化
- 调用 DeepSeek API 拆解任务
- 将执行指令写入 0_决策层/当前指令_待发.md
- 更新 0_决策层/任务进度.md
- 支持循环工作，直到任务完成

使用方法：
    python decision_agent.py
"""

import os
import time
import json
import subprocess
from datetime import datetime
import requests

# ==================== 配置 ====================
TASK_FILE = "0_决策层/当前任务目标.md"
INSTRUCTION_FILE = "0_决策层/当前指令_待发.md"
PROGRESS_FILE = "0_决策层/任务进度.md"
LOG_FILE = "decision_agent.log"
CHECK_INTERVAL = 5  # 轮询间隔（秒）

# 执行层成果文件路径
CODEX_WORK_FILE = "1_Codex/工作成果.md"
CLAUDE_WORK_FILE = "2_ClaudeCode/工作成果.md"

# DeepSeek API 配置（请填写你的 API Key）
DEEPSEEK_API_KEY = "you key"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
# ==============================================

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = f"[{ts}] {msg}"
    print(full)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full + "\n")

def get_mtime(path):
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return 0.0

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return ""

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def call_deepseek(task_content):
    """调用 DeepSeek API 拆解任务"""
    system_prompt = read_file("0_决策层/【只读】永久记忆.md")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
任务目标：
{task_content}

【输出要求】
直接输出可执行的命令，每行一条，不要包含任何分段标签（如 === 任务拆解 ===、=== 执行指令 ===、=== 风险预判 ===、=== 策划文案 ===）。
不要包含任何分析、解释或建议，只输出给执行层的指令文本。

格式示例：
让 Codex 说"原神牛逼"。
让 Claude Code 说"原神牛逼克拉斯"。

不需要指定输出文件路径，执行层已通过各自的永久记忆知道默认输出位置。
"""}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            log(f"API 调用失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log(f"API 调用异常: {e}")
        return None

def call_deepseek_judge(task_target, progress, latest_result):
    """调用 DeepSeek API 判断成果并决定下一步"""
    system_prompt = read_file("0_决策层/【只读】永久记忆.md")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
当前任务目标：
{task_target}

当前任务进度：
{progress}

执行层最新成果：
{latest_result}

请根据以上信息判断任务是否完成。输出格式要求（只输出以下两者之一，不要额外内容）：

如果任务已完成：
状态：已完成

如果任务未完成，需要继续推进：
状态：继续推进
下一步指令：[生成下一步执行指令，格式与最初的任务拆解一致]

注意：
- 不要包含任何分段标签（=== 任务拆解 === 等）
- 不要包含分析、解释或建议
- 只需要输出"状态：已完成"或"状态：继续推进"+"下一步指令"
"""}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            log(f"判断 API 调用失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log(f"判断 API 调用异常: {e}")
        return None

def update_progress(status, current_task, completed, next_step):
    content = f"""状态：{status}
当前子任务：{current_task}
已完成：{completed}
下一步：{next_step}
更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""
    write_file(PROGRESS_FILE, content)

def main():
    log("🚀 决策层自动轮询脚本启动")
    log(f"📂 监听任务文件: {TASK_FILE}")
    log(f"📂 监听成果文件: {CODEX_WORK_FILE}, {CLAUDE_WORK_FILE}")

    last_task_mtime = get_mtime(TASK_FILE)
    last_codex_mtime = get_mtime(CODEX_WORK_FILE)
    last_claude_mtime = get_mtime(CLAUDE_WORK_FILE)

    # 记录已处理的任务内容，防止重复处理
    last_task_content = read_file(TASK_FILE)

    log("✅ 等待新任务或执行层成果...")

    try:
        while True:
            time.sleep(CHECK_INTERVAL)

            # 1. 检查任务文件是否有更新
            current_task_mtime = get_mtime(TASK_FILE)
            if current_task_mtime != last_task_mtime:
                last_task_mtime = current_task_mtime
                task_content = read_file(TASK_FILE)

                if task_content and task_content != last_task_content:
                    last_task_content = task_content
                    log(f"📝 检测到新任务: {task_content[:50]}...")

                    # 更新进度：拆解中
                    update_progress("拆解中", "正在调用决策层分析任务", "无", "等待API响应")

                    # 调用 DeepSeek API
                    log("🧠 调用 DeepSeek API 拆解任务...")
                    instruction = call_deepseek(task_content)

                    if instruction:
                        # 写入指令文件
                        write_file(INSTRUCTION_FILE, instruction)
                        log(f"✅ 已生成执行指令并写入 {INSTRUCTION_FILE}")
                        update_progress("待执行", "任务已拆解，等待执行层处理", "任务拆解完成", "执行层将自动开始工作")
                    else:
                        log("❌ 任务拆解失败，请检查 API Key 或网络")
                        update_progress("拆解失败", "API 调用失败", "无", "请检查日志")

            # 2. 检查 Codex 工作成果是否有更新
            current_codex_mtime = get_mtime(CODEX_WORK_FILE)
            if current_codex_mtime != last_codex_mtime:
                last_codex_mtime = current_codex_mtime
                codex_result = read_file(CODEX_WORK_FILE)
                if codex_result:
                    log(f"📝 检测到 Codex 成果更新，正在评估...")
                    evaluate_progress(codex_result, "Codex")

            # 3. 检查 Claude Code 工作成果是否有更新
            current_claude_mtime = get_mtime(CLAUDE_WORK_FILE)
            if current_claude_mtime != last_claude_mtime:
                last_claude_mtime = current_claude_mtime
                claude_result = read_file(CLAUDE_WORK_FILE)
                if claude_result:
                    log(f"📝 检测到 Claude 成果更新，正在评估...")
                    evaluate_progress(claude_result, "Claude")

    except KeyboardInterrupt:
        log("🛑 收到中断信号，脚本已停止")
        sys.exit(0)

def evaluate_progress(latest_result, source_name):
    """评估执行层成果并决定下一步"""
    task_target = read_file(TASK_FILE)
    progress = read_file(PROGRESS_FILE)

    if not task_target:
        log("⚠️ 没有当前任务目标，跳过评估")
        return

    log(f"🧠 调用 DeepSeek API 评估{source_name}成果...")
    judgment = call_deepseek_judge(task_target, progress, latest_result)

    if not judgment:
        log("❌ 成果评估失败，请检查日志")
        return

    log(f"🔍 {source_name}成果评估结果: {judgment[:100]}...")

    if "状态：已完成" in judgment:
        log(f"✅ 任务已完成！更新进度文件")
        update_progress("已完成", "所有子任务已完成", "全部任务完成", "无")
        # 记录决策日志
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {source_name} 成果评估：任务已完成"
        log_file = "0_决策层/历史决策日志.md"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

    elif "状态：继续推进" in judgment:
        # 提取下一步指令
        next_instruction = judgment.replace("状态：继续推进", "").replace("下一步指令：", "").strip()
        if next_instruction:
            write_file(INSTRUCTION_FILE, next_instruction)
            log(f"✅ 已生成下一步指令并写入 {INSTRUCTION_FILE}")
            update_progress("待执行", "正在推进任务", "部分子任务已完成", "等待执行层处理下一步指令")
            log(f"📝 下一步指令: {next_instruction[:100]}...")
    else:
        log(f"⚠️ 无法识别的评估结果: {judgment[:100]}")

if __name__ == "__main__":
    import sys
    main()