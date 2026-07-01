#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动同步脚本：监控 bookkeeping 目录文件变化，自动 git commit + push 到 GitHub

使用方法:
1. 设置环境变量 GITHUB_TOKEN=你的PAT
2. 运行: python auto_sync.py
"""

import os
import subprocess
import time
from pathlib import Path

REPO_DIR = Path(__file__).parent
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REMOTE = f"https://meldevorah:{TOKEN}@github.com/meldevorah/bookkeeping.git"

if not TOKEN:
    print("❌ 错误：请先设置环境变量 GITHUB_TOKEN")
    print('   Windows PowerShell: $env:GITHUB_TOKEN="你的PAT"')
    print('   然后重新运行: python auto_sync.py')
    exit(1)

GITIGNORE_PATH = REPO_DIR / ".gitignore"
IGNORE_PATTERNS = {"__pycache__", ".git", ".gitignore", "auto_sync.py", "*.db", "*.pyc"}


def get_changed_files():
    """返回自上次检查以来有变动的文件列表（不含 .db 等忽略项）"""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if result.returncode != 0:
        return []

    changed = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.strip().split(" ", 1)
        if len(parts) < 2:
            continue
        fname = parts[1].strip()
        if any(pat in fname or fname.endswith(pat.replace("*", ""))
               for pat in IGNORE_PATTERNS):
            continue
        changed.append(fname)
    return changed


def do_sync():
    changed = get_changed_files()
    if not changed:
        return

    # git add .
    subprocess.run(["git", "-C", str(REPO_DIR), "add", "."],
                   capture_output=True)

    # git commit
    msg = f"sync: {'; '.join(changed[:5])}" + (" ..." if len(changed) > 5 else "")
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "commit", "-m", msg],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if result.returncode != 0:
        return

    # git push
    push_result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "push", REMOTE, "main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if push_result.returncode == 0:
        print(f"[sync] ✅ pushed: {msg}")
    else:
        print(f"[sync] ❌ push failed")


if __name__ == "__main__":
    print(f"🚀 Auto-sync started, watching: {REPO_DIR}")
    print("📌 Press Ctrl+C to stop\n")
    while True:
        do_sync()
        time.sleep(10)
