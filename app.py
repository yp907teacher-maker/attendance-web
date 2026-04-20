import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="學生點名進度系統", layout="centered")

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. 你的專屬試算表網址
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 4. 讀取資料
try:
    # 使用 ttl=0 確保不使用快取，每次都讀取最新資料
    df = conn.read(spreadsheet=URL, ttl=0)
    
    # 強制格式化資料，避免運算錯誤
    df['學生姓名'] = df['學生姓名'].astype(str)
    for col in ['總堂數', '已上堂數', '缺席次數', '已補課次數']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
except Exception as e:
    st.error("⚠️ 目前無法連線至 Google 試算表")
    st.info("請檢查以下三點：\n1. 是否已將試算表「共用」給 `json-685@atomic-legacy-493918-j7.iam.gserviceaccount.com` 並設為「編輯者」？\n2. Streamlit Cloud 的 Secrets 內容是否正確？\n3. 試算表的第一列標題是否包含：學生姓名、總堂數、已上堂數、缺席次數、已補課次數、點名紀錄。")
    st.stop()

st.title("🍎 點名與補課進度管理")

# --- 第一區：點名操作 ---
with st.expander("📝 進行點名 / 新增學生"):
    name_list = [""] + list(df['學生姓名'].unique())
    name = st.selectbox("選擇學生", options=name_list)
    if name == "":
        name = st.text_input("或輸入新學生姓名")
    
    col_op1, col_op2 = st.columns(2)
    with col_op1:
        total_lessons = st.number_input("本月總堂數", min_value=1, value=8)
        status = st.selectbox("狀態", ["出席", "缺席", "補課"])
    with col_op2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("提交並同步雲端", use_container_width=True):
        if name:
            date_str = date_val.strftime("%m-%d")
            
            # 如果是新學生，建立新列
            if name not in df['學生姓名'].values:
                new_data = {
                    '學生姓名': name, '總堂數': total_lessons, 
                    '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""
                }
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
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
                    st.error("⚠️ 此學生沒有缺席紀錄可供補課！")
                    st.stop()
            
            # 更新日期紀錄
            old_rec = str(df.at[idx, '點名紀錄'])
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if old_rec in ["nan", ""] else f"{old_rec}, {new_rec}"
            
            # 寫回 Google Sheets
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} 紀錄已同步！系統重新整理中...")
            st.rerun()

st.divider()

# --- 第二區：核心統計統計 ---
st.subheader("📊 目前進度統計")

if not df.empty:
    # 計算衍生數據
    df['待補課'] = df['缺席次數'] - df['已補課次數']
    df['剩餘堂數'] = df['總堂數'] - df['已上堂數']
    
    search_name = st.selectbox("🔍 查詢特定學生", options=["所有學生"] + list(df['學生姓名'].unique()))
    
    if search_name == "所有學生":
        # 顯示精簡總表
        st.dataframe(
            df[['學生姓名', '已上堂數', '待補課', '剩餘堂數']], 
            use_container_width=True,
            hide_index=True
        )
    else:
        # 顯示個人圖表卡片
        row = df[df['學生姓名'] == search_name].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("已上堂數", f"{int(row['已上堂數'])} 堂")
        c2.metric("待補課", f"{int(row['待補課'])} 次", delta_color="inverse" if row['待補課'] > 0 else "normal")
        c3.metric("剩餘堂數", f"{int(row['剩餘堂數'])} 堂")
        
        st.write(f"📌 **歷史明細：** {row['點名紀錄']}")
else:
    st.info("目前試算表內尚無學生資料。")
