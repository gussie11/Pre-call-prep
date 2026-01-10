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
        st.rerun()

# --- 4. Helper Functions ---
def run_gemini(prompt):
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        # We use 1.5 Pro or Flash as they have good internal knowledge
        models = ["models/gemini-1.5-pro-latest", "models/gemini-1.5-flash", "models/gemini-2.0-flash-exp"]
        for m in models:
            try:
                model = genai.GenerativeModel(m)
                return model.generate_content(prompt).text
            except: continue
    except Exception as e:
        st.error(f"Config Error: {e}")
    return None

def extract_json(text):
    try:
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0]
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except: return None

def robust_search(query, max_retries=3):
    with DDGS() as ddgs:
        for attempt in range(max_retries):
            try:
                # Get results as a list
                results = [r for r in ddgs.text(query, max_results=4)]
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
    company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Agilent")
    
    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
            
        with st.spinner(f"Scanning entities for '{company_input}'..."):
            # SEARCH TRICK: Look for investor relations pages specifically
            q = f"{company_input} investor relations distinct legal entities headquarters"
            results = robust_search(q)
            search_text = str(results)
            
            prompt = f"""
            Task: Identify major corporate entities named '{company_input}'.
            Context: Distinguish between similar companies (e.g. Merck US vs Merck Germany).
            Search Data: {search_text}
            
            OUTPUT: JSON list ONLY.
            Format: [{{ "name": "Full Legal Name", "description": "HQ/Type", "units": ["Unit 1", "Unit 2"] }}]
            """
            
            response = run_gemini(prompt)
            data = extract_json(response) if response else None
            
            if data:
                st.session_state.entity_options = data
                st.session_state.step = 2
                st.rerun()
            else:
                st.error("No distinct entities found.")

# STEP 2: DEEP DIVE
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    if not st.session_state.entity_options: st.warning("No data."); st.stop()

    col1, col2 = st.columns(2)
    with col1:
        opts = st.session_state.entity_options
        names = [f"{o['name']} ({o['description']})" for o in opts]
        idx = st.radio("Select Legal Entity:", range(len(opts)), format_func=lambda x: names[x])
        real_company = opts[idx]['name']
    with col2:
        # "All" Option + Units
        raw_units = opts[idx].get('units', [])
        combined_units = ["All / Full Company Overview"] + raw_units
        real_unit = st.selectbox("Select Business Unit:", combined_units)

    st.markdown("---")
    with st.expander("Add Deal Context", expanded=True):
        c1, c2 = st.columns(2)
        competitors = c1.text_input("Competitors", placeholder="e.g. Thermo Fisher")
        context = c2.text_input("Your Goal", placeholder="e.g. Selling CRM software")

    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Analyzing {real_company}..."):
            
            # 1. TARGETED SEARCH (BETTER QUERIES)
            search_dump = ""
            
            # Use 'site:' operator to force official data sources if possible
            # We assume company name is unique enough, or we use the specific name found in Step 1
            if "All" in real_unit:
                queries = [
                    f"{real_company} investor relations presentation 2024 2025",
                    f"{real_company} annual report 2024 strategic priorities",
                    f"{real_company} financial results Q3 2024 revenue growth",
                    f"{real_company} restructuring layoffs cost savings 2025"
                ]
            else:
                queries = [
                    f"{real_company} {real_unit} revenue organic growth 2024",
                    f"{real_company} {real_unit} strategic focus areas 2025",
                    f"{real_company} {real_unit} competitor market share analysis"
                ]
            
            for q in queries:
                res = robust_search(q)
                if res:
                    search_dump += f"\nQuery: {q}\nData: {str(res)}\n"

            # 2. THE "ANALYST INSTINCT" PROMPT
            final_prompt = f"""
            Role: Expert Senior Sales Analyst.
            Target: **{real_company}** (Scope: **{real_unit}**).
            Competitors: {competitors}
            User Context: {context}
            
            LIVE WEB DATA (Use this Priority #1):
            {search_dump}
            
            CRITICAL INSTRUCTIONS:
            1. **Synthesis Strategy:** Use the Web Data for specific recent numbers (2024/2025).
            2. **Knowledge Fallback:** If the Web Data is thin (e.g. misses a specific growth %), YOU MUST USE YOUR INTERNAL KNOWLEDGE of {real_company} to fill the gaps.
               - Example: If search misses "Strategy", use your knowledge that {real_company} focuses on [Known Strategy].
               - Do NOT say "Data Unavailable" unless absolutely necessary.
               - Do NOT hallucinate fake numbers, but DO provide "General Strategic Direction" based on your training.
            
            REPORT SECTIONS:
            
            SECTION A: Business Health
            - **Growth Signal**: (e.g. Expanding/Stable). Use internal knowledge if web data is missing.
            - **Market Position**: Qualitative assessment against {competitors}.
            
            SECTION B: Strategic Initiatives (Follow the Money)
            - List 2-3 likely funded priorities (e.g. Digital Transformation, Capacity Expansion).
            - **Operational Goal**: Why are they doing this?
            
            SECTION C: Risks & Financials
            - **Layoff Radar**: Any known cost-cutting programs in this industry?
            - **Cash Position**: Investing vs Saving.
            
            SECTION D: "Soft Signals"
            - Hiring trends or leadership focus.
            
            Format: Markdown Tables and Bullet Points. Be confident.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                
                with st.expander("🔎 View Source Data"):
                    st.text(search_dump if search_dump else "No raw data found. Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
