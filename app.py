import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定
st.set_page_config(page_title="永平育樂營-籃球點名", page_icon="🏀", layout="centered")

# --- CSS 美化樣式 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { 
        border-radius: 20px; 
        background-color: #ff5722; 
        color: white; 
        border: none; 
        height: 3em; 
        font-weight: bold; 
        width: 100%;
    }
    .stButton>button:hover { background-color: #e64a19; color: white; }
    div[data-testid="stExpander"] { 
        border: none; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.1); 
        border-radius: 10px; 
        background-color: white; 
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. 建立連線
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 3. 讀取資料與防錯
try:
    raw_df = conn.read(spreadsheet=URL, ttl=0)
    if raw_df is None or raw_df.empty or '日期' not in raw_df.columns:
        raw_df = pd.DataFrame(columns=['日期', '學生姓名', '班別', '狀態', '點名者', '當月總堂數'])
except Exception:
    st.error("⚠️ 系統連線異常，請檢查試算表權限。")
    st.stop()

# --- 側邊欄控制 ---
with st.sidebar:
    st.header("⚙️ 系統選單")
    # 修改點名者名單為 教練1~5
    staff_list = ["教練1", "教練2", "教練3", "教練4", "教練5"]
    current_user = st.selectbox("🙋 當前點名者", staff_list)
    
    st.divider()
    
    selected_month = st.selectbox("📅 統計月份", [f"{i:02d}" for i in range(1, 13)], 
                                  index=int(datetime.now().strftime("%m")) - 1)
    view_class = st.radio("👥 顯示班別", ["全部", "基礎班", "競技班"])

# --- 數據運算：流水帳轉月統計表 ---
if not raw_df.empty:
    calc_df = raw_df.copy()
    calc_df['日期_dt'] = pd.to_datetime(calc_df['日期'], errors='coerce')
    calc_df = calc_df.dropna(subset=['日期_dt'])
    calc_df['月份'] = calc_df['日期_dt'].dt.strftime('%m')
    
    monthly_data = calc_df[calc_df['月份'] == selected_month]
    
    if not monthly_data.empty:
        stats = monthly_data.groupby(['學生姓名', '班別']).agg(
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
else:
    stats = pd.DataFrame(columns=['學生姓名', '班別', '總堂數', '已上', '待補', '剩餘'])

# --- 第一區：統計卡片 ---
st.title("🏀 永平育樂營")
display_df = stats if view_class == "全部" else stats[stats['班別'] == view_class]

m1, m2, m3 = st.columns(3)
m1.metric("當月學員", f"{len(display_df)} 人")
m2.metric("累積上課", f"{int(display_df['已上'].sum()) if not display_df.empty else 0} 次")
m3.metric("待補總數", f"{int(display_df['待補'].sum()) if not display_df.empty else 0} 次")

# --- 第二區：點名提交 ---
with st.expander("📝 點名紀錄提交", expanded=True):
    op_class = st.radio("1. 選擇班別", ["基礎班", "競技班"], horizontal=True)
    all_known_students = sorted(raw_df['學生姓名'].unique().tolist()) if not raw_df.empty else []
    name = st.selectbox("2. 學員姓名", options=[""] + all_known_students)
    if name == "":
        name = st.text_input("或輸入新學員姓名")
    
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("今日狀態", ["出席", "缺席", "補課"])
        monthly_total = st.number_input("設定本月總堂數", min_value=1, value=8)
    with c2:
        date_val = st.date_input("點名日期", datetime.now())

    if st.button("🚀 提交紀錄"):
        if name:
            # 重複點名檢查
            if not raw_df.empty:
                raw_df['tmp_date'] = pd.to_datetime(raw_df['日期'], errors='coerce').dt.date
                is_dup = raw_df[(raw_df['學生姓名'] == name) & (raw_df['tmp_date'] == date_val)]
                if not is_dup.empty:
                    st.error(f"🚫 {name} 在 {date_val} 已經有點名紀錄了！")
                    st.stop()
            
            # 準備新資料列
            new_row = pd.DataFrame([{
                "日期": date_val.strftime("%Y-%m-%d"),
                "學生姓名": name,
                "班別": op_class,
                "狀態": status,
                "點名者": current_user,
                "當月總堂數": monthly_total
            }])
            
            # 清理暫存欄位並合併
            final_save_df = raw_df.drop(columns=['tmp_date']) if 'tmp_date' in raw_df.columns else raw_df
            updated_df = pd.concat([final_save_df, new_row], ignore_index=True)
            
            conn.update(spreadsheet=URL, data=updated_df)
            st.success(f"✅ {name} 紀錄成功！(點名者：{current_user})")
            st.rerun()

st.divider()

# --- 第三區：數據報表 ---
st.markdown(f"#### 📅 {selected_month} 月份統計報表")
st.dataframe(display_df[['班別', '學生姓名', '總堂數', '已上', '待補', '剩餘']], width=1000, hide_index=True)

# --- 個人詳細明細查詢 ---
st.markdown("---")
search_name = st.selectbox("🔍 查詢個人詳細紀錄", options=[""] + sorted(raw_df['學生姓名'].unique().tolist()) if not raw_df.empty else [""])
if search_name:
    personal_df = raw_df[raw_df['學生姓名'] == search_name].copy()
    personal_df['日期_dt'] = pd.to_datetime(personal_df['日期'], errors='coerce')
    personal_df = personal_df[personal_df['日期_dt'].dt.strftime('%m') == selected_month]
    
    if not personal_df.empty:
        st.info(f"🏀 **{search_name}** {selected_month} 月份詳細明細：")
        for _, row in personal_df.sort_values('日期').iterrows():
            st.write(f"🔹 {row['日期']} | {row['狀態']} | 點名者: {row['點名者']}")
    else:
        st.write("本月份尚無紀錄")
