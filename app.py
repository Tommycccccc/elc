
import warnings
warnings.filterwarnings("ignore", message="Could not infer format.*")

import streamlit as st
import pandas as pd
from io import BytesIO
from pathlib import Path
import datetime

st.set_page_config(page_title="Public Records Directory — Hard-Coded XLSX", layout="wide")

# Location of the master file committed with the app
DEFAULT_PATH = Path(__file__).parent / "data" / "master.xlsx"

# Pinned filters if present in the sheet
PINNED_FILTERS = ["County", "City/Municipality", "Department Type"]

def infer_type(series: pd.Series):
    s = series.astype(str).str.strip()
    parsed = pd.to_datetime(s.replace({"": None, "nan": None}), errors="coerce")
    if parsed.notna().mean() >= 0.6:
        return "date"
    lower = s.str.lower()
    uniq = set(lower.unique())
    if uniq.issubset({"true","false","yes","no","y","n","1","0",""}):
        return "bool"
    nums = pd.to_numeric(s, errors="coerce")
    if nums.notna().mean() >= 0.8:
        return "number"
    nonempty = s[s.ne("")]
    if not nonempty.empty and nonempty.nunique() <= max(10, len(nonempty)//10):
        return "category"
    return "text"

@st.cache_data
def load_df_from_file(path: Path):
    if not path.exists():
        st.error(f"Master XLSX not found at: {path}. Upload one-time below or add data/master.xlsx to the repo.")
        st.stop()
    df = pd.read_excel(path).fillna("")
    df.columns = [c.strip() for c in df.columns]
    return df

def to_xlsx_bytes(df):
    from io import BytesIO
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf

st.title("📒 ELC Public Records Directory")
st.caption("Loads the committed Excel at **data/master.xlsx** so end users don't need to upload anything.")

# Always load from the hard-coded file first
if "df" not in st.session_state:
    st.session_state.df = load_df_from_file(DEFAULT_PATH)

# Optional: allow a temporary per-session override upload (for testing)
with st.sidebar.expander("Optional: Test a different XLSX FIle (only affects your session)"):
    uploaded = st.file_uploader("Upload XLSX (optional)", type=["xlsx"])
    if uploaded is not None:
        tmp = pd.read_excel(uploaded).fillna("")
        tmp.columns = [c.strip() for c in tmp.columns]
        st.session_state.df = tmp
        st.success("Using uploaded file for this session only. Reload the page to revert to data/master.xlsx.")

df = st.session_state.df.copy()

st.sidebar.header("Filters")
filtered = df.copy()

# Pinned filters
for col in PINNED_FILTERS:
    if col in df.columns:
        vals = ["(All)"] + sorted([v for v in df[col].unique().tolist() if str(v) != ""])
        sel = st.sidebar.selectbox(col, vals, key=f"pin_{col}")
        if sel != "(All)":
            filtered = filtered[filtered[col] == sel]

# Dynamic filters for all columns
with st.sidebar.expander("More filters (all columns)", expanded=False):
    for col in df.columns:
        if col in PINNED_FILTERS:
            continue
        if (df[col] == "").all():
            continue
        col_type = infer_type(df[col])
        if col_type == "category":
            options = sorted([v for v in df[col].unique().tolist() if str(v) != ""])
            selected = st.multiselect(f"{col}", options, default=[], key=f"cat_{col}")
            if selected:
                filtered = filtered[filtered[col].isin(selected)]
        elif col_type == "bool":
            choice = st.selectbox(f"{col}", ["(All)","Yes","No"], key=f"bool_{col}")
            if choice != "(All)":
                yes_set = {"true","yes","y","1"}
                col_l = filtered[col].astype(str).str.strip().str.lower()
                mask = col_l.isin(yes_set)
                filtered = filtered[mask] if choice == "Yes" else filtered[~mask]
        elif col_type == "number":
            nums = pd.to_numeric(df[col].astype(str).str.strip(), errors="coerce")
            if nums.notna().any():
                mn = float(nums.min()); mx = float(nums.max())
                rng = st.slider(f"{col} range", min_value=mn, max_value=mx, value=(mn, mx), key=f"num_{col}")
                nums_f = pd.to_numeric(filtered[col].astype(str).str.strip(), errors="coerce")
                filtered = filtered[(nums_f >= rng[0]) & (nums_f <= rng[1])]
        elif col_type == "date":
            dt_full = pd.to_datetime(df[col].astype(str).str.strip().replace({"": None, "nan": None}),
                                     errors="coerce")
            if dt_full.notna().any():
                min_d = dt_full.min().date(); max_d = dt_full.max().date()
                sel = st.date_input(f"{col} range", value=(min_d, max_d), key=f"date_{col}")
                if isinstance(sel, tuple) and len(sel) == 2:
                    start, end = sel
                    dt_filtered = pd.to_datetime(filtered[col].astype(str).str.strip().replace({"": None, "nan": None}),
                                                 errors="coerce")
                    mask = (dt_filtered >= pd.to_datetime(start)) & (dt_filtered <= pd.to_datetime(end))
                    filtered = filtered[mask]
        else:
            q = st.text_input(f"Search in {col}", key=f"text_{col}")
            if q:
                filtered = filtered[filtered[col].astype(str).str.contains(q, case=False, na=False)]

st.subheader("Results")
st.dataframe(filtered, use_container_width=True, height=460)

with st.expander("📧 Emails in current view"):
    if "Email" in filtered.columns:
        emails = sorted({e.strip() for row in filtered["Email"].tolist()
                         for e in (str(row).split(",")) if str(row).strip()})
        st.code(", ".join(emails) if emails else "(no emails)")
    else:
        st.info("No 'Email' column in sheet.")

with st.expander("🔗 Portal URLs in current view"):
    if "Public Records Portal URL" in filtered.columns:
        urls = [u for u in filtered["Public Records Portal URL"].tolist() if str(u).strip()]
        st.code("\n".join(urls) if urls else "(no portal URLs)")
    else:
        st.info("No 'Public Records Portal URL' column in sheet.")

