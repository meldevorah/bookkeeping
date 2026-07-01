#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的记账小程序
支持文字输入和截图OCR识别
"""

import sqlite3
from datetime import datetime
import re
import os
from pathlib import Path

# 创建数据库
DB_PATH = Path(__file__).parent / "bookkeeping.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,  -- 'income' or 'expense'
            category TEXT,
            amount REAL NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_record(date, type_, category, amount, description):
    """添加记账记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO records (date, type, category, amount, description) VALUES (?, ?, ?, ?, ?)",
        (date, type_, category, amount, description)
    )
    conn.commit()
    conn.close()

def parse_text_input(text):
    """
    解析文字输入
    格式示例：
    - "午餐 35" -> 支出 餐饮 35
    - "工资 8000" -> 收入 工资 8000
    - "7月1日 打车 28" -> 支出 交通 28
    """
    # 尝试提取金额
    amount_match = re.search(r'(\d+\.?\d*)', text)
    if not amount_match:
        return None
    
    amount = float(amount_match.group(1))
    
    # 判断类型（收入/支出）
    income_keywords = ['工资', '收入', '奖金', '报销', '退款', '兼职']
    type_ = 'income' if any(kw in text for kw in income_keywords) else 'expense'
    
    # 提取类别
    categories = {
        '餐饮': ['午餐', '晚餐', '早餐', '外卖', '餐厅', '咖啡', '奶茶'],
        '交通': ['打车', '地铁', '公交', '加油', '停车'],
        '购物': ['淘宝', '京东', '网购', '买'],
        '娱乐': ['电影', '游戏', '音乐', '视频'],
        '生活': ['水电', '物业', '话费', '网费'],
        '医疗': ['药店', '医院', '体检'],
    }
    
    category = '其他'
    for cat, keywords in categories.items():
        if any(kw in text for kw in keywords):
            category = cat
            break
    
    # 提取日期
    date_match = re.search(r'(\d+)月(\d+)日', text)
    if date_match:
        month, day = date_match.groups()
        date = f"{datetime.now().year}-{month.zfill(2)}-{day.zfill(2)}"
    else:
        date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        'date': date,
        'type': type_,
        'category': category,
        'amount': amount,
        'description': text
    }

def get_summary(month=None):
    """获取统计摘要"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if month:
        cursor.execute("""
            SELECT type, SUM(amount) 
            FROM records 
            WHERE date LIKE ?
            GROUP BY type
        """, (f"{month}%",))
    else:
        cursor.execute("""
            SELECT type, SUM(amount) 
            FROM records 
            GROUP BY type
        """)
    
    results = dict(cursor.fetchall())
    conn.close()
    
    return {
        'income': results.get('income', 0),
        'expense': results.get('expense', 0),
        'balance': results.get('income', 0) - results.get('expense', 0)
    }

def update_record(id_, date, type_, category, amount, description):
    """更新指定记录"""
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
    """删除指定记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id=?", (id_,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def get_record(id_):
    """根据ID获取单条记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, type, category, amount, description, created_at FROM records WHERE id=?",
        (id_,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    columns = ['id', 'date', 'type', 'category', 'amount', 'description', 'created_at']
    return dict(zip(columns, row))

def get_records(limit=50):
    """获取最近记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date, type, category, amount, description, created_at
        FROM records
        ORDER BY date DESC, created_at DESC
        LIMIT ?
    """, (limit,))
    
    columns = ['id', 'date', 'type', 'category', 'amount', 'description', 'created_at']
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    
    return results

def analyze_screenshot(image_path):
    """
    分析截图（占位函数）
    实际使用时需要集成 OCR 服务
    """
    # TODO: 集成 OCR API
    # 可以调用百度OCR、腾讯OCR等
    return {
        'amount': 0,
        'type': 'expense',
        'category': '其他',
        'description': '截图待识别'
    }

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成")
