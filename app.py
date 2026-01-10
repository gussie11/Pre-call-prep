import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS

# 1. Page Config
st.set_page_config(page_title="Sales Prep Analyst", page_icon="🕵️‍♂️", layout="wide")

# 2. Session State Setup (To remember step 1)
if "step" not in st.session_state:
    st.session_state.step = 1
if "company_info" not in st.session_state:
    st.session_state.company_info = ""

# 3. Sidebar (API Key)
with st.sidebar:
    st.header("⚙️ Configuration")
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ Key loaded from Secrets")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
    
    # Reset Button
    if st.button("Start Over"):
        st.session_state.step = 1
        st.rerun()

# 4. Helper Functions
def get_working_model():
    return ["models/gemini-2.5-flash", "models/gemini-1.5-flash", "models/gemini-pro"]

def run_gemini(prompt):
    genai.configure(api_key=api_key)
    models = get_working_model()
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            return model.generate_content(prompt).text
        except: continue
    return "Error: Could not connect to AI."

# --- APP FLOW ---

st.title("🕵️‍♂️ 360° Account Validator & Analyst")

# STEP 1: ENTITY CHECK
if st.session_state.step == 1:
    st.subheader("Step 1: Account Confirmation")
    company_input = st.text_input("Enter Target Company Name", placeholder="e.g. Merck")
    
    if st.button("Find Entity"):
        if not api_key:
            st.error("Please provide an API Key.")
            st.stop()
            
        with st.spinner("Verifying corporate structure..."):
            # Search for basic info
            with DDGS() as ddgs:
                q = f"{company_input} corporate headquarters business units stock ticker"
                results = list(ddgs.text(q, max_results=3))
            
            # AI Confirmation Prompt
            prompt = f"""
            Role: Sales Researcher.
            Input: "{company_input}"
            Search Data: {str(results)}
            
            Task: Identify if this company name is ambiguous (e.g. Merck US vs Merck KGaA).
            
            Output Format:
            1. If ambiguous, list the options with HQ location and Ticker.
            2. If clear, list the Major Business Units found.
            3. Ask the user to confirm which specific Unit or Division they want to analyze.
            
            Keep it brief.
            """
            response = run_gemini(prompt)
            
            # Store result and move to next step
            st.session_state.company_info = response
            st.session_state.target_name = company_input
            st.session_state.step = 2
            st.rerun()

# STEP 2: SCOPE SELECTION & ANALYSIS
if st.session_state.step == 2:
    st.subheader("Step 2: Confirm Scope")
    
    # Show what the AI found
    st.info(f"**Entity Report for '{st.session_state.target_name}':**")
    st.write(st.session_state.company_info)
    
    st.markdown("---")
    st.write("👇 **Now, define your analysis:**")
    
    col1, col2 = st.columns(2)
    with col1:
        # Pre-fill these if user wants to change them
        confirmed_company = st.text_input("Confirmed Entity Name", value=st.session_state.target_name)
        selected_unit = st.text_input("Business Unit to Analyze", placeholder="e.g. Life Science / Process Solutions")
    with col2:
        competitors = st.text_input("Competitors (Optional)", placeholder="e.g. Thermo Fisher")
        context = st.text_area("Your Goals / Context", placeholder="I'm selling a new CRM tool...", height=100)
        
    if st.button("Run Deep Dive Analysis", type="primary"):
        with st.spinner("Generating Analyst Report..."):
            # Deep Search
            search_data = ""
            with DDGS() as ddgs:
                queries = [
                    f"{confirmed_company} {selected_unit} revenue growth 2024 2025",
                    f"{confirmed_company} {selected_unit} strategic priorities investments 2025",
                    f"{confirmed_company} {selected_unit} layoffs risks 2025"
                ]
                for q in queries:
                    r = ddgs.text(q, max_results=2)
                    search_data += f"\n{r}"
            
            # Final Report Prompt
            final_prompt = f"""
            Role: Senior Sales Analyst.
            Target: {confirmed_company} ({selected_unit})
            Competitors: {competitors}
            Context: {context}
            Data: {search_data}
            
            Output Markdown Report:
            1. **Unit Health**: Growth, Margins, Market Share.
            2. **Strategy**: Top 3 funded initiatives (Follow the money).
            3. **Risks**: Cash flow, Layoffs, leadership changes.
            4. **Buying Signal**: Who buys? (Customer profile).
            """
            
            report = run_gemini(final_prompt)
            
            st.markdown("### 📊 Final Analyst Briefing")
            st.markdown(report)
            
            if st.button("Start New Search"):
                st.session_state.step = 1
                st.rerun()
