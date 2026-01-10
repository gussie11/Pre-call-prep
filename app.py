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
        # 1.5 Pro is BEST for reasoning. Flash is fallback.
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
    """Robust JSON extractor for chatty AI responses."""
    try:
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0]
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except: return None

def robust_search(query, max_retries=3):
    """Fetches 10 results to ensure high context."""
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

# ==========================================
# STEP 1: IDENTIFICATION (Adaptive)
# ==========================================
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    company_input = st.text_input("Target Company Name", placeholder="e.g. Solvias, Merck")
    
    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
            
        with st.spinner(f"Scanning global entities for '{company_input}'..."):
            # Search for structure
            q = f"{company_input} corporate structure headquarters business units investor relations"
            results = robust_search(q)
            search_text = str(results)
            
            # Adaptive Prompt (Handles Unique AND Ambiguous names)
            prompt = f"""
            Task: Analyze the search data for '{company_input}'.
            
            SCENARIO A: Ambiguous Name (e.g. "Merck") -> List distinct legal entities (e.g. Merck US vs Merck DE).
            SCENARIO B: Unique Name (e.g. "Solvias") -> List just the one company found.
            
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
                st.error("No data found. Try adding the HQ city (e.g. 'Solvias Basel').")

# ==========================================
# STEP 2: DEEP DIVE (The "Mega Prompt")
# ==========================================
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    if not st.session_state.entity_options: st.warning("No data."); st.stop()

    col1, col2 = st.columns(2)
    with col1:
        opts = st.session_state.entity_options
        names = [f"{o['name']} ({o['description']})" for o in opts]
        # Auto-select first option if only one exists
        idx = st.radio("Select Legal Entity:", range(len(opts)), format_func=lambda x: names[x], index=0)
        real_company = opts[idx]['name']
    with col2:
        # Add "All" option for corporate overview
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
            
            # 1. TARGETED SEARCH (Mapped to Prompt Sections)
            search_dump = ""
            
            # Define queries based on scope
            if "All" in real_unit:
                queries = [
                    f"{real_company} investor presentation 2024 2025 strategic priorities",
                    f"{real_company} annual report 2024 revenue growth outlook",
                    f"{real_company} leadership team changes CEO 2024 2025",
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

            # 2. THE MEGA PROMPT (Hard-coded)
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Task: Produce a "Zero-Fluff" competitive briefing for **{real_company}** (Unit: **{real_unit}**).
            Context: {context}
            Competitors: {competitors}
            
            RAW WEB DATA (Priority #1):
            {search_dump}
            
            CRITICAL INSTRUCTION (The "Hybrid" Rule):
            1. Use the Web Data for specific recent numbers (2024/2025).
            2. **MISSING DATA FALLBACK:** If web data is thin (e.g. for private companies like Solvias), USE YOUR INTERNAL KNOWLEDGE to fill the gaps.
               - Example: If you can't find specific 2025 revenue, estimate the *Strategic Trajectory* based on your training (e.g. "Likely expanding in gene therapy").
               - Do NOT say "Data Unavailable" unless absolutely necessary.
            
            GENERATE THIS REPORT:
            
            ### Section A: Business Unit Health & Competitor Mapping
            | Metric | Assessment | Signal |
            | :--- | :--- | :--- |
            | **Growth** | (e.g. "Aggressive", "Stable", "Struggling") | Cited Revenue % or Strategic Inference. |
            | **Market Share** | Gaining/Losing vs {competitors}? | Primary Threat identified. |
            
            ### Section B: Main Customers & Markets (Who pays the bills?)
            * **Key Segments:** Who are they selling to? (e.g. Big Pharma, Biotech, Academia).
            * **Reference Customers:** List specific names if found (e.g. Pfizer, Vertex) OR infer likely client types based on their services.
            * **Buying Behavior:** Why do they buy? (e.g. "Buying for Speed" vs "Buying for Compliance").
            
            ### Section C: Strategic Initiatives (Follow the Money)
            Identify 2-3 "Funded" Priorities.
            * **Initiative:** (e.g. "New Factory in X", "Acquisition of Y").
            * **Operational Goal:** What metric are they changing? (e.g. "Increase capacity").
            
            ### Section D: Financial & Risk Reality
            * **Cash/Capex:** Investing heavily or cost-cutting?
            * **Layoff Radar:** Any restructuring/WARN notices?
            * **Risk Factors:** Top risks (e.g. Supply Chain, Regulatory).
            
            ### Section E: "Soft Signal" Sentiment
            * **Leadership:** Key names (CEO, Heads of Unit).
            * **Culture/Hiring:** Are they hiring for sales/R&D?
            
            Format: Strict Markdown tables. Bullet points must be concise.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                
                with st.expander("🔎 View Source Data"):
                    st.text(search_dump if search_dump else "Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
