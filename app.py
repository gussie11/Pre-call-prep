import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import json

# --- 1. Page Config ---
st.set_page_config(page_title="Sales Prep Analyst", page_icon="🕵️‍♂️", layout="wide")

# --- 2. Session State Setup ---
# We use this to remember data between Step 1 and Step 2
if "step" not in st.session_state:
    st.session_state.step = 1
if "entity_options" not in st.session_state:
    st.session_state.entity_options = []

# --- 3. Sidebar & API Key ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Try to load key from Secrets first
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ Key loaded from Secrets")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
    
    # Reset Button to clear the screen
    if st.button("🔄 Start New Search"):
        st.session_state.step = 1
        st.session_state.entity_options = []
        st.rerun()

# --- 4. Helper Function: Robust Gemini Call ---
def run_gemini(prompt):
    """
    Tries multiple model versions in case one is deprecated or region-locked.
    """
    if not api_key: return None
    
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        return None

    # Priority list based on your access level
    models_to_try = [
        "models/gemini-2.5-flash",       # Bleeding edge (Fast)
        "models/gemini-1.5-flash",       # Standard
        "models/gemini-pro",             # Legacy
        "gemini-1.5-pro-latest"          # Fallback
    ]
    
    for m in models_to_try:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            continue # Try the next model silently
            
    return None # If all fail

# --- APP INTERFACE ---

st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# ==========================================
# STEP 1: SEARCH & IDENTIFY (The "Smart Lookup")
# ==========================================
if st.session_state.step == 1:
    st.subheader("Step 1: Account Lookup")
    st.markdown("Enter a company name to verify the legal entity and business units.")
    
    company_input = st.text_input("Target Company Name", placeholder="e.g. Merck, Agilent, Solvias")
    
    if st.button("Find Account", type="primary"):
        if not api_key:
            st.error("❌ Please provide an API Key in the sidebar.")
            st.stop()
            
        with st.spinner(f"Scanning corporate structure for '{company_input}'..."):
            # 1. Search Web for Structure
            search_text = ""
            try:
                with DDGS() as ddgs:
                    # Specific query to find divisions/units
                    q = f"{company_input} corporate structure business units investor relations annual report"
                    results = ddgs.text(q, max_results=4)
                    search_text = str(results)
            except Exception as e:
                st.warning(f"Search warning: {e}")
            
            # 2. AI Parsing (Force JSON Output)
            prompt = f"""
            Task: Analyze the search results for '{company_input}'.
            Goal: Identify the distinct corporate entities and their business units.
            
            Search Data: {search_text}
            
            OUTPUT INSTRUCTIONS:
            Return ONLY a valid JSON list. Do not add markdown formatting.
            Structure:
            [
                {{
                    "name": "Exact Company Name (Ticker)",
                    "description": "Brief 5-word description (HQ Location)",
                    "units": ["Unit 1", "Unit 2", "Unit 3", "All Units"]
                }}
            ]
            If multiple companies match (e.g. Merck US vs Merck DE), list them as separate objects.
            """
            
            response_text = run_gemini(prompt)
            
            # 3. Handle the JSON Response
            if response_text:
                try:
                    # Sanitize string (remove ```json wrappers if AI added them)
                    clean_json = response_text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    
                    if data:
                        st.session_state.entity_options = data
                        st.session_state.step = 2
                        st.rerun()
                    else:
                        st.error("AI found no data. Please try a more specific name.")
                except Exception as e:
                    st.error(f"Error parsing AI response: {e}")
                    st.caption("Raw AI Output for debugging:")
                    st.code(response_text)
            else:
                st.error("❌ Could not connect to Gemini. Check your API Key permissions.")

# ==========================================
# STEP 2: SELECTOR & DEEP DIVE
# ==========================================
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    if not st.session_state.entity_options:
        st.warning("Session data lost. Please start over.")
        if st.button("Back"): 
            st.session_state.step = 1
            st.rerun()
        st.stop()

    # --- THE SMART SELECTORS ---
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.info("🏢 **Select the Legal Entity**")
        # Create a list of display names
        options = st.session_state.entity_options
        display_names = [f"{o.get('name', 'Unknown')} - {o.get('description', '')}" for o in options]
        
        selected_idx = st.radio("Choose Entity:", range(len(options)), format_func=lambda x: display_names[x])
        
        # Get the selected object
        selected_entity = options[selected_idx]
        real_company_name = selected_entity['name']

    with col_b:
        st.success("📂 **Select Business Unit**")
        # Populate dropdown based on the radio selection
        unit_options = selected_entity.get('units', ["General"])
        real_unit_name = st.selectbox("Analyze which Unit?", unit_options)

    st.markdown("---")
    
    # Optional Context Inputs
    with st.expander("Add Deal Context (Optional)", expanded=True):
        col_c, col_d = st.columns(2)
        with col_c:
            competitors = st.text_input("Competitors", placeholder="e.g. Thermo Fisher")
        with col_d:
            context = st.text_input("Your Goal", placeholder="e.g. Selling a CRM implementation...")

    # FINAL RUN BUTTON
    if st.button("🚀 Run Deep Dive Analysis", type="primary"):
        with st.spinner(f"Analyzing {real_company_name} ({real_unit_name})..."):
            
            # 1. Deep Search (Targeted)
            search_data = ""
            try:
                with DDGS() as ddgs:
                    queries = [
                        f"{real_company_name} {real_unit_name} revenue growth financial results 2024 2025",
                        f"{real_company_name} {real_unit_name} strategic initiatives investments 2025",
                        f"{real_company_name} {real_unit_name} layoffs risks restructuring 2025"
                    ]
                    for q in queries:
                        r = ddgs.text(q, max_results=2)
                        search_data += f"\nQuery: {q}\nResults: {str(r)}\n"
            except Exception as e:
                st.warning(f"Search hiccup: {e}. Proceeding with available data.")
            
            # 2. Final Analyst Prompt
            final_prompt = f"""
            Role: Senior Enterprise Sales Analyst.
            Target: {real_company_name}
            Business Unit: {real_unit_name}
            Competitors: {competitors}
            User Context: {context}
            
            LATEST WEB DATA:
            {search_data}
            
            OUTPUT FORMAT (Markdown Report):
            1. **Business Unit Health**:
               - Growth Trend (Revenue/Margins).
               - Market Share Signal (Gaining/Losing vs Competitors).
               
            2. **Strategic Initiatives (Follow the Money)**:
               - Identify 2-3 funded projects or priorities found in the search.
               - Operational Goal for each.
               
            3. **Financial & Risk Reality**:
               - Cash Flow/Capex.
               - Layoff Radar/Restructuring.
               - Key Risks.
               
            4. **Soft Signals**:
               - Leadership changes.
               - Hiring patterns.
               
            Constraint: Be concise. No generic advice.
            """
            
            report = run_gemini(final_prompt)
            
            if report:
                st.markdown(f"### 📊 Analyst Briefing: {real_company_name}")
                st.markdown(report)
            else:
                st.error("Failed to generate report. Please check API Key.")
