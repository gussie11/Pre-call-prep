import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS

# --- Page Config ---
st.set_page_config(page_title="360° Sales Analyst (Direct)", page_icon="⚡", layout="wide")

# --- Sidebar: Secrets Management ---
with st.sidebar:
    st.header("⚙️ Configuration")
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ Gemini Key loaded!")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
        
    if api_key:
        genai.configure(api_key=api_key)

# --- Main App ---
st.title("⚡ 360° Sales Analyst (Direct Mode)")

col1, col2 = st.columns(2)
with col1:
    company = st.text_input("Target Company", "Agilent")
    unit = st.text_input("Business Unit", "Life Sciences")
with col2:
    competitors = st.text_input("Competitors", "Thermo Fisher")
    context = st.text_area("Context", height=100)

if st.button("Run Analysis"):
    if not api_key:
        st.error("❌ Please provide an API Key in the sidebar.")
        st.stop()

    st.info(f"🔍 Searching the web for {company} {unit}...")
    
    # 1. Direct Search (No Agent)
    results = ""
    try:
        with DDGS() as ddgs:
            # Search for Financials
            q1 = f"{company} {unit} Q3 2025 financial results revenue growth"
            results += f"\n--- Financials ---\n" + str([r for r in ddgs.text(q1, max_results=3)])
            
            # Search for Strategy
            q2 = f"{company} {unit} strategic initiatives 2025 investor presentation"
            results += f"\n--- Strategy ---\n" + str([r for r in ddgs.text(q2, max_results=3)])
            
            # Search for Layoffs/Risk
            q3 = f"{company} {unit} layoffs restructuring risk factors 2025"
            results += f"\n--- Risks ---\n" + str([r for r in ddgs.text(q3, max_results=3)])
    except Exception as e:
        st.warning(f"Search had a hiccup, but proceeding: {e}")

    # 2. Direct AI Call (No Chains)
    st.info("🧠 Analyzing data with Gemini...")
    
    prompt = f"""
    Role: Senior Market Intelligence Analyst.
    Task: Write a competitive briefing for **{company}** ({unit}).
    Competitors: {competitors}
    
    User Context: {context}
    
    LATEST WEB DATA FOUND:
    {results}
    
    OUTPUT FORMAT:
    Produce a report with these Markdown tables:
    1. Business Unit Health (Growth, Margins, Market Share Signal)
    2. Strategic Initiatives (Funded Priorities)
    3. Financial & Risk (Cash Flow, Layoffs, Risks)
    4. Soft Signals (Leadership, Hiring)
    """
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        st.markdown("### 📊 Analyst Report")
        st.markdown(response.text)
    except Exception as e:
        st.error(f"Gemini Error: {e}")
