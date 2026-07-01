#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署到 GitHub Pages
"""

import json
import requests
import time
import base64

# 你的 GitHub 信息
# Token 从环境变量读取，避免硬编码
import os
USERNAME = os.environ.get("GH_USERNAME", "meldevorah")
TOKEN = os.environ.get("GH_TOKEN", "")
REPO_NAME = "bookkeeping-app"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# 1. 创建仓库
print("正在创建仓库...")
repo_data = {
    "name": REPO_NAME,
    "description": "Simple bookkeeping app",
    "public": True,
    "auto_init": True
}

response = requests.post(
    "https://api.github.com/user/repos",
    headers=headers,
    json=repo_data
)

if response.status_code == 201:
    print(f"[OK] 仓库创建成功: {REPO_NAME}")
elif response.status_code == 422:
    print("[!] 仓库已存在，继续...")
else:
    print(f"[ERROR] 创建失败: {response.status_code}")
    print(response.text)
    exit(1)

# 等待仓库初始化
print("\n等待仓库初始化...")
time.sleep(3)

# 2. 获取文件内容（用于获取 sha，如果文件已存在）
print("\n正在上传 index.html...")
get_response = requests.get(
    f"https://api.github.com/repos/{USERNAME}/{REPO_NAME}/contents/index.html",
    headers=headers
)

# 读取本地文件
with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Base64 编码
content_encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

# 准备上传数据
file_data = {
    "message": "Add bookkeeping app",
    "content": content_encoded,
    "branch": "main"
}

# 如果文件已存在，需要添加 sha
if get_response.status_code == 200:
    file_data["sha"] = get_response.json()["sha"]
    print("[!] 文件已存在，将更新...")

# 上传文件
response = requests.put(
    f"https://api.github.com/repos/{USERNAME}/{REPO_NAME}/contents/index.html",
    headers=headers,
    json=file_data
)

if response.status_code in [200, 201]:
    print("[OK] 文件上传成功")
else:
    print(f"[ERROR] 上传失败: {response.status_code}")
    print(response.text)
    exit(1)

# 3. 启用 GitHub Pages
print("\n正在启用 GitHub Pages...")
time.sleep(2)

pages_data = {
    "source": {
        "branch": "main",
        "path": "/"
    }
}

response = requests.post(
    f"https://api.github.com/repos/{USERNAME}/{REPO_NAME}/pages",
    headers=headers,
    json=pages_data
)

if response.status_code == 201:
    print("[OK] GitHub Pages 已启用")
elif response.status_code == 400 and "already" in response.text.lower():
    print("[!] GitHub Pages 已启用")
else:
    print(f"[!] Pages 状态: {response.status_code}")
    print(response.text)

print("\n" + "="*50)
print("部署完成！")
print(f"访问地址: https://{USERNAME}.github.io/{REPO_NAME}")
print("="*50)
print("\n注意：GitHub Pages 需要 1-2 分钟生效，请稍后访问")
