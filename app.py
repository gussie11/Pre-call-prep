import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import json
import re
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Sales Prep Analyst", page_icon="🕵️‍♂️", layout="wide")

if "step" not in st.session_state: st.session_state.step = 1
if "entity_options" not in st.session_state: st.session_state.entity_options = []
if "manual_entry" not in st.session_state: st.session_state.manual_entry = False

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

# --- 2. HELPER FUNCTIONS ---
def run_gemini(prompt):
    if not api_key: return None, "No API Key"
    try:
        genai.configure(api_key=api_key)
        models = ["models/gemini-1.5-pro", "models/gemini-1.5-pro-latest", "models/gemini-1.5-flash"]
        for m in models:
            try:
                model = genai.GenerativeModel(m)
                return model.generate_content(prompt).text, None
            except: continue
        return None, "All models failed"
    except Exception as e:
        return None, str(e)

def extract_json(text):
    try:
        text = re.sub(r"```json|```", "", text).strip()
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except: return None

def robust_search(query, max_results=5):
    with DDGS() as ddgs:
        try:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            if results: return results
        except: pass
        time.sleep(0.5)
        try:
            # Fallback to simpler query
            results = [r for r in ddgs.text(query.split(" 20")[0], max_results=max_results)]
            if results: return results
        except: pass
    return []

def execute_dragnet(company, unit):
    """
    Runs parallel search agents on the CONFIRMED target.
    """
    raw_text = ""
    
    # 1. Financials / Structure
    if "All" in unit:
        q_fin = [
            f"{company} investor relations annual report 2024 2025",
            f"{company} financial results revenue growth 2024",
            f"{company} corporate structure ownership private equity" # Catch private owners
        ]
    else:
        q_fin = [
            f"{company} {unit} revenue growth financial results",
            f"{company} {unit} market share competitor analysis"
        ]
    
    # 2. Strategy / News (The "Growth" Signals)
    q_news = [
        f"{company} press release 2024 2025 new facility expansion",
        f"{company} strategic priorities investor presentation 2025",
        f"{company} acquisition partnership announcement 2025"
    ]
    
    # 3. People / Risk
    q_risk = [
        f"{company} leadership team CEO appointment 2024",
        f"{company} layoffs restructuring cost savings 2025"
    ]

    all_queries = q_fin + q_news + q_risk
    
    # Run the searches
    for q in all_queries:
        res = robust_search(q, max_results=4)
        if res:
            for item in res:
                raw_text += f"\nSOURCE: {item['title']} ({item['href']})\nCONTENT: {item['body']}\n"
    
    return raw_text

# --- 3. APP FLOW ---
st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# STEP 1: IDENTIFICATION (The Gatekeeper)
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    
    col_input, col_manual = st.columns([3, 1])
    with col_input:
        company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Solvias")
    with col_manual:
        st.write(""); st.write("")
        if st.button("Skip & Manual Entry"):
            st.session_state.manual_entry = True
            st.session_state.entity_options = [{"name": company_input if company_input else "Target Company", "description": "Manual Entry", "units": ["General / All Units"]}]
            st.session_state.step = 2
            st.rerun()

    if st.button("Find Account", type="primary"):
        if not api_key: st.error("❌ Need API Key"); st.stop()
        
        with st.spinner(f"Scanning for '{company_input}'..."):
            # Search for Structure
            q = f"{company_input} corporate structure headquarters business units investor relations"
            results = robust_search(q, max_results=8)
            search_text = str(results)
            
            if not results:
                st.error("No results found. Try Manual Entry.")
                st.stop()

            # AI Disambiguation
            prompt = f"""
            Task: Identify corporate entities for '{company_input}' from: {search_text}
            
            SCENARIO A (Ambiguous): If multiple distinct companies exist (e.g. Merck US vs Merck DE), LIST BOTH separately.
            SCENARIO B (Unique/Private): If only one company found (e.g. Solvias), list just that one.
            
            Output JSON ONLY:
            [ {{ "name": "Legal Name", "description": "HQ/Type", "units": ["Unit 1", "Unit 2"] }} ]
            """
            
            response, error = run_gemini(prompt)
            data = extract_json(response) if response else None
            
            if data:
                st.session_state.entity_options = data
                st.session_state.step = 2
                st.rerun()
            else:
                st.error("AI parsing failed. Try Manual Entry.")

# STEP 2: DEEP DIVE (The Dragnet)
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    opts = st.session_state.entity_options
    
    if st.session_state.get("manual_entry"):
        st.info("⚠️ Manual Mode")
        col1, col2 = st.columns(2)
        with col1: real_company = st.text_input("Company:", value=opts[0]['name'])
        with col2: real_unit = st.text_input("Unit:", value="General Overview")
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
        with st.spinner(f"Running Dragnet Search on {real_company}..."):
            
            # 1. EXECUTE DRAGNET (The Robust Search)
            raw_intel = execute_dragnet(real_company, real_unit)
            
            # 2. THE MEGA PROMPT (Restored)
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Task: Produce a "Zero-Fluff" competitive briefing for **{real_company}** (Unit: **{real_unit}**).
            Context: {context}
            Competitors: {competitors}
            
            RAW INTELLIGENCE (Priority #1):
            {raw_intel}
            
            CRITICAL INSTRUCTIONS:
            1. **Hybrid Intelligence:** Use the web data for specific numbers (2024/2025). If web data is missing (common for Private Companies like Solvias), USE YOUR INTERNAL KNOWLEDGE to fill the gaps regarding their strategy, ownership, and reputation.
            2. **Private Company Logic:** If you see no stock data, look for "Growth Proxies" in the text: New Facilities, Hiring, or Partnerships.
            3. **Be Specific:** Name the specific facilities (e.g. RTP), drugs, or leaders found.
            
            GENERATE REPORT:
            
            ### Section A: Business Health & Signals
            * **Growth Signal:** (e.g. "Expansion Phase"). Cite specific facilities or M&A.
            * **Market Position:** Niche Specialist or Volume Leader? vs {competitors}.
            
            ### Section B: Strategic Initiatives (Follow the Money)
            Identify 2-3 "Funded" Priorities.
            * **Initiative:** (e.g. "New Factory in X").
            * **Goal:** Why are they doing this? (e.g. "Gene Therapy Expansion").
            
            ### Section C: Leadership & Ownership
            * **Ownership:** PE Firm? Founder? Public?
            * **Key People:** CEO/CSO names found in data.
            
            ### Section D: Risks & Friction
            * **Operational:** Integration pains? Staffing?
            * **Financial:** PE Exit pressure?
            
            Format: Markdown tables. Concise bullet points.
            """
            
            report, error = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                with st.expander("🔎 View Source Intelligence"):
                    st.text(raw_intel if raw_intel else "Relied on Internal Knowledge.")
            else:
                st.error("AI generation failed.")
                if error: st.write(error)
