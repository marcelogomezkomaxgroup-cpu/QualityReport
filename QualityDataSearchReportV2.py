import streamlit as st
import pandas as pd
import re
import os
from datetime import date, timedelta
from collections import Counter

# --- LOG PARSER (Same logic, refined for DataFrames) ---
class LogParser:
    def __init__(self):
        self.header_time_re = re.compile(r"LearnStarted\s*\(\s*(.*?)\)")
        self.header_user_re = re.compile(r"UserName = <font.*?><b>(.*?)</b></font>")
        self.key_re = re.compile(r"ArticleKey = <font.*?><b>(.*?)</b></font>")
        self.data_re = re.compile(r"<b>(.*?)</b>")

    def parse_file(self, filepath, file_date):
        merged_data = {}
        if not os.path.exists(filepath): return []
        
        current_article, current_timestamp, current_user = "Unknown", "Unknown", "Unknown"
        
        try:
            with open(filepath, 'r', encoding='latin-1') as file:
                for line in file:
                    h_match = self.header_time_re.search(line)
                    if h_match: current_timestamp = h_match.group(1).strip()
                    
                    k_match = self.key_re.search(line)
                    if k_match: current_article = k_match.group(1).strip()

                    u_match = self.header_user_re.search(line)
                    if u_match: current_user = u_match.group(1).strip()

                    if "<b>" not in line: continue
                    m = self.data_re.search(line)
                    if not m: continue
                    
                    p = [x.strip().replace('"', '') for x in m.group(1).split(',')]

                    # Logic for Crimp, Pull, and Length
                    if "CrimpHeight =" in line and len(p) >= 5:
                        uid = f"{file_date}_{current_article}_{p[0]}_{p[1]}_{current_timestamp}"
                        status = "PASS" if p[2].upper() in ["TRUE", "PASS"] else "FAIL"
                        merged_data[uid] = {
                            "Date": file_date, "Time": current_timestamp, "User": current_user,
                            "Article": current_article, "Wire": p[0], "Terminal": p[1],
                            "Crimp_H": p[3], "Crimp_Stat": status,
                            "Pull_F": None, "Pull_Stat": None, "Len_Val": None, "Len_Stat": None
                        }
                    elif "PullOffForce =" in line and len(p) >= 4:
                        uid = f"{file_date}_{current_article}_{p[0]}_{p[1]}_{current_timestamp}"
                        status = "PASS" if p[2].upper() in ["TRUE", "PASS"] else "FAIL"
                        if uid in merged_data:
                            merged_data[uid].update({"Pull_Stat": status, "Pull_F": p[3]})
                        else:
                            merged_data[uid] = {
                                "Date": file_date, "Time": current_timestamp, "User": current_user,
                                "Article": current_article, "Wire": p[0], "Terminal": p[1],
                                "Crimp_H": None, "Crimp_Stat": None, "Pull_F": p[3], "Pull_Stat": status,
                                "Len_Val": None, "Len_Stat": None
                            }
                    elif "WireLength =" in line and len(p) >= 3:
                        uid = f"{file_date}_{current_article}_{p[0]}_LEN_{current_timestamp}"
                        status = "PASS" if p[1].upper() in ["TRUE", "PASS"] else "FAIL"
                        merged_data[uid] = {
                            "Date": file_date, "Time": current_timestamp, "User": current_user,
                            "Article": current_article, "Wire": p[0], "Terminal": "WIRE-LEN",
                            "Crimp_H": None, "Crimp_Stat": None, "Pull_F": None, "Pull_Stat": None,
                            "Len_Val": p[2], "Len_Stat": status
                        }
            return list(merged_data.values())
        except Exception:
            return []

# --- STREAMLIT UI ---
st.set_page_config(page_title="Zeta Production Manager", layout="wide")

st.title("🚀 Zeta Production Manager v5.0")
st.markdown("---")

# Sidebar Configuration
st.sidebar.header("Settings")
root_dir = st.sidebar.text_input("Log Path", value=r"E:\CreatedPrograms\PythonProjects\Zeta_Programs\WPCS-Feedback")
date_range = st.sidebar.date_input("Date Range", value=[date.today(), date.today()])

# Helper to load data
@st.cache_data
def get_data(path, start_dt, end_dt):
    parser = LogParser()
    all_records = []
    curr = start_dt
    while curr <= end_dt:
        # Build path: Year/Month/Day/File
        p = os.path.join(path, curr.strftime("%Y"), curr.strftime("%m"), curr.strftime("%d"), "Production state data.htm")
        if os.path.exists(p):
            all_records.extend(parser.parse_file(p, curr.isoformat()))
        curr += timedelta(days=1)
    return pd.DataFrame(all_records)

# Load Data
if st.sidebar.button("Search Records"):
    if len(date_range) == 2:
        df = get_data(root_dir, date_range[0], date_range[1])
        st.session_state['raw_df'] = df
    else:
        st.error("Please select a valid start and end date.")

if 'raw_df' in st.session_state and not st.session_state['raw_df'].empty:
    df = st.session_state['raw_df']

    # --- Statistics Section ---
    st.subheader("📊 Production Overview")
    total_count = len(df)
    
    # Logic to find any failures across columns
    fail_mask = (df['Crimp_Stat'] == "FAIL") | (df['Pull_Stat'] == "FAIL") | (df['Len_Stat'] == "FAIL")
    fail_count = len(df[fail_mask])
    yield_rate = ((total_count - fail_count) / total_count * 100) if total_count > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Processed", total_count)
    col2.metric("Total Failures", fail_count, delta_color="inverse")
    col3.metric("Yield Rate", f"{yield_rate:.1f}%")

    # --- Filtering ---
    st.markdown("---")
    search_query = st.text_input("🔍 Filter Table (Article, User, Wire...)", "")
    
    if search_query:
        # Simple search across all columns
        df_display = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
    else:
        df_display = df

    # --- Data Display ---
    # We style the dataframe to highlight FAILures in red
    def highlight_fail(val):
        color = '#ff4b4b' if val == "FAIL" else None
        return f'background-color: {color}'

    styled_df = df_display.style.applymap(highlight_fail, subset=['Crimp_Stat', 'Pull_Stat', 'Len_Stat'])
    
    st.dataframe(styled_df, use_container_width=True, height=500)

    # --- Actions ---
    st.subheader("📥 Export")
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name=f"Zeta_Export_{date.today()}.csv",
        mime='text/csv',
    )
    
    # Top Failing Articles list
    if fail_count > 0:
        st.warning("⚠️ Top Failing Articles")
        fail_articles = Counter(df[fail_mask]['Article']).most_common(5)
        for art, count in fail_articles:
            st.write(f"- **{art}**: {count} failures")

elif 'raw_df' in st.session_state:
    st.info("No records found for the selected criteria.")
else:
    st.info("Set the path and date range in the sidebar, then click 'Search Records'.")
