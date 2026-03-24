import streamlit as st
import pandas as pd
import io
import plotly.express as px
from simulation_engine import FactorySimulation
import os 

st.set_page_config(page_title="Factory Batch Simulation", layout="wide")

st.title("🏭 Customizable Factory Simulation")
st.markdown("""
This tool simulates a manufacturing shop floor where jobs are routed through various machines. 
You can customize the machines, the job demand, batch sizes, and the processing sequences.
""")
with open("./factory_config.xlsx", "rb") as template_file:
    btn = st.download_button(
        label="Download Configuration Template (Excel)",
        data=template_file,
        file_name="factory_config_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.divider()

uploaded_file = st.file_uploader("Upload your Configuration Excel File", type=["xlsx"])

if uploaded_file is not None:
    df_machines = pd.read_excel(uploaded_file, sheet_name="Machines")
    df_jobs = pd.read_excel(uploaded_file, sheet_name="Jobs")
    df_routings = pd.read_excel(uploaded_file, sheet_name="Routings")
    
    st.subheader("📝 Edit Configuration on the Fly")
    st.info("You can edit the tables below directly. Changes will be used in the simulation.")
    
    # Create the Paths DataFrame for visualization and editing
    df_paths = df_routings.pivot(index="Job_Type", columns="Sequence_Order", values="Machine_ID").reset_index()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Machines", "Jobs", "Routings", "Job Paths (Edit Route)"])
    
    with tab1:
        st.write("Define your machines and their quantities. (Failures/Repairs are parameterized)")
        edited_machines = st.data_editor(df_machines, num_rows="dynamic", use_container_width=True)
        
    with tab2:
        st.write("Set the Target Demand and Batch Size for each Job Type.")
        edited_jobs = st.data_editor(df_jobs, num_rows="dynamic", use_container_width=True)
        
    with tab3:
        st.write("Full routing details including Process and Setup times.")
        edited_routings = st.data_editor(df_routings, num_rows="dynamic", use_container_width=True)
        
    with tab4:
        st.write("Simplified view of the sequence path for each job. Editing Machine IDs here automatically updates the Routings!")
        edited_paths = st.data_editor(df_paths, num_rows="dynamic", use_container_width=True)
        # Reconstruct updated paths into the edited_routings
        melted_paths = edited_paths.melt(id_vars=["Job_Type"], var_name="Sequence_Order", value_name="Machine_ID").dropna(subset=['Machine_ID'])
        melted_paths['Sequence_Order'] = pd.to_numeric(melted_paths['Sequence_Order'])
        
        # Merge the edited Machine IDs back into the detailed routing table (retaining times)
        new_routings = pd.merge(edited_routings.drop(columns=['Machine_ID']), melted_paths, on=['Job_Type', 'Sequence_Order'], how='inner')
        edited_routings = new_routings[['Job_Type', 'Sequence_Order', 'Machine_ID', 'Process_Time_Per_Unit', 'Setup_Time_Per_Batch']]
        
    st.divider()
    
    if st.button("🚀 Run Simulation until Target Demand Achieved", type="primary"):
        with st.spinner("Simulating... This might take a few seconds."):
            sim = FactorySimulation(edited_machines, edited_jobs, edited_routings)
            st.session_state['simulation_results'] = sim.run()
            st.session_state['sim_machines_df'] = edited_machines
            
    if 'simulation_results' in st.session_state:
        results = st.session_state['simulation_results']
        cached_machines_df = st.session_state['sim_machines_df']
        
        st.success("Simulation Data Ready!")
        
        total_time = results["Total_Time"]
        df_batches = results["Batch_Metrics"]
        stats = results["Machine_Stats"]
        
        st.header("📈 Advanced Kanban & Flow Metrics")
        
        # Calculate Flow Metrics
        total_batches = len(df_batches)
        avg_flow_time = df_batches["Flow_Time"].mean() if total_batches > 0 else 0
        avg_wip = results["WIP_Timeline"]["WIP"].mean() if not results["WIP_Timeline"].empty else 0
        throughput = total_batches / total_time if total_time > 0 else 0
        
        df_batches["Efficiency"] = (df_batches["Active_Time"] / df_batches["Flow_Time"]) * 100
        avg_efficiency = df_batches["Efficiency"].mean() if total_batches > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Makespan (Total Time)", f"{round(total_time, 2)} mins")
        c2.metric("Flow Time (Lead Time per batch)", f"{round(avg_flow_time, 2)} mins")
        c3.metric("Flow Velocity (Throughput)", f"{round(throughput, 4)} batches/min")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Flow Load (Avg WIP)", f"{round(avg_wip, 2)} batches active")
        c5.metric("Flow Efficiency", f"{round(avg_efficiency, 2)} %")
        
        total_operations = sum([s['completed_operations'] for s in stats.values()])
        total_units = df_batches["Units"].sum()
        avg_cycle_time = total_time / total_units if total_units > 0 else 0 # Simple cycle time formulation
        c6.metric("Overall Cycle Time per Unit", f"{round(avg_cycle_time, 2)} mins/unit")
        
        st.divider()
        
        st.subheader("📊 Machine Utilization Summary")
        utilization_data = []
        for m_id, m_stat in stats.items():
            count = int(cached_machines_df[cached_machines_df['Machine_ID'] == m_id]['Count'].values[0])
            available_time = total_time * count
            util = m_stat['working_time'] / available_time if available_time > 0 else 0
            setup_ratio = m_stat['setup_time'] / available_time if available_time > 0 else 0
            failure_ratio = m_stat['down_time'] / available_time if available_time > 0 else 0
            idle = 1 - util - setup_ratio - failure_ratio
            utilization_data.append({
                "Machine": m_id, 
                "Processing %": round(util * 100, 2),
                "Setup %": round(setup_ratio * 100, 2),
                "Failure %": round(failure_ratio * 100, 2),
                "Idle/Wait %": round(idle * 100, 2)
            })
            
        df_util = pd.DataFrame(utilization_data)
        st.dataframe(df_util, use_container_width=True)

        # Categorical Y-Axis Machine Graphs Options
        st.divider()
        st.subheader("📈 Machine Status Categorical Flow Graphs")
        st.markdown("These charts strictly plot categorical values ('Idle', 'Setup', 'Processing', 'Failure') on the Y-Axis exactly as requested.")
        
        gdf = results.get("Gantt_Log", pd.DataFrame())
        if not gdf.empty:
            machine_options = gdf["Category_ID"].unique().tolist()
            selected_machine = st.selectbox("Select target Machine:", machine_options)
            
            # Filter down to the exact unit blocks for this machine type
            m_gdf = gdf[gdf["Category_ID"] == selected_machine].copy()
            
            # To calculate "Idle" periods, we construct a continuous timeline from 0 to total_time
            # For simplicity in categorical line plotting, let's sort all blocks by Start time
            m_gdf = m_gdf.sort_values("Start")
            
            # Build continuous point-in-time arrays (adding explicit Idle times between blocks)
            points = []
            last_end = 0
            state_map = {"Failure": 0, "Idle": 1, "Setup": 2, "Processing": 3}
            m_gdf["State_Int"] = m_gdf["State"].map(state_map)
            
            for _, row in m_gdf.iterrows():
                if row["Start"] > last_end:
                    # 1. Idle Period existed right before this block
                    points.append({"Time": last_end, "State": "Idle", "State_Val": 1})
                    points.append({"Time": row["Start"], "State": "Idle", "State_Val": 1})
                    
                # 2. Add the actual active state block (Setup, Process, Failure)
                points.append({"Time": row["Start"], "State": row["State"], "State_Val": state_map[row["State"]]})
                points.append({"Time": row["Finish"], "State": row["State"], "State_Val": state_map[row["State"]]})
                
                last_end = max(last_end, row["Finish"])
                
            # End pad with Idle
            if last_end < total_time:
                points.append({"Time": last_end, "State": "Idle", "State_Val": 1})
                points.append({"Time": total_time, "State": "Idle", "State_Val": 1})
                
            df_points = pd.DataFrame(points)

            # Step Line Chart (Heart-rate monitor style)
            fig = px.line(df_points, x="Time", y="State", 
                          title=f"Categorical Step Line Chart of {selected_machine}",
                          line_shape='hv')
            fig.update_yaxes(categoryorder="array", categoryarray=["Failure", "Idle", "Setup", "Processing"])
            st.plotly_chart(fig, use_container_width=True)

        # WIP Timeline Graph
        with st.expander("View Overall Work-In-Progress (WIP) Timeline"):
            wip_df = results["WIP_Timeline"]
            if not wip_df.empty:
                fig2 = px.line(wip_df, x="Time", y="WIP", title="Active Batches in Factory over Time", line_shape='hv')
                st.plotly_chart(fig2, use_container_width=True)

        with st.expander("Show detailed simulation event log"):
            st.dataframe(results["Logs"])

# Trigger Streamlit reload
