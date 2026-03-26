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
from components.ai_assistant import render_ai_assistant

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
    num_runs = st.number_input("Number of Simulation Runs", min_value=1, max_value=100, value=5)
    if st.button("🚀 Run New Simulation", use_container_width=True, type="primary"):
        st.session_state['trigger_sim'] = True
        st.session_state['num_runs'] = num_runs

# --- MAIN AREA ---
st.markdown('<div class="dashboard-header">🏭 Factory Digital Twin</div>', unsafe_allow_html=True)

# TABBING FOR CLEAN INTERFACE
tab_sim, tab_config, tab_ai = st.tabs(["📊 Performance Dashboard", "📝 Edit Configuration", "🤖 Ask the Factory AI"])

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
            import math
            results_list = []
            runs = st.session_state.get('num_runs', 1)
            for i in range(runs):
                sim = FactorySimulation(
                    st.session_state['machines_df'], 
                    st.session_state['jobs_df'], 
                    st.session_state['routings_df']
                )
                results_list.append(sim.run())
            
            # Aggregate stats
            df_stats = pd.DataFrame({
                'Makespan': [r['Total_Time'] for r in results_list],
                'Lead_Time': [r['Batch_Metrics']['Flow_Time'].mean() for r in results_list],
                'Units': [r['Batch_Metrics']['Units'].sum() for r in results_list],
                'Efficiency': [(r['Batch_Metrics']['Active_Time'] / r['Batch_Metrics']['Flow_Time'] * 100).mean() for r in results_list]
            })
            
            all_batches = []
            all_logs = []
            all_wip = []
            all_gantt = []
            
            machine_stats_agg = {}
            for m_id in results_list[0]['Machine_Stats']:
                machine_stats_agg[m_id] = {'working_time': 0, 'setup_time': 0, 'down_time': 0}
                
            for run_idx, r in enumerate(results_list):
                run_id = f"Run_{run_idx+1}"
                
                bm = r['Batch_Metrics'].copy()
                bm['Run_ID'] = run_id
                all_batches.append(bm)
                
                lg = r['Logs'].copy()
                lg['Run_ID'] = run_id
                all_logs.append(lg)
                
                wip = r['WIP_Timeline'].copy()
                wip['Run_ID'] = run_id
                all_wip.append(wip)
                
                gantt = r['Gantt_Log'].copy()
                gantt['Run_ID'] = run_id
                if not gantt.empty:
                    all_gantt.append(gantt)
                
                for m_id, stats in r['Machine_Stats'].items():
                    machine_stats_agg[m_id]['working_time'] += stats['working_time']
                    machine_stats_agg[m_id]['setup_time'] += stats['setup_time']
                    machine_stats_agg[m_id]['down_time'] += stats['down_time']

            for m_id in machine_stats_agg:
                machine_stats_agg[m_id]['working_time'] /= runs
                machine_stats_agg[m_id]['setup_time'] /= runs
                machine_stats_agg[m_id]['down_time'] /= runs

            def get_stats(col):
                mean = df_stats[col].mean()
                std = df_stats[col].std() if len(df_stats) > 1 else 0.0
                n = len(df_stats)
                ci95 = 1.96 * (std / math.sqrt(n)) if n > 1 else 0.0
                return {"mean": mean, "std": std, "ci95": ci95}
                
            multi_stats = {
                'Number_of_Runs': runs,
                'Makespan': get_stats('Makespan'),
                'Lead_Time': get_stats('Lead_Time'),
                'Units': get_stats('Units'),
                'Efficiency': get_stats('Efficiency')
            }
            
            final_result = {
                "Total_Time": df_stats['Makespan'].mean(),
                "Batch_Metrics": pd.concat(all_batches, ignore_index=True),
                "Machine_Stats": machine_stats_agg,
                "Logs": pd.concat(all_logs, ignore_index=True),
                "WIP_Timeline": pd.concat(all_wip, ignore_index=True),
                "Gantt_Log": pd.concat(all_gantt, ignore_index=True) if all_gantt else pd.DataFrame(),
                "Completed_Jobs": results_list[-1]["Completed_Jobs"],
                "MultiRunStats": multi_stats,
                "df_stats": df_stats
            }
            
            st.session_state['simulation_results_list'] = results_list
            st.session_state['simulation_results'] = final_result
            st.session_state['trigger_sim'] = False
        except Exception as e:
            st.error(f"Simulation Failed: {e}")
            st.session_state['trigger_sim'] = False

# --- DASHBOARD RENDERING ---
if 'simulation_results' in st.session_state:
    results_agg = st.session_state['simulation_results']
    results_list = st.session_state.get('simulation_results_list', [results_agg])
    
    with tab_sim:
        st.subheader("Dashboard View Options")
        run_options = ["All Runs (Aggregated)"] + [f"Run_{i+1}" for i in range(len(results_list))]
        selected_view = st.selectbox("📊 Select Dashboard View:", run_options)
        
        if selected_view == "All Runs (Aggregated)":
            results = results_agg
        else:
            run_idx = int(selected_view.split("_")[1]) - 1
            results = results_list[run_idx]

        st.divider()

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

    with tab_ai:
        render_ai_assistant(results, st.session_state['machines_df'])

else:
    with tab_sim:
        st.info("👋 Welcome! Click 'Run New Simulation' in the sidebar to start.")
        st.image("https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&q=80&w=2070", caption="Industrial Factory Digital Twin Insight")

# --- FOOTER ---
st.markdown("---")
st.markdown("<small style='color: grey'>Factory Digital Twin Pro v2.1 | Modular Architecture</small>", unsafe_allow_html=True)
