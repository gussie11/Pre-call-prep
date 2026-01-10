import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Sales Prep Analyst", page_icon="📊", layout="wide")

if "step" not in st.session_state: st.session_state.step = 1

with st.sidebar:
    st.header("⚙️ Configuration")
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ Key loaded from Secrets")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
    
    if st.button("🔄 Reset App"):
        st.session_state.step = 1
        st.rerun()

# --- 2. HELPER: CONNECT TO ANY WORKING MODEL ---
def get_gemini_response(prompt):
    """
    Tries multiple model names until one works. 
    Prioritizes the 2.x models you have access to.
    """
    if not api_key: return "❌ No API Key found."
    
    genai.configure(api_key=api_key)
    
    # The list of models to try, in order of preference
    # Based on your previous logs, you have access to the 2.x series.
    candidates = [
        "models/gemini-2.5-pro",
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash-exp",
        "models/gemini-1.5-pro-latest",
        "models/gemini-1.5-pro",
        "gemini-1.5-pro"
    ]
    
    last_error = ""
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = str(e)
            continue # Try the next one
            
    return f"❌ All models failed. Last error: {last_error}"

# --- 3. THE FACT HUNTER ---
def get_facts(company):
    """
    Hunts for the specific data points seen in your good example.
    """
    raw_data = ""
    with DDGS() as ddgs:
        queries = [
            # Section A (Competitors & Market)
            f"{company} competitors CRO market share",
            f"{company} services market position vs Eurofins SGS",
            # Section B (Customers)
            f"{company} strategic partnership press release 2024 2025",
            f"{company} client case study pharma biotech",
            # Section C (Initiatives - looking for RTP/Vertex)
            f"{company} new facility expansion North Carolina RTP",
            f"{company} Vertex Pharmaceuticals agreement details",
            # Section E (Leadership & Ownership)
            f"{company} CEO appointment Archie Cullen",
            f"{company} acquisition Water Street JLL Partners"
        ]
        
        status = st.status(f"🕵️‍♂️ Mirroring ChatGPT's research on {company}...", expanded=True)
        
        for q in queries:
            try:
                # status.write(f"Searching: {q}...") # Commented out to reduce flicker
                results = [r for r in ddgs.text(q, max_results=2)]
                for r in results:
                    raw_data += f"\nSOURCE: {r['title']}\nTEXT: {r['body']}\n"
                time.sleep(0.2)
            except: continue
            
        status.update(label="✅ Data Collected", state="complete", expanded=False)
    return raw_data

# --- 4. THE ANALYST ---
def run_analysis(company, unit, data):
    prompt = f"""
    Role: Senior Market Analyst.
    Target: {company} (Focus: {unit}).
    
    RAW INTELLIGENCE FOUND:
    {data}
    
    TASK: Produce a briefing EXACTLY matching this structure. 
    If data is private/missing, write "N/A" just like a real analyst would. Do not hallucinate numbers.
    
    REQUIRED OUTPUT FORMAT:
    
    ## Section A: Business Unit Health & Competitor Mapping
    | Metric | {unit} Status |
    | :--- | :--- |
    | **Performance** | (e.g. "N/A (Private)" or "Organic Growth X%") |
    | **Direct Competitors** | List 2-3 rivals (e.g. Eurofins, SGS). |
    | **Market Share** | Assessment vs Rivals. |

    ## Section B: Main Customers & Markets
    * **Key Segments:** Who pays? (e.g. Pharma, Biotech).
    * **Reference Customers:** (Look for "Vertex", "Moderna", etc. in the text).
    * **Buying Behavior:** Why do they choose {company}? (e.g. "GMP Release Readiness").

    ## Section C: Strategic Initiatives (Funded Priorities)
    *Find specific projects in the text (like "RTP Center" or "Digital Operations").*
    | Initiative | Evidence | Operational Goal |
    | :--- | :--- | :--- |
    | (Name) | (Source/Date) | (What metric does it improve?) |

    ## Section D: Financial & Risk Reality
    * **Cash/Capex:** (e.g. "N/A (Private)" or details if found).
    * **Layoff Radar:** Any recent cuts?
    
    ## Section E: "Soft Signal" Sentiment
    | Signal | Evidence | Implication |
    | :--- | :--- | :--- |
    | **Leadership** | (e.g. Archie Cullen appointed CEO) | (Continuity/Growth?) |
    | **Hiring/Footprint** | (e.g. RTP Facility ~200 jobs) | (Scaling Capacity) |
    """
    
    return get_gemini_response(prompt)

# --- 5. UI ---
st.title("📊 360° Analyst (Mirror Mode)")

col1, col2 = st.columns(2)
with col1:
    target = st.text_input("Company", value="Solvias")
with col2:
    # Mimicking your prompt's "Roll-up" concept
    unit = st.selectbox("Unit / Scope", ["All (Roll-up)", "Small Molecules", "Ligands & Catalysts", "Biologics & CGT"])

if st.button("🚀 Generate Report", type="primary"):
    # 1. Get Data
    intel = get_facts(target)
    
    # 2. Generate
    with st.spinner("Writing report..."):
        report = run_analysis(target, unit, intel)
    
    # 3. Show
    st.markdown(report)
    
    with st.expander("View Underlying Data"):
        st.text(intel)
