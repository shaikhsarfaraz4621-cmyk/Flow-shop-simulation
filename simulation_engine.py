import simpy
import random
import math
import logging
import pandas as pd
from typing import Dict, List, Any

# Configure simple logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

def get_lognormal_params(mean, std):
    """Convert desired mean and standard dev to underlying normal distribution parameters."""
    variance = std ** 2
    mean_sq = mean ** 2
    # Ensure mean_sq is positive
    sigma = math.sqrt(math.log(1 + variance / mean_sq))
    mu = math.log(mean) - (sigma ** 2) / 2
    return mu, sigma

class FactorySimulation:
    def __init__(self, machines_df: pd.DataFrame, jobs_df: pd.DataFrame, routings_df: pd.DataFrame):
        self.env = simpy.Environment()
        self.machines_df = machines_df
        self.jobs_df = jobs_df
        self.routings_df = routings_df
        
        self.machines = {}  # {machine_id: simpy.PriorityResource}
        self.machine_stats = {} # utilization tracking
        self.machine_current_state = {} # tracking number of units in each state right now
        
        self.completed_jobs = {job: 0 for job in jobs_df['Job_Type'].unique()}
        self.target_demand = dict(zip(jobs_df['Job_Type'], jobs_df['Target_Demand']))
        self.batch_sizes = dict(zip(jobs_df['Job_Type'], jobs_df['Batch_Size']))
        
        self.all_demands_met = self.env.event()
        
        self.log_events = []
        self.state_timeline = [] # Strict step-chart point-in-time data
        self.gantt_log = [] # Explicit Start-End blocks for states
        
        # Advanced Metrics tracking
        self.batch_metrics = [] # {batch_id: ..., start_time, end_time, active_time}
        self.current_wip = 0
        self.wip_timeline = [] # {time, wip}
        
    def log(self, time, machine, job, batch_id, event_type, details=""):
        self.log_events.append({
            "Time": round(time, 2),
            "Machine": machine,
            "Job": job,
            "Batch": batch_id,
            "Event": event_type,
            "Details": details
        })

    def change_machine_state(self, m_id, state_key, delta):
        # Update current state count
        self.machine_current_state[m_id][state_key] += delta
        count = self.machine_current_state[m_id]["Count"]
        
        proc = self.machine_current_state[m_id]["Processing"]
        setup = self.machine_current_state[m_id]["Setup"]
        fail = self.machine_current_state[m_id]["Failure"]
        idle = count - (proc + setup + fail)
        
        self.state_timeline.append({
            "Time": self.env.now,
            "Machine": m_id,
            "Processing": proc,
            "Setup": setup,
            "Failure": fail,
            "Idle": idle
        })

    def change_wip(self, delta):
        self.current_wip += delta
        self.wip_timeline.append({"Time": self.env.now, "WIP": self.current_wip})
        
    def setup_factory(self):
        # Initialize WIP
        self.change_wip(0)
        
        # Create Machines
        for _, row in self.machines_df.iterrows():
            m_id = row['Machine_ID']
            count = int(row['Count'])
            self.machines[m_id] = simpy.PriorityResource(self.env, capacity=count)
            self.machine_stats[m_id] = {'working_time': 0, 'setup_time': 0, 'down_time': 0, 'completed_operations': 0}
            self.machine_current_state[m_id] = {"Count": count, "Processing": 0, "Setup": 0, "Failure": 0}
            
            # Initial state log
            self.change_machine_state(m_id, "Processing", 0) 
            
            # Start failure/repair process for this machine category
            for i in range(count):
                self.env.process(self.machine_failure_process(
                    m_id, 
                    alpha=row['Weibull_Shape_Alpha'], 
                    beta=row['Weibull_Scale_Beta'], 
                    mu=row['Lognormal_Mu'], 
                    sigma=row['Lognormal_Sigma'],
                    unit_index=i+1
                ))

    def machine_failure_process(self, m_id, alpha, beta, mu, sigma, unit_index):
        """Simulate machine breakdowns and repairs."""
        resource = self.machines[m_id]
        norm_mu, norm_sigma = get_lognormal_params(mu, sigma)
        
        while True:
            time_to_fail = random.weibullvariate(beta, alpha)
            yield self.env.timeout(time_to_fail)
            
            with resource.request(priority=0) as req:
                yield req
                start_fail = self.env.now
                self.log(self.env.now, m_id, "System", f"Unit_{unit_index}", "Failure Start")
                self.change_machine_state(m_id, "Failure", 1)
                
                repair_time = random.lognormvariate(norm_mu, norm_sigma)
                yield self.env.timeout(repair_time)
                
                self.machine_stats[m_id]['down_time'] += repair_time
                self.change_machine_state(m_id, "Failure", -1)
                self.log(self.env.now, m_id, "System", f"Unit_{unit_index}", "Failure End (Repaired)")
                
                # Append to explicit Gantt Log
                self.gantt_log.append({
                    "Machine": f"{m_id}_{unit_index}", 
                    "Category_ID": m_id,
                    "State": "Failure", 
                    "Start": start_fail, 
                    "Finish": self.env.now
                })
            
    def process_job_batch(self, job_type, batch_id):
        """A single batch of a job type moving through its routing sequence."""
        routing = self.routings_df[self.routings_df['Job_Type'] == job_type].sort_values('Sequence_Order')
        batch_size = self.batch_sizes[job_type]
        
        start_time = self.env.now
        self.change_wip(1)
        active_work_time = 0
        
        for _, step in routing.iterrows():
            m_id = step['Machine_ID']
            setup_time = step['Setup_Time_Per_Batch']
            process_time_per_unit = step['Process_Time_Per_Unit']
            total_process_time = process_time_per_unit * batch_size
            
            with self.machines[m_id].request(priority=1) as machine_req:
                self.log(self.env.now, m_id, job_type, batch_id, "Queue Enter")
                yield machine_req
                self.log(self.env.now, m_id, job_type, batch_id, "Queue Exit / Start Setup")
                
                # Setup
                start_setup = self.env.now
                self.change_machine_state(m_id, "Setup", 1)
                yield self.env.timeout(setup_time)
                self.change_machine_state(m_id, "Setup", -1)
                self.machine_stats[m_id]['setup_time'] += setup_time
                active_work_time += setup_time
                self.log(self.env.now, m_id, job_type, batch_id, "Setup Finish / Start Process")
                
                # Log explicitly per unit processing it (for Count > 1, we just label it as Machine_1 arbitrarily for Gantt if simpy doesn't expose it easily. Instead, we'll label by batch_id roughly)
                unit_label = f"{m_id}_u1" # Simplified label for Gantt unit tracking
                self.gantt_log.append({"Machine": unit_label, "Category_ID": m_id, "State": "Setup", "Start": start_setup, "Finish": self.env.now})
                
                # Processing
                start_proc = self.env.now
                self.change_machine_state(m_id, "Processing", 1)
                yield self.env.timeout(total_process_time)
                self.change_machine_state(m_id, "Processing", -1)
                self.machine_stats[m_id]['working_time'] += total_process_time
                self.machine_stats[m_id]['completed_operations'] += 1
                active_work_time += total_process_time
                self.log(self.env.now, m_id, job_type, batch_id, "Process Finish", details=f"Processed {batch_size} units")
                
                self.gantt_log.append({"Machine": unit_label, "Category_ID": m_id, "State": "Processing", "Start": start_proc, "Finish": self.env.now})
        
        # Batch completed
        end_time = self.env.now
        self.change_wip(-1)
        
        self.batch_metrics.append({
            "Job_Type": job_type,
            "Batch_ID": batch_id,
            "Units": batch_size,
            "Start_Time": start_time,
            "End_Time": end_time,
            "Flow_Time": end_time - start_time,
            "Active_Time": active_work_time
        })
        
        self.completed_jobs[job_type] += batch_size
        
        if all(self.completed_jobs[jt] >= self.target_demand[jt] for jt in self.target_demand):
            if not self.all_demands_met.triggered:
                self.all_demands_met.succeed()

    def job_source(self, job_type):
        """Generate batches for a specific job type until demand is met."""
        batch_size = self.batch_sizes[job_type]
        target = self.target_demand[job_type]
        batches_needed = (target + batch_size - 1) // batch_size
        
        for i in range(batches_needed):
            batch_id = f"{job_type}_{i+1}"
            self.env.process(self.process_job_batch(job_type, batch_id=batch_id))
            # Spawn jobs at time 0 to heavily load the factory
            # If the factory needs a pull system or specific arrival rate, a timeout would be used here.
            yield self.env.timeout(0)

    def run(self):
        self.setup_factory()
        
        for job_type in self.target_demand.keys():
            self.env.process(self.job_source(job_type))
            
        self.env.run(until=self.all_demands_met)
        
        return {
            "Total_Time": self.env.now,
            "Completed_Jobs": self.completed_jobs,
            "Machine_Stats": self.machine_stats,
            "Logs": pd.DataFrame(self.log_events),
            "State_Timeline": pd.DataFrame(self.state_timeline),
            "Gantt_Log": pd.DataFrame(self.gantt_log),
            "Batch_Metrics": pd.DataFrame(self.batch_metrics),
            "WIP_Timeline": pd.DataFrame(self.wip_timeline)
        }

def run_simulation(machines_df, jobs_df, routings_df):
    sim = FactorySimulation(machines_df, jobs_df, routings_df)
    results = sim.run()
    return results
