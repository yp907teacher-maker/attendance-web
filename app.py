import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="永平育樂營-籃球點名", page_icon="🏀", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 20px; background-color: #ff5722; color: white; border: none; height: 3em; font-weight: bold; width: 100%; }
    div[data-testid="stExpander"] { border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 10px; background-color: white; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True) # 修正點

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

try:
    df = conn.read(spreadsheet=URL, ttl=0)
    df['學生姓名'] = df['學生姓名'].astype(str)
    if '班別' not in df.columns: df['班別'] = '基礎班'
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 系統連線異常")
    st.write("詳細錯誤摘要：", str(e)[:100]) # 顯示前100個字幫助診斷
    st.info("請檢查：1. Secrets 格式是否正確 2. 試算表是否已共用給服務帳號 Email。")
    st.stop()

st.title("🏀 永平育樂營")
st.markdown("##### 籃球訓練班點名系統")

with st.sidebar:
    st.header("⚙️ 系統選單")
    selected_month = st.selectbox("📅 統計月份", [f"{i:02d}" for i in range(1, 13)], index=int(datetime.now().strftime("%m")) - 1)
    view_class = st.radio("👥 顯示班別", ["全部", "基礎班", "競技班"])

stats_df = df.copy()
def get_monthly_stat(record_str, month, target):
    if not record_str or record_str == "nan": return 0
    return sum(1 for r in record_str.split(", ") if r.startswith(f"{month}-") and f"({target})" in r)

stats_df['月出席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "出席"))
stats_df['月補課'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "補課"))
stats_df['月缺席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "缺席"))
stats_df['已上'] = stats_df['月出席'] + stats_df['月補課']
stats_df['待補'] = stats_df['月缺席'] - stats_df['月補課']
stats_df['剩餘'] = stats_df['總堂數'] - stats_df['已上']

if view_class != "全部":
    display_df = stats_df[stats_df['班別'] == view_class]
else:
    display_df = stats_df

st.markdown(f"### 🚩 {view_class} 概況")
m1, m2, m3 = st.columns(3)
m1.metric("學員人數", f"{len(display_df)} 人")
m2.metric("本月總出勤", f"{int(display_df['已上'].sum())} 次")
m3.metric("待補課總數", f"{int(display_df['待補'].sum())} 次", delta_color="inverse")

with st.expander("📝 點名紀錄提交", expanded=False):
    op_class = st.radio("1. 選擇班別", ["基礎班", "競技班"], horizontal=True)
    f_names = df[df['班別'] == op_class]['學生姓名'].unique()
    name = st.selectbox("2. 學員姓名", options=[""] + list(f_names))
    if name == "": name = st.text_input("或手動輸入新姓名")
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        total_set = st.number_input("設定本月總堂數", min_value=1, value=8)
    with c2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("🚀 提交紀錄"):
        if name:
            date_str = date_val.strftime("%m-%d")
            if name not in df['學生姓名'].values:
                new_row = {'學生姓名': name, '班別': op_class, '總堂數': total_set, '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            idx = df[df['學生姓名'] == name].index[0]
            if date_str in str(df.at[idx, '點名紀錄']):
                st.error("🚫 此日期已有紀錄"); st.stop()
            if status == "出席": df.at[idx, '已上堂數'] += 1
            elif status == "缺席": df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1; df.at[idx, '已上堂數'] += 1
                else: st.error("⚠️ 無缺席紀錄可補"); st.stop()
            new_r = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_r if str(df.at[idx, '點名紀錄']) in ["nan", ""] else f"{df.at[idx, '點名紀錄']}, {new_r}"
            conn.update(spreadsheet=URL, data=df)
            st.success("✅ 紀錄同步成功！"); st.rerun()

st.divider()
st.markdown(f"#### 📅 {selected_month} 月份詳細名單")
st.dataframe(display_df[['班別', '學生姓名', '已上', '待補', '剩餘']], width=1000, hide_index=True)
