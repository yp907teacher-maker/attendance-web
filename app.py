import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="永平育樂營-籃球點名", page_icon="🏀", layout="centered")

# --- CSS 美化 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 20px; background-color: #ff5722; color: white; border: none; height: 3em; font-weight: bold; width: 100%; }
    div[data-testid="stExpander"] { border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 10px; background-color: white; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 2. 建立連線
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

try:
    df = conn.read(spreadsheet=URL, ttl=0)
    df['學生姓名'] = df['學生姓名'].astype(str)
    if '班別' not in df.columns: df['班別'] = '基礎班'
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 系統連線異常，請檢查試算表權限。")
    st.stop()

# --- 標題 ---
st.title("🏀 永平育樂營")
st.markdown("##### 籃球訓練班點名系統")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 系統選單")
    selected_month = st.selectbox("📅 統計月份", [f"{i:02d}" for i in range(1, 13)], index=int(datetime.now().strftime("%m")) - 1)
    view_class = st.radio("👥 顯示班別", ["全部", "基礎班", "競技班"])
    st.divider()
    # 這裡可以預設幾位常用的點名老師
    staff_list = ["老師A", "老師B", "教練C", "教練D"] 
    current_user = st.selectbox("🙋 當前點名者", staff_list)

# --- 數據運算 ---
def get_monthly_stat(record_str, month, target):
    if not record_str or record_str == "nan": return 0
    return sum(1 for r in record_str.split(", ") if r.startswith(f"{month}-") and f"({target})" in r)

stats_df = df.copy()
stats_df['月出席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "出席"))
stats_df['月補課'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "補課"))
stats_df['月缺席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "缺席"))
stats_df['當月已上'] = stats_df['月出席'] + stats_df['月補課']
stats_df['該月有紀錄'] = (stats_df['當月已上'] + stats_df['月缺席']) > 0
stats_df['顯示總堂數'] = stats_df.apply(lambda r: r['總堂數'] if r['該月有紀錄'] else 0, axis=1)
stats_df['待補'] = stats_df.apply(lambda r: r['月缺席'] - r['月補課'] if r['該月有紀錄'] else 0, axis=1)
stats_df['剩餘'] = stats_df.apply(lambda r: r['顯示總堂數'] - r['當月已上'] if r['該月有紀錄'] else 0, axis=1)

# --- 統計卡片 ---
if view_class != "全部":
    display_df = stats_df[stats_df['班別'] == view_class]
else:
    display_df = stats_df

st.markdown(f"### 🚩 {view_class} 概況")
m1, m2, m3 = st.columns(3)
m1.metric("學員人數", f"{len(display_df)} 人")
m2.metric("本月總出勤", f"{int(display_df['當月已上'].sum())} 次")
m3.metric("待補課總數", f"{int(display_df['待補'].sum())} 次")

# --- 點名提交 ---
with st.expander("📝 點名紀錄提交", expanded=False):
    op_class = st.radio("1. 選擇班別", ["基礎班", "競技班"], horizontal=True)
    f_names = df[df['班別'] == op_class]['學生姓名'].unique()
    name = st.selectbox("2. 學員姓名", options=[""] + list(f_names))
    if name == "": name = st.text_input("或手動輸入新姓名")
    
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        new_total_lessons = st.number_input("設定本月總堂數", min_value=1, value=8)
    with c2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("🚀 提交紀錄"):
        if name:
            date_str = date_val.strftime("%m-%d")
            if name not in df['學生姓名'].values:
                new_row = {'學生姓名': name, '班別': op_class, '總堂數': new_total_lessons, '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            current_rec = str(df.at[idx, '點名紀錄'])
            
            if date_str in current_rec:
                st.error(f"🚫 {name} 在 {date_str} 已經有點名紀錄了！")
                st.stop()
            
            # 更新總堂數邏輯
            if date_val.strftime("%m-") not in current_rec:
                df.at[idx, '總堂數'] = new_total_lessons
            
            # 更新數據次數
            if status == "出席": df.at[idx, '已上堂數'] += 1
            elif status == "缺席": df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if get_monthly_stat(current_rec, selected_month, "缺席") > get_monthly_stat(current_rec, selected_month, "補課"):
                    df.at[idx, '已補課次數'] += 1; df.at[idx, '已上堂數'] += 1
                else: st.error("⚠️ 無缺席紀錄可補"); st.stop()
            
            # 【新功能】紀錄格式：日期(狀態)-點名者
            new_r = f"{date_str}({status})-{current_user}"
            df.at[idx, '點名紀錄'] = new_r if current_rec in ["nan", ""] else f"{current_rec}, {new_r}"
            
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ 紀錄成功！(由 {current_user} 點名)")
            st.rerun()

st.divider()

# --- 數據表格 ---
st.markdown(f"#### 📅 {selected_month} 月份名單")
view_df = display_df[['班別', '學生姓名', '顯示總堂數', '當月已上', '待補', '剩餘']].copy()
view_df.columns = ['班別', '學生姓名', '總堂數', '已上', '待補', '剩餘']
st.dataframe(view_df, width=1000, hide_index=True)

# --- 個人詳細明細 (此處會顯示是誰點的名) ---
search_name = st.selectbox("🔍 查詢個人詳細紀錄", options=[""] + list(df['學生姓名'].unique()))
if search_name:
    p_row = stats_df[stats_df['學生姓名'] == search_name].iloc[0]
    all_r = str(p_row['點名紀錄']).split(", ")
    m_r = [r for r in all_r if r.startswith(f"{selected_month}-")]
    st.info(f"🏀 **{search_name}** - {selected_month}月紀錄：")
    if m_r:
        for r in m_r:
            st.write(f"🔹 {r}")
    else:
        st.write("本月無紀錄")
