import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import initialize_agent, AgentType
from langchain.callbacks import StreamlitCallbackHandler

# --- Page Configuration ---
st.set_page_config(
    page_title="360° Sales Analyst",
    page_icon="🕵️‍♂️",
    layout="wide"
)

# --- Sidebar: Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("OpenAI API Key (Optional)", type="password", help="Required only if you want to run the analysis directly here.")
    st.info("💡 **No Key?** No problem. Fill out the form, generate the prompt, and copy-paste it into Gemini or ChatGPT.")
    st.markdown("---")
    st.markdown("**About**\n\nThis tool generates a 'Zero-Fluff' competitive intelligence briefing based on the **Mega-Prompt V3** framework.")

# --- Main Interface ---
st.title("🕵️‍♂️ 360° Sales Intelligence Analyst")
st.markdown("Generate deep-dive competitive briefings for your prospects in seconds.")

col1, col2 = st.columns(2)

with col1:
    target_company = st.text_input("Target Company", placeholder="e.g. Agilent Technologies")
    business_unit = st.text_input("Business Unit / Focus Area", placeholder="e.g. Life Sciences Group")

with col2:
    competitors = st.text_input("Known Competitors (Optional)", placeholder="e.g. Thermo Fisher, Waters")
    user_context = st.text_area("Additional Context (Optional)", placeholder="Paste LinkedIn snippets, job posts, or specific questions here...", height=100)

# --- The Mega-Prompt Template ---
def build_prompt(company, unit, comps, context):
    competitor_text = f"specifically against {comps}" if comps else "against their direct unit-level competitors"
    
    prompt_text = f"""
    **Role:** You are a Senior Market Intelligence Analyst. Your goal is to produce a "Zero-Fluff" competitive briefing for **{company}**, focusing specifically on the **{unit}** business unit.

    **Constraint:** Do NOT provide generic sales advice. Do NOT guess. If a data point is unavailable, mark it as "N/A".

    **Context Provided:**
    {context}

    **Instructions:**
    Using the latest 10-K, Investor Presentations, and Quarterly Earnings:

    **Section A: Business Unit Health & Competitor Mapping**
    *Create a table with these columns:*
    * **Selected Unit:** {unit}
    * **Performance:** Organic Growth % (YoY) and Margin Trend for this unit.
    * **Direct Competitors:** Compare {competitor_text}.
    * **Market Share Signal:** Are they growing faster or slower than these rivals?

    **Section B: Main Customers & Markets**
    *Identify the primary buyer types for {unit}.*
    * **Key Segments:** Who are they selling to?
    * **Reference Customers:** List specific company names if public.
    * **Buying Behavior:** Why do customers choose {company} over competitors? (e.g., Speed vs. Price vs. Regulatory Safety).

    **Section C: Strategic Initiatives (Follow the Money)**
    *Identify 2-3 "Funded" Priorities for {unit}.*
    * **Initiative Name:** (e.g., "Project Level Up").
    * **Evidence:** Must be cited from Investor Decks or Press Releases.
    * **Operational Goal:** What metric are they trying to change?

    **Section D: Financial & Risk Reality**
    * **Cash Flow (Company Level):** Operating Cash Flow vs. Capex.
    * **Layoff Radar:** Any WARN notices or restructuring costs in the last 6 months?
    * **Risk Factors:** Top 3 risks from the 10-K that directly impact {unit}.

    **Section E: "Soft Signal" Sentiment**
    * **Leadership:** Recent changes in Division Heads or C-Suite.
    * **Hiring Patterns:** Are they opening new hubs or R&D centers?

    **Output Format:**
    Strict Markdown tables. Bullet points must be concise (under 15 words).
    """
    return prompt_text

# --- Logic ---
if target_company and business_unit:
    final_prompt = build_prompt(target_company, business_unit, competitors, user_context)
    
    # Tab Structure
    tab1, tab2 = st.tabs(["📋 Generate Prompt", "🤖 Run AI Agent"])

    # TAB 1: Copy-Paste Mode
    with tab1:
        st.subheader("Generated Prompt")
        st.markdown("Copy this text and paste it into **Gemini Advanced** or **ChatGPT Plus**.")
        st.code(final_prompt, language="markdown")

    # TAB 2: Agent Mode
    with tab2:
        st.subheader("Live Analysis Agent")
        if not api_key:
            st.warning("⚠️ Please enter an OpenAI API Key in the sidebar to run the agent.")
        else:
            if st.button("Run Analysis Now"):
                st.info("🔍 Agent is browsing the web... this may take 1-2 minutes.")
                
                # Initialize Tools & Agent
                search = DuckDuckGoSearchRun()
                llm = ChatOpenAI(temperature=0, openai_api_key=api_key, model_name="gpt-4-turbo")
                
                # We use a Zero-Shot React Agent to allow the LLM to search multiple times
                tools = [search]
                agent = initialize_agent(
                    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True, handle_parsing_errors=True
                )
                
                st_callback = StreamlitCallbackHandler(st.container())
                
                # Execute
                response = agent.run(final_prompt, callbacks=[st_callback])
                st.markdown("### 📊 Analyst Report")
                st.markdown(response)

else:
    st.info("👈 Enter a Company and Business Unit to begin.")
