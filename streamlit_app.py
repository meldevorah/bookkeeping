#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记账小程序 - Streamlit Web 界面
移动端友好：输入区固定在页面顶部，记录列表紧随其后
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import (
    init_db, add_record, parse_text_input,
    get_summary, get_records, update_record,
    delete_record
)
import streamlit as st
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="记账",
    page_icon="💰",
    layout="centered"
)

init_db()

st.markdown("""
<style>
    /* 移动端优化 */
    .stTextArea textarea, .stTextInput input {
        font-size: 16px !important;
    }
    .stButton button {
        width: 100%;
    }
    /* 统计卡片行内显示 */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stMetric"] {
        background: #f0f2f6;
        border-radius: 8px;
        padding: 8px;
        text-align: center;
    }
    /* 隐藏多余边距 */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    /* 记录行样式 */
    .record-row {
        background: #ffffff;
        border: 1px solid #e8e8e8;
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .record-type-expense { color: #e74c3c; font-weight: bold; }
    .record-type-income  { color: #27ae60; font-weight: bold; }
    .record-amount-expense { color: #e74c3c; font-size: 18px; font-weight: 600; }
    .record-amount-income  { color: #27ae60; font-size: 18px; font-weight: 600; }
    .record-meta { color: #888; font-size: 12px; }
    .record-desc { font-size: 14px; }
    /* 按钮列 */
    .btn-col { display: flex; gap: 4px; flex-shrink: 0; }
    /* 分割线 */
    hr.section-divider { margin: 8px 0; }
    /* 折叠区块 */
    details > summary { cursor: pointer; font-size: 14px; color: #666; }
</style>
""", unsafe_allow_html=True)

# ============ 顶部标题 ============
st.title("💰 记账")

# ============ 顶部统计 ============
summary = get_summary()
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("收入", f"¥{summary['income']:.2f}")
with c2:
    st.metric("支出", f"¥{summary['expense']:.2f}")
with c3:
    st.metric("结余", f"¥{summary['balance']:.2f}",
              delta_color="normal" if summary['balance'] >= 0 else "inverse")

st.divider()

# ============ 输入区 ============
st.subheader("➕ 添加记录")

with st.expander("📝 文字输入（自动解析）", expanded=True):
    text_input = st.text_area(
        "输入内容",
        placeholder="示例：午餐 35   工资 8000   7月1日 打车 28",
        label_visibility="collapsed",
        key="text_input"
    )
    col_parse_btn, col_parse_hint = st.columns([1, 3])
    with col_parse_btn:
        if st.button("✅ 解析添加", use_container_width=True, key="parse_text"):
            if text_input:
                result = parse_text_input(text_input)
                if result:
                    add_record(result['date'], result['type'], result['category'],
                               result['amount'], result['description'])
                    st.success(f"已添加：{result['category']} {result['amount']:.2f}元")
                    st.rerun()
                else:
                    st.error("无法解析，请检查输入格式")
    with col_parse_hint:
        st.caption("格式：描述 + 空格 + 金额，如「午餐 35」")

with st.expander("✏️ 手动输入"):
    m1, m2 = st.columns(2)
    with m1:
        date = st.date_input("日期", datetime.now(), key="add_date")
        type_ = st.selectbox("类型", ["expense", "income"],
                              index=0,
                              format_func=lambda x: "📉 支出" if x == "expense" else "📈 收入",
                              key="add_type")
    with m2:
        category = st.selectbox("类别",
                                ["餐饮", "交通", "购物", "娱乐", "生活", "医疗", "工资", "其他"],
                                key="add_category")
        amount = st.number_input("金额", min_value=0.0, step=0.01,
                                  key="add_amount", label_visibility="visible")

    description = st.text_input("备注（可选）", key="add_desc", label_visibility="visible")

    if st.button("✅ 添加记录", use_container_width=True, key="add_manual"):
        if amount > 0:
            add_record(date.strftime("%Y-%m-%d"), type_, category, amount, description)
            st.success(f"已添加：{category} {amount:.2f}元")
            st.rerun()
        else:
            st.error("金额需大于0")

st.divider()

# ============ Session state ============
if "editing_id" not in st.session_state:
    st.session_state["editing_id"] = None
if "deleting_id" not in st.session_state:
    st.session_state["deleting_id"] = None

# ============ 记录列表 ============
st.subheader("📋 记录列表")
records = get_records(100)

if records:
    for rec in records:
        rec_id = rec["id"]
        is_income = rec["type"] == "income"
        type_label = "📈 收入" if is_income else "📉 支出"
        type_cls = "income" if is_income else "expense"

        # ----- 删除确认 -----
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

        # ----- 编辑表单 -----
        if st.session_state.get("editing_id") == rec_id:
            st.markdown("#### ✏️ 编辑记录")
            default_date = datetime.strptime(rec["date"], "%Y-%m-%d").date()

            ce1, ce2 = st.columns(2)
            with ce1:
                edit_date = st.date_input("日期", default_date, key=f"edit_date_{rec_id}")
                edit_type = st.selectbox("类型", ["expense", "income"],
                                         index=["expense", "income"].index(rec["type"]),
                                         format_func=lambda x: "📉 支出" if x == "expense" else "📈 收入",
                                         key=f"edit_type_{rec_id}")
            with ce2:
                ALL_CATS = ["餐饮", "交通", "购物", "娱乐", "生活", "医疗", "工资", "其他"]
                cat_idx = ALL_CATS.index(rec["category"]) if rec["category"] in ALL_CATS else 7
                edit_category = st.selectbox("类别", ALL_CATS, index=cat_idx,
                                             key=f"edit_cat_{rec_id}")
                edit_amount = st.number_input("金额", value=float(rec["amount"]),
                                              min_value=0.0, step=0.01,
                                              key=f"edit_amt_{rec_id}", label_visibility="visible")

            edit_desc = st.text_input("备注", value=rec["description"] or "",
                                       key=f"edit_desc_{rec_id}", label_visibility="visible")

            es1, es2 = st.columns(2)
            with es1:
                if st.button("💾 保存", key=f"save_{rec_id}", type="primary", use_container_width=True):
                    update_record(rec_id, edit_date.strftime("%Y-%m-%d"), edit_type,
                                  edit_category, edit_amount, edit_desc)
                    st.session_state["editing_id"] = None
                    st.success("已保存")
                    st.rerun()
            with es2:
                if st.button("❌ 取消", key=f"cancel_{rec_id}", use_container_width=True):
                    st.session_state["editing_id"] = None
                    st.rerun()

            st.divider()
            continue

        # ----- 正常显示行 -----
        col_info, col_amount, col_btn = st.columns([3, 1, 2])

        with col_info:
            st.markdown(f"**{type_label}** {rec['description'] or rec['category']}")
            st.caption(f"{rec['date']} · {rec['category']}")

        with col_amount:
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

else:
    st.info("暂无记录，开始添加吧！")

# ============ 使用说明 ============
with st.expander("📖 使用说明"):
    st.markdown("""
    **文字输入格式：**
    - `午餐 35` → 支出 餐饮 35元
    - `工资 8000` → 收入 工资 8000元
    - `7月3日 打车 28` → 指定日期
    - `奖金 1000` → 收入 奖金 1000元

    **修改/删除：** 点击每条记录右侧 ✏️ 或 🗑️ 按钮
    """)
