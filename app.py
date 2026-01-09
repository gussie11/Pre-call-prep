import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain.callbacks import StreamlitCallbackHandler

# --- 1. Page Config ---
st.set_page_config(page_title="360° Sales Analyst", page_icon="🕵️‍♂️", layout="wide")

# --- 2. Sidebar for API Key ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("OpenAI API Key", type="password")
    st.markdown("---")
    st.markdown("**How it works:**\n\nThis app uses an AI Agent to browse the web (10-K, News, Earnings) and build a competitive briefing based on your Mega-Prompt framework.")

# --- 3. Main Interface ---
st.title("🕵️‍♂️ 360° Competitive Intelligence Analyst")
st.markdown("Enter a target, and the AI will research specific initiatives, risks, and health signals.")

col1, col2 = st.columns(2)
with col1:
    target_company = st.text_input("Target Company", placeholder="e.g. Agilent Technologies")
    business_unit = st.text_input("Business Unit / Focus", placeholder="e.g. Life Sciences Group")
with col2:
    competitors = st.text_input("Direct Competitors", placeholder="e.g. Thermo Fisher, Waters")
    user_context = st.text_area("Additional Context (Optional)", placeholder="Paste LinkedIn notes or specific questions here...", height=100)

# --- 4. The Logic ---
if st.button("🚀 Run Analysis"):
    if not api_key:
        st.warning("⚠️ Please enter your OpenAI API Key in the sidebar to proceed.")
        st.stop()
    
    if not target_company or not business_unit:
        st.warning("⚠️ Please enter both a Company and a Business Unit.")
        st.stop()

    # Define the "Mega-Prompt" Template
    # We inject the user's inputs directly into the system instructions
    prompt_template = PromptTemplate.from_template(
        """
        You are a Senior Market Intelligence Analyst. Your goal is to produce a "Zero-Fluff" competitive briefing.
        
        TARGET: {company}
        UNIT: {unit}
        COMPETITORS: {competitors}
        CONTEXT: {context}

        TOOLS:
        You have access to the following tools:
        {tools}

        INSTRUCTIONS:
        Use the tools to find the latest 10-K, Quarterly Earnings, and Press Releases.
        Then, answer the following request with strict adherence to the format below.
        
        OUTPUT FORMAT (Use Markdown Tables):
        
        **Section A: Business Unit Health**
        - Compare {unit} growth/margins vs {competitors}.
        - Rate the health (Positive/Neutral/Negative).
        
        **Section B: Strategic Initiatives**
        - Identify 2-3 funded projects (M&A, New Factories, R&D).
        - Cite the source (e.g., "Q3 Earnings Call").
        
        **Section C: Risk Radar**
        - Cash Flow position.
        - Layoff/Restructuring news in last 6 months.
        - Top 3 Risk Factors from the 10-K specific to this unit.
        
        **Section D: Soft Signals**
        - Leadership changes (C-Suite).
        - Hiring hotspots (Locations/Roles).

        ----------------
        To use a tool, use this format:
        
        Question: the input question you must answer
        Thought: you should always think about what to do
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can repeat N times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question

        Begin!

        Question: Research {company} and generate the report.
        Thought: {agent_scratchpad}
        """
    )

    # Initialize Tools & Model
    search = DuckDuckGoSearchRun()
    tools = [search]
    llm = ChatOpenAI(temperature=0, openai_api_key=api_key, model_name="gpt-4-turbo-preview")

    # Create the Agent (The Modern Way)
    agent = create_react_agent(llm, tools, prompt_template)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    # Run the Agent with Streamlit Feedback
    st.info(f"🔍 Analyzing {target_company}... This takes about 45 seconds.")
    st_callback = StreamlitCallbackHandler(st.container())
    
    # Execute
    input_data = {
        "company": target_company,
        "unit": business_unit,
        "competitors": competitors if competitors else "Direct Competitors",
        "context": user_context if user_context else "None provided"
    }
    
    response = agent_executor.invoke(input_data, config={"callbacks": [st_callback]})
    
    # Display Result
    st.success("Analysis Complete!")
    st.markdown("### 📊 Analyst Report")
    st.markdown(response["output"])
