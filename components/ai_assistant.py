import streamlit as st
import pandas as pd
from openai import OpenAI

def get_ai_context(results, machines_df):
    """Summarize simulation results into a text context for the AI."""
    total_time = results["Total_Time"]
    df_batches = results["Batch_Metrics"]
    stats = results["Machine_Stats"]
    
    # Identify Bottleneck
    utilization_data = []
    for m_id, m_stat in stats.items():
        count = int(machines_df[machines_df['Machine_ID'] == m_id]['Count'].values[0])
        avail = total_time * count
        util = (m_stat['working_time'] / avail) * 100 if avail > 0 else 0
        utilization_data.append((m_id, util))
    
    bottleneck_m, bottleneck_val = max(utilization_data, key=lambda x: x[1])
    
    context = f"""
    You are a Factory Optimization Expert. Analyze the following simulation results:
    - Total Production Time (Makespan): {round(total_time, 1)} min.
    - Average Batch Lead Time: {round(df_batches['Flow_Time'].mean(), 1)} min.
    - Total Units Completed: {df_batches['Units'].sum()}.
    - Critical Bottleneck: {bottleneck_m} ({round(bottleneck_val, 1)}% busy).
    - Resource Stats: {stats}
    
    The user is asking a question about these results. Provide a professional, data-driven answer.
    """
    return context

def get_deepseek_response(user_query, context):
    """Call the DeepSeek API using the OpenAI-compatible client."""
    try:
        api_key = st.secrets.get("DEEPSEEK_API_KEY")
        if not api_key:
            return "❌ API Key not found in Streamlit secrets."
            
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": user_query},
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ DeepSeek Error: {str(e)}"

def render_ai_assistant(results, machines_df):
    """Render the DeepSeek-powered AI Chat Interface."""
    st.subheader("🤖 DeepSeek Factory Assistant")
    
    # Initialize Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "I've analyzed your latest run. How can I help you improve your factory's performance?"}
        ]

    # Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask DeepSeek about your factory..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate Response from DeepSeek
        with st.spinner("DeepSeek is thinking..."):
            context = get_ai_context(results, machines_df)
            response = get_deepseek_response(prompt, context)
        
        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
