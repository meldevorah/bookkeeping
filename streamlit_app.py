#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记账小程序 - 完整版
移动端友好：登录保护 / 批量录入 / 分类统计 / 月度年度总结 / 导出备份
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app import (
    init_db, verify_user, get_user_id, change_password,
    add_record, add_records_batch, parse_text_input,
    update_record, delete_record, get_records,
    get_summary, get_category_summary, get_monthly_summary, get_yearly_summary,
    export_to_json
)
import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="💰 记账", page_icon="💰", layout="centered")

init_db()

# ──────────────────────────────────────────
# Session state
# ──────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = None

def logout():
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = None

# ──────────────────────────────────────────
# 登录页
# ──────────────────────────────────────────
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

# ──────────────────────────────────────────
# 已登录
# ──────────────────────────────────────────
uid = st.session_state["user_id"]
username = st.session_state["username"]

st.title(f"💰 {username} 的账本")

# ── 顶栏：登出 + 修改密码 ──
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
            elif change_password(uid, new_pw):
                st.success("密码修改成功！")
            else:
                st.error("修改失败")

# ── Tab 布局 ──
tab1, tab2, tab3 = st.tabs(["📝 记账", "📊 月度总结", "�年度总结"])

# ══════════════════════════════════════════
# Tab 1：记账
# ══════════════════════════════════════════
with tab1:
    # 统计概览
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

    # ── 添加记录 ──
    st.subheader("➕ 添加记录")

    input_method = st.radio(
        "输入方式",
        ["📝 批量文字（支持多行）", "✏️ 手动输入"],
        captions=["一次输入多条，如：午餐 35 /n 打车 28", "单条详细录入"],
        label_visibility="collapsed",
        horizontal=True
    )

    if input_method.startswith("📝"):
        with st.container(border=True):
            text_input = st.text_area(
                "输入内容（每行一条）",
                placeholder="示例：\n午餐 35\n打车 28\n工资 8000\n7月3日 咖啡 32",
                height=120,
                key="batch_text"
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

    # ── Session state ──
    if "editing_id" not in st.session_state:
        st.session_state["editing_id"] = None
    if "deleting_id" not in st.session_state:
        st.session_state["deleting_id"] = None

    # ── 记录列表 ──
    st.subheader("📋 记录列表")
    records = get_records(limit=100, user_id=uid)

    if records:
        for rec in records:
            rec_id = rec["id"]
            is_income = rec["type"] == "income"

            # 删除确认
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

            # 编辑表单
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

            # 正常记录行
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

        # 导出按钮
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

# ══════════════════════════════════════════
# Tab 2：月度总结
# ══════════════════════════════════════════
with tab2:
    st.subheader("📊 月度总结")

    # 选择月份
    all_records = get_records(limit=5000, user_id=uid)
    months_set = sorted(set(r['date'][:7] for r in all_records), reverse=True)
    if not months_set:
        months_set = [datetime.now().strftime("%Y-%m")]

    selected_month = st.selectbox("选择月份", months_set)

    # 当月统计
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

    # 支出分类
    if cs['expense']:
        total_exp = sum(e['amount'] for e in cs['expense'])
        st.markdown("**📉 支出分类**")
        for item in cs['expense']:
            pct = item['amount'] / total_exp * 100
            st.markdown(f"{item['category']}  ¥{item['amount']:.2f}  ({pct:.1f}%)")
            st.progress(pct / 100, text="")

    # 收入分类
    if cs['income']:
        st.markdown("**📈 收入分类**")
        for item in cs['income']:
            st.markdown(f"{item['category']}  ¥{item['amount']:.2f}")

# ══════════════════════════════════════════
# Tab 3：年度总结
# ══════════════════════════════════════════
with tab3:
    st.subheader("🏆 年度总结")

    year = st.selectbox(
        "选择年份",
        list(range(datetime.now().year, datetime.now().year - 5, -1))
    )

    ys = get_yearly_summary(year=year, user_id=uid)

    # 年统计
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

    # 月度趋势
    st.markdown(f"**📅 {year} 年每月收支**")
    month_names = ["1月","2月","3月","4月","5月","6月",
                   "7月","8月","9月","10月","11月","12月"]
    labels = []
    income_vals = []
    expense_vals = []
    for m in range(1, 13):
        mm = str(m).zfill(2)
        month_data = ys['months'].get(mm, {'income': 0, 'expense': 0})
        if month_data['income'] > 0 or month_data['expense'] > 0:
            labels.append(month_names[m - 1])
            income_vals.append(month_data['income'])
            expense_vals.append(month_data['expense'])

    if labels:
        import pandas as pd
        df_chart = pd.DataFrame({
            "月份": labels,
            "收入": income_vals,
            "支出": expense_vals
        })
        st.bar_chart(df_chart.set_index("月份"))
    else:
        st.info("该年度暂无数据")

    # 导出按钮
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
