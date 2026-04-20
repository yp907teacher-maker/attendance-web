import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# 1. 網頁基本設定
st.set_page_config(page_title="永平籃球營-專業營運系統", page_icon="🏀", layout="wide")

# --- CSS 支援深色模式與自訂樣式 ---
st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 10px; }
    .stButton>button { 
        border-radius: 20px; background-color: #ff5722; color: white !important; 
        border: none; height: 3em; font-weight: bold; width: 100%;
    }
    .stButton>button:hover { background-color: #e64a19; }
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

# --- 數據運算：跨班別通用點數邏輯 ---
if not raw_df.empty:
    calc_df = raw_df.copy()
    calc_df['日期_dt'] = pd.to_datetime(calc_df['日期'], errors='coerce')
    calc_df = calc_df.dropna(subset=['日期_dt'])
    
    # 【關鍵修正】總額度計算：只根據「學生姓名」分組，不分班別
    total_stats_per_person = calc_df.groupby('學生姓名').apply(lambda x: pd.Series({
        '總出席': ((x['狀態'] == '出席') | (x['狀態'] == '補課')).sum(),
        '全課表總私假': ((x['狀態'] == '缺席') & (x['假別備註'].str.contains('私假', na=False))).sum(),
        '最後模式': x['收費模式'].iloc[-1]
    }), include_groups=False).reset_index()

    # 月份過濾
    calc_df['月份'] = calc_df['日期_dt'].dt.strftime('%m')
    monthly_data = calc_df[calc_df['月份'] == selected_month]
    
    if not monthly_data.empty:
        # 月統計報表仍按「姓名+班別」分開，以便了解學生去向
        m_stats = monthly_data.groupby(['學生姓名', '班別']).agg(
            月出席=('狀態', lambda x: (x == '出席').sum()),
            月缺席=('狀態', lambda x: (x == '缺席').sum()),
            月補課=('狀態', lambda x: (x == '補課').sum())
        ).reset_index()
        # 合併總額度數據 (認人不認班)
        stats = pd.merge(m_stats, total_stats_per_person, on='學生姓名', how='left')
    else:
        stats = pd.DataFrame(columns=['學生姓名', '班別', '月出席', '月缺席', '月補課', '總出席', '最後模式', '全課表總私假'])
else:
    stats = pd.DataFrame(columns=['學生姓名', '班別', '總出席', '全課表總私假'])

# --- 介面顯示 ---
st.title("永平籃球營點名系統 V3.3")

display_df = stats if view_class == "全部" else stats[stats['班別'] == view_class]
c1, c2, c3 = st.columns(3)
c1.metric("當月上課人次", len(display_df))
c2.metric("本月總補課", int(display_df['月補課'].sum()) if '月補課' in display_df else 0)
c3.metric("需注意缺席", int(display_df['月缺席'].sum()) if '月缺席' in display_df else 0)

# --- 點名提交 ---
with st.expander("📝 執行點名 / 請假登記", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        op_class = st.radio("1. 選擇班別", ["基礎班", "競技班", "興趣班"], horizontal=True)
        all_names = sorted(raw_df['學生姓名'].unique().tolist()) if not raw_df.empty else []
        name = st.selectbox("2. 學員姓名", options=[""] + all_names)
        if name == "": name = st.text_input("或輸入新學員姓名")
        mode = st.selectbox("3. 收費模式", ["一期(7-8天)", "任選10堂", "單堂體驗"])
        
    with col2:
        date_val = st.date_input("4. 點名日期", datetime.now())
        status = st.selectbox("5. 今日狀態", ["出席", "缺席", "補課"])
        note = "無"
        if status == "缺席":
            note = st.radio("請假類別", ["病假(附收據)", "私假(本期僅限1次)", "公假", "無故缺席"], horizontal=True)
        elif status == "補課":
            note = st.text_input("備註 (例如：補 3/1 缺課)")

    if st.button("🚀 確認提交紀錄"):
        if name:
            if not raw_df.empty:
                raw_df['tmp_date'] = pd.to_datetime(raw_df['日期'], errors='coerce').dt.date
                is_dup = raw_df[(raw_df['學生姓名'] == name) & (raw_df['班別'] == op_class) & (raw_df['tmp_date'] == date_val)]
                if not is_dup.empty:
                    st.error(f"🚫 {name} 今日在 {op_class} 已有點名紀錄！")
                    st.stop()
            
            new_row = pd.DataFrame([{
                "日期": date_val.strftime("%Y-%m-%d"),
                "學生姓名": name, "班別": op_class, "收費模式": mode,
                "狀態": status, "假別備註": note, "點名者": current_user
            }])
            
            final_save_df = raw_df.drop(columns=['tmp_date']) if 'tmp_date' in raw_df.columns else raw_df
            updated_df = pd.concat([final_save_df, new_row], ignore_index=True)
            conn.update(spreadsheet=URL, data=updated_df)
            st.success(f"✅ {name} 紀錄完成！")
            st.rerun()

st.divider()

# --- 數據報表 ---
st.subheader(f"📅 {selected_month} 月份統計")
if not display_df.empty:
    report_df = display_df.copy()
    if '最後模式' in report_df:
        # 此處計算剩餘堂數會反映跨班加總後的結果
        report_df['剩餘堂數(10堂制)'] = report_df.apply(
            lambda r: 10 - r['總出席'] if r['最後模式'] == "任選10堂" else "-", axis=1
        )
    show_cols = ['班別', '學生姓名', '月出席', '月缺席', '月補課', '剩餘堂數(10堂制)']
    st.dataframe(report_df[[c for c in show_cols if c in report_df.columns]], use_container_width=True, hide_index=True)

# --- 追蹤與預警 ---
st.subheader("🔍 學員個人請假與補課追蹤")
search_name = st.selectbox("選擇學員查看補課效期", options=[""] + all_names)
if search_name:
    p_df = raw_df[raw_df['學生姓名'] == search_name].copy()
    p_df['日期_dt'] = pd.to_datetime(p_df['日期'], errors='coerce')
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**📌 跨班缺席紀錄預警 (4週內需完成)**")
        absents = p_df[p_df['狀態'] == '缺席'].sort_values('日期')
        if absents.empty: st.write("無缺席紀錄")
        for _, row in absents.iterrows():
            deadline = row['日期_dt'] + timedelta(days=28)
            days_left = (deadline.date() - datetime.now().date()).days
            msg = f"{row['日期']} ({row['班別']}) | {row['假別備註']}"
            if days_left < 0:
                st.error(f"❌ {msg} (已過期 {abs(days_left)} 天)")
            else:
                st.warning(f"⚠️ {msg} (剩餘 {days_left} 天可補)")
    
    with col_b:
        st.write("**📊 全課表統計資訊**")
        total_p_leave = len(p_df[(p_df['狀態'] == '缺席') & (p_df['假別備註'].str.contains('私假', na=False))])
        if total_p_leave >= 1:
            st.error(f"該生本期已請私假 {total_p_leave} 次 (制度規定總限補 1 次)")
        else:
            st.success("該生本期尚未請過私假")
        
        last_mode = p_df['收費模式'].iloc[-1]
        total_finished = len(p_df[(p_df['狀態'] == '出席') | (p_df['狀態'] == '補課')])
        st.info(f"當前模式：{last_mode} / 累積已上：{total_finished} 堂")
