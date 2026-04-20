import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="永平育樂營點名系統", layout="centered")

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 3. 讀取資料
try:
    df = conn.read(spreadsheet=URL, ttl=0)
    # 統一資料格式，避免計算錯誤
    df['學生姓名'] = df['學生姓名'].astype(str)
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 目前無法連線至 Google 試算表")
    st.info("請檢查試算表是否已『共用』給服務帳號 Email 位址並設為編輯者。")
    st.stop()

# --- 網頁大標題 ---
st.title("🏹 永平育樂營點名系統")

# --- 月份切換器 (側邊欄) ---
current_date = datetime.now()
selected_month = st.sidebar.selectbox("📅 選擇統計月份", 
    options=[f"{i:02d}" for i in range(1, 13)],
    index=int(current_date.strftime("%m")) - 1
)

# --- 點名操作區 ---
with st.expander("📝 每日點名操作", expanded=True):
    name_list = [""] + list(df['學生姓名'].unique())
    name = st.selectbox("選擇學生", options=name_list)
    if name == "":
        name = st.text_input("或輸入新學生姓名")
    
    col1, col2 = st.columns(2)
    with col1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        total_set = st.number_input("設定本月總堂數", min_value=1, value=8)
    with col2:
        # 預設為今天日期
        date_val = st.date_input("點名日期", current_date)

    if st.button("確認提交紀錄", width='stretch'):
        if name:
            date_str = date_val.strftime("%m-%d")
            
            # 若為新學生則初始化列資料
            if name not in df['學生姓名'].values:
                new_row = {'學生姓名': name, '總堂數': total_set, '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
            # 【防呆機制】檢查同一天是否已有紀錄
            existing_records = str(df.at[idx, '點名紀錄'])
            if date_str in existing_records:
                st.error(f"🚫 警告：{name} 在 {date_str} 已經有點名紀錄了，一天只能記錄一筆！")
                st.stop()
            
            # 更新邏輯
            if status == "出席":
                df.at[idx, '已上堂數'] += 1
            elif status == "缺席":
                df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1
                    df.at[idx, '已上堂數'] += 1
                else:
                    st.error("⚠️ 此學生目前無缺席紀錄可供補課"); st.stop()
            
            # 更新歷史紀錄字串 (格式如: 04-21(出席))
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if existing_records in ["nan", ""] else f"{existing_records}, {new_rec}"
            
            # 更新回雲端 Google Sheets
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} {date_str} 紀錄成功同步！")
            st.rerun()

st.divider()

# --- 數據統計區 (自動按月份拆分顯示) ---
st.subheader(f"📊 {selected_month} 月份學習進度統計")

def get_monthly_stat(record_str, month, target):
    if not record_str or record_str == "nan": return 0
    # 拆分字串並過濾符合月份與狀態的項目
    return sum(1 for r in record_str.split(", ") if r.startswith(f"{month}-") and f"({target})" in r)

if not df.empty:
    # 複製資料表進行當月統計運算
    stats_df = df.copy()
    stats_df['月出席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "出席"))
    stats_df['月補課'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "補課"))
    stats_df['月缺席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "缺席"))
    
    # 計算顯示用的統計值
    stats_df['當月已上'] = stats_df['月出席'] + stats_df['月補課']
    stats_df['待補課'] = stats_df['月缺席'] - stats_df['月補課']
    stats_df['剩餘堂數'] = stats_df['總堂數'] - stats_df['當月已上']

    # 顯示全體學生統計總表
    st.dataframe(
        stats_df[['學生姓名', '當月已上', '待補課', '剩餘堂數']], 
        width='stretch', hide_index=True
    )
    
    # 個人詳細明細查詢
    search_name = st.selectbox("🔍 查詢個人詳細明細", options=[""] + list(df['學生姓名'].unique()))
    if search_name:
        row = stats_df[stats_df['學生姓名'] == search_name].iloc[0]
        # 過濾出該月份的歷史紀錄字串
        all_rec = str(row['點名紀錄']).split(", ")
        month_rec = [r for r in all_rec if r.startswith(f"{selected_month}-")]
        st.info(f"📅 **{search_name} {selected_month} 月明細：** {', '.join(month_rec) if month_rec else '本月份尚無紀錄'}")
        
