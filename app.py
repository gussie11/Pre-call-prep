import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS

# 1. Page Configuration
st.set_page_config(page_title="Sales Prep Analyst", page_icon="🚀", layout="wide")

# 2. API Key Management
with st.sidebar:
    st.header("⚙️ Settings")
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ API Key loaded from Secrets")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
        if not api_key:
            st.warning("⚠️ Please enter your key to proceed.")

# 3. Configure Gemini
if api_key:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Configuration Error: {e}")

# --- HELPER: Find a working model ---
def get_working_model():
    # List of models to try in order of preference
    candidates = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro",
        "models/gemini-1.5-flash",
        "models/gemini-pro"
    ]
    
    # Simple check to return the string (we'll catch errors during generation)
    # Ideally, we would list_models() but that requires an extra API call.
    # We will let the generation loop handle the fallback.
    return candidates

# 4. Main Interface
st.title("🚀 360° Sales Analyst (Auto-Fix)")
st.markdown("Generate a pre-call briefing using live web data.")

col1, col2 = st.columns(2)
with col1:
    target_company = st.text_input("Target Company", placeholder="e.g. Agilent Technologies")
    business_unit = st.text_input("Business Unit", placeholder="e.g. Life Sciences Group")
with col2:
    competitors = st.text_input("Competitors", placeholder="e.g. Thermo Fisher")
    user_context = st.text_area("Context", placeholder="Paste notes here...", height=100)

# 5. Logic
if st.button("Run Analysis", type="primary"):
    if not api_key:
        st.error("❌ API Key missing.")
        st.stop()
        
    # --- PHASE 1: SEARCH ---
    status = st.empty()
    status.info(f"🔍 Searching web for {target_company}...")
    
    search_results = ""
    try:
        with DDGS() as ddgs:
            queries = [
                f"{target_company} {business_unit} financial results 2024 2025 revenue",
                f"{target_company} {business_unit} strategic initiatives investments 2025",
                f"{target_company} {business_unit} risks layoffs 2025"
            ]
            for q in queries:
                r = ddgs.text(q, max_results=2)
                if r: search_results += f"\nQ: {q}\nResult: {str(r)}\n"
    except Exception as e:
        st.warning(f"Search minor error: {e}")

    # --- PHASE 2: GENERATE (With Fallback) ---
    status.info("🧠 Connecting to Gemini...")
    
    prompt = f"""
    Role: Senior Sales Analyst.
    Task: Briefing for {target_company} ({business_unit}).
    Competitors: {competitors}
    Context: {user_context}
    
    Data:
    {search_results}
    
    Output:
    1. Business Health (Growth/Margins)
    2. Strategic Initiatives (Funded Projects)
    3. Risks (Cash/Layoffs)
    4. Soft Signals (Hiring/Leadership)
    """
    
    # Try models one by one
    success = False
    model_list = get_working_model()
    
    for model_name in model_list:
        try:
            status.text(f"Trying model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            # If we get here, it worked!
            status.empty()
            st.success(f"✅ Generated using {model_name}")
            st.markdown("### 📊 Analyst Report")
            st.markdown(response.text)
            success = True
            break # Stop the loop
        except Exception as e:
            print(f"Failed on {model_name}: {e}")
            continue # Try the next one

    if not success:
        status.error("❌ All models failed. Debug Info Below:")
        st.error("We could not find a model that accepts your key. Here are the models your key DOES have access to:")
        try:
            # List available models to debug
            available = list(genai.list_models())
            valid_names = [m.name for m in available if 'generateContent' in m.supported_generation_methods]
            st.code(valid_names)
        except Exception as e:
            st.error(f"Could not list models: {e}")
