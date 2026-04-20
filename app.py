import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="永平育樂營-籃球點名系統", layout="centered")

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 3. 讀取資料
try:
    df = conn.read(spreadsheet=URL, ttl=0)
    df['學生姓名'] = df['學生姓名'].astype(str)
    # 確保班別欄位存在
    if '班別' not in df.columns:
        df['班別'] = '基礎班'
    
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 系統連線異常，請確認試算表權限。")
    st.stop()

# --- 網頁標題 ---
st.title("🏀 永平育樂營：籃球點名系統")

# --- 側邊欄控制 ---
st.sidebar.header("⚙️ 篩選與設定")
selected_month = st.sidebar.selectbox("📅 統計月份", 
    options=[f"{i:02d}" for i in range(1, 13)],
    index=int(datetime.now().strftime("%m")) - 1
)
# 增加班別篩選
view_class = st.sidebar.radio("👥 顯示班別", ["全部", "基礎班", "競技班"])

# --- 點名操作區 ---
with st.expander("📝 點名紀錄提交", expanded=True):
    # 選擇班別以過濾學生名單
    op_class = st.radio("1. 選擇操作班別", ["基礎班", "競技班"], horizontal=True)
    
    filtered_names = df[df['班別'] == op_class]['學生姓名'].unique()
    name = st.selectbox("2. 選擇學生姓名", options=[""] + list(filtered_names))
    
    if name == "":
        name = st.text_input("或輸入新學員姓名")
    
    col1, col2 = st.columns(2)
    with col1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        total_set = st.number_input("設定本月總堂數", min_value=1, value=8)
    with col2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("確認提交", width='stretch'):
        if name:
            date_str = date_val.strftime("%m-%d")
            
            # 若為新學員
            if name not in df['學生姓名'].values:
                new_row = {'學生姓名': name, '班別': op_class, '總堂數': total_set, 
                           '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
            # 防呆：重複日期檢查
            existing_records = str(df.at[idx, '點名紀錄'])
            if date_str in existing_records:
                st.error(f"🚫 {name} 在 {date_str} 已經有點名紀錄了！")
                st.stop()
            
            # 更新邏輯
            if status == "出席": df.at[idx, '已上堂數'] += 1
            elif status == "缺席": df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1
                    df.at[idx, '已上堂數'] += 1
                else:
                    st.error("⚠️ 無缺席紀錄可供補課"); st.stop()
            
            # 更新字串
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if existing_records in ["nan", ""] else f"{existing_records}, {new_rec}"
            
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} ({op_class}) 紀錄成功！")
            st.rerun()

st.divider()

# --- 數據統計報表 ---
st.subheader(f"📊 {selected_month} 月份 - {view_class} 統計")

def get_monthly_stat(record_str, month, target):
    if not record_str or record_str == "nan": return 0
    return sum(1 for r in record_str.split(", ") if r.startswith(f"{month}-") and f"({target})" in r)

if not df.empty:
    stats_df = df.copy()
    # 過濾顯示班別
    if view_class != "全部":
        stats_df = stats_df[stats_df['班別'] == view_class]
        
    stats_df['已上'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "出席") + get_monthly_stat(x, selected_month, "補課"))
    stats_df['待補'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "缺席") - get_monthly_stat(x, selected_month, "補課"))
    stats_df['剩餘'] = stats_df['總堂數'] - stats_df['已上']

    st.dataframe(
        stats_df[['班別', '學生姓名', '已上', '待補', '剩餘']], 
        width='stretch', hide_index=True
    )
