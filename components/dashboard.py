import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def render_top_metrics(results):
    """Render the top metric cards."""
    m1, m2, m3, m4 = st.columns(4)
    
    if "MultiRunStats" in results:
        stats = results["MultiRunStats"]
        m1.metric("Production Makespan", f"{round(stats['Makespan']['mean'], 1)} ± {round(stats['Makespan']['ci95'], 1)} min")
        m2.metric("Avg Batch Lead Time", f"{round(stats['Lead_Time']['mean'], 1)} ± {round(stats['Lead_Time']['ci95'], 1)} min")
        m3.metric("Total Success Units", f"{round(stats['Units']['mean'], 1)} ± {round(stats['Units']['ci95'], 1)}")
        m4.metric("Avg Flow Efficiency", f"{round(stats['Efficiency']['mean'], 1)} ± {round(stats['Efficiency']['ci95'], 1)}%")
    else:
        total_time = results["Total_Time"]
        df_batches = results["Batch_Metrics"]
        
        m1.metric("Production Makespan", f"{round(total_time, 1)} min")
        m2.metric("Avg Batch Lead Time", f"{round(df_batches['Flow_Time'].mean(), 1)} min")
        m3.metric("Total Success Units", int(df_batches['Units'].sum()))
        
        # Calculate Flow Efficiency
        df_batches["Efficiency"] = (df_batches["Active_Time"] / df_batches["Flow_Time"]) * 100
        m4.metric("Avg Flow Efficiency", f"{round(df_batches['Efficiency'].mean(), 1)}%")

def render_utilization_analysis(results, res_machines_df):
    """Render machine utilization bars and bottleneck insights."""
    total_time = results["Total_Time"]
    stats = results["Machine_Stats"]
    
    utilization_data = []
    for m_id, m_stat in stats.items():
        count = int(res_machines_df[res_machines_df['Machine_ID'] == m_id]['Count'].values[0])
        available_time = total_time * count
        util = (m_stat['working_time'] / available_time) * 100 if available_time > 0 else 0
        setup = (m_stat['setup_time'] / available_time) * 100 if available_time > 0 else 0
        fail = (m_stat['down_time'] / available_time) * 100 if available_time > 0 else 0
        idle = 100 - util - setup - fail
        
        for t, v in [("Processing", util), ("Setup", setup), ("Failure", fail), ("Idle/Wait", idle)]:
            utilization_data.append({"Machine": m_id, "Type": t, "Value": v})
            
    df_util = pd.DataFrame(utilization_data)
    
    c_util, c_bottleneck = st.columns([2, 1])
    
    with c_util:
        fig_util = px.bar(
            df_util, x="Machine", y="Value", color="Type",
            title="Avg Resource Utilization Breakdown" if "MultiRunStats" in results else "Resource Utilization Breakdown",
            color_discrete_map={"Processing": "#2ca02c", "Setup": "#ff7f0e", "Failure": "#d62728", "Idle/Wait": "#1f77b4"},
            labels={"Value": "Percentage Time (%)"}
        )
        st.plotly_chart(fig_util, use_container_width=True)

    with c_bottleneck:
        proc_only = df_util[df_util["Type"] == "Processing"]
        if not proc_only.empty:
            bottleneck = proc_only.loc[proc_only['Value'].idxmax()]
            st.info(f"### 🚨 Bottleneck Alert\n**{bottleneck['Machine']}** is your most utilized resource at **{round(bottleneck['Value'], 1)}%**.")
            
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = bottleneck['Value'],
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Bottleneck Utilization"},
                gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "#d62728"}}
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_gauge, use_container_width=True)

