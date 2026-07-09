#!/usr/bin/env python3
import io
import os
import sys
import time
import subprocess
from datetime import datetime

# 解决 Windows 重定向 stdout 时 GBK 无法编码 emoji 的问题
if sys.stdout.encoding and sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'cp936'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() in ('gbk', 'gb2312', 'cp936'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

INSTRUCTION_FILE = "0_决策层/当前指令_待发.md"
CHECK_INTERVAL = 2
EXEC_TIMEOUT = 300
LOG_FILE = "trigger.log"
WORK_FILE = "2_ClaudeCode/工作成果.md"

# Agent 命令配置（每个 Agent 独立定义命令和参数）
AGENT_CONFIG = {
    "claude": {
        "cmd": "E:/npm-global/claude.cmd",
        "args": ["--dangerously-skip-permissions", "-p"],
    },
    "codex": {
        "cmd": "C:/Users/21828/AppData/Roaming/npm/codex.cmd",
        "args": ["exec", "--skip-git-repo-check"],
    },
}
DEFAULT_AGENT = "claude"

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

def ensure_file():
    if not os.path.exists(INSTRUCTION_FILE):
        os.makedirs(os.path.dirname(INSTRUCTION_FILE), exist_ok=True)
        with open(INSTRUCTION_FILE, "w", encoding="utf-8") as f:
            f.write("# 请在此写入策划指令\n")
        log("⚠️ 已创建指令文件")

def run_loop():
    log("🚀 trigger.py 启动")
    log(f"📂 监听文件: {INSTRUCTION_FILE}")
    ensure_file()
    last = get_mtime(INSTRUCTION_FILE)
    log("✅ 等待指令更新...")

    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            cur = get_mtime(INSTRUCTION_FILE)
            if cur != last:
                last = cur
                try:
                    with open(INSTRUCTION_FILE, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    if not lines or not "".join(lines).strip():
                        log("⚠️ 指令文件为空，跳过执行")
                        continue

                    # 解析第一行确定目标 Agent
                    first_line = lines[0].strip()
                    agent = DEFAULT_AGENT
                    if "[Codex]" in first_line:
                        agent = "codex"
                    elif "[Claude]" in first_line:
                        agent = "claude"

                    agent_cfg = AGENT_CONFIG[agent]
                    instruction_content = "".join(lines).strip()
                    log(f"📝 检测到指令更新，启动{agent.capitalize()}...")

                    result = subprocess.run(
                        [agent_cfg["cmd"]] + agent_cfg["args"] + [instruction_content],
                        capture_output=True,
                        encoding="utf-8", errors="replace",
                        timeout=EXEC_TIMEOUT,
                        env=os.environ
                    )
                    if result.returncode == 0:
                        log(f"✅ {agent.capitalize()}执行完成")
                        with open(WORK_FILE, "w", encoding="utf-8") as f:
                            f.write(result.stdout)
                    else:
                        log(f"❌ {agent.capitalize()}执行失败，退出码: {result.returncode}")
                        with open(WORK_FILE, "w", encoding="utf-8") as f:
                            f.write(f"=== 执行摘要 ===\n状态：失败\n关键输出：{result.stderr}\n文件变更：无\n建议下一步：检查错误后重试\n")
                except subprocess.TimeoutExpired:
                    log("⏰ 执行超时")
                except Exception as e:
                    log(f"❌ 异常: {e}")
    except KeyboardInterrupt:
        log("🛑 已停止")

if __name__ == "__main__":
    run_loop()
