import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="學生點名系統", layout="centered")

# 2. 建立連線 (使用您提供的 JSON 金鑰資訊)
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 3. 讀取資料
try:
    df = conn.read(spreadsheet=URL, ttl=0)
    # 統一資料格式
    df['學生姓名'] = df['學生姓名'].astype(str)
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 無法連線至 Google 試算表。")
    st.info("請檢查：試算表是否已『共用』給 `json-685@atomic-legacy-493918-j7.iam.gserviceaccount.com` 並設為編輯者？")
    st.stop()

st.title("🍎 每日點名管理系統")

# --- 月份切換器 (預設為當月) ---
current_date = datetime.now()
selected_month = st.sidebar.selectbox("📅 統計月份", 
    options=[f"{i:02d}" for i in range(1, 13)],
    index=int(current_date.strftime("%m")) - 1
)

# --- 點名操作區 ---
with st.expander("📝 今日點名操作", expanded=True):
    name_list = [""] + list(df['學生姓名'].unique())
    name = st.selectbox("選擇學生", options=name_list)
    if name == "":
        name = st.text_input("輸入新學生姓名")
    
    col1, col2 = st.columns(2)
    with col1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        total_set = st.number_input("設定月總堂數", min_value=1, value=8)
    with col2:
        # 預設為今天日期，達成一天點名一次的便利性
        date_val = st.date_input("點名日期", current_date)

    if st.button("確認提交紀錄", width='stretch'):
        if name:
            date_str = date_val.strftime("%m-%d")
            
            # 若為新學生則初始化
            if name not in df['學生姓名'].values:
                new_row = {'學生姓名': name, '總堂數': total_set, '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
            # 更新數據 (出席/缺席/補課)
            if status == "出席":
                df.at[idx, '已上堂數'] += 1
            elif status == "缺席":
                df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1
                    df.at[idx, '已上堂數'] += 1
                else:
                    st.error("⚠️ 無缺席紀錄可供補課"); st.stop()
            
            # 更新歷史字串
            old_rec = str(df.at[idx, '點名紀錄'])
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if old_rec in ["nan", ""] else f"{old_rec}, {new_rec}"
            
            # 更新回雲端
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} {date_str} 紀錄成功！")
            st.rerun()

st.divider()

# --- 數據統計區 (自動按月份拆分) ---
st.subheader(f"📊 {selected_month} 月份學習進度")

def get_monthly_stat(record_str, month, target):
    if not record_str or record_str == "nan": return 0
    return sum(1 for r in record_str.split(", ") if r.startswith(f"{month}-") and f"({target})" in r)

if not df.empty:
    # 運算當月數據
    stats_df = df.copy()
    stats_df['月出席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "出席"))
    stats_df['月補課'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "補課"))
    stats_df['月缺席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "缺席"))
    
    stats_df['當月已上'] = stats_df['月出席'] + stats_df['月補課']
    stats_df['待補課'] = stats_df['月缺席'] - stats_df['月補課']
    stats_df['剩餘堂數'] = stats_df['總堂數'] - stats_df['當月已上']

    # 顯示總表
    st.dataframe(
        stats_df[['學生姓名', '當月已上', '待補課', '剩餘堂數']], 
        width='stretch', hide_index=True
    )
