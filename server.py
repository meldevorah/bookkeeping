#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记账小程序 - Flask 服务器
"""

from flask import Flask, render_template, jsonify, request
from pathlib import Path
import sys

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app import init_db, add_record, parse_text_input, get_summary, get_records

app = Flask(__name__, template_folder='templates')

# 初始化数据库
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/records')
def api_records():
    """获取记录和统计"""
    records = get_records(50)
    summary = get_summary()
    
    return jsonify({
        'records': records,
        'summary': summary
    })

@app.route('/api/parse', methods=['POST'])
def api_parse():
    """解析文字输入并添加记录"""
    data = request.json
    text = data.get('text', '')
    
    result = parse_text_input(text)
    if result:
        add_record(
            result['date'],
            result['type'],
            result['category'],
            result['amount'],
            result['description']
        )
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '无法解析输入'})

@app.route('/api/add', methods=['POST'])
def api_add():
    """手动添加记录"""
    data = request.json
    
    try:
        add_record(
            data['date'],
            data['type'],
            data['category'],
            data['amount'],
            data.get('description', '')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print(f"记账小程序已启动！端口: {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port)
