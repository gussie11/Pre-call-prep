import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import time
import io
import csv

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="360° Customer Intelligence",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS (Your High-Contrast Dark Mode) ---
st.markdown("""
<style>
    /* 1. MAIN APP BACKGROUND */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* 2. TEXT COLORS */
    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: #FAFAFA;
        font-family: 'Helvetica Neue', sans-serif;
    }
    h1 { font-weight: 700; }
    h3 { font-weight: 600; color: #E0E0E0 !important; }
    
    /* 3. INPUT BOXES */
    .stTextInput > div > div > input, 
    .stSelectbox > div > div > div, 
    .stMultiSelect > div > div > div {
        background-color: #262730 !important;
        color: white !important;
        border: 1px solid #4A4A4A;
    }

    /* FIX: FORCE DROPDOWNS TO BE WHITE */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    div[role="listbox"] {
        background-color: #ffffff !important;
        border: 1px solid #ccc !important;
    }
    li[role="option"],
    div[role="option"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    div[data-baseweb="menu"] div, 
    div[data-baseweb="menu"] span,
    li[role="option"] span, 
    li[role="option"] div {
        color: #000000 !important; 
    }
    li[role="option"]:hover,
    div[role="option"]:hover {
        background-color: #f0f0f0 !important;
        color: #000000 !important;
    }
    
    .stMultiSelect span[data-baseweb="tag"] {
        background-color: #FF4B4B !important; 
        color: white !important;
    }
    .stMultiSelect span[data-baseweb="tag"] span {
        color: white !important;
    }
    
    /* 4. RESULT BOX */
    .result-box {
        background-color: #262730;
        padding: 2rem;
        border-radius: 12px;
        border-left: 6px solid #FF4B4B;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-top: 2rem;
        color: #FAFAFA;
    }
    
    /* 5. BUTTON STYLING */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        height: 3em;
        background-color: #FF4B4B;
        color: white !important;
        border: none;
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        background-color: #FF2B2B;
        transform: translateY(-2px);
    }
    
    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if "generated_result" not in st.session_state:
    st.session_state.generated_result = None
if "last_company" not in st.session_state:
    st.session_state.last_company = ""

# --- API SETUP ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = None

if not api_key:
    st.error("⚠️ API Key missing. Please set GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=api_key)
MODEL_NAME = 'models/gemini-2.0-flash-exp'

# --- HELPER FUNCTIONS ---
def clean_raw_output(text):
    if not text: return ""
    # Basic cleanup if needed
    if "||" in text: text = text.replace("||", "|\n|")
    return text

@st.cache_data(show_spinner=False)
def generate_content_with_retry(model_name, prompt):
    model = genai.GenerativeModel(model_name)
    delay = 45 
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(prompt)
            return response.text
        except exceptions.ResourceExhausted:
            st.warning(f"📉 Quota hit. Cooling down for {delay}s... (Attempt {attempt}/{max_retries})")
            time.sleep(delay)
            delay += 10
        except Exception as e:
            return f"Error: {str(e)}"
    return "❌ Failed: Maximum retries exceeded."

# --- PROMPT TEMPLATE ---
# This is the "Mega-Prompt" logic tailored for the app
MASTER_PROMPT = """
You are a Senior Market Intelligence Analyst. Your goal is to produce a "Zero-Fluff" competitive briefing.

INPUTS:
- Target Company: {company}
- Business Unit / Scope: {unit}
- Direct Competitors: {competitors}
- User Context: {context}

INSTRUCTIONS:
Conduct a deep-dive analysis. If data is unavailable, write "N/A". 
Do NOT provide generic advice. Focus on financial facts and strategic shifts.

OUTPUT FORMAT:
Generate a response with exactly these Markdown tables:

**Section A: Business Unit Health**
| Metric | Trend/Value | Rating (Pos/Neu/Neg) | Sales Implication |
|---|---|---|---|
| Revenue Growth | [Insert Data] | [Rating] | [One sentence takeaway] |
| Margins | [Insert Data] | [Rating] | [One sentence takeaway] |
| Market Share vs {competitors} | [Insert Data] | [Rating] | [One sentence takeaway] |

**Section B: Strategic Initiatives (Follow the Money)**
| Initiative Name | Status (Plan/Build/Live) | Operational Goal |
|---|---|---|
| [Project 1] | [Status] | [What metric are they changing?] |
| [Project 2] | [Status] | [What metric are they changing?] |

**Section C: Risk & Stability Radar**
| Category | Observation | Risk Level (High/Med/Low) |
|---|---|---|
| Cash Flow | [Op Cash vs Capex] | [Level] |
| Layoffs/Restructuring | [Any news in last 6mo?] | [Level] |
| Top Management Risk | [From 10-K Risk Factors] | [Level] |

**Section D: Soft Signals**
- **Leadership Changes:** [List recent C-level moves]
- **Hiring Hotspots:** [List roles/locations actively hiring]
"""

# --- UI LAYOUT ---
col_logo, col_title = st.columns([0.5, 5])
with col_logo:
    st.markdown("## 🕵️‍♂️")
with col_title:
    st.title("360° Customer Intelligence")
    st.caption("Generate deep-dive competitive briefings for call preparation.")

st.write("") 

# --- MAIN FORM CONTAINER ---
with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 1. Target Definition")
        company = st.text_input("Target Company", placeholder="e.g., Agilent Technologies")
        unit = st.text_input("Business Unit / Focus", placeholder="e.g., Life Sciences Group")
    
    with col2:
        st.markdown("### 2. Competitive Landscape")
        competitors = st.text_input("Direct Competitors", placeholder="e.g., Thermo Fisher, Waters")
        context = st.text_area("Additional Context (Optional)", placeholder="Paste LinkedIn notes or specific questions...", height=68)

    st.write("") 
    st.write("---") 
    
    # --- BUTTON ---
    submit_btn = st.button("✨ Run Analysis", type="primary", use_container_width=True)

# --- LOGIC EXECUTION ---
if submit_btn:
    if not company or not unit:
        st.warning("⚠️ Please define at least the Company and Business Unit.")
    else:
        with st.spinner(f"Analyzing {company} ({unit})..."):
            
            final_prompt = MASTER_PROMPT.format(
                company=company, 
                unit=unit, 
                competitors=competitors if competitors else "Direct Competitors",
                context=context if context else "None provided"
            )
            
            # Run Gemini
            raw_text = generate_content_with_retry(MODEL_NAME, final_prompt)
            clean_text = clean_raw_output(raw_text)
            
            st.session_state.generated_result = clean_text
            st.session_state.last_company = company

# --- RESULT DISPLAY ---
if st.session_state.generated_result:
    st.markdown(f"""
    <div class="result-box">
        <h3>📊 Intelligence Report: {st.session_state.last_company}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(st.session_state.generated_result)
    
    # CSV Logic (Scrapes tables from the Markdown response)
    try:
        lines = st.session_state.generated_result.split('\n')
        # Simple heuristic: Lines with pipes | are table rows
        table_lines = [line for line in lines if "|" in line]
        
        cleaned_rows = []
        for line in table_lines:
            # Clean up Markdown table formatting
            cells = [c.strip() for c in line.split('|')]
            if len(cells) > 0 and cells[0] == '': cells.pop(0)
            if len(cells) > 0 and cells[-1] == '': cells.pop(-1)
            
            # Filter out separator lines (e.g., ---|---|---)
            is_separator = True
            for cell in cells:
                if any(c.isalnum() for c in cell):
                    is_separator = False
                    break
            if not is_separator:
                cleaned_rows.append(cells)
        
        if cleaned_rows:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerows(cleaned_rows)
            csv_data = output.getvalue()
            
            safe_comp = "".join([c for c in st.session_state.last_company if c.isalnum() or c in (' ','-','_')]).strip().replace(' ', '_')
            
            st.download_button(
                label="📥 Download Data as CSV",
                data=csv_data,
                file_name=f"Analysis_{safe_comp}.csv",
                mime="text/csv"
            )
    except Exception as e:
        print(f"CSV Error: {e}")
