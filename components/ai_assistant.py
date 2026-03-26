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
    
    if "MultiRunStats" in results:
        m_stats = results["MultiRunStats"]
        runs = m_stats['Number_of_Runs']
        perf_summary = f"""
    - Number of Runs: {runs}
    - Total Production Time (Makespan): Mean={round(m_stats['Makespan']['mean'], 1)} min, SD={round(m_stats['Makespan']['std'], 1)}, 95% CI=[{round(m_stats['Makespan']['mean'] - m_stats['Makespan']['ci95'], 1)}, {round(m_stats['Makespan']['mean'] + m_stats['Makespan']['ci95'], 1)}]
    - Average Batch Lead Time: Mean={round(m_stats['Lead_Time']['mean'], 1)} min, SD={round(m_stats['Lead_Time']['std'], 1)}, 95% CI=[{round(m_stats['Lead_Time']['mean'] - m_stats['Lead_Time']['ci95'], 1)}, {round(m_stats['Lead_Time']['mean'] + m_stats['Lead_Time']['ci95'], 1)}]
    - Total Units Completed: Mean={round(m_stats['Units']['mean'], 1)}, SD={round(m_stats['Units']['std'], 1)}, 95% CI=[{round(m_stats['Units']['mean'] - m_stats['Units']['ci95'], 1)}, {round(m_stats['Units']['mean'] + m_stats['Units']['ci95'], 1)}]
    - Average Flow Efficiency: Mean={round(m_stats['Efficiency']['mean'], 1)}%, SD={round(m_stats['Efficiency']['std'], 1)}%, 95% CI=[{round(m_stats['Efficiency']['mean'] - m_stats['Efficiency']['ci95'], 1)}%, {round(m_stats['Efficiency']['mean'] + m_stats['Efficiency']['ci95'], 1)}%]
    - Critical Bottleneck (Last Run): {bottleneck_m} ({round(bottleneck_val, 1)}% busy).
    - Resource Stats (Last Run): {stats}
"""
        prompt_instruction = "The user is asking a question about these results. Provide a professional, data-driven answer. Since these results are aggregated over multiple simulation runs, explicitly state the 95% confidence intervals when discussing future, projected, or what-if scenarios to highlight the statistical reliability of the predictions."
    else:
        perf_summary = f"""
    - Total Production Time (Makespan): {round(total_time, 1)} min.
    - Average Batch Lead Time: {round(df_batches['Flow_Time'].mean(), 1)} min.
    - Total Units Completed: {df_batches['Units'].sum()}.
    - Critical Bottleneck: {bottleneck_m} ({round(bottleneck_val, 1)}% busy).
    - Resource Stats: {stats}
"""
        prompt_instruction = "The user is asking a question about these results. Provide a professional, data-driven answer."
        
    context = f"""
    You are a Factory Optimization Expert. Analyze the following simulation results:
    {perf_summary}
    
    {prompt_instruction}
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
