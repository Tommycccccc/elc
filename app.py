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
def load_contacts(path: Path):
    xl = pd.ExcelFile(path)
    contacts = xl.parse("contacts").fillna("")
    contacts.columns = [c.strip() for c in contacts.columns]
    contacts["_n_county"] = contacts["County"].map(norm_county)
    contacts["_n_city"]   = contacts["City"].map(norm_city)
    contacts["_n_dept"]   = contacts["Dept Type"].astype(str).str.strip().str.lower()
    return contacts

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
    exact = contacts[(contacts["_n_county"]==ncounty) & (contacts["_n_city"]==ncity)]
    if not exact.empty: return exact, True
    uninc = contacts[(contacts["_n_county"]==ncounty) & (contacts["_n_city"]=="unincorporated")]
    if not uninc.empty: return uninc, False
    anyc  = contacts[(contacts["_n_county"]==ncounty) & (contacts["_n_city"]=="*")]
    if not anyc.empty: return anyc, False
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

def make_mailto(to_emails, subject, body):
    to = ",".join(to_emails)
    qs = urllib.parse.urlencode({"subject": subject, "body": body})
    return f"mailto:{to}?{qs}"

def portal_urls(df):
    if "Portal URL" not in df.columns: return []
    urls = [str(u).strip() for u in df["Portal URL"].tolist() if str(u).strip()]
    seen=set(); out=[]
    for u in urls:
        if u not in seen:
            out.append(u); seen.add(u)
    return out

# =============== App ===============
contacts = load_contacts(DATA_PATH)

tab1, tab2 = st.tabs(["📒 Directory", "🧭 Jurisdiction Finder"])

with tab1:
    st.header("ELC Public Records Directory")
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

with tab2:
    st.header("Jurisdiction Finder")
    with st.form("req_form"):
        addr = st.text_input("Address*", placeholder="e.g., 17520 Rockefeller Circle, Fort Myers, FL 33967")
        county_override = st.text_input("County")
        apn = st.text_input("APN / Parcel #", placeholder="e.g., 08-46-25-15-00008.0410")
        project = st.text_input("Project #", placeholder="e.g., 25-XXXX")
        submitted = st.form_submit_button("Find")

    if submitted:
        if not addr.strip():
            st.error("Address is required.")
        else:
            with st.spinner("Geocoding & matching..."):
                info, err = geocode_address(addr + ", FL")
                if county_override.strip():
                    info = info or {}
                    info["county"] = county_override.strip()
                if err and not county_override.strip():
                    st.error(err)
                else:
                    city, county = info.get("city",""), info.get("county","")
                    st.success(f"Matched to: {city} — {county}")
                    matched, incorporated = match_contacts(contacts, county, city)
                    if matched.empty:
                        st.warning("No contacts configured yet for this jurisdiction.")
                    else:
                        depts = split_by_dept(matched)
                        ctx = {"address": addr, "city": city, "county": county, "apn": apn, "project": project}

                        for dep_key, dep_label in [("building","Building"),("planning","Planning"),("environmental","Environmental"),("fire","Fire")]:
                            st.subheader(dep_label)
                            df = depts.get(dep_key, pd.DataFrame())
                            if df.empty:
                                st.info("No contact configured in your workbook.")
                                continue
                            show = ["County","City","Dept Type","Dept Name","Contact","Email","Portal URL","Preferred Method","Notes"]
                            show = [c for c in show if c in df.columns]
                            st.dataframe(df[show], use_container_width=True)

                            # Portal buttons (from sheet)
                            for url in portal_urls(df):
                                st.link_button("Open Portal", url)

                            # Email
                            tpl = TEMPLATES.get(dep_key)
                            if tpl:
                                subj = tpl["subject"]
                                body = tpl["body"].format(**ctx)
                                st.markdown("**Subject:** " + subj)
                                st.text_area("Email body", body, height=260, key=f"body_{dep_key}")
                                emails = email_list(df)
                                if emails:
                                    st.code(", ".join(emails))

                        # ---------- All-in-one Email (after the four depts) ----------
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
