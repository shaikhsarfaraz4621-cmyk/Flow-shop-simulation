import streamlit as st
import pandas as pd
import os

def load_default_config():
    """Load the default config from the local file system."""
    base_path = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(base_path, "factory_config.xlsx")
    if os.path.exists(config_path):
        try:
            m = pd.read_excel(config_path, sheet_name="Machines")
            j = pd.read_excel(config_path, sheet_name="Jobs")
            r = pd.read_excel(config_path, sheet_name="Routings")
            return m, j, r
        except Exception as e:
            st.error(f"Error loading default config: {e}")
    return None, None, None

def initialize_session_state():
    """Initialize the session state with default data if not already present."""
    if 'machines_df' not in st.session_state:
        m, j, r = load_default_config()
        st.session_state['machines_df'] = m
        st.session_state['jobs_df'] = j
        st.session_state['routings_df'] = r

def handle_file_upload(uploaded_file):
    """Update session state with data from uploaded Excel file."""
    if uploaded_file:
        try:
            st.session_state['machines_df'] = pd.read_excel(uploaded_file, sheet_name="Machines")
            st.session_state['jobs_df'] = pd.read_excel(uploaded_file, sheet_name="Jobs")
            st.session_state['routings_df'] = pd.read_excel(uploaded_file, sheet_name="Routings")
            st.success("Config uploaded successfully!")
            return True
        except Exception as e:
            st.error(f"Error reading file: {e}")
    return False
