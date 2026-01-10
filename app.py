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
        # 1.5 Pro is best for "Reasoning" and detail. Flash is faster but thinner.
        models = ["models/gemini-1.5-pro-latest", "models/gemini-1.5-pro", "models/gemini-1.5-flash"]
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
    Fetches MORE results (max_results=10) to ensure high detail.
    """
    with DDGS() as ddgs:
        for attempt in range(max_retries):
            try:
                # Increased to 10 to get deep context
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
    company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Agilent")
    
    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
            
        with st.spinner(f"Scanning entities for '{company_input}'..."):
            # SEARCH: Look for distinct entities
            q = f"{company_input} distinct legal entities headquarters investor relations"
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
        raw_units = opts[idx].get('units', [])
        combined_units = ["All / Full Company Overview"] + raw_units
        real_unit = st.selectbox("Select Business Unit:", combined_units)

    st.markdown("---")
    with st.expander("Add Deal Context", expanded=True):
        c1, c2 = st.columns(2)
        competitors = c1.text_input("Competitors", placeholder="e.g. Thermo Fisher")
        context = c2.text_input("Your Goal", placeholder="e.g. Selling CRM software")

    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Generating Deep-Dive for {real_company}..."):
            
            # 1. DEEP SEARCH STRATEGY
            search_dump = ""
            if "All" in real_unit:
                queries = [
                    f"{real_company} annual report 2024 CEO letter strategy outlook",
                    f"{real_company} investor presentation 2025 strategic priorities",
                    f"{real_company} Q3 2024 financial results transcript revenue growth",
                    f"{real_company} operational challenges restructuring risks 2025"
                ]
            else:
                queries = [
                    f"{real_company} {real_unit} revenue growth market share 2024",
                    f"{real_company} {real_unit} strategic focus innovation 2025",
                    f"{real_company} {real_unit} competitors comparison analysis"
                ]
            
            for q in queries:
                res = robust_search(q)
                if res:
                    search_dump += f"\nQuery: {q}\nData: {str(res)}\n"

            # 2. THE "HIGH FIDELITY" PROMPT
            final_prompt = f"""
            Role: Expert Enterprise Strategist.
            Target: **{real_company}** (Scope: **{real_unit}**).
            Competitors: {competitors}
            User Context: {context}
            
            RAW WEB DATA:
            {search_dump}
            
            INSTRUCTIONS FOR RICHNESS:
            1. **Expand & Connect:** Do not just list facts. Explain *why* they matter. Connect the web data to your internal knowledge of the company's long-term history and culture.
            2. **Fill the Gaps:** If the web data is thin on a specific number, use your internal training to describe the *strategic reality* of that unit (e.g., "While 2025 specific targets aren't public, this unit historically drives 40% of revenue through X strategy...").
            3. **Be Specific:** Name specific drugs, products, regions, or technologies whenever possible.
            
            PRODUCE THIS REPORT:
            
            ### 1. Business Health & Trajectory
            * **Growth Reality:** Go beyond "Stable." Are they in a super-cycle? A restructuring phase? A post-COVID slump? Cite revenue trends if available, or infer from industry context.
            * **Competitive Dynamics:** How do they actually stack up against {competitors}? Who is winning the innovation war?
            
            ### 2. Strategic Initiatives (Follow the Money)
            * Identify 3 concrete areas where they are spending money (e.g. New Factories, R&D in AI, M&A).
            * **The "Why":** For each initiative, explain the operational goal. (e.g., "Building a factory in Cork to bypass US tariffs").
            
            ### 3. The Risk Landscape
            * **Financial Pressure:** Are they cash-rich and buying? Or debt-heavy and cutting?
            * **Operational Friction:** Layoffs, supply chain issues, or leadership exits?
            
            ### 4. "Soft Signals" & Culture
            * What is the leadership vibe? (e.g., "New CEO focused on efficiency" vs "Founder-led innovation").
            * Hiring/Firing trends.
            
            Format: Comprehensive paragraphs and detailed bullet points. Avoid brevity.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Deep-Dive Analysis: {real_company}")
                st.markdown(report)
                
                with st.expander("🔎 Source Data Used"):
                    st.text(search_dump if search_dump else "Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
