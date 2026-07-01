#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记账小程序 - Streamlit Web 界面
支持增删改查
"""

import sys
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app import (
    init_db, add_record, parse_text_input,
    get_summary, get_records, update_record,
    delete_record, get_record
)
import streamlit as st
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="简单记账",
    page_icon="💰",
    layout="wide"
)

# 初始化数据库
init_db()

# 标题
st.title("💰 简单记账小程序")

# ============ 侧边栏 ============
with st.sidebar:
    st.header("添加记录")

    # 方式1：文字输入
    st.subheader("方式1：文字输入")
    text_input = st.text_area(
        "输入内容（示例：午餐 35、工资 8000）",
        height=100,
        help="自动识别金额、类别",
        key="text_input"
    )

    if st.button("解析并添加", key="parse_text"):
        if text_input:
            result = parse_text_input(text_input)
            if result:
                add_record(
                    result['date'],
                    result['type'],
                    result['category'],
                    result['amount'],
                    result['description']
                )
                st.success(f"已添加：{result['category']} {result['amount']}元")
                st.rerun()
            else:
                st.error("无法解析输入内容")

    st.divider()

    # 方式2：手动输入
    st.subheader("方式2：手动输入")
    date = st.date_input("日期", datetime.now(), key="add_date")
    type_ = st.selectbox(
        "类型",
        ["expense", "income"],
        format_func=lambda x: "支出" if x == "expense" else "收入",
        key="add_type"
    )
    category = st.selectbox(
        "类别",
        ["餐饮", "交通", "购物", "娱乐", "生活", "医疗", "工资", "其他"],
        key="add_category"
    )
    amount = st.number_input("金额", min_value=0.0, step=0.01, key="add_amount")
    description = st.text_input("描述", key="add_desc")

    if st.button("添加记录", key="add_manual"):
        if amount > 0:
            add_record(
                date.strftime("%Y-%m-%d"),
                type_,
                category,
                amount,
                description
            )
            st.success(f"已添加：{category} {amount}元")
            st.rerun()

    st.divider()

    # 方式3：截图上传
    st.subheader("方式3：截图识别")
    uploaded_file = st.file_uploader(
        "上传支付截图",
        type=['png', 'jpg', 'jpeg'],
        help="支持微信/支付宝/银行APP截图",
        key="screenshot"
    )

    if uploaded_file is not None:
        st.image(uploaded_file, caption="上传的截图", use_column_width=True)
        st.info("OCR识别功能需要配置API密钥（见下方说明）")

# ============ 主界面 ============

# 统计卡片
col1, col2, col3 = st.columns(3)
summary = get_summary()

with col1:
    st.metric("总收入", f"¥{summary['income']:.2f}")

with col2:
    st.metric("总支出", f"¥{summary['expense']:.2f}")

with col3:
    balance_color = "normal" if summary['balance'] >= 0 else "inverse"
    st.metric("结余", f"¥{summary['balance']:.2f}")

st.divider()

# ============ 编辑模式 ============
# 初始化 session state
if "editing_id" not in st.session_state:
    st.session_state["editing_id"] = None

if "deleting_id" not in st.session_state:
    st.session_state["deleting_id"] = None

# 通用类别列表
ALL_CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "生活", "医疗", "工资", "其他"]

# 显示记录
st.header("📋 记录列表")

records = get_records(100)

if records:
    for rec in records:
        rec_id = rec["id"]
        is_income = rec["type"] == "income"
        type_label = "📈 收入" if is_income else "📉 支出"
        type_color = "green" if is_income else "red"

        col_label, col_amount, col_cat, col_date, col_actions = st.columns(
            [2, 1, 1, 1, 2]
        )

        with col_label:
            st.markdown(f"**{type_label}** {rec['description'] or rec['category']}")

        with col_amount:
            amount_val = rec["amount"]
            st.markdown(f"<span style='color:{type_color};font-weight:bold'>¥{amount_val:.2f}</span>",
                        unsafe_allow_html=True)

        with col_cat:
            st.caption(rec["category"])

        with col_date:
            st.caption(rec["date"])

        with col_actions:
            # 编辑按钮
            edit_key = f"edit_{rec_id}"
            del_key = f"del_{rec_id}"

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️", key=edit_key, help="编辑"):
                    st.session_state["editing_id"] = rec_id
                    st.rerun()
            with c2:
                if st.button("🗑️", key=del_key, help="删除"):
                    st.session_state["deleting_id"] = rec_id
                    st.rerun()

        # ===== 删除确认 =====
        if st.session_state.get("deleting_id") == rec_id:
            conf_key = f"conf_del_{rec_id}"
            cancel_key = f"cancel_del_{rec_id}"

            warn_col1, warn_col2, warn_col3 = st.columns([1, 2, 1])
            with warn_col2:
                st.warning(f"⚠️ 确认删除这条记录？金额 ¥{rec['amount']}（{rec['date']}）")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ 确认删除", key=conf_key, type="primary"):
                        delete_record(rec_id)
                        st.session_state["deleting_id"] = None
                        st.rerun()
                with cc2:
                    if st.button("❌ 取消", key=cancel_key):
                        st.session_state["deleting_id"] = None
                        st.rerun()

        # ===== 编辑表单 =====
        if st.session_state.get("editing_id") == rec_id:
            with st.container():
                st.markdown("---")
                st.subheader(f"✏️ 编辑记录 #{rec_id}")

                # 回填现有值
                default_date = datetime.strptime(rec["date"], "%Y-%m-%d").date()
                edit_date = st.date_input("日期", default_date, key=f"edit_date_{rec_id}")
                edit_type = st.selectbox(
                    "类型",
                    ["expense", "income"],
                    index=["expense", "income"].index(rec["type"]),
                    format_func=lambda x: "支出" if x == "expense" else "收入",
                    key=f"edit_type_{rec_id}"
                )
                edit_category = st.selectbox(
                    "类别",
                    ALL_CATEGORIES,
                    index=ALL_CATEGORIES.index(rec["category"])
                    if rec["category"] in ALL_CATEGORIES else 7,
                    key=f"edit_cat_{rec_id}"
                )
                edit_amount = st.number_input(
                    "金额",
                    value=float(rec["amount"]),
                    min_value=0.0,
                    step=0.01,
                    key=f"edit_amt_{rec_id}"
                )
                edit_desc = st.text_input(
                    "描述",
                    value=rec["description"] or "",
                    key=f"edit_desc_{rec_id}"
                )

                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("💾 保存修改", key=f"save_{rec_id}", type="primary"):
                        ok = update_record(
                            rec_id,
                            edit_date.strftime("%Y-%m-%d"),
                            edit_type,
                            edit_category,
                            edit_amount,
                            edit_desc
                        )
                        if ok:
                            st.session_state["editing_id"] = None
                            st.success("已保存修改")
                            st.rerun()
                with ec2:
                    if st.button("❌ 取消编辑", key=f"cancel_{rec_id}"):
                        st.session_state["editing_id"] = None
                        st.rerun()

                st.markdown("---")

        st.divider()

else:
    st.info("暂无记录，开始添加吧！")

# ============ 使用说明 ============
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 文字输入格式示例
    - `午餐 35` → 支出/餐饮/35元
    - `打车 28` → 支出/交通/28元
    - `工资 8000` → 收入/工资/8000元
    - `7月1日 咖啡 32` → 指定日期

    ### 编辑和删除
    - 点击每条记录右侧的 ✏️ 按钮可进入编辑模式
    - 点击 🗑️ 按钮会弹出删除确认，确认后删除记录
    """)
