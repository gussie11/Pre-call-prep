import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS

# 1. Page Configuration
st.set_page_config(page_title="Sales Prep Analyst", page_icon="🚀", layout="wide")

# 2. API Key Management (Sidebar)
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Check if the key is in Secrets (Best practice)
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ API Key loaded from Secrets")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        # Fallback: Ask the user for the key
        api_key = st.text_input("Enter Gemini API Key", type="password")
        if not api_key:
            st.warning("⚠️ Please enter your key to proceed.")

    st.markdown("---")
    st.markdown("**Note:** This tool uses DuckDuckGo for live data and Google Gemini for analysis.")

# 3. Configure Gemini
if api_key:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"API Key Error: {e}")

# 4. Main Interface
st.title("🚀 360° Sales Analyst (Gemini)")
st.markdown("Generate a pre-call briefing using live web data.")

col1, col2 = st.columns(2)

with col1:
    target_company = st.text_input("Target Company", placeholder="e.g. Agilent Technologies")
    business_unit = st.text_input("Business Unit", placeholder="e.g. Life Sciences Group")

with col2:
    competitors = st.text_input("Competitors", placeholder="e.g. Thermo Fisher, Waters")
    user_context = st.text_area("Internal Context / Notes", placeholder="Paste any specific goals or notes here...", height=100)

# 5. The Logic (Run Button)
if st.button("Run Analysis", type="primary"):
    if not api_key:
        st.error("❌ You must provide an API Key first.")
        st.stop()
        
    if not target_company or not business_unit:
        st.error("❌ Please enter both a Company and a Business Unit.")
        st.stop()

    # --- PHASE 1: SEARCH ---
    status_text = st.empty()
    status_text.info(f"🔍 Searching the web for '{target_company} {business_unit}'...")
    
    search_results = ""
    try:
        with DDGS() as ddgs:
            # We run 3 specific searches to get a complete picture
            queries = [
                f"{target_company} {business_unit} recent financial results revenue growth 2024 2025",
                f"{target_company} {business_unit} strategic initiatives and investments 2025",
                f"{target_company} {business_unit} layoffs restructuring risk factors 2025"
            ]
            
            for q in queries:
                results = ddgs.text(q, max_results=3)
                if results:
                    search_results += f"\nQuery: {q}\nResults: {str(results)}\n"
                    
    except Exception as e:
        st.warning(f"⚠️ Search had a minor issue: {e}. Proceeding with available data.")

    # --- PHASE 2: ANALYZE ---
    status_text.info("🧠 Gemini is analyzing the data...")
    
    # The Mega-Prompt
    final_prompt = f"""
    Role: You are an expert Enterprise Sales Analyst.
    Task: Write a deep-dive pre-call briefing for: **{target_company}** (Unit: **{business_unit}**).
    
    Context provided by user: "{user_context}"
    Competitors to benchmark against: "{competitors}"
    
    REAL-TIME WEB DATA (Use this to write the report):
    {search_results}
    
    OUTPUT INSTRUCTIONS:
    Structure the response into these 4 sections using Markdown tables and bullet points.
    
    1. **Business Unit Health**:
       - Growth Trend (Revenue/Margins)
       - Market Share Signal (Gaining vs. Losing against competitors)
       
    2. **Strategic Initiatives (Follow the Money)**:
       - List 2-3 specific funded projects or investment areas found in the search.
       - Identify the operational goal for each.
       
    3. **Financial & Risk Reality**:
       - Cash Flow/Capex status.
       - Layoff/Restructuring Radar (Any recent cuts?).
       - Key Risks.
       
    4. **Soft Signals**:
       - Recent Leadership changes.
       - Hiring patterns (if found).
       
    Constraint: Be concise. No generic sales advice. Focus on facts.
    """
    
    try:
        # Call Gemini Pro
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(final_prompt)
        
        # Display Result
        status_text.empty() # Clear the status message
        st.markdown("### 📊 Competitive Intelligence Report")
        st.markdown(response.text)
        
    except Exception as e:
        status_text.error(f"❌ AI Error: {e}")
