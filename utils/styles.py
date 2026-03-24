import streamlit as st

def inject_custom_css():
    """Inject premium Dark Mode CSS into the Streamlit app."""
    st.markdown("""
    <style>
        /* Main Background */
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        
        /* Metric Cards */
        [data-testid="stMetricValue"] {
            font-size: 2.2rem;
            color: #00d4ff;
            font-weight: 700;
        }
        [data-testid="stMetricLabel"] {
            color: #8892b0;
        }
        div[data-testid="metric-container"] {
            background-color: #1a1f29;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            border: 1px solid #2d3748;
        }
        
        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #161b22;
            border-right: 1px solid #30363d;
        }
        
        /* Custom Headers */
        .dashboard-header {
            background: linear-gradient(135deg, #00d4ff 0%, #00ff7f 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
            font-size: 3rem;
            margin-bottom: 25px;
            letter-spacing: -1px;
        }

        /* Subheaders */
        h1, h2, h3 {
            color: #ffffff !important;
        }

        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            color: #8892b0;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: #00d4ff;
        }
        .stTabs [aria-selected="true"] {
            color: #ffffff !important;
            border-bottom-color: #00d4ff !important;
        }
    </style>
    """, unsafe_allow_html=True)
