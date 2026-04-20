import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="永平育樂營-籃球點名系統", layout="centered")

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 3. 讀取與格式化資料
try:
    df = conn.read(spreadsheet=URL, ttl=0)
    df['學生姓名'] = df['學生姓名'].astype(str)
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 系統連線中斷")
    st.info("請檢查試算表是否已共用給 `json-685@atomic-legacy-493918-j7.iam.gserviceaccount.com`。")
    st.stop()

# --- 網頁大標題 ---
st.title("🏀 永平育樂營：籃球點名系統")

# --- 側邊月份切換 ---
current_date = datetime.now()
selected_month = st.sidebar.selectbox("📅 統計月份切換", 
    options=[f"{i:02d}" for i in range(1, 13)],
    index=int(current_date.strftime("%m")) - 1
)

# --- 點名操作區 ---
with st.expander("📝 每日籃球紀錄提交", expanded=True):
    name_list = [""] + list(df['學生姓名'].unique())
    name = st.selectbox("選擇學生姓名", options=name_list)
    if name == "":
        name = st.text_input("或手動新增學生")
    
    col1, col2 = st.columns(2)
    with col1:
        status = st.selectbox("今日訓練狀態", ["出席", "缺席", "補課"])
        total_set = st.number_input("本月合約總堂數", min_value=1, value=8)
    with col2:
        date_val = st.date_input("點名日期", current_date)

    if st.button("確認提交點名", width='stretch'):
        if name:
            date_str = date_val.strftime("%m-%d")
            
            # 若為新學員則初始化
            if name not in df['學生姓名'].values:
                new_row = {'學生姓名': name, '總堂數': total_set, '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
            # 【防呆】檢查日期唯一性
            existing_records = str(df.at[idx, '點名紀錄'])
            if date_str in existing_records:
                st.error(f"🚫 該學員 {name} 在 {date_str} 已經有點名紀錄，不可重複點名！")
                st.stop()
            
            # 點名邏輯計算
            if status == "出席":
                df.at[idx, '已上堂數'] += 1
            elif status == "缺席":
                df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1
                    df.at[idx, '已上堂數'] += 1
                else:
                    st.error("⚠️ 此學員目前沒有待補課紀錄！"); st.stop()
            
            # 更新紀錄字串
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if existing_records in ["nan", ""] else f"{existing_records}, {new_rec}"
            
            # 更新回雲端
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} 紀錄完成！")
            st.rerun()

st.divider()

# --- 數據統計區 ---
st.subheader(f"📊 {selected_month} 月份訓練統計報表")

def get_monthly_stat(record_str, month, target):
    if not record_str or record_str == "nan": return 0
    return sum(1 for r in record_str.split(", ") if r.startswith(f"{month}-") and f"({target})" in r)

if not df.empty:
    stats_df = df.copy()
    stats_df['月出席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "出席"))
    stats_df['月補課'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "補課"))
    stats_df['月缺席'] = stats_df['點名紀錄'].apply(lambda x: get_monthly_stat(x, selected_month, "缺席"))
    
    stats_df['當月已上'] = stats_df['月出席'] + stats_df['月補課']
    stats_df['待補課次數'] = stats_df['月缺席'] - stats_df['月補課']
    stats_df['剩餘堂數'] = stats_df['總堂數'] - stats_df['當月已上']

    # 顯示精簡統計表
    st.dataframe(
        stats_df[['學生姓名', '當月已上', '待補課次數', '剩餘堂數']], 
        width='stretch', hide_index=True
    )
    
    # 個人歷史詳細查詢
    search_name = st.selectbox("🔍 查詢個別學員明細", options=[""] + list(df['學生姓名'].unique()))
    if search_name:
        row = stats_df[stats_df['學生姓名'] == search_name].iloc[0]
        all_rec = str(row['點名紀錄']).split(", ")
        month_rec = [r for r in all_rec if r.startswith(f"{selected_month}-")]
        st.info(f"📅 **{search_name} - {selected_month} 月明細：** {', '.join(month_rec) if month_rec else '本月無紀錄'}")
        
