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
        # 1.5 Pro is essential for analyzing complex press releases
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

def robust_search(query, max_retries=2):
    """
    Search that returns Title + Link + Snippet for verification.
    """
    with DDGS() as ddgs:
        try:
            # We fetch 10 results to dig deep for PDFs and Press Releases
            results = [r for r in ddgs.text(query, max_results=10)]
            if results: return results
        except: pass
        
        # Fallback
        time.sleep(1)
        try:
            results = [r for r in ddgs.text(query + " news", max_results=8)]
            if results: return results
        except: pass
    return []

# --- APP FLOW ---
st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# ==========================================
# STEP 1: IDENTIFICATION
# ==========================================
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
            # 1. Search (Broad)
            q = f"{company_input} corporate structure business units investor relations"
            results = robust_search(q)
            search_text = str(results)

            if not results:
                st.error(f"Search found 0 results for '{company_input}'. Try the 'Skip' button.")
                st.stop()

            # 2. AI Parsing
            prompt = f"""
            Task: Extract corporate entities for '{company_input}' from: {search_text}
            
            SCENARIO A (Ambiguous): If multiple distinct companies exist (e.g. Merck US vs Merck DE), list both.
            SCENARIO B (Unique): If only one company is found (e.g. Solvias), list just that one.
            
            Output JSON ONLY:
            [ {{ "name": "Legal Name", "description": "HQ/Type", "units": ["Unit 1", "Unit 2"] }} ]
            """
            
            response_text, error = run_gemini(prompt)
            data = extract_json(response_text) if response_text else None
            
            if data:
                st.session_state.entity_options = data
                st.session_state.step = 2
                st.rerun()
            else:
                st.error("AI couldn't parse the data. Use 'Skip & Enter Manually'.")

# ==========================================
# STEP 2: DEEP DIVE (Source Hunter Mode)
# ==========================================
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
        with st.spinner(f"Hunting for official data on {real_company}..."):
            
            # 1. INTELLIGENT "SOURCE HUNTING"
            # We specifically target "Press Releases", "PDFs" (Reports), and "News"
            
            search_context = ""
            
            # A. The "Official" Docs (Public or Private)
            queries = [
                f"{real_company} press release 2024 2025 new facility expansion",
                f"{real_company} press release 2024 2025 acquisition partnership",
                f"{real_company} annual report 2024 strategic priorities filetype:pdf", # Try to find PDFs
                f"{real_company} leadership team CEO appointment 2024 2025"
            ]
            
            # B. Unit Specific (if selected)
            if "All" not in real_unit:
                queries.append(f"{real_company} {real_unit} revenue growth market share")
            
            all_results = []
            
            for q in queries:
                res = robust_search(q)
                if res:
                    for item in res:
                        # We format the result to emphasize the SOURCE URL
                        entry = f"SOURCE: {item.get('title')} ({item.get('href')})\nCONTENT: {item.get('body')}\n"
                        search_context += entry + "\n"
                        all_results.append(item)

            # 2. THE "SOURCE-TRUTH" PROMPT
            final_prompt = f"""
            Role: Senior Market Intelligence Analyst.
            Task: Competitive briefing for **{real_company}** (Unit: **{real_unit}**).
            Context: {context}
            Competitors: {competitors}
            
            RAW SEARCH DATA (Includes Links):
            {search_context}
            
            INSTRUCTIONS:
            1. **Prioritize Official Sources:** Look at the "SOURCE" lines. Trust data from the company's own website or major PR wires (BusinessWire, PR Newswire) above generic blogs.
            2. **Find the "Real" News:** Look for specific mentions of **New Facilities**, **Acquisitions**, or **Leadership Changes** in the text.
            3. **Private Company Handling:** If {real_company} is private (no stock data), focus purely on these "Growth Signals" (hiring, building, buying) rather than revenue $.
            4. **Gap Filling:** If specific data is missing, use your INTERNAL KNOWLEDGE to explain the *general* strategy of this company, but label it "Strategic Inference."
            
            GENERATE REPORT:
            
            ### Section A: Business Health & Signals
            * **Growth Signal:** (e.g. "Expansion Phase"). Cite the specific Facility or M&A deal if found in the search data.
            * **Market Position:** Niche Specialist or Volume Leader?
            
            ### Section B: Strategic Initiatives (Follow the Money)
            Identify 2-3 "Funded" Priorities.
            * **Initiative:** (e.g. "New Site in RTP").
            * **Evidence:** (e.g. "Announced in 2024 Press Release").
            * **Goal:** Why are they doing this?
            
            ### Section C: Leadership & Ownership
            * **Ownership:** Who owns them? (PE Firm? Public?).
            * **Key People:** CEO/CSO names found in the data.
            
            ### Section D: Risks & Friction
            * **Operational:** Integration risks? Staffing new sites?
            * **Financial:** PE Exit pressure?
            
            Format: Markdown tables.
            """
            
            report_text, error_msg = run_gemini(final_prompt)
            
            if report_text:
                st.markdown(f"### 📊 Analyst Briefing: {real_company}")
                st.markdown(report_text)
                
                # SHOW THE SOURCES (Transparency)
                with st.expander("🔗 Verified Sources (Click to Read)"):
                    if all_results:
                        for item in all_results[:5]: # Show top 5 distinct sources
                            st.markdown(f"- [{item.get('title')}]({item.get('href')})")
                    else:
                        st.write("No direct links found. Analysis based on internal knowledge.")
            else:
                st.error("AI generation failed.")
                if error_msg:
                    with st.expander("Debug"): st.write(error_msg)
