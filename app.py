import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="學生點名進度系統", layout="centered")

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. 填入你的試算表網址 (請務必確認這行換成你自己的網址)
URL = "https://docs.google.com/spreadsheets/d/你的試算表ID/edit"

# 4. 讀取資料 (ttl=0 確保每次抓取都是最新的)
try:
    df = conn.read(spreadsheet=URL, ttl=0)
    # 確保姓名欄位是字串，數值欄位是數字
    df['學生姓名'] = df['學生姓名'].astype(str)
    df['總堂數'] = pd.to_numeric(df['總堂數'], errors='coerce').fillna(0)
    df['已上堂數'] = pd.to_numeric(df['已上堂數'], errors='coerce').fillna(0)
    df['缺席次數'] = pd.to_numeric(df['缺席次數'], errors='coerce').fillna(0)
    df['已補課次數'] = pd.to_numeric(df['已補課次數'], errors='coerce').fillna(0)
except Exception as e:
    st.error(f"連線失敗，請檢查金鑰與共用權限：{e}")
    df = pd.DataFrame(columns=['學生姓名', '總堂數', '已上堂數', '缺席次數', '已補課次數', '點名紀錄'])

st.title("🍎 點名與補課進度管理")

# --- 第一區：點名操作 ---
with st.expander("📝 點名/新增學生", expanded=False):
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

    if st.button("提交點名紀錄", use_container_width=True):
        if name:
            date_str = date_val.strftime("%m-%d")
            # 邏輯處理：如果不存在則新增
            if name not in df['學生姓名'].values:
                new_data = {
                    '學生姓名': name, '總堂數': total_lessons, 
                    '已上堂數': 0, '缺席次數': 0, '已補課次數': 0, '點名紀錄': ""
                }
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            
            idx = df[df['學生姓名'] == name].index[0]
            
            # 更新數據邏輯
            if status == "出席":
                df.at[idx, '已上堂數'] += 1
            elif status == "缺席":
                df.at[idx, '缺席次數'] += 1
            elif status == "補課":
                if df.at[idx, '缺席次數'] > df.at[idx, '已補課次數']:
                    df.at[idx, '已補課次數'] += 1
                    df.at[idx, '已上堂數'] += 1
                else:
                    st.error("⚠️ 補課額度不足！")
                    st.stop()
            
            # 更新紀錄字串
            old_rec = str(df.at[idx, '點名紀錄'])
            new_rec = f"{date_str}({status})"
            df.at[idx, '點名紀錄'] = new_rec if old_rec in ["nan", ""] else f"{old_rec}, {new_rec}"
            
            # 寫回雲端
            conn.update(spreadsheet=URL, data=df)
            st.success(f"✅ {name} 紀錄已同步！")
            st.rerun()

st.divider()

# --- 第二區：核心統計 (你要的顯示方式) ---
st.subheader("📊 目前進度統計")

if not df.empty:
    # 計算衍生欄位
    df['待補課'] = df['缺席次數'] - df['已補課次數']
    df['剩餘堂數'] = df['總堂數'] - df['已上堂數']
    
    # 學生篩選器
    search_name = st.selectbox("🔍 快速查詢學生狀況", options=["所有學生"] + list(df['學生姓名'].unique()))
    
    if search_name == "所有學生":
        # 顯示全體精簡表格
        st.dataframe(
            df[['學生姓名', '已上堂數', '待補課', '剩餘堂數']], 
            use_container_width=True,
            hide_index=True
        )
    else:
        # 顯示個人大卡片
        row = df[df['學生姓名'] == search_name].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("已上堂數", f"{int(row['已上堂數'])} 堂")
        c2.metric("待補課", f"{int(row['待補課'])} 次", delta_color="inverse")
        c3.metric("剩餘堂數", f"{int(row['剩餘堂數'])} 堂")
        
        st.write(f"📌 **詳細日期紀錄：** {row['點名紀錄']}")
else:
    st.info("目前還沒有學生資料喔！")
