import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import json
import re

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
        # Priority list: Try 2.0/2.5 first (Fastest), fallback to 1.5
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
    """
    Robustly finds JSON in chatty AI responses.
    """
    try:
        # Method 1: Look for Markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
            return json.loads(text)
        
        # Method 2: Regex search for the first list [...]
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
            
        # Method 3: Raw parse attempt
        return json.loads(text)
    except:
        return None

# --- APP FLOW ---
st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# ==========================================
# STEP 1: SMART SEARCH & IDENTIFY
# ==========================================
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Agilent")
    
    if st.button("Find Account", type="primary"):
        if not api_key:
            st.error("❌ Need API Key"); st.stop()
            
        with st.spinner(f"Scanning structure for '{company_input}'..."):
            search_text = ""
            try:
                with DDGS() as ddgs:
                    # FIX: Force generator to list immediately
                    results = [r for r in ddgs.text(f"{company_input} corporate structure business units", max_results=4)]
                    search_text = str(results)
            except Exception as e:
                st.warning(f"Search warning: {e}")

            # Strict Prompt for JSON
            prompt = f"""
            Task: Identify distinct corporate entities and their business units for '{company_input}' based on this data: {search_text}
            
            OUTPUT INSTRUCTIONS:
            Return ONLY a valid JSON list. No explanation text.
            Format:
            [
                {{
                    "name": "Exact Legal Name",
                    "description": "Headquarters/Industry Type",
                    "units": ["Unit 1", "Unit 2", "Unit 3"]
                }}
            ]
            """
            
            response = run_gemini(prompt)
            
            if response:
                data = extract_json(response)
                if data:
                    st.session_state.entity_options = data
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("AI returned invalid data structure. Please try again.")
                    with st.expander("Debug Raw Output"):
                        st.code(response)
            else:
                st.error("Connection failed. Check API Key.")

# ==========================================
# STEP 2: DEEP DIVE (The "Mega Prompt")
# ==========================================
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    if not st.session_state.entity_options:
        st.warning("No data found."); st.stop()

    # Dynamic Selectors
    col1, col2 = st.columns(2)
    with col1:
        opts = st.session_state.entity_options
        names = [f"{o['name']} ({o['description']})" for o in opts]
        idx = st.radio("Legal Entity:", range(len(opts)), format_func=lambda x: names[x])
        real_company = opts[idx]['name']
    with col2:
        real_unit = st.selectbox("Business Unit:", opts[idx].get('units', ['General']))

    st.markdown("---")
    with st.expander("Add Context", expanded=True):
        c1, c2 = st.columns(2)
        competitors = c1.text_input("Competitors", placeholder="e.g. Thermo Fisher")
        context = c2.text_input("Your Goal", placeholder="e.g. Selling CRM software")

    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Analyzing {real_company} ({real_unit})..."):
            
            # Deep Search Loop
            search_dump = ""
            queries = [
                f"{real_company} {real_unit} revenue growth financial results 2024 2025",
                f"{real_company} {real_unit} strategic priorities investments 2025",
                f"{real_company} {real_unit} layoffs restructuring risks 2025",
                f"{real_company} {real_unit} recent contracts partnerships 2025"
            ]
            
            try:
                with DDGS() as ddgs:
                    for q in queries:
                        # Force list conversion
                        res = [r for r in ddgs.text(q, max_results=3)]
                        if res:
                            search_dump += f"\nQuery: {q}\nData: {str(res)}\n"
            except Exception as e:
                st.warning(f"Search warning: {e}")

            # Analyst Prompt
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Target: **{real_company}** (Specific Unit: **{real_unit}**).
            Competitors: {competitors}
            User Context: {context}
            
            RAW SEARCH DATA:
            {search_dump}
            
            INSTRUCTIONS:
            Write a 'Zero-Fluff' competitive briefing. Base it strictly on the search data provided.
            
            SECTION A: Business Unit Health
            - **Growth Signal**: (e.g., "Expanding", "Stable", "Struggling"). Cite specific revenue % if found.
            - **Market Position**: Gaining or losing share vs {competitors}?
            
            SECTION B: Strategic Initiatives (Follow the Money)
            - List 2-3 funded priorities for 2025/2026 found in the text.
            - **Operational Goal**: What metric are they improving?
            
            SECTION C: Risks & Financials
            - **Layoff Radar**: Mentions of "restructuring", "cost savings", or "reduction".
            - **Cash Position**: Investing or saving?
            
            SECTION D: "Soft Signals"
            - Leadership changes or hiring focuses.
            
            Format: Markdown Tables and Bullet Points.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report)
                with st.expander("View Raw Sources"):
                    st.code(search_dump)
            else:
                st.error("AI generation failed.")
