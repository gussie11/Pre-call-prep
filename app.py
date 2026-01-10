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
        models = ["models/gemini-2.0-flash-exp", "models/gemini-2.5-flash", "models/gemini-1.5-flash"]
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
    """
    Tries to search. If it fails or returns empty, waits and retries.
    """
    with DDGS() as ddgs:
        for attempt in range(max_retries):
            try:
                # Get results as a list immediately
                results = [r for r in ddgs.text(query, max_results=5)]
                if results:
                    return results
                time.sleep(1) # Wait 1s before retry
            except Exception as e:
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
            
        with st.spinner(f"Scanning global entities for '{company_input}'..."):
            # 1. Search
            q = f"{company_input} distinct legal entities headquarters business units"
            results = robust_search(q)
            search_text = str(results)
            
            # 2. Analyze
            prompt = f"""
            Task: Identify ALL distinct major corporate entities named '{company_input}'.
            Context: The user needs to distinguish between companies like Merck US vs Merck KGaA.
            
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
                st.error("No distinct entities found. Try adding the HQ location.")

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
        # FORCE "ALL" OPTION HERE
        raw_units = opts[idx].get('units', [])
        # We insert "All / Full Company" at the top of the list
        combined_units = ["All / Full Company Overview"] + raw_units
        real_unit = st.selectbox("Select Business Unit:", combined_units)

    st.markdown("---")
    with st.expander("Add Deal Context", expanded=True):
        c1, c2 = st.columns(2)
        competitors = c1.text_input("Competitors", placeholder="e.g. Thermo Fisher")
        context = c2.text_input("Your Goal", placeholder="e.g. Selling CRM software")

    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Analyzing {real_company}..."):
            
            # 1. SMART QUERY BUILDER
            search_dump = ""
            if "All" in real_unit:
                # Corporate Level Search
                queries = [
                    f"{real_company} investor relations annual report 2024 2025 strategy",
                    f"{real_company} revenue growth outlook 2025 financial results",
                    f"{real_company} corporate restructuring layoffs risks 2025"
                ]
            else:
                # Unit Level Search
                queries = [
                    f"{real_company} {real_unit} revenue growth financial results 2024 2025",
                    f"{real_company} {real_unit} strategic priorities investments 2025",
                    f"{real_company} {real_unit} layoffs restructuring risks 2025"
                ]
            
            found_data = False
            for q in queries:
                res = robust_search(q)
                if res:
                    found_data = True
                    search_dump += f"\nQuery: {q}\nData: {str(res)}\n"
            
            # Fallback
            if not found_data:
                fallback_q = f"{real_company} annual report 2024 business strategy"
                res = robust_search(fallback_q)
                search_dump += f"\nFallback Data: {str(res)}\n"

            # 2. HYBRID INTELLIGENCE PROMPT
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Target: **{real_company}** (Scope: **{real_unit}**).
            Competitors: {competitors}
            User Context: {context}
            
            LIVE WEB DATA (Use this Priority #1):
            {search_dump}
            
            INSTRUCTIONS:
            1. Analyze the web data to write a Competitive Briefing.
            2. **HYBRID BACKUP:** If the web data is missing specific details (like specific 2025 revenue), use your **INTERNAL KNOWLEDGE** of this company to fill in the context (e.g., their known historical strategy, typical risks, or market position).
            3. **Do NOT** say "I cannot answer." If data is thin, make reasonable strategic inferences based on the industry.
            
            SECTION A: Business Health
            - **Growth Signal**: Expanding, Stable, or Struggling? (Cite Web Data if available).
            - **Market Position**: Gaining or losing share?
            
            SECTION B: Strategic Initiatives (Follow the Money)
            - List 2-3 funded priorities (e.g. "New Factory in X", "AI Investment").
            - **Operational Goal**: What metric are they improving?
            
            SECTION C: Risks & Financials
            - **Layoff Radar**: Any restructuring or cost-cutting?
            - **Cash Position**: Investing or saving?
            
            SECTION D: "Soft Signals"
            - Leadership changes or hiring focuses.
            
            Format: Markdown Tables and Bullet Points. Concise.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                
                with st.expander("🔎 View Source Data (Verify Results)"):
                    st.text(search_dump if search_dump else "No raw data found. Used Internal Knowledge.")
            else:
                st.error("AI generation failed.")
