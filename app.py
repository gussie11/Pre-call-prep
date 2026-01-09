import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain.callbacks import StreamlitCallbackHandler

# --- Page Configuration ---
st.set_page_config(page_title="360° Sales Analyst (Gemini)", page_icon="🕵️‍♂️", layout="wide")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # 1. Try to find the key in secrets
    if "GOOGLE_API_KEY" in st.secrets:
        st.success("✅ Gemini Key loaded!")
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        # 2. Fallback: Ask user if secret is missing
        api_key = st.text_input("Enter Gemini API Key", type="password")
        st.info("💡 Add 'GOOGLE_API_KEY' to your Secrets to skip this.")

# --- Main Interface ---
st.title("🕵️‍♂️ 360° Sales Analyst (Gemini Powered)")

col1, col2 = st.columns(2)
with col1:
    target_company = st.text_input("Target Company", placeholder="e.g. Agilent")
    business_unit = st.text_input("Business Unit", placeholder="e.g. Life Sciences")
with col2:
    competitors = st.text_input("Competitors", placeholder="e.g. Thermo Fisher")
    user_context = st.text_area("Context", placeholder="Paste notes here...", height=100)

# --- Prompt Builder ---
def build_prompt(company, unit, comps, context):
    return f"""
    Act as a Senior Market Intelligence Analyst. Write a briefing for **{company}** ({unit} unit).
    Compare against: {comps if comps else "Direct Competitors"}.
    
    Context: {context}
    
    SECTIONS:
    1. Business Unit Health (Growth/Margins vs Competitors)
    2. Strategic Initiatives (Funded Priorities)
    3. Financial & Risk (Cash Flow, Layoffs, Risk Factors)
    4. Soft Signals (Leadership Changes, Hiring)
    
    Format: Markdown Tables. No fluff.
    """

# --- App Logic ---
if target_company and business_unit:
    final_prompt = build_prompt(target_company, business_unit, competitors, user_context)
    
    tab1, tab2 = st.tabs(["📋 Generate Prompt", "🤖 Run Agent"])

    with tab1:
        st.subheader("Copy this Prompt")
        st.code(final_prompt, language="markdown")

    with tab2:
        if not api_key:
            st.warning("⚠️ Please enter a Gemini API Key in the sidebar.")
        else:
            if st.button("Run Analysis"):
                st.info("🔍 Gemini is thinking... (This may take 30s)")
                
                # 1. Setup Tools
                search = DuckDuckGoSearchRun()
                tools = [search]
                
                # 2. Setup LLM (SWITCHED TO GEMINI)
                llm = ChatGoogleGenerativeAI(
                    model="gemini-pro", 
                    google_api_key=api_key,
                    temperature=0
                )
                
                # 3. Define the ReAct Prompt
                template = '''Answer the following questions as best you can. You have access to the following tools:

                {tools}

                Use the following format:

                Question: the input question you must answer
                Thought: you should always think about what to do
                Action: the action to take, should be one of [{tool_names}]
                Action Input: the input to the action
                Observation: the result of the action
                ... (this Thought/Action/Action Input/Observation can repeat N times)
                Thought: I now know the final answer
                Final Answer: the final answer to the original input question

                Begin!

                Question: {input}
                Thought:{agent_scratchpad}'''

                prompt = PromptTemplate.from_template(template)

                # 4. Create Agent
                agent = create_react_agent(llm, tools, prompt)
                agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)
                
                # 5. Run
                st_callback = StreamlitCallbackHandler(st.container())
                response = agent_executor.invoke({"input": final_prompt}, {"callbacks": [st_callback]})
                
                st.markdown("### 📊 Analyst Report")
                st.markdown(response['output'])
