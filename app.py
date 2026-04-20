import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# 1. 網頁基本設定
st.set_page_config(page_title="永平籃球營-專業營運系統", page_icon="🏀", layout="wide")

# --- CSS 樣式 ---
st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 10px; }
    .stButton>button { 
        border-radius: 20px; background-color: #ff5722; color: white !important; 
        border: none; height: 3em; font-weight: bold; width: 100%;
    }
    .stButton>button:hover { background-color: #e64a19; }
    .student-card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 15px;
        background-color: rgba(128, 128, 128, 0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# 2. 建立連線
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1ThX8dzMdz-JRCIked4ad3YC8s8BMfipdjKDwSrkZpeM/edit?usp=sharing"

# 3. 讀取資料
try:
    raw_df = conn.read(spreadsheet=URL, ttl=0)
    if raw_df is None or raw_df.empty or '日期' not in raw_df.columns:
        raw_df = pd.DataFrame(columns=['日期', '學生姓名', '班別', '收費模式', '狀態', '假別備註', '點名者'])
except Exception:
    st.error("⚠️ 系統連線異常")
    st.stop()

# --- 側邊欄控制 ---
with st.sidebar:
    st.header("🏀 營運選單")
    staff_list = ["教練1", "教練2", "教練3", "教練4", "教練5"]
    current_user = st.selectbox("🙋 當前點名教練", staff_list)
    st.divider()
    selected_month = st.selectbox("📅 統計月份", [f"{i:02d}" for i in range(1, 13)], 
                                  index=int(datetime.now().strftime("%m")) - 1)
    view_class = st.radio("👥 顯示班別", ["全部", "基礎班", "競技班", "興趣班"])

# --- 數據運算 ---
if not raw_df.empty:
    calc_df = raw_df.copy()
    calc_df['日期_dt'] = pd.to_datetime(calc_df['日期'], errors='coerce')
    calc_df = calc_df.dropna(subset=['日期_dt'])
    
    # 全歷史數據 (認人不認班，計算共享額度)
    total_stats_per_person = calc_df.groupby('學生姓名').apply(lambda x: pd.Series({
        '總出席': ((x['狀態'] == '出席') | (x['狀態'] == '補課')).sum(),
        '最後模式': x['收費模式'].iloc[-1],
        '最後班別': x['班別'].iloc[-1]
    }), include_groups=False).reset_index()

    # 月份過濾
    calc_df['月份'] = calc_df['日期_dt'].dt.strftime('%m')
    monthly_data = calc_df[calc_df['月份'] == selected_month]
    
    if not monthly_data.empty:
        m_stats = monthly_data.groupby(['學生姓名']).agg(
            月出席=('狀態', lambda x: (x == '出席').sum()),
            月缺席=('狀態', lambda x: (x == '缺席').sum()),
            月補課=('狀態', lambda x: (x == '補課').sum()),
            本月上課班別=('班別', lambda x: ", ".join(x.unique()))
        ).reset_index()
        stats = pd.merge(m_stats, total_stats_per_person, on='學生姓名', how='left')
    else:
        stats = pd.DataFrame()
else:
    stats = pd.DataFrame()

# --- 介面顯示 ---
st.title("永平籃球營點名系統 V3.5")

# --- 點名提交 ---
with st.expander("📝 快速點名 / 請假登記", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        op_class = st.radio("1. 選擇班別", ["基礎班", "競技班", "興趣班"], horizontal=True)
        all_names = sorted(raw_df['學生姓名'].unique().tolist()) if not raw_df.empty else []
        name = st.selectbox("2. 學員姓名", options=[""] + all_names)
        if name == "": name = st.text_input("或輸入新學員姓名")
        
        # 修正後的收費模式選項
        mode = st.selectbox("3. 收費模式", ["一期(8天)", "一期(7天)", "任選10堂", "單堂體驗"])
    with col2:
        date_val = st.date_input("4. 點名日期", datetime.now())
        status = st.selectbox("5. 今日狀態", ["出席", "缺席", "補課"])
        note = "無"
        if status == "缺席":
            note = st.radio("請假類別", ["病假(附收據)", "私假(本期僅限1次)", "公假", "無故缺席"], horizontal=True)
        elif status == "補課":
            note = st.text_input("備註 (例如：補 3/1 缺課)")

    if st.button("🚀 確認提交"):
        if name:
            new_row = pd.DataFrame([{
                "日期": date_val.strftime("%Y-%m-%d"), "學生姓名": name, "班別": op_class, 
                "收費模式": mode, "狀態": status, "假別備註": note, "點名者": current_user
            }])
            updated_df = pd.concat([raw_df, new_row], ignore_index=True)
            conn.update(spreadsheet=URL, data=updated_df)
            st.success(f"✅ {name} 紀錄完成！")
            st.rerun()

st.divider()

# --- 數據報表：個人條列式卡片 ---
st.subheader(f"📅 {selected_month} 月份學員進度報告")

if not stats.empty:
    display_stats = stats if view_class == "全部" else stats[stats['本月上課班別'].str.contains(view_class)]
    
    if display_stats.empty:
        st.write("此班別本月暫無紀錄。")
    else:
        for _, row in display_stats.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="student-card">
                    <span style="font-size: 1.2em; font-weight: bold;">👤 {row['學生姓名']}</span> 
                    <span style="margin-left: 10px; color: #ff5722; font-size: 0.9em;">[{row['本月上課班別']}]</span>
                    <hr style="margin: 10px 0; border: 0.5px solid rgba(128,128,128,0.2);">
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"📅 **本月出席**：{int(row['月出席'])} 次")
                c2.write(f"⚠️ **本月缺席**：{int(row['月缺席'])} 次")
                c3.write(f"🩹 **本月補課**：{int(row['月補課'])} 次")
                
                # 自動判斷模式並計算剩餘堂數
                current_mode = row['最後模式']
                total_attended = int(row['總出席'])
                
                if current_mode == "任選10堂":
                    base = 10
                elif current_mode == "一期(8天)":
                    base = 8
                elif current_mode == "一期(7天)":
                    base = 7
                else:
                    base = None
                
                if base:
                    left = base - total_attended
                    color = "red" if left <= 1 else "green"
                    c4.markdown(f"🔥 **剩餘額度**：<span style='color:{color}; font-weight:bold; font-size:1.2em;'>{left}</span> / {base} 堂", unsafe_allow_html=True)
                else:
                    c4.write(f"📝 **模式**：{current_mode}")

else:
    st.info("尚無統計資料。")

st.divider()

# --- 詳細查詢 (保留底部功能) ---
search_name = st.selectbox("🔍 選擇學員查看詳細歷史與補課效期", options=[""] + all_names)
if search_name:
    p_df = raw_df[raw_df['學生姓名'] == search_name].copy()
    p_df['日期_dt'] = pd.to_datetime(p_df['日期'], errors='coerce')
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**📌 補課效期預警 (4週內)**")
        absents = p_df[p_df['狀態'] == '缺席'].sort_values('日期')
        for _, row in absents.iterrows():
            deadline = row['日期_dt'] + timedelta(days=28)
            days_left = (deadline.date() - datetime.now().date()).days
            if days_left < 0:
                st.error(f"❌ {row['日期']} ({row['班別']}) | 已過期")
            else:
                st.warning(f"⚠️ {row['日期']} ({row['班別']}) | 剩餘 {days_left} 天")
    with col_b:
        st.write("**📊 歷史統計**")
        total_p_leave = len(p_df[(p_df['狀態'] == '缺席') & (p_df['假別備註'].str.contains('私假', na=False))])
        st.write(f"累積私假：{total_p_leave} 次")
        st.info(f"當前模式：{p_df['收費模式'].iloc[-1]}")
