#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记账小程序 - 完整版（单文件部署版）
移动端友好：登录保护 / 批量录入 / 分类统计 / 月度年度总结 / 导出备份
所有核心逻辑内联，无外部模块依赖
"""

import sqlite3
import json
import re
import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# ──────────────────────────────────────────
# 配置：数据库路径（部署环境兼容）
# ──────────────────────────────────────────
# Streamlit Cloud 上 /mount/data 是持久化目录；本地用脚本同目录
try:
    DB_DIR = Path("/mount/data")
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DB_DIR / "bookkeeping.db"
except Exception:
    DB_PATH = Path(__file__).parent / "bookkeeping.db"

# ──────────────────────────────────────────
# 数据库初始化
# ──────────────────────────────────────────
def _table_has_column(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT,
            amount REAL NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    # 迁移：旧表缺 user_id 列则添加
    if not _table_has_column(cursor, "records", "user_id"):
        cursor.execute("ALTER TABLE records ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        conn.commit()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                       ("admin", "123456"))
        conn.commit()
    conn.close()

# ──────────────────────────────────────────
# 用户认证
# ──────────────────────────────────────────
def verify_user(username, password):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=? AND password=?",
                   (username, password))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def change_password(user_id, new_password):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password=? WHERE id=?",
                   (new_password, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

# ──────────────────────────────────────────
# 记录增删改查
# ──────────────────────────────────────────
def add_record(date, type_, category, amount, description, user_id=1):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO records (date, type, category, amount, description, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (date, type_, category, amount, description, user_id)
    )
    conn.commit()
    conn.close()

def add_records_batch(records, user_id=1):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    data = [(r['date'], r['type'], r['category'], r['amount'],
             r.get('description', ''), user_id) for r in records]
    cursor.executemany(
        "INSERT INTO records (date, type, category, amount, description, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        data
    )
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count

def update_record(id_, date, type_, category, amount, description):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE records SET date=?, type=?, category=?, amount=?, description=? WHERE id=?",
        (date, type_, category, amount, description, id_)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def delete_record(id_):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id=?", (id_,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def get_records(limit=200, user_id=1):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, type, category, amount, description, created_at "
        "FROM records WHERE user_id=? ORDER BY date DESC, created_at DESC LIMIT ?",
        (user_id, limit)
    )
    columns = ['id', 'date', 'type', 'category', 'amount', 'description', 'created_at']
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return results

# ──────────────────────────────────────────
# 文字解析（支持批量多行）
# ──────────────────────────────────────────
INCOME_KEYWORDS = ['工资', '收入', '奖金', '报销', '退款', '兼职', '分红']
CATEGORIES = {
    '餐饮': ['午餐', '晚餐', '早餐', '外卖', '餐厅', '咖啡', '奶茶', '零食', '买菜'],
    '交通': ['打车', '地铁', '公交', '加油', '停车', '高铁', '火车', '飞机'],
    '购物': ['淘宝', '京东', '网购', '衣服', '日用品', '超市'],
    '娱乐': ['电影', '游戏', '音乐', '视频', '会员', '健身', '旅游'],
    '生活': ['水电', '物业', '话费', '网费', '房租', '快递'],
    '医疗': ['药店', '医院', '体检', '门诊', '药'],
    '工资': ['工资', '薪水', '月奖'],
}

def parse_text_input(text):
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if not lines:
        return None
    results = []
    for line in lines:
        amount_match = re.search(r'(\d+\.?\d*)', line)
        if not amount_match:
            continue
        amount = float(amount_match.group(1))
        type_ = 'income' if any(kw in line for kw in INCOME_KEYWORDS) else 'expense'
        category = '其他'
        for cat, keywords in CATEGORIES.items():
            if any(kw in line for kw in keywords):
                category = cat
                break
        date_match = re.search(r'(\d{1,2})月(\d{1,2})日', line)
        if date_match:
            month, day = date_match.groups()
            date = f"{datetime.now().year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            date = datetime.now().strftime("%Y-%m-%d")
        results.append({
            'date': date, 'type': type_, 'category': category,
            'amount': amount, 'description': line
        })
    return results if results else None

# ──────────────────────────────────────────
# 统计
# ──────────────────────────────────────────
def get_summary(month=None, user_id=1):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    if month:
        cursor.execute(
            "SELECT type, SUM(amount) FROM records WHERE date LIKE ? AND user_id=? GROUP BY type",
            (f"{month}%", user_id)
        )
    else:
        cursor.execute(
            "SELECT type, SUM(amount) FROM records WHERE user_id=? GROUP BY type",
            (user_id,)
        )
    results = dict(cursor.fetchall())
    conn.close()
    return {
        'income': results.get('income', 0),
        'expense': results.get('expense', 0),
        'balance': results.get('income', 0) - results.get('expense', 0)
    }

def get_category_summary(month=None, user_id=1):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    if month:
        cursor.execute(
            "SELECT type, category, SUM(amount) FROM records "
            "WHERE date LIKE ? AND user_id=? GROUP BY type, category ORDER BY SUM(amount) DESC",
            (f"{month}%", user_id)
        )
    else:
        cursor.execute(
            "SELECT type, category, SUM(amount) FROM records "
            "WHERE user_id=? GROUP BY type, category ORDER BY SUM(amount) DESC",
            (user_id,)
        )
    rows = cursor.fetchall()
    conn.close()
    expense, income = [], []
    for type_, cat, total in rows:
        item = {'category': cat, 'amount': total}
        if type_ == 'expense':
            expense.append(item)
        else:
            income.append(item)
    return {'expense': expense, 'income': income}

def get_yearly_summary(year=None, user_id=1):
    if year is None:
        year = datetime.now().year
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT strftime('%m', date) AS month, type, SUM(amount) "
        "FROM records WHERE user_id=? AND date LIKE ? "
        "GROUP BY month, type ORDER BY month",
        (user_id, f"{year}%")
    )
    rows = cursor.fetchall()
    conn.close()
    months = {str(m).zfill(2): {'income': 0, 'expense': 0} for m in range(1, 13)}
    for month, type_, amount in rows:
        months[month][type_] = amount
    return {'year': year, 'months': months}

def export_to_json(user_id=1):
    records = get_records(limit=10000, user_id=user_id)
    summary = get_summary(user_id=user_id)
    cat_summary = get_category_summary(user_id=user_id)
    return {
        'exported_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'summary': summary,
        'category_breakdown': cat_summary,
        'records': records
    }

# ══════════════════════════════════════════
# Streamlit UI
# ══════════════════════════════════════════
st.set_page_config(page_title="💰 记账", page_icon="💰", layout="centered")

init_db()

# Session state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = None

def logout():
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = None

# 登录页
if not st.session_state["logged_in"]:
    st.title("💰 记账")
    st.caption("请先登录")
    with st.form("login_form", clear_on_submit=True):
        username = st.text_input("用户名", placeholder="默认：admin")
        password = st.text_input("密码", type="password", placeholder="默认：123456")
        submitted = st.form_submit_button("登录", use_container_width=True)
        if submitted:
            uid = verify_user(username or "admin", password or "123456")
            if uid:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = uid
                st.session_state["username"] = username or "admin"
                st.rerun()
            else:
                st.error("用户名或密码错误")
    st.caption("忘记密码请重新初始化数据库")
    st.stop()

uid = st.session_state["user_id"]
username = st.session_state["username"]
st.title(f"💰 {username} 的账本")

col_header1, col_header2 = st.columns(2)
with col_header1:
    if st.button("🚪 退出登录", use_container_width=True):
        logout()
        st.rerun()
with col_header2:
    with st.popover("🔑 修改密码"):
        old_pw = st.text_input("当前密码", type="password", key="old_pw")
        new_pw = st.text_input("新密码", type="password", key="new_pw")
        new_pw2 = st.text_input("再次输入新密码", type="password", key="new_pw2")
        if st.button("确认修改", key="change_pw_btn"):
            if new_pw != new_pw2:
                st.error("两次密码不一致")
            elif len(new_pw) < 4:
                st.error("密码长度至少4位")
            elif verify_user(username, old_pw) and change_password(uid, new_pw):
                st.success("密码修改成功！")
            else:
                st.error("当前密码错误或修改失败")

tab1, tab2, tab3 = st.tabs(["📝 记账", "📊 月度总结", "📅 年度总结"])

# Tab 1：记账
with tab1:
    summary = get_summary(user_id=uid)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("总收入", f"¥{summary['income']:.2f}")
    with c2:
        st.metric("总支出", f"¥{summary['expense']:.2f}")
    with c3:
        st.metric("结余", f"¥{summary['balance']:.2f}",
                  delta_color="normal" if summary['balance'] >= 0 else "inverse")

    st.divider()
    st.subheader("➕ 添加记录")

    input_method = st.radio(
        "输入方式",
        ["📝 批量文字（支持多行）", "✏️ 手动输入"],
        captions=["一次输入多条，如：午餐 35", "单条详细录入"],
        label_visibility="collapsed", horizontal=True
    )

    if input_method.startswith("📝"):
        with st.container(border=True):
            text_input = st.text_area(
                "输入内容（每行一条）",
                placeholder="示例：\n午餐 35\n打车 28\n工资 8000\n7月3日 咖啡 32",
                height=120, key="batch_text"
            )
            col_parse, col_hint = st.columns([1, 3])
            with col_parse:
                if st.button("✅ 批量添加", use_container_width=True, key="batch_add"):
                    if text_input.strip():
                        results = parse_text_input(text_input)
                        if results:
                            count = add_records_batch(results, user_id=uid)
                            st.success(f"✅ 成功添加 {count} 条记录！")
                            st.rerun()
                        else:
                            st.error("无法解析，请检查格式（金额必须为数字）")
            with col_hint:
                st.caption("每行格式：描述 + 空格 + 金额，如「午餐 35」")
    else:
        with st.container(border=True):
            m1, m2 = st.columns(2)
            with m1:
                date = st.date_input("日期", datetime.now(), key="add_date")
                type_ = st.selectbox(
                    "类型", ["expense", "income"],
                    format_func=lambda x: "📉 支出" if x == "expense" else "📈 收入",
                    key="add_type"
                )
            with m2:
                category = st.selectbox(
                    "类别",
                    ["餐饮", "交通", "购物", "娱乐", "生活", "医疗", "工资", "其他"],
                    key="add_cat"
                )
                amount = st.number_input("金额", min_value=0.01, step=0.01,
                                         key="add_amt", label_visibility="visible")
            description = st.text_input("备注（可选）", key="add_desc")
            if st.button("✅ 添加记录", use_container_width=True, key="add_manual"):
                if amount > 0:
                    add_record(date.strftime("%Y-%m-%d"), type_, category, amount, description, user_id=uid)
                    st.success(f"已添加：{category} {amount:.2f}元")
                    st.rerun()

    st.divider()

    if "editing_id" not in st.session_state:
        st.session_state["editing_id"] = None
    if "deleting_id" not in st.session_state:
        st.session_state["deleting_id"] = None

    st.subheader("📋 记录列表")
    records = get_records(limit=100, user_id=uid)

    if records:
        for rec in records:
            rec_id = rec["id"]
            is_income = rec["type"] == "income"

            if st.session_state.get("deleting_id") == rec_id:
                st.warning(f"⚠️ 确认删除？{rec['date']} {rec['category']} ¥{rec['amount']:.2f}")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("✅ 确认删除", key=f"conf_del_{rec_id}", type="primary"):
                        delete_record(rec_id)
                        st.session_state["deleting_id"] = None
                        st.rerun()
                with dc2:
                    if st.button("❌ 取消", key=f"cancel_del_{rec_id}"):
                        st.session_state["deleting_id"] = None
                        st.rerun()
                st.divider()
                continue

            if st.session_state.get("editing_id") == rec_id:
                st.markdown("**✏️ 编辑记录**")
                default_date = datetime.strptime(rec["date"], "%Y-%m-%d").date()
                ALL_CATS = ["餐饮", "交通", "购物", "娱乐", "生活", "医疗", "工资", "其他"]
                cat_idx = ALL_CATS.index(rec["category"]) if rec["category"] in ALL_CATS else 7

                ce1, ce2 = st.columns(2)
                with ce1:
                    edit_date = st.date_input("日期", default_date, key=f"edit_date_{rec_id}")
                    edit_type = st.selectbox(
                        "类型", ["expense", "income"],
                        index=["expense", "income"].index(rec["type"]),
                        format_func=lambda x: "📉 支出" if x == "expense" else "📈 收入",
                        key=f"edit_type_{rec_id}"
                    )
                with ce2:
                    edit_cat = st.selectbox("类别", ALL_CATS, index=cat_idx, key=f"edit_cat_{rec_id}")
                    edit_amt = st.number_input("金额", value=float(rec["amount"]),
                                               min_value=0.01, step=0.01,
                                               key=f"edit_amt_{rec_id}", label_visibility="visible")
                edit_desc = st.text_input("备注", value=rec["description"] or "",
                                          key=f"edit_desc_{rec_id}", label_visibility="visible")

                es1, es2 = st.columns(2)
                with es1:
                    if st.button("💾 保存", key=f"save_{rec_id}", type="primary", use_container_width=True):
                        update_record(rec_id, edit_date.strftime("%Y-%m-%d"), edit_type,
                                      edit_cat, edit_amt, edit_desc)
                        st.session_state["editing_id"] = None
                        st.success("已保存")
                        st.rerun()
                with es2:
                    if st.button("❌ 取消", key=f"cancel_{rec_id}", use_container_width=True):
                        st.session_state["editing_id"] = None
                        st.rerun()
                st.divider()
                continue

            col_info, col_amt, col_btn = st.columns([3, 1, 2])
            with col_info:
                type_label = "📈 收入" if is_income else "📉 支出"
                st.markdown(f"**{type_label}** {rec['description'] or rec['category']}")
                st.caption(f"{rec['date']} · {rec['category']}")
            with col_amt:
                amt_color = "#27ae60" if is_income else "#e74c3c"
                st.markdown(
                    f"<span style='color:{amt_color};font-size:18px;font-weight:600'>"
                    f"{'+' if is_income else '-'}{rec['amount']:.2f}</span>",
                    unsafe_allow_html=True
                )
            with col_btn:
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✏️", key=f"edit_{rec_id}", help="编辑"):
                        st.session_state["editing_id"] = rec_id
                        st.rerun()
                with b2:
                    if st.button("🗑️", key=f"del_{rec_id}", help="删除"):
                        st.session_state["deleting_id"] = rec_id
                        st.rerun()
            st.divider()

        data = export_to_json(user_id=uid)
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "📥 导出备份（JSON）",
            data=json_str,
            file_name=f"账本备份_{timestamp}.json",
            mime="application/json",
            use_container_width=True
        )
    else:
        st.info("暂无记录，开始添加吧！")

# Tab 2：月度总结
with tab2:
    st.subheader("📊 月度总结")
    all_records = get_records(limit=5000, user_id=uid)
    months_set = sorted(set(r['date'][:7] for r in all_records), reverse=True)
    if not months_set:
        months_set = [datetime.now().strftime("%Y-%m")]

    selected_month = st.selectbox("选择月份", months_set)

    ms = get_summary(month=selected_month, user_id=uid)
    cs = get_category_summary(month=selected_month, user_id=uid)

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("本月收入", f"¥{ms['income']:.2f}")
    with sc2:
        st.metric("本月支出", f"¥{ms['expense']:.2f}")
    with sc3:
        st.metric("本月结余", f"¥{ms['balance']:.2f}",
                  delta_color="normal" if ms['balance'] >= 0 else "inverse")

    if cs['expense']:
        total_exp = sum(e['amount'] for e in cs['expense'])
        st.markdown("**📉 支出分类**")
        for item in cs['expense']:
            pct = item['amount'] / total_exp * 100
            st.markdown(f"{item['category']}  ¥{item['amount']:.2f}  ({pct:.1f}%)")
            st.progress(pct / 100, text="")

    if cs['income']:
        st.markdown("**📈 收入分类**")
        for item in cs['income']:
            st.markdown(f"{item['category']}  ¥{item['amount']:.2f}")

# Tab 3：年度总结
with tab3:
    st.subheader("🏆 年度总结")
    year = st.selectbox(
        "选择年份",
        list(range(datetime.now().year, datetime.now().year - 5, -1))
    )

    ys = get_yearly_summary(year=year, user_id=uid)
    year_income = sum(m['income'] for m in ys['months'].values())
    year_expense = sum(m['expense'] for m in ys['months'].values())
    year_balance = year_income - year_expense

    yc1, yc2, yc3 = st.columns(3)
    with yc1:
        st.metric(f"{year} 年收入", f"¥{year_income:.2f}")
    with yc2:
        st.metric(f"{year} 年支出", f"¥{year_expense:.2f}")
    with yc3:
        st.metric(f"{year} 年结余", f"¥{year_balance:.2f}",
                  delta_color="normal" if year_balance >= 0 else "inverse")

    st.markdown(f"**📅 {year} 年每月收支**")
    month_names = ["1月","2月","3月","4月","5月","6月",
                   "7月","8月","9月","10月","11月","12月"]
    labels, income_vals, expense_vals = [], [], []
    for m in range(1, 13):
        mm = str(m).zfill(2)
        month_data = ys['months'].get(mm, {'income': 0, 'expense': 0})
        if month_data['income'] > 0 or month_data['expense'] > 0:
            labels.append(month_names[m - 1])
            income_vals.append(month_data['income'])
            expense_vals.append(month_data['expense'])

    if labels:
        try:
            import pandas as pd
            df_chart = pd.DataFrame({
                "月份": labels, "收入": income_vals, "支出": expense_vals
            })
            st.bar_chart(df_chart.set_index("月份"))
        except ImportError:
            # 纯 Streamlit 实现柱状图
            for i, (lbl, inc, exp) in enumerate(zip(labels, income_vals, expense_vals)):
                st.markdown(f"**{lbl}**")
                st.markdown(f"收入 ¥{inc:.2f}　支出 ¥{exp:.2f}")
    else:
        st.info("该年度暂无数据")

    data = export_to_json(user_id=uid)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "📥 导出年度备份（JSON）",
        data=json_str,
        file_name=f"账本_{year}年备份_{timestamp}.json",
        mime="application/json",
        use_container_width=True
    )
