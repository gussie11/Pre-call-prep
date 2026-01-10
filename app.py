import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import json
import re
import time

# --- 1. Page Config ---
st.set_page_config(page_title="Sales Prep Analyst", page_icon="🕵️‍♂️", layout="wide")

# --- 2. Session State ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "entity_options" not in st.session_state:
    st.session_state.entity_options = []
if "manual_entry" not in st.session_state:
    st.session_state.manual_entry = False

# --- 3. Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ Key loaded from Secrets")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
    
    if st.button("🔄 Start New Search"):
        st.session_state.step = 1
        st.session_state.entity_options = []
        st.session_state.manual_entry = False
        st.rerun()

# --- 4. Helper Functions ---
def run_gemini(prompt):
    if not api_key: return None, "No API Key"
    try:
        genai.configure(api_key=api_key)
        # UPDATED MODEL LIST: Prioritizing the models you definitely have access to
        models = [
            "models/gemini-2.0-flash-exp", 
            "models/gemini-2.5-flash", 
            "models/gemini-1.5-pro", 
            "models/gemini-1.5-pro-latest", 
            "models/gemini-1.5-flash"
        ]
        
        errors = []
        for m in models:
            try:
                model = genai.GenerativeModel(m)
                response = model.generate_content(prompt)
                return response.text, None # Success
            except Exception as e:
                errors.append(f"{m}: {str(e)}")
                continue
        
        return None, errors # Return all errors if all failed
        
    except Exception as e:
        return None, str(e)

def extract_json(text):
    try:
        text = re.sub(r"```json|```", "", text).strip()
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except: return None

def robust_search(query, max_retries=2):
    with DDGS() as ddgs:
        for attempt in range(max_retries):
            try:
                results = [r for r in ddgs.text(query, max_results=10)]
                if results: return results
                time.sleep(0.5)
            except:
                time.sleep(1)
                continue
    return []

# --- APP FLOW ---
st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# STEP 1: IDENTIFICATION
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    
    col_input, col_manual = st.columns([3, 1])
    with col_input:
        company_input = st.text_input("Target Company Name", placeholder="e.g. Solvias, Merck")
    with col_manual:
        st.write("") 
        st.write("") 
        if st.button("Skip & Enter Manually"):
            st.session_state.manual_entry = True
            st.session_state.entity_options = [{"name": company_input if company_input else "Target Company", "description": "Manual Entry", "units": ["General / All Units"]}]
            st.session_state.step = 2
            st.rerun()

    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
        
        with st.spinner(f"Scanning for '{company_input}'..."):
            # 1. Search
            q = f"{company_input} corporate structure business units investor relations"
            results = robust_search(q)
            search_text = str(results)
            
            # 2. Analyze
            prompt = f"""
            Task: Extract corporate entities for '{company_input}' from: {search_text}
            
            SCENARIO A (Ambiguous): If multiple distinct companies exist (e.g. Merck US vs Merck DE), list both.
            SCENARIO B (Unique): If only one company is found (e.g. Solvias), list just that one.
            
            Output JSON ONLY:
            [ {{ "name": "Legal Name", "description": "HQ/Type", "units": ["Unit 1", "Unit 2"] }} ]
            """
            
            response_text, error_msg = run_gemini(prompt)
            data = extract_json(response_text) if response_text else None
            
            if data:
                st.session_state.entity_options = data
                st.session_state.step = 2
                st.rerun()
            else:
                st.error("AI could not parse the data.")
                if error_msg:
                    with st.expander("View Error Log"):
                        st.write(error_msg)

