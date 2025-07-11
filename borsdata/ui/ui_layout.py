import streamlit as st

def setup_page():
    st.set_page_config(
        page_title="Borsdata Stock Screener",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("Borsdata Stock Screener")

def apply_custom_css():
    st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display: none;}
        .stApp > header {display: none;}
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 70vw !important;
            width: 70vw !important;
            margin-left: auto;
            margin-right: auto;
            margin-bottom: 50px;
        }
        .stDataFrame {
            width: 100%;
        }
        .stSelectbox, .stMultiselect {
            width: 100%;
        }
        .stButton > button {
            width: 100%;
        }
    </style>
    """, unsafe_allow_html=True)

def kpi_filter_help():
    with st.expander("ℹ️ How to use KPI Filter Groups"):
        st.markdown("""
        **Creating Filter Groups:**
        1. Select KPIs from the dropdown above
        2. Click "Add Group" to create a new filter group
        3. Add filters to each group using the dropdown within the group
        4. Choose AND/OR relationship within each group
        5. Choose AND/OR relationship between groups
        
        **Filter Logic:**
        - Filters within the same group use the selected operator (AND/OR)
        - Groups are combined using the "Relationship between groups" setting
        - Example: `(A AND B) OR (C AND D)` means either both A and B are true, OR both C and D are true
        
        **Filter Methods:**
        - **Absolute**: Compare KPI value to a threshold
        - **Relative**: Compare year-over-year change
        - **Direction**: Check if value is positive/negative
        - **Trend**: Check for Positive or transitions
        """)