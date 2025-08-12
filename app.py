import warnings
warnings.filterwarnings("ignore", message="Could not infer format.*")

import streamlit as st
import pandas as pd
import requests, re, urllib.parse
from io import BytesIO
from pathlib import Path
import datetime

st.set_page_config(page_title="ELC Public Records Directory", layout="wide")

DATA_PATH = Path(__file__).parent / "data" / "master.xlsx"

# ---------------------- NAV + STATE ----------------------
PAGES = ["📒 Directory", "🧭 Jurisdiction Finder", "🔎 OCULUS Search"]

# Router + form memory
if "active_page" not in st.session_state:
    st.session_state.active_page = PAGES[0]
if "pending_search" not in st.session_state:
    st.session_state.pending_search = None

# UI radio uses its own key; no default index -> no warning
if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = st.session_state.active_page

# When code changes pages (e.g., after Find), we sync radio before rendering
if "_sync_nav" not in st.session_state:
    st.session_state._sync_nav = False
if st.session_state._sync_nav:
    st.session_state.nav_choice = st.session_state.active_page
    st.session_state._sync_nav = False

# =============== Hard-coded templates (clean formatting) ===============
TEMPLATES = {
    "building": {
        "subject": "Freedom of Information Act (FOIA) Request/File Review Request",
        "body": """{county} Building Department

Address: {address}
Parcel ID#: {apn}
Project No. {project}

To whom it may concern:

Please accept this as a request for any information/documentation/files with your department regarding the above-referenced property.

I am currently conducting a Phase I Environmental Site Assessment for the above property. The ASTM Practice E1527 Standard Practice of Environmental Site Assessments requires that a records search be conducted with local regulatory departments for information regarding the subject property. Of particular interest are the following items:

- Permit summary (date, type of permit, applicant/tenant) or available permits from construction to present. Upon review of a permit summary we may request review of individual permits.
- Construction date (current building, previous buildings if applicable)
- List of tenants which have occupied the subject property
- Permits of environmental concern (petroleum storage tanks, septic systems, oil/water separators)
- Oldest and most recent site layout plan from the above mentioned property if available
- Erosion control plans on record for the subject property
- Record violations or complaints registered against the subject property

Please call (954-658-8177) or email (admin@envlogcon.com) me to discuss the file information or if you require further information. Thank you for your time and attention regarding this matter.
"""
    },
    "planning": {
        "subject": "Freedom of Information Act (FOIA) Request/File Review Request",
        "body": """{county} Planning Department

Address: {address}
Parcel ID#: {apn}
Project No. {project}

To whom it may concern:

Please accept this as a request for any information/documentation/files with your department regarding the above-referenced property.

I am currently conducting a Phase I Environmental Site Assessment for the above property. The ASTM Practice E1527 Standard Practice of Environmental Site Assessments requires that a records search be conducted with local regulatory departments for information regarding the subject property. Of particular interest are the following items:

- Record of any Activity Use Limitations (AULs) in connection with the property. An AUL is a legal or physical restriction or limitation on the use of, or access to, a site or facility. (1) to reduce or eliminate potential exposure to hazardous substances or petroleum products in the soil, soil vapor, groundwater, and/or surface water on the property, or (2) to prevent activities that could interfere with the effectiveness of a response action, in order to ensure maintenance of a condition of no significance risk to public health or the environment. These legal or physical restrictions, which may include institutional and/or engineering controls, are intended to prevent adverse impacts to individuals or populations that may be exposed to hazardous substances and petroleum products in the soil, soil vapor, groundwater, and/or surface water on a property. AULs are typically in place at sites which would prevent future uses of a property.
- Subject property zoning and any current zoning violations.

Please call (954-658-8177) or email (admin@envlogcon.com) me to discuss the file information or if you require further information. Thank you for your time and attention regarding this matter.
"""
    },
    "fire": {
        "subject": "Freedom of Information Act (FOIA) Request/File Review Request",
        "body": """{county} Fire Department

Address: {address}
Parcel ID#: {apn}
Project No. {project}

To whom it may concern:

Please accept this as a request for any information/documentation/files with your department regarding the above-referenced property.

I am currently conducting a Phase I Environmental Site Assessment for the above property. The ASTM Practice E1527 Standard Practice of Environmental Site Assessments requires that a records search be conducted with local regulatory departments for information regarding the subject property. Of particular interest are the following items:

- Records regarding hazardous materials usage/storage/incidents or fires at the property,
- Records regarding aboveground or underground storage tank (UST) systems, which are currently or historically located at the property,
- Records of fire inspections at the subject property.

Please call (954-658-8177) or email (admin@envlogcon.com) me to discuss the file information or if you require further information. Thank you for your time and attention regarding this matter.
"""
    },
    "environmental": {
        "subject": "Freedom of Information Act (FOIA) Request/File Review Request",
        "body": """{county} Environmental Department

Address: {address}
Parcel ID#: {apn}
Project No. {project}

To whom it may concern:

Please accept this as a request for any information/documentation/files with your department regarding the above-referenced property.

I am currently conducting a Phase I Environmental Site Assessment for the property. The ASTM Practice E1527 Standard Practice of Environmental Site Assessments requires that a records search be conducted with local regulatory departments for the following items:

- Records regarding hazardous materials usage/storage/incidents or known environmental concerns/contamination which may have affected the property,
- Records regarding aboveground or underground storage tank (UST) systems, which are currently or historically located at the property,
- Record of septic systems installation and repairs at the subject property, and/or
- Records of wells in connection with the subject property.

Please call (954-658-8177) or email (admin@envlogcon.com) me to discuss the file information or if you require further information. Thank you for your time and attention regarding this matter.
"""
    },
    "all": {
        "subject": "Freedom of Information Act (FOIA) Request/File Review Request",
        "body": """{county} County Clerk

Address: {address}
Parcel ID#: {apn}
Project No. {project}

To whom it may concern:

Please accept this as a request for any information/documentation/files with your department regarding the above-referenced property. ASTM Practice E1527 Standard Practice of Environmental Site Assessments requires that a records search be conducted with local regulatory departments for information regarding the subject property. Of particular interest are the following items:

Building Department
- Permit summary or available permits from construction to present. Upon review of a permit summary we may request review of individual permits. 
- Construction date (current building, previous buildings if applicable) 
- List of tenants which have occupied the subject property
- Oldest and most recent site layout plan from the above mentioned property if available
- Record violations or complaints registered against the subject property

Planning Department
- Record of any Activity Use Limitations (AULs) in connection with the property. AULs are typically in place at sites which would prevent future uses of a property.
- Subject property zoning and any current zoning violations.

Fire Department
- Records regarding hazardous materials incidents or fires at the property.
- Records of fire inspections at the subject property.

Environmental Department
- Records regarding hazardous materials usage/storage/incidents or known environmental concerns/contamination which may have affected the property,
- Records regarding aboveground or underground storage tank (UST) systems, which are currently or historically located at the property,  
- Record of septic systems installation and repairs at the subject property, and/or
- Records of wells in connection with the subject property.

"""
    },
}

