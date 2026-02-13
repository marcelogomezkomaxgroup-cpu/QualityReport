import re
import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import date, timedelta
from collections import Counter

# --- CONFIGURATION ---
DEFAULT_FILENAME = "Production state data.htm"

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

class ZetaMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Zeta Production Manager v5.0")
        self.root.geometry("1600x900")
        self.root.configure(bg="#2c3e50")
        
        self.parser = LogParser()
        self.root_dir = tk.StringVar(value=r"E:\CreatedPrograms\PythonProjects\Zeta_Programs\WPCS-Feedback")
        self.data_records = [] # All data found
        self.display_records = [] # Data currently shown (filtered)
        
        self.cols = ("Date", "Time", "User", "Article", "Wire", "Terminal", 
                     "Crimp_H", "Crimp_Stat", "Pull_F", "Pull_Stat", "Len_Val", "Len_Stat")
        
        self._setup_ui()

    def _setup_ui(self):
        # --- Top Control Bar ---
        ctrl = tk.Frame(self.root, bg="#34495e", pady=15, padx=15); ctrl.pack(fill=tk.X)
        
        # Row 1: Search Settings
        r1 = tk.Frame(ctrl, bg="#34495e"); r1.pack(fill=tk.X, pady=5)
        tk.Label(r1, text="LOG PATH:", bg="#34495e", fg="#ecf0f1", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        tk.Entry(r1, textvariable=self.root_dir, width=50).pack(side=tk.LEFT, padx=10)
        tk.Button(r1, text="Browse", command=self.browse, bg="#95a5a6").pack(side=tk.LEFT)
        
        tk.Label(r1, text="DATE RANGE:", bg="#34495e", fg="#f1c40f", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(20, 5))
        self.start_in = tk.Entry(r1, width=12); self.start_in.insert(0, date.today().isoformat()); self.start_in.pack(side=tk.LEFT)
        tk.Label(r1, text="to", bg="#34495e", fg="white").pack(side=tk.LEFT, padx=5)
        self.end_in = tk.Entry(r1, width=12); self.end_in.insert(0, date.today().isoformat()); self.end_in.pack(side=tk.LEFT)
        
        tk.Button(r1, text="SEARCH RECORDS", command=self.run_search, bg="#2ecc71", fg="white", font=("Segoe UI", 9, "bold"), padx=10).pack(side=tk.LEFT, padx=20)

        # Row 2: Filter & Report
        r2 = tk.Frame(ctrl, bg="#34495e", pady=5); r2.pack(fill=tk.X)
        tk.Label(r2, text="FILTER TABLE:", bg="#34495e", fg="#3498db", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", self.update_filter)
        tk.Entry(r2, textvariable=self.filter_var, width=40, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=10)

        # Report Buttons
        btn_style = {"font": ("Segoe UI", 9, "bold"), "fg": "white", "padx": 15}
        tk.Button(r2, text="Export CSV", command=self.export_csv, bg="#9b59b6", **btn_style).pack(side=tk.RIGHT, padx=5)
        tk.Button(r2, text="Generate HTML Report", command=self.export_html, bg="#e67e22", **btn_style).pack(side=tk.RIGHT, padx=5)

        # --- Data Table ---
        frame = tk.Frame(self.root); frame.pack(expand=True, fill='both', padx=15, pady=10)
        self.tree = ttk.Treeview(frame, columns=self.cols, show='headings')

        headers = {
            "Date": "Date", "Time": "Time", "User": "Operator", "Article": "Article", 
            "Wire": "Wire", "Terminal": "Terminal", 
            "Crimp_H": "Crimp H", "Crimp_Stat": "C-Stat", 
            "Pull_F": "Pull F", "Pull_Stat": "P-Stat", 
            "Len_Val": "Length", "Len_Stat": "L-Stat"
        }

        for col in self.cols:
            self.tree.heading(col, text=headers[col], command=lambda c=col: self.sort_column(c, False))
            w = 180 if col in ["Article", "Wire"] else 80
            self.tree.column(col, width=w, anchor="center" if w < 100 else "w")
        
        vsb = ttk.Scrollbar(frame, command=self.tree.yview); vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview); hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set); self.tree.pack(fill='both', expand=True)
        
        self.tree.tag_configure('FAIL', background='#c0392b', foreground='white')
        self.tree.tag_configure('even', background='#ecf0f1')

    def browse(self):
        d = filedialog.askdirectory()
        if d: self.root_dir.set(d)

    def run_search(self):
        self.data_records = []
        try:
            curr, e_dt = date.fromisoformat(self.start_in.get()), date.fromisoformat(self.end_in.get())
            while curr <= e_dt:
                p = os.path.join(self.root_dir.get(), curr.strftime("%Y"), curr.strftime("%m"), curr.strftime("%d"), DEFAULT_FILENAME)
                if os.path.exists(p): self.data_records.extend(self.parser.parse_file(p, curr.isoformat()))
                curr += timedelta(days=1)
            self.display_records = self.data_records
            self.refresh_table(self.display_records)
            if not self.data_records: messagebox.showinfo("Result", "No files found in that range.")
        except Exception as e: messagebox.showerror("Search Error", str(e))

    def update_filter(self, *args):
        val = self.filter_var.get().lower()
        if not self.data_records: return
        self.display_records = [r for r in self.data_records if any(val in str(v).lower() for v in r.values())]
        self.refresh_table(self.display_records)

    def refresh_table(self, data):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(data):
            f_cols = [r.get('Crimp_Stat'), r.get('Pull_Stat'), r.get('Len_Stat')]
            is_fail = any(x == "FAIL" for x in f_cols)
            tag = 'FAIL' if is_fail else ('even' if i % 2 == 0 else 'odd')
            self.tree.insert('', tk.END, values=[r.get(c, "") for c in self.cols], tags=(tag,))

    def export_csv(self):
        if not self.display_records: return
        f = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"Zeta_RawData_{date.today()}.csv")
        if f:
            with open(f, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=self.cols)
                writer.writeheader()
                writer.writerows(self.display_records)
            messagebox.showinfo("Success", "CSV Exported.")

    def export_html(self):
        if not self.display_records: return
        f = filedialog.asksaveasfilename(defaultextension=".html", initialfile=f"Zeta_Report_{date.today()}.html")
        if not f: return

        # Statistics
        total = len(self.display_records)
        fails = [r for r in self.display_records if "FAIL" in [r['Crimp_Stat'], r['Pull_Stat'], r['Len_Stat']]]
        fail_count = len(fails)
        yield_pct = ((total - fail_count) / total * 100) if total > 0 else 0
        
        # Most Common Failures
        fail_articles = [r['Article'] for r in fails]
        top_fails = Counter(fail_articles).most_common(3)

        # HTML Generation
        html = f"""
        <!DOCTYPE html>
        <html><head><title>Zeta Production Report</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f4f7f6; color: #333; }}
            .header {{ background: #2c3e50; color: white; padding: 25px; border-radius: 8px; margin-bottom: 30px; }}
            h1 {{ margin: 0; font-size: 24px; }}
            .stats-row {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; flex: 1; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 4px solid #3498db; }}
            .card.fail {{ border-top-color: #e74c3c; }}
            .card.yield {{ border-top-color: #2ecc71; }}
            .big-num {{ font-size: 32px; font-weight: bold; margin-top: 5px; }}
            .fail-list {{ background: #fff0f0; padding: 15px; border-radius: 8px; border: 1px solid #ffcccc; margin-bottom: 30px; }}
            table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; font-size: 14px; }}
            th {{ background: #34495e; color: white; padding: 12px 8px; text-align: left; }}
            td {{ padding: 10px 8px; border-bottom: 1px solid #eee; }}
            tr:nth-child(even) {{ background: #f9f9f9; }}
            .badge {{ padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; display: inline-block; width: 40px; text-align: center; }}
            .pass {{ background: #d4edda; color: #155724; }}
            .fail {{ background: #f8d7da; color: #721c24; }}
        </style>
        </head><body>
            <div class="header">
                <h1>Zeta Production Quality Report</h1>
                <p>Range: {self.start_in.get()} to {self.end_in.get()} | Filter: "{self.filter_var.get()}"</p>
            </div>
            
            <div class="stats-row">
                <div class="card"><div>Total Processed</div><div class="big-num">{total}</div></div>
                <div class="card fail"><div>Total Failures</div><div class="big-num">{fail_count}</div></div>
                <div class="card yield"><div>Yield Rate</div><div class="big-num">{yield_pct:.1f}%</div></div>
            </div>

            <div class="fail-list">
                <h3>⚠️ Top Failing Articles</h3>
                <ul>
                    {''.join([f"<li><b>{k}</b>: {v} Failures</li>" for k,v in top_fails]) if top_fails else "<li>No failures found! Great job!</li>"}
                </ul>
            </div>

            <table>
                <thead><tr>
                    <th>Date</th><th>User</th><th>Article</th><th>Wire</th><th>Crimp</th><th>Pull</th><th>Length</th>
                </tr></thead>
                <tbody>
        """
        
        for r in self.display_records:
            # Badge Logic
            c_cls = "pass" if r['Crimp_Stat'] == "PASS" else ("fail" if r['Crimp_Stat'] == "FAIL" else "")
            p_cls = "pass" if r['Pull_Stat'] == "PASS" else ("fail" if r['Pull_Stat'] == "FAIL" else "")
            l_cls = "pass" if r['Len_Stat'] == "PASS" else ("fail" if r['Len_Stat'] == "FAIL" else "")

            # Only show badge if value exists
            c_html = f"<span class='badge {c_cls}'>{r['Crimp_H']}</span>" if c_cls else "---"
            p_html = f"<span class='badge {p_cls}'>{r['Pull_F']}</span>" if p_cls else "---"
            l_html = f"<span class='badge {l_cls}'>{r['Len_Val']}</span>" if l_cls else "---"

            html += f"""
                <tr>
                    <td>{r['Date']} {r['Time']}</td>
                    <td>{r['User']}</td>
                    <td>{r['Article']}</td>
                    <td>{r['Wire']}</td>
                    <td>{c_html}</td>
                    <td>{p_html}</td>
                    <td>{l_html}</td>
                </tr>"""
        
        html += "</tbody></table></body></html>"
        
        with open(f, 'w', encoding='utf-8') as file: file.write(html)
        messagebox.showinfo("Report Ready", f"Dashboard saved to:\n{f}")

    def sort_column(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        try: l.sort(key=lambda t: float(t[0]) if t[0].replace('.','',1).isdigit() else t[0].lower(), reverse=reverse)
        except: l.sort(reverse=reverse)
        for i, (v, k) in enumerate(l): self.tree.move(k, '', i)
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

if __name__ == "__main__":
    root = tk.Tk(); app = ZetaMonitorApp(root); root.mainloop()