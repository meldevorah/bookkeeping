# 记账小程序

简单记账工具，支持文字输入、手动录入，支出一览和修改删除。

## 本地运行

```bash
pip install streamlit
streamlit run streamlit_app.py
```

## 部署到云端

使用 Streamlit Cloud：

1. fork 本仓库
2. 去 [share.streamlit.io](https://share.streamlit.io) 用 GitHub 登录
3. 选择 `meldevorah/bookkeeping`，入口文件选 `streamlit_app.py`

## 自动同步本地改动到 GitHub

```powershell
# 1. 设置 GitHub Token 环境变量（永久生效）
[Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "你的PAT", "User")

# 2. 启动自动同步（会自动检测文件变化并推送）
python auto_sync.py
```

> 注意：`.db` 数据库文件和 `__pycache__` 不会同步到 GitHub。

## 目录结构

```
bookkeeping/
├── app.py              # 核心数据库逻辑
├── streamlit_app.py    # Web 界面
├── bookkeeping.db      # SQLite 数据库（本地，不上传）
├── auto_sync.py        # 自动同步脚本
├── deploy.py           # 部署相关
├── server.py           # 服务端入口
├── requirements.txt    # Python 依赖
└── README.md
```