# STEP 2: DEEP DIVE
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    opts = st.session_state.entity_options
    
    if st.session_state.get("manual_entry"):
        st.info("⚠️ Manual Mode Active")
        col1, col2 = st.columns(2)
        with col1:
            real_company = st.text_input("Confirm Company Name:", value=opts[0]['name'])
        with col2:
            real_unit = st.text_input("Business Unit / Focus Area:", value="General Overview")
    else:
        col1, col2 = st.columns(2)
        with col1:
            names = [f"{o['name']} ({o['description']})" for o in opts]
            idx = st.radio("Select Legal Entity:", range(len(opts)), format_func=lambda x: names[x], index=0)
            real_company = opts[idx]['name']
        with col2:
            raw_units = opts[idx].get('units', [])
            combined_units = ["All / Full Company Overview"] + raw_units
            real_unit = st.selectbox("Select Business Unit:", combined_units)

    st.markdown("---")
    with st.expander("Add Deal Context", expanded=True):
        c1, c2 = st.columns(2)
        competitors = c1.text_input("Competitors", placeholder="e.g. Thermo Fisher")
        context = c2.text_input("Your Goal", placeholder="e.g. Selling Lab Automation")

    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Running 'Zero-Fluff' Analysis for {real_company}..."):
            
            # 1. SEARCH
            search_dump = ""
            if "All" in real_unit or st.session_state.get("manual_entry"):
                queries = [
                    f"{real_company} investor presentation 2024 2025 strategic priorities",
                    f"{real_company} annual report 2024 revenue growth outlook",
                    f"{real_company} leadership team CEO management changes 2024 2025",
                    f"{real_company} restructuring layoffs new facility investment 2025",
                    f"{real_company} major customers partnerships case studies"
                ]
            else:
                queries = [
                    f"{real_company} {real_unit} revenue growth market share 2024",
                    f"{real_company} {real_unit} strategic initiatives new products 2025",
                    f"{real_company} {real_unit} competitors comparison {competitors}",
                    f"{real_company} {real_unit} leadership management team"
                ]
            
            for q in queries:
                res = robust_search(q)
                if res:
                    search_dump += f"\nQuery: {q}\nData: {str(res)}\n"

            # 2. MEGA PROMPT
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Task: Produce a "Zero-Fluff" competitive briefing for **{real_company}** (Unit: **{real_unit}**).
            Context: {context}
            Competitors: {competitors}
            
            RAW WEB DATA (Priority #1):
            {search_dump}
            
            CRITICAL INSTRUCTION:
            1. Use Web Data for recent numbers (2024/2025).
            2. **MISSING DATA FALLBACK:** If web data is thin, USE YOUR INTERNAL KNOWLEDGE to fill gaps. 
               - Estimate strategic trajectory based on industry norms.
               - Do NOT say "Data Unavailable" unless absolutely necessary.
            
            GENERATE THIS REPORT:
            
            ### Section A: Business Unit Health & Competitor Mapping
            | Metric | Assessment | Signal |
            | :--- | :--- | :--- |
            | **Growth** | (e.g. "Aggressive", "Stable") | Cited Revenue % or Strategic Inference. |
            | **Market Share** | Gaining/Losing vs {competitors}? | Primary Threat. |
            
            ### Section B: Main Customers & Markets
            * **Key Segments:** Who do they sell to?
            * **Reference Customers:** Specific names or likely client types.
            * **Buying Behavior:** Why do they buy?
            
            ### Section C: Strategic Initiatives
            Identify 2-3 "Funded" Priorities.
            * **Initiative:** (e.g. "New Factory", "Acquisition").
            * **Goal:** What metric are they changing?
            
            ### Section D: Financial & Risk Reality
            * **Cash/Capex:** Investing or saving?
            * **Layoff Radar:** Restructuring/WARN notices?
            * **Risk Factors:** Top risks.
            
            ### Section E: "Soft Signal" Sentiment
            * **Leadership:** Key names (CEO, Heads).
            * **Culture/Hiring:** Hiring trends?
            
            Format: Markdown tables.
            """
            
            report_text, error_msg = run_gemini(final_prompt)
            
            if report_text:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report_text)
                with st.expander("🔎 View Source Data"):
                    st.text(search_dump if search_dump else "Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
                if error_msg:
                    with st.expander("View Debug Logs"):
                        st.write(error_msg)
