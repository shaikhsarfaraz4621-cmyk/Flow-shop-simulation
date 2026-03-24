import streamlit as st
import os
import pandas as pd
from simulation_engine import FactorySimulation

# Import Custom Modules
from utils.styles import inject_custom_css
from utils.data_handler import initialize_session_state, handle_file_upload
from components.dashboard import (
    render_top_metrics, 
    render_utilization_analysis, 
    render_flow_dynamics, 
    render_job_performance
)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Factory Digital Twin Pro",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INJECT UI STYLES ---
inject_custom_css()

# --- INITIALIZE DATA ---
initialize_session_state()

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/factory.png", width=100)
    st.title("⚙️ Config Center")
    st.markdown("---")
    
    # Upload handling
    uploaded_file = st.file_uploader("Upload Configuration Excel", type=["xlsx"])
    if uploaded_file:
        handle_file_upload(uploaded_file)

    st.markdown("### 📥 Download Template")
    try:
        template_path = os.path.join(os.path.dirname(__file__), "factory_config.xlsx")
        with open(template_path, "rb") as f:
            st.download_button(
                label="Get Excel Template",
                data=f,
                file_name="factory_config_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except:
        st.warning("Template file not found.")

    st.markdown("---")
    st.markdown("### 🛠️ Quick Controls")
    if st.button("🚀 Run New Simulation", use_container_width=True, type="primary"):
        st.session_state['trigger_sim'] = True

# --- MAIN AREA ---
st.markdown('<div class="dashboard-header">🏭 Factory Digital Twin</div>', unsafe_allow_html=True)

# TABBING FOR CLEAN INTERFACE
tab_sim, tab_config = st.tabs(["📊 Performance Dashboard", "📝 Edit Configuration"])

with tab_config:
    st.subheader("Edit Setup Values Directly")
    st.info("💡 Changes made here are saved in the session and used for the next simulation run.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Machines Inventory**")
        st.session_state['machines_df'] = st.data_editor(
            st.session_state['machines_df'], 
            num_rows="dynamic", 
            width="stretch",
            key="editor_machines"
        )
    with col_b:
        st.markdown("**Job Demand & Batching**")
        st.session_state['jobs_df'] = st.data_editor(
            st.session_state['jobs_df'], 
            num_rows="dynamic", 
            width="stretch",
            key="editor_jobs"
        )
    
    st.markdown("**Production Routings**")
    st.session_state['routings_df'] = st.data_editor(
        st.session_state['routings_df'], 
        num_rows="dynamic", 
        width="stretch",
        key="editor_routings"
    )

# --- SIMULATION LOGIC ---
if st.session_state.get('trigger_sim', False):
    with st.spinner("🚀 Running Engine..."):
        try:
            sim = FactorySimulation(
                st.session_state['machines_df'], 
                st.session_state['jobs_df'], 
                st.session_state['routings_df']
            )
            st.session_state['simulation_results'] = sim.run()
            st.session_state['trigger_sim'] = False
        except Exception as e:
            st.error(f"Simulation Failed: {e}")
            st.session_state['trigger_sim'] = False

# --- DASHBOARD RENDERING ---
if 'simulation_results' in st.session_state:
    results = st.session_state['simulation_results']
    
    with tab_sim:
        # 1. TOP METRICS
        render_top_metrics(results)
        st.divider()

        # 2. MACHINE PERFORMANCE & BOTTLENECK
        render_utilization_analysis(results, st.session_state['machines_df'])
        st.divider()

        # 3. FLOW DYNAMICS (WIP AND CATEGORICAL)
        render_flow_dynamics(results)
        st.divider()

        # 4. JOB ANALYSIS
        render_job_performance(results, st.session_state['jobs_df'])

        with st.expander("📝 View Raw Simulation Event Logs"):
            st.dataframe(results["Logs"], use_container_width=True)

else:
    with tab_sim:
        st.info("👋 Welcome! Click 'Run New Simulation' in the sidebar to start.")
        st.image("https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&q=80&w=2070", caption="Industrial Factory Digital Twin Insight")

# --- FOOTER ---
st.markdown("---")
st.markdown("<small style='color: grey'>Factory Digital Twin Pro v2.1 | Modular Architecture</small>", unsafe_allow_html=True)
