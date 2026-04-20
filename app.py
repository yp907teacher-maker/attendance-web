import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="永平育樂營-流水帳點名系統", page_icon="🏀", layout="centered")

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

# 3. 讀取資料
try:
    # 讀取所有歷史紀錄
    raw_df = conn.read(spreadsheet=URL, ttl=0)
    # 預設學生名單（若您有固定名單，可改為從另一個 Sheet 讀取，這裡暫由歷史紀錄產生）
    all_students = raw_df['學生姓名'].unique().tolist() if not raw_df.empty else []
except Exception as e:
    st.error("⚠️ 系統連線異常")
    st.stop()

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 系統選單")
    selected_month = st.selectbox("📅 統計月份", [f"{i:02d}" for i in range(1, 13)], index=int(datetime.now().strftime("%m")) - 1)
    view_class = st.radio("👥 顯示班別", ["全部", "基礎班", "競技班"])
    staff_list = ["教練A", "教練B", "老師C"] 
    current_user = st.selectbox("🙋 當前點名者", staff_list)

# --- 核心邏輯：將流水帳轉為當月統計表 ---
if not raw_df.empty:
    calc_df = raw_df.copy()
    # 加上 errors='coerce'，遇到無法轉換的文字會變成 NaT (空值) 而不報錯
    calc_df['日期'] = pd.to_datetime(calc_df['日期'], errors='coerce')
    # 移除日期轉換失敗的列，避免後續計算錯誤
    calc_df = calc_df.dropna(subset=['日期'])
    
    calc_df['月份'] = calc_df['日期'].dt.strftime('%m')ㄈ
    # 依學生進行群組統計
    stats = monthly_df.groupby(['學生姓名', '班別']).agg(
        出席=('狀態', lambda x: (x == '出席').sum()),
        缺席=('狀態', lambda x: (x == '缺席').sum()),
        補課=('狀態', lambda x: (x == '補課').sum()),
        總堂數=('當月總堂數', 'max')
    ).reset_index()
    
    stats['已上'] = stats['出席'] + stats['補課']
    stats['待補'] = stats['缺席'] - stats['補課']
    stats['剩餘'] = stats['總堂數'] - stats['已上']
else:
    stats = pd.DataFrame(columns=['學生姓名', '班別', '總堂數', '已上', '待補', '剩餘'])

# --- 統計卡片顯示 ---
display_df = stats if view_class == "全部" else stats[stats['班別'] == view_class]
st.title("🏀 永平育樂營")
m1, m2, m3 = st.columns(3)
m1.metric("當月學員", f"{len(display_df)} 人")
m2.metric("累積上課", f"{int(display_df['已上'].sum()) if not display_df.empty else 0} 次")
m3.metric("待補總數", f"{int(display_df['待補'].sum()) if not display_df.empty else 0} 次")

# --- 點名提交 (新增一列到 Google Sheets) ---
with st.expander("📝 點名紀錄提交", expanded=True):
    op_class = st.radio("1. 選擇班別", ["基礎班", "競技班"], horizontal=True)
    name = st.selectbox("2. 學員姓名", options=[""] + sorted(list(set(all_students))))
    if name == "": name = st.text_input("或輸入新姓名")
    
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        monthly_total = st.number_input("設定本月總堂數", min_value=1, value=8)
    with c2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("🚀 提交紀錄"):
        if name:
            # 防呆：檢查同一天同一個人是否已有點名 (在當前讀取的 raw_df 中檢查)
            check_date = date_val.strftime("%Y-%m-%d")
            if not raw_df.empty:
                # 這裡要比對原始日期字串
                duplicate = raw_df[(raw_df['學生姓名'] == name) & (pd.to_datetime(raw_df['日期']).dt.date == date_val)]
                if not duplicate.empty:
                    st.error(f"🚫 {name} 今日已有紀錄！")
                    st.stop()
            
            # 準備新的一列資料
            new_data = pd.DataFrame([{
                "日期": date_val.strftime("%Y-%m-%d"),
                "學生姓名": name,
                "班別": op_class,
                "狀態": status,
                "點名者": current_user,
                "當月總堂數": monthly_total
            }])
            
            # 合併並更新
            updated_df = pd.concat([raw_df, new_data], ignore_index=True)
            conn.update(spreadsheet=URL, data=updated_df)
            st.success(f"✅ 已存入試算表第 {len(updated_df)+1} 列")
            st.rerun()

st.divider()
st.markdown(f"#### 📅 {selected_month} 月份統計報表")
st.dataframe(display_df[['班別', '學生姓名', '總堂數', '已上', '待補', '剩餘']], width=1000, hide_index=True)
