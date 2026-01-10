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
        # We use 1.5 Pro to handle the complex "Mega Prompt" instructions
        models = ["models/gemini-1.5-pro", "models/gemini-1.5-pro-latest", "models/gemini-1.5-flash"]
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
                # 10 results to ensure we catch financial tables and leadership names
                results = [r for r in ddgs.text(query, max_results=10)]
                if results: return results
                time.sleep(0.5)
            except:
                time.sleep(1)
                continue
    return []

# --- APP FLOW ---
st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# STEP 1: IDENTIFICATION (Phase 1 of your Prompt)
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Solvias")
    
    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
            
        with st.spinner(f"Scanning for '{company_input}'..."):
            q = f"{company_input} corporate structure headquarters business units"
            results = robust_search(q)
            search_text = str(results)
            
            # Adaptive Prompt
            prompt = f"""
            Task: Analyze the search data for '{company_input}'.
            
            SCENARIO A: Ambiguous Name (e.g. "Merck") -> List distinct legal entities (US vs DE).
            SCENARIO B: Unique Name (e.g. "Solvias") -> List just the one company.
            
            Output: JSON list ONLY.
            Format: [{{ "name": "Full Legal Name", "description": "HQ/Type", "units": ["Unit 1", "Unit 2"] }}]
            
            Search Data: {search_text}
            """
            
            response = run_gemini(prompt)
            data = extract_json(response) if response else None
            
            if data:
                st.session_state.entity_options = data
                st.session_state.step = 2
                st.rerun()
            else:
                st.error("No data found. Try adding the HQ city.")

# STEP 2: DEEP DIVE (Phase 2 of your Prompt)
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    if not st.session_state.entity_options: st.warning("No data."); st.stop()

    col1, col2 = st.columns(2)
    with col1:
        opts = st.session_state.entity_options
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
            
            # 1. TARGETED SEARCH (Mapped to your Prompt Sections)
            search_dump = ""
            queries = [
                # Section A: Health
                f"{real_company} {real_unit} organic growth margin trend 2024 2025",
                # Section B: Initiatives
                f"{real_company} {real_unit} strategic priorities new facility investment 2025",
                f"{real_company} investor presentation 2025 capital expenditure projects",
                # Section C: Risk
                f"{real_company} restructuring costs layoffs WARN notice 2024 2025",
                f"{real_company} annual report risk factors 10-K 2024",
                # Section D: Soft Signals
                f"{real_company} leadership team changes CEO 2024 2025"
            ]
            
            for q in queries:
                res = robust_search(q)
                if res:
                    search_dump += f"\nQuery: {q}\nData: {str(res)}\n"

            # 2. THE EXACT "MEGA PROMPT"
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Task: Produce a "Zero-Fluff" competitive briefing for **{real_company}** (Unit: **{real_unit}**).
            Context: {context}
            Competitors: {competitors}
            
            RAW WEB DATA (Use this Priority #1):
            {search_dump}
            
            CONSTRAINT: Do NOT provide generic sales advice. If a data point is unavailable in the web data, USE YOUR INTERNAL KNOWLEDGE to estimate the strategic reality (e.g., typical margins for this industry), but mark it as "Inferred".
            
            GENERATE THIS REPORT:
            
            ### Section A: Business Unit Health & Competitor Mapping
            Create a table:
            | Metric | {real_unit} Performance | Competitor Signal |
            | :--- | :--- | :--- |
            | **Growth** | Organic Growth % (YoY) & Margin Trend (Cite data if found) | Growing faster or slower than {competitors}? |
            | **Market Share** | Gaining/Losing Share? | Who is the primary threat? |
            
            ### Section B: Strategic Initiatives (Follow the Money)
            Identify 2-3 "Funded" Priorities for this unit.
            * **Initiative Name:** (e.g. "Project Level Up", "New Factory in Cork").
            * **Evidence:** Cite the press release or source.
            * **Operational Goal:** What metric are they changing? (e.g. "Increase capacity 50%").
            
            ### Section C: Financial & Risk Reality
            * **Cash Flow:** Operating Cash Flow vs. Capex status.
            * **Layoff Radar:** Any WARN notices or "Restructuring Costs" in the last 12 months?
            * **Risk Factors:** Top 3 risks from the 10-K/Annual Report.
            
            ### Section D: "Soft Signal" Sentiment
            * **Leadership:** Recent changes in Division Heads or C-Suite.
            * **Hiring Patterns:** Are they opening new hubs or R&D centers?
            
            Format: Strict Markdown tables. Bullet points must be concise (under 15 words).
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                
                with st.expander("🔎 View Source Data"):
                    st.text(search_dump if search_dump else "Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
