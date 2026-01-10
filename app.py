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
        # 1.5 Pro is best for complex JSON parsing
        models = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-2.0-flash-exp"]
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
        # Robust regex to find the largest list structure
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except: return None

def robust_search(query, max_retries=3):
    with DDGS() as ddgs:
        for attempt in range(max_retries):
            try:
                # Get more results to ensure we catch smaller companies
                results = [r for r in ddgs.text(query, max_results=8)]
                if results: return results
                time.sleep(0.5)
            except:
                time.sleep(1)
                continue
    return []

# --- APP FLOW ---
st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# STEP 1: ADAPTIVE IDENTIFICATION
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Solvias, Agilent")
    
    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
            
        with st.spinner(f"Scanning for '{company_input}'..."):
            # 1. Broad Search
            q = f"{company_input} corporate structure headquarters business units investor relations"
            results = robust_search(q)
            search_text = str(results)
            
            # 2. Adaptive Prompt
            prompt = f"""
            Task: Analyze the search data for '{company_input}'.
            
            SCENARIO A: Ambiguous Name (e.g. "Merck")
            - Return multiple objects for each distinct legal entity (e.g. Merck & Co US, Merck KGaA Germany).
            
            SCENARIO B: Unique Name (e.g. "Solvias")
            - Return a SINGLE object for that company.
            
            Output: JSON list ONLY.
            Format: 
            [
              {{ 
                "name": "Full Legal Name", 
                "description": "HQ Location / Core Business", 
                "units": ["List 3-5 Major Business Units found"] 
              }}
            ]
            
            Search Data: {search_text}
            """
            
            response = run_gemini(prompt)
            data = extract_json(response) if response else None
            
            if data:
                st.session_state.entity_options = data
                st.session_state.step = 2
                st.rerun()
            else:
                st.error(f"Could not structure data for '{company_input}'. Try adding the HQ city (e.g. 'Solvias Basel').")

# STEP 2: DEEP DIVE
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    if not st.session_state.entity_options: st.warning("No data."); st.stop()

    col1, col2 = st.columns(2)
    with col1:
        opts = st.session_state.entity_options
        names = [f"{o['name']} ({o['description']})" for o in opts]
        # If only 1 option, auto-select it
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
        context = c2.text_input("Your Goal", placeholder="e.g. Selling Lab Automation...")

    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Analyzing {real_company}..."):
            
            # 1. INTELLIGENT SEARCH
            search_dump = ""
            
            # Detect if it's a private company (like Solvias) or public
            if "All" in real_unit:
                queries = [
                    f"{real_company} investor relations annual report 2024 2025",
                    f"{real_company} press releases new facility investment 2025",
                    f"{real_company} strategic partnership announcements 2024",
                    f"{real_company} leadership changes CEO 2024 2025"
                ]
            else:
                queries = [
                    f"{real_company} {real_unit} revenue growth market share",
                    f"{real_company} {real_unit} new service launch 2025",
                    f"{real_company} {real_unit} competitor analysis {competitors}"
                ]
            
            for q in queries:
                res = robust_search(q)
                if res:
                    search_dump += f"\nQuery: {q}\nData: {str(res)}\n"

            # 2. "HIGH FIDELITY" PROMPT
            final_prompt = f"""
            Role: Expert Senior Sales Analyst.
            Target: **{real_company}** (Scope: **{real_unit}**).
            Competitors: {competitors}
            User Context: {context}
            
            RAW WEB DATA:
            {search_dump}
            
            INSTRUCTIONS:
            1. **Synthesis:** Combine the web data with your internal knowledge. 
               - If the company is Private (like Solvias), you won't find a 10-K. Instead, look for "Proxies" of growth: New factory openings, acquisitions, or hiring sprees.
            2. **Be Specific:** Do not just say "They are growing." Say "They expanded the North Carolina facility" (if true).
            3. **Fill Gaps:** If numbers are missing, explain the *Strategic Logic* of the unit based on industry standards.
            
            REPORT SECTIONS:
            
            ### 1. Business Health & Signals
            * **Growth Reality:** (e.g. "Aggressive Expansion" vs "Cost Cutting"). Cite evidence (e.g. New sites, M&A).
            * **Market Position:** Where do they fit vs {competitors}? (e.g. "Premium Niche Player" vs "Volume Leader").
            
            ### 2. Strategic Initiatives (Follow the Money)
            * List 3 concrete investments (Buildings, Tech, People).
            * **The Goal:** Why are they spending this money?
            
            ### 3. Risk & Friction
            * **Operational:** Integration pains? Regulatory hurdles?
            * **Financial:** Private Equity ownership pressure? (If PE owned).
            
            ### 4. "Soft Signals"
            * Culture vibe, Leadership focus, Hiring hot-spots.
            
            Format: Rich Markdown with clear headings.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                
                with st.expander("🔎 View Source Data"):
                    st.text(search_dump if search_dump else "Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
