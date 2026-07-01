#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记账小程序 - 核心逻辑
支持多用户、批量录入、分类统计、导出备份
"""

import sqlite3
import json
import re
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "bookkeeping.db"

# ──────────────────────────────────────────
# 数据库初始化
# ──────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    # 创建默认用户
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=? AND password=?",
                   (username, password))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_id(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def change_password(user_id, new_password):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO records (date, type, category, amount, description, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (date, type_, category, amount, description, user_id)
    )
    conn.commit()
    conn.close()

def add_records_batch(records, user_id=1):
    """批量添加记录，records 为 dict 列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data = [(r['date'], r['type'], r['category'], r['amount'], r.get('description', ''), user_id)
            for r in records]
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id=?", (id_,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def get_records(limit=200, user_id=1):
    conn = sqlite3.connect(DB_PATH)
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

def get_record(id_):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, type, category, amount, description, created_at "
        "FROM records WHERE id=?", (id_,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(['id', 'date', 'type', 'category', 'amount', 'description', 'created_at'], row))

# ──────────────────────────────────────────
# 文字解析（支持批量多行）
# ──────────────────────────────────────────
INCOME_KEYWORDS = ['工资', '收入', '奖金', '报销', '退款', '兼职', '分红']
CATEGORIES = {
    '餐饮': ['午餐', '晚餐', '早餐', '外卖', '餐厅', '咖啡', '奶茶', '零食', '买菜'],
    '交通': ['打车', '地铁', '公交', '加油', '停车', '打车费', '高铁', '火车', '飞机'],
    '购物': ['淘宝', '京东', '网购', '买', '超市', '衣服', '日用品'],
    '娱乐': ['电影', '游戏', '音乐', '视频', '会员', '健身', '旅游'],
    '生活': ['水电', '物业', '话费', '网费', '房租', '快递'],
    '医疗': ['药店', '医院', '体检', '门诊', '药'],
    '工资': ['工资', '薪水', '月奖'],
}

def parse_text_input(text):
    """
    解析文字输入，支持批量（多行，每行一条记录）。
    返回 dict 列表，每条含 date/type/category/amount/description。
    如果解析失败返回 None。
    """
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
            'date': date,
            'type': type_,
            'category': category,
            'amount': amount,
            'description': line
        })

    return results if results else None

# ──────────────────────────────────────────
# 统计
# ──────────────────────────────────────────
def get_summary(month=None, user_id=1):
    conn = sqlite3.connect(DB_PATH)
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
    """各分类支出/收入汇总"""
    conn = sqlite3.connect(DB_PATH)
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
    expense = []
    income = []
    for type_, cat, total in rows:
        item = {'category': cat, 'amount': total}
        if type_ == 'expense':
            expense.append(item)
        else:
            income.append(item)
    return {'expense': expense, 'income': income}

def get_monthly_summary(user_id=1):
    """各月收支汇总"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT strftime('%Y-%m', date) AS month, type, SUM(amount) "
        "FROM records WHERE user_id=? GROUP BY month, type ORDER BY month DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    # 整理成 {month: {income, expense}}
    data = {}
    for month, type_, amount in rows:
        if month not in data:
            data[month] = {'income': 0, 'expense': 0, 'balance': 0}
        data[month][type_] = amount
        data[month]['balance'] = data[month]['income'] - data[month]['expense']
    return data

def get_yearly_summary(year=None, user_id=1):
    """年度各月收支汇总"""
    if year is None:
        year = datetime.now().year
    conn = sqlite3.connect(DB_PATH)
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

# ──────────────────────────────────────────
# 导出 / 备份
# ──────────────────────────────────────────
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

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成")
