import streamlit as st
import pandas as pd
import re
import os
import zipfile
import tempfile
from datetime import date, timedelta
from collections import Counter

# --- LOG PARSER CLASS ---
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
                    # Context Tracking
                    h_match = self.header_time_re.search(line)
                    if h_match: current_timestamp = h_match.group(1).strip()
                    
                    k_match = self.key_re.search(line)
                    if k_match: current_article = k_match.group(1).strip()

                    u_match = self.header_user_re.search(line)
                    if u_match: current_user = u_match.group(1).strip()

                    # Data Extraction
                    if "<b>" not in line: continue
                    m = self.data_re.search(line)
                    if not m: continue
                    
                    p = [x.strip().replace('"', '') for x in m.group(1).split(',')]

                    # Crimp Height
                    if "CrimpHeight =" in line and len(p) >= 5:
                        uid = f"{file_date}_{current_article}_{p[0]}_{p[1]}_{current_timestamp}"
                        status = "PASS" if p[2].upper() in ["TRUE", "PASS"] else "FAIL"
                        merged_data[uid] = {
                            "Date": file_date, "Time": current_timestamp, "User": current_user,
                            "Article": current_article, "Wire": p[0], "Terminal": p[1],
                            "Crimp_H": p[3], "Crimp_Stat": status,
                            "Pull_F": "---", "Pull_Stat": "---", "Len_Val": "---", "Len_Stat": "---"
                        }

                    # Pull Force
                    elif "PullOffForce =" in line and len(p) >= 4:
                        uid = f"{file_date}_{current_article}_{p[0]}_{p[1]}_{current_timestamp}"
                        status = "PASS" if p[2].upper() in ["TRUE", "PASS"] else "FAIL"
                        if uid in merged_data:
                            merged_data[uid].update({"Pull_Stat": status, "Pull_F": p[3]})
                        else:
                            merged_data[uid] = {
                                "Date": file_date, "Time": current_timestamp, "User": current_user,
                                "Article": current_article, "Wire": p[0], "Terminal": p[1],
                                "Crimp_H": "---", "Crimp_Stat": "---", "Pull_F": p[3], "Pull_Stat": status,
                                "Len_Val": "---", "Len_Stat": "---"
                            }

                    # Wire Length
                    elif "WireLength =" in line and len(p) >= 3:
                        uid = f"{file_date}_{current_article}_{p[0]}_LEN_{current_timestamp}"
                        status = "PASS" if p[1].upper() in ["TRUE", "PASS"] else "FAIL"
                        merged_data[uid] = {
                            "Date": file_date, "Time": current_timestamp, "User": current_user,
                            "Article": current_article, "Wire": p[0], "Terminal": "WIRE-LEN",
                            "Crimp_H": "---", "Crimp_Stat": "---", "Pull_F": "---", "Pull_Stat": "---",
                            "Len_Val": p[2], "Len_Stat": status
                        }
            return list(merged_data.values())
        except Exception:
            return []

# --- MAIN APP LOGIC ---
def main():
    st.set_page_config(page_title="Zeta Production Manager", layout="wide")
    
    st.title("🚀 Zeta Production Manager v5.0")
    st.markdown("Upload a ZIP file containing your production logs (YYYY/MM/DD structure).")

    # --- Sidebar ---
    st.sidebar.header("Data Source")
    uploaded_file = st.sidebar.file_uploader("Upload 'WPCS-Feedback.zip'", type="zip")
    
    st.sidebar.header("Filters")
    # Date Range Selection
    today = date.today()
    date_range = st.sidebar.date_input("Select Date Range", value=[today - timedelta(days=7), today])
    
    # --- Main Logic ---
    if uploaded_file:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Unzip
            with zipfile.ZipFile(uploaded_file, "r") as z:
                z.extractall(tmp_dir)
            
            # Process Data
            parser = LogParser()
            all_records = []
            
            if len(date_range) == 2:
                start_dt, end_dt = date_range
                
                with st.status("Parsing log files...") as status:
                    curr = start_dt
                    while curr <= end_dt:
                        # Folder path construction
                        # This looks for: ROOT/YEAR/MONTH/DAY/Production state data.htm
                        sub_path = os.path.join(curr.strftime("%Y"), curr.strftime("%m"), curr.strftime("%d"), "Production state data.htm")
                        
                        # We check the root of the zip and also one level deep (in case the zip contains a parent folder)
                        full_path = os.path.join(tmp_dir, sub_path)
                        alt_path = None
                        
                        # Find the file even if user zipped the folder itself or just the contents
                        if not os.path.exists(full_path):
                            for root, dirs, files in os.walk(tmp_dir):
                                if sub_path in os.path.join(root, sub_path):
                                    test_path = os.path.join(root, sub_path)
                                    if os.path.exists(test_path):
                                        full_path = test_path
                                        break

                        if os.path.exists(full_path):
                            st.write(f"🔎 Reading: {curr.isoformat()}")
                            all_records.extend(parser.parse_file(full_path, curr.isoformat()))
                        
                        curr += timedelta(days=1)
                    
                    status.update(label="Scanning complete!", state="complete")
            
            # --- Display Results ---
            if all_records:
                df = pd.DataFrame(all_records)
                
                # Global Statistics Metrics
                st.subheader("📊 Key Metrics")
                total = len(df)
                # Check for "FAIL" in any of the status columns
                fail_mask = (df['Crimp_Stat'] == "FAIL") | (df['Pull_Stat'] == "FAIL") | (df['Len_Stat'] == "FAIL")
                fail_count = len(df[fail_mask])
                yield_rate = ((total - fail_count) / total * 100) if total > 0 else 0
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Samples", total)
                m2.metric("Total Failures", fail_count, delta_color="inverse")
                m3.metric("Yield Rate", f"{yield_rate:.1f}%")

                # Filtering UI
                st.markdown("---")
                search = st.text_input("🔍 Search table (Article, User, Wire...)", "")
                if search:
                    df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]

                # Table Display with Conditional Formatting
                st.subheader("📋 Production Data")
                
                def highlight_fail(val):
                    return 'background-color: #ff4b4b; color: white' if val == "FAIL" else ''

                styled_df = df.style.applymap(highlight_fail, subset=['Crimp_Stat', 'Pull_Stat', 'Len_Stat'])
                st.dataframe(styled_df, use_container_width=True, height=600)

                # Export
                st.download_button(
                    label="📥 Download Filtered Data as CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name=f"Zeta_Report_{date.today()}.csv",
                    mime='text/csv'
                )
            else:
                st.info("No data found for the selected dates. Ensure your ZIP contains the YYYY/MM/DD folder structure.")
    else:
        st.info("👋 Welcome! Please upload your 'WPCS-Feedback' ZIP file in the sidebar to begin.")

if __name__ == "__main__":
    main()