# =============== Helpers ===============
def norm_county(val: str) -> str:
    if not isinstance(val, str): return ""
    v = val.strip().lower()
    v = re.sub(r"\s+county\b.*", "", v)
    v = v.replace("saint", "st").replace(".", "").strip()
    return v

def norm_city(val: str) -> str:
    if not isinstance(val, str): return ""
    v = val.strip().lower()
    v = v.replace("saint", "st").replace(".", "").strip()
    return v

@st.cache_data
def load_contacts(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    lower_map = {name.strip().lower(): name for name in xl.sheet_names}
    for candidate in ("contacts", "contact", "directory", "master", "data", "sheet1"):
        if candidate in lower_map:
            sheet = lower_map[candidate]; break
    else:
        sheet = xl.sheet_names[0]
        st.info(f"Using sheet '{sheet}' (no sheet named 'contacts' found).")

    df = xl.parse(sheet).copy()
    df.columns = [c.strip() for c in df.columns]

    rename_pairs = {
        "County": ["County"],
        "City": ["City", "Municipality", "Municipality / City", "Municipality/City"],
        "Dept Type": ["Dept Type", "Department Type", "Dept"],
        "Dept Name": ["Dept Name", "Department Name"],
        "Contact": ["Contact", "Contact Person"],
        "Title/Role": ["Title/Role", "Title", "Role"],
        "Phone": ["Phone", "Phone Number"],
        "Email": ["Email", "Emails"],
        "Portal URL": ["Portal URL", "Portal", "Public Records Portal", "Records Portal"],
        "Preferred Method": ["Preferred Method", "Method"],
        "Notes": ["Notes", "Note"],
        "Verified": ["Verified"],
        "Date Verified": ["Date Verified", "Verified Date", "Date Verified (YYYY-MM-DD)"],
    }

    rename_map = {}
    for std, alts in rename_pairs.items():
        for alt in alts:
            if alt in df.columns:
                rename_map[alt] = std; break
    df = df.rename(columns=rename_map)

    required = ["County", "City", "Dept Type", "Dept Name"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(
            "Your workbook is missing required columns: "
            f"{missing}. Found: {list(df.columns)}"
        )
        return pd.DataFrame(columns=required + [
            "Contact","Title/Role","Phone","Email","Portal URL",
            "Preferred Method","Notes","Verified","Date Verified"
        ])

    df = df.fillna("")
    df["_n_county"] = df["County"].astype(str).map(norm_county)
    df["_n_city"]   = df["City"].astype(str).map(norm_city)
    df["_n_dept"]   = df["Dept Type"].astype(str).str.strip().str.lower()
    return df

def geocode_address(addr: str):
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {"address": addr, "benchmark": "Public_AR_Current", "format": "json"}
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches: return None, "No geocoder match"
    m = matches[0]
    comps = m.get("addressComponents", {})
    geog = m.get("geographies", {})
    county = ""
    if geog:
        for k in ["Counties","County"]:
            if k in geog and geog[k]:
                county = geog[k][0].get("NAME", county)
    if not county:
        county = comps.get("county","")
    city = comps.get("city") or comps.get("municipality") or ""
    return {"city": city, "county": county, "state": comps.get("state","FL")}, None

def match_contacts(contacts, county, city):
    ncounty, ncity = norm_county(county), norm_city(city)
    in_county = contacts[contacts["_n_county"] == ncounty]
    exact     = in_county[in_county["_n_city"] == ncity]
    uninc     = in_county[in_county["_n_city"] == "unincorporated"]
    wildcard  = in_county[in_county["_n_city"] == "*"]
    if not exact.empty:
        return pd.concat([exact, wildcard], ignore_index=True).drop_duplicates(), True
    if not uninc.empty:
        return pd.concat([uninc, wildcard], ignore_index=True).drop_duplicates(), False
    if not wildcard.empty:
        return wildcard, False
    return contacts.iloc[0:0], False

def split_by_dept(df):
    out = {}
    for dep in ["building","planning","environmental","fire"]:
        out[dep] = df[df["_n_dept"]==dep]
    return out

def email_list(df):
    ems = []
    if "Email" in df.columns:
        for v in df["Email"].astype(str).tolist():
            if v.strip():
                ems += [p.strip() for p in v.split(",") if p.strip()]
    return sorted(set(ems))

def portal_urls(df):
    if "Portal URL" not in df.columns: return []
    urls = [str(u).strip() for u in df["Portal URL"].tolist() if str(u).strip()]
    seen=set(); out=[]
    for u in urls:
        if u not in seen:
            out.append(u); seen.add(u)
    return out

def _oculus_base_url() -> str:
    base = "https://depedms.dep.state.fl.us/Oculus/servlet/lookupUtility"
    params = {
        "catalog": "11",
        "profile": "Administrative",
        "CallingProperty": "Facility-Site ID",
        "process": "search",
    }
    return f"{base}?{urllib.parse.urlencode(params)}"

# =======================================================
contacts = load_contacts(DATA_PATH)

# ---------------------- NAV BAR ------------------------
st.title("ELC Public Records Directory")

st.radio(
    "Navigate",
    PAGES,
    horizontal=True,
    key="nav_choice",   # no index parameter -> no yellow warning
)
# Keep router in sync with the radio selection
st.session_state.active_page = st.session_state.nav_choice

# ---------------------- PAGES --------------------------
def page_directory():
    st.subheader("Directory")
    c1, c2, c3 = st.columns(3)
    with c1:
        counties = ["(All)"] + sorted(contacts["County"].unique().tolist())
        f_county = st.selectbox("County", counties)
    with c2:
        if f_county != "(All)":
            cities = ["(All)"] + sorted(contacts[contacts["County"]==f_county]["City"].unique().tolist())
        else:
            cities = ["(All)"] + sorted(contacts["City"].unique().tolist())
        f_city = st.selectbox("City/Municipality", cities)
    with c3:
        dept_types = ["(All)"] + sorted(contacts["Dept Type"].str.capitalize().unique().tolist())
        f_dept = st.selectbox("Department Type", dept_types)

    filtered = contacts.copy()
    if f_county != "(All)": filtered = filtered[filtered["County"]==f_county]
    if f_city != "(All)": filtered = filtered[filtered["City"]==f_city]
    if f_dept != "(All)": filtered = filtered[filtered["Dept Type"].str.capitalize()==f_dept]

    cols = [c for c in ["County","City","Dept Type","Dept Name","Contact","Title/Role","Phone","Email","Portal URL","Preferred Method","Notes","Verified","Date Verified"] if c in filtered.columns]
    st.dataframe(filtered[cols], use_container_width=True, height=460)

def _run_and_render_search(addr, county_override, municipality_override, apn, project):
    if not addr.strip():
        st.error("Address is required."); return
    with st.spinner("Geocoding & matching..."):
        info, err = geocode_address(addr + ", FL")
        if err and not county_override.strip() and not municipality_override.strip():
            st.error(err); return
        geocoded_city = (info or {}).get("city", "")
        geocoded_county = (info or {}).get("county", "")
        final_city = (municipality_override or "").strip() or geocoded_city
        final_county = (county_override or "").strip() or geocoded_county
        if not final_county:
            st.error("Could not determine county. Please provide a county override."); return

        st.success(f"Using jurisdiction: {final_city or '(unincorporated)'} — {final_county}")
        matched, _ = match_contacts(contacts, final_county, final_city)
        if matched.empty:
            st.warning("No contacts configured yet for this jurisdiction."); return

        depts = split_by_dept(matched)
        ctx = {"address": addr, "city": final_city, "county": final_county, "apn": apn, "project": project}

        for dep_key, dep_label in [("building","Building"),("planning","Planning"),("environmental","Environmental"),("fire","Fire")]:
            st.subheader(dep_label)
            df = depts.get(dep_key, pd.DataFrame())
            if df.empty:
                st.info("No contact configured in your workbook.")
                continue
            show = ["County","City","Dept Type","Dept Name","Contact","Email","Portal URL","Preferred Method","Notes"]
            show = [c for c in show if c in df.columns]
            st.dataframe(df[show], use_container_width=True)

            for url in portal_urls(df):
                st.link_button("Open Portal", url)

            tpl = TEMPLATES.get(dep_key)
            if tpl:
                subj = tpl["subject"]
                body = tpl["body"].format(**ctx)
                st.markdown("**Subject:** " + subj)
                st.text_area("Email body", body, height=260, key=f"body_{dep_key}")
                emails = email_list(df)
                if emails:
                    st.code(", ".join(emails))

        dept_emails_map = {
            "building": email_list(depts.get("building", pd.DataFrame())),
            "planning": email_list(depts.get("planning", pd.DataFrame())),
            "environmental": email_list(depts.get("environmental", pd.DataFrame())),
            "fire": email_list(depts.get("fire", pd.DataFrame())),
        }
        all_emails = sorted({e for lst in dept_emails_map.values() for e in lst})

        ctx_all = dict(ctx)
        ctx_all.update({
            "building_emails": ", ".join(dept_emails_map["building"]),
            "planning_emails": ", ".join(dept_emails_map["planning"]),
            "environmental_emails": ", ".join(dept_emails_map["environmental"]),
            "fire_emails": ", ".join(dept_emails_map["fire"]),
            "all_emails": ", ".join(all_emails),
        })

        st.subheader("All-in-one Email")
        tpl_all = TEMPLATES.get("all")
        if tpl_all:
            subj_all = tpl_all["subject"]
            body_all = tpl_all["body"].format(**ctx_all)
            st.markdown("**Subject:** " + subj_all)
            st.text_area("Email body (all depts)", body_all, height=260, key="body_all")
            if all_emails:
                st.code(", ".join(all_emails))
            else:
                st.info("No emails found to send an all-in-one request for this jurisdiction.")

def page_jurisdiction():
    st.subheader("Jurisdiction Finder")
    with st.form("req_form"):
        addr = st.text_input("Address*", placeholder="e.g., 17520 Rockefeller Circle, Fort Myers, FL 33967")
        county_override = st.text_input("County")
        municipality_override = st.text_input("City / Municipality")
        apn = st.text_input("APN / Parcel #", placeholder="e.g., 08-46-25-15-00008.0410")
        project = st.text_input("Project #", placeholder="e.g., 25-XXXX")
        submitted = st.form_submit_button("Find")

    if submitted:
        st.session_state.pending_search = {
            "addr": addr,
            "county_override": county_override,
            "municipality_override": municipality_override,
            "apn": apn,
            "project": project,
        }
        # programmatic nav: update router and tell radio to sync next run
        st.session_state.active_page = "🧭 Jurisdiction Finder"
        st.session_state._sync_nav = True
        st.rerun()

    # Render last (or current) search if any
    if st.session_state.pending_search:
        ps = st.session_state.pending_search
        _run_and_render_search(ps["addr"], ps["county_override"], ps["municipality_override"], ps["apn"], ps["project"])

def page_oculus():
    st.subheader("Florida DEP — OCULUS Quick Search")
    st.link_button("Open OCULUS Search", _oculus_base_url())
    with st.expander("Open OCULUS inside the app"):
        st.components.v1.iframe(_oculus_base_url(), height=620, scrolling=True)
    st.caption("Note: OCULUS doesn’t accept those field values via URL. "
               "Use the ‘Copy to OCULUS’ boxes above to paste Address and County into the OCULUS form, then click **Search**.")

# ---------------------- ROUTER -------------------------
page = st.session_state.active_page
if page == "📒 Directory":
    page_directory()
elif page == "🧭 Jurisdiction Finder":
    page_jurisdiction()
else:
    page_oculus()