def render_flow_dynamics(results):
    """Render WIP trend and Categorical Machine Flow."""
    c_left, c_right = st.columns(2)
    
    with c_left:
        if "Run_ID" in results["WIP_Timeline"].columns and len(results["WIP_Timeline"]["Run_ID"].unique()) > 1:
            st.subheader("📦 Work-In-Progress (WIP) Variances")
            fig_wip = px.line(results["WIP_Timeline"], x="Time", y="WIP", color="Run_ID", title="Active Batches (All Runs)", line_shape='hv')
            fig_wip.update_traces(opacity=0.6)
        else:
            st.subheader("📦 Work-In-Progress (WIP) Trend")
            fig_wip = px.area(results["WIP_Timeline"], x="Time", y="WIP", title="Active Batches in Factory", line_shape='hv', color_discrete_sequence=['#00d4ff'])
        st.plotly_chart(fig_wip, use_container_width=True)
        
    with c_right:
        st.subheader("⏳ Machine Status Timeline")
        gdf = results.get("Gantt_Log", pd.DataFrame())
        if not gdf.empty:
            machine_options = gdf["Category_ID"].unique().tolist()
            if "Run_ID" in gdf.columns:
                run_options = gdf["Run_ID"].unique().tolist()
                
                c_sel1, c_sel2 = st.columns(2)
                sel_run = c_sel1.selectbox("Select Run:", run_options)
                sel_m = c_sel2.selectbox("Select Machine:", machine_options)
                
                m_gdf = gdf[(gdf["Category_ID"] == sel_m) & (gdf["Run_ID"] == sel_run)].sort_values("Start")
            else:
                sel_m = st.selectbox("Select Machine:", machine_options)
                m_gdf = gdf[gdf["Category_ID"] == sel_m].sort_values("Start")
   
            points = []
            last_end = 0
            
            # Since total_time might be the mean across runs now, we grab the max finish of this specific run or Use the specific run's makespan
            if "df_stats" in results:
                run_idx = int(sel_run.split("_")[1]) - 1
                sp_total_time = results["df_stats"].iloc[run_idx]["Makespan"]
                run_label = f"({sel_run})"
            else:
                sp_total_time = results["Total_Time"]
                run_label = ""
                
            for _, row in m_gdf.iterrows():
                if row["Start"] > last_end:
                    points.append({"Time": last_end, "State": "Idle"})
                    points.append({"Time": row["Start"], "State": "Idle"})
                points.append({"Time": row["Start"], "State": row["State"]})
                points.append({"Time": row["Finish"], "State": row["State"]})
                last_end = max(last_end, row["Finish"])
            
            if last_end < sp_total_time:
                points.append({"Time": last_end, "State": "Idle"})
                points.append({"Time": sp_total_time, "State": "Idle"})
            
            fig_flow = px.line(pd.DataFrame(points), x="Time", y="State", title=f"{sel_m} States {run_label}", line_shape='hv')
            fig_flow.update_yaxes(categoryorder="array", categoryarray=["Failure", "Idle", "Setup", "Processing"])
            st.plotly_chart(fig_flow, use_container_width=True)

def render_job_performance(results, jobs_df):
    """Render Job Lead Time Boxplots and Target Status."""
    df_batches = results["Batch_Metrics"]
    c_job_a, c_job_b = st.columns(2)
    
    with c_job_a:
        fig_box = px.box(df_batches, x="Job_Type", y="Flow_Time", color="Job_Type", title="Lead Time Variability")
        st.plotly_chart(fig_box, use_container_width=True)
        
    with c_job_b:
        completed_counts = results["Completed_Jobs"]
        comp_list = []
        for jt, target in zip(jobs_df['Job_Type'], jobs_df['Target_Demand']):
            comp_list.append({"Job": jt, "Status": "Completed", "Value": completed_counts.get(jt, 0)})
            rem = max(0, target - completed_counts.get(jt, 0))
            if rem > 0:
                comp_list.append({"Job": jt, "Status": "Remaining", "Value": rem})
        
        fig_comp = px.bar(pd.DataFrame(comp_list), x="Job", y="Value", color="Status", title="Target Performance")
        st.plotly_chart(fig_comp, use_container_width=True)
