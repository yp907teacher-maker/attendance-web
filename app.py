import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="學生點名進度系統-月份版", layout="centered")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 讀取資料
try:
    df = conn.read(spreadsheet=URL, ttl=0)
    # 確保基本格式
    df['學生姓名'] = df['學生姓名'].astype(str)
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error("⚠️ 無法連線至 Google 試算表，請檢查權限與標題格式。")
    st.stop()

st.title("🍎 點名與補課管理 (月份切換版)")

# --- 月份選擇器 ---
current_month = datetime.now().strftime("%m")
selected_month = st.sidebar.selectbox("📅 選擇統計月份", 
    options=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
    index=int(current_month)-1
)

# --- 第一區：點名操作 ---
with st.expander("📝 進行點名 / 新增學生"):
    name_list = [""] + list(df['學生姓名'].unique())
    name = st.selectbox("選擇學生", options=name_list)
    if name == "":
        name = st.text_input("或輸入新學生姓名")
    
    col_op1, col_op2 = st.columns(2)
    with col_op1:
        total_lessons = st.number_input("該月預計總堂數", min_value=1, value=8)
        status = st.selectbox("狀態", ["出席", "缺席", "補課"])
    with col_op2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("提交並同步雲端", width='stretch'):
        if name:
            date_str = date_val.strftime("%m-%d")
            
            if name not in df['學生姓名'].values:
                new_data = {'學生姓名': name, '總堂數': total_lessons, '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""}
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
            # 更新邏輯
            if status == "出席": df.at[idx, '已上堂數'] += 1
            elif status == "缺席": df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1
                    df.at[idx, '已上堂數'] += 1
                else:
                    st.error("⚠️ 補課額度不足！"); st.stop()
            
            old_rec = str(df.at[idx, '點名紀錄'])
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if old_rec in ["nan", ""] else f"{old_rec}, {new_rec}"
            
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} 紀錄已同步！")
            st.rerun()

st.divider()

# --- 第二區：按月份統計邏輯 ---
st.subheader(f"📊 {selected_month} 月份進度統計")

def count_month_status(record_str, month, target_status):
    """從歷史紀錄字串中，計算特定月份與狀態的次數"""
    if not record_str or record_str == "nan": return 0
    records = record_str.split(", ")
    count = 0
    for r in records:
        if r.startswith(f"{month}-") and f"({target_status})" in r:
            count += 1
    return count

if not df.empty:
    # 建立一個暫時的統計表，只包含當月數據
    monthly_df = df.copy()
    monthly_df['當月出席'] = monthly_df['點名紀錄'].apply(lambda x: count_month_status(x, selected_month, "出席"))
    monthly_df['當月補課'] = monthly_df['點名紀錄'].apply(lambda x: count_month_status(x, selected_month, "補課"))
    monthly_df['當月缺席'] = monthly_df['點名紀錄'].apply(lambda x: count_month_status(x, selected_month, "缺席"))
    
    # 當月總上課數 = 當月出席 + 當月補課
    monthly_df['已上堂數'] = monthly_df['當月出席'] + monthly_df['當月補課']
    monthly_df['待補課'] = monthly_df['當月缺席'] - monthly_df['當月補課']
    monthly_df['剩餘堂數'] = monthly_df['總堂數'] - monthly_df['已上堂數']

    search_name = st.selectbox("🔍 查詢學生", options=["所有學生"] + list(df['學生姓名'].unique()))
    
    if search_name == "所有學生":
        st.dataframe(
            monthly_df[['學生姓名', '已上堂數', '待補課', '剩餘堂數']], 
            width='stretch', hide_index=True
        )
    else:
        row = monthly_df[monthly_df['學生姓名'] == search_name].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("當月已上", f"{int(row['已上堂數'])} 堂")
        c2.metric("待補課", f"{int(row['待補課'])} 次", 
                  delta=f"{int(row['待補課'])} 次" if row['待補課'] > 0 else None, delta_color="inverse")
        c3.metric("月剩餘", f"{int(row['剩餘堂數'])} 堂")
        
        # 過濾出該月份的歷史明細顯示
        all_rec = str(row['點名紀錄']).split(", ")
        month_rec = [r for r in all_rec if r.startswith(f"{selected_month}-")]
        st.write(f"📌 **{selected_month} 月明細：** {', '.join(month_rec) if month_rec else '無紀錄'}")
