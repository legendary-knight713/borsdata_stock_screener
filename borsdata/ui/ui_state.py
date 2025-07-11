import streamlit as st

PAGE_SIZE = 50

def initialize_session_state():
    if 'kpi_filters' not in st.session_state:
        st.session_state['kpi_filters'] = []
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 0
    if 'filter_groups' not in st.session_state:
        st.session_state['filter_groups'] = []
    if 'group_relationships' not in st.session_state:
        st.session_state['group_relationships'] = 'AND'
    if 'selected_kpis' not in st.session_state:
        st.session_state['selected_kpis'] = []
    if 'logic_preview' not in st.session_state:
        st.session_state['logic_preview'] = ''

def reset_pagination():
    st.session_state['current_page'] = 0

def pagination_controls(current_page, total_pages, total_results):
    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
    with col1:
        if st.button("← Previous", disabled=current_page == 0):
            st.session_state['current_page'] = current_page - 1
            st.rerun()
    with col2:
        st.write(f"Page {current_page + 1} of {total_pages}")
    with col3:
        st.write(f"Showing {min((current_page + 1) * PAGE_SIZE, total_results)} of {total_results} results")
    with col4:
        if st.button("Next →", disabled=current_page >= total_pages - 1):
            st.session_state['current_page'] = current_page + 1
            st.rerun()

def kpi_filter_validate():
    if st.session_state['filter_groups']:
        empty_groups = [i+1 for i, group in enumerate(st.session_state['filter_groups']) if not group['filters']]
        if empty_groups:
            st.warning(f"⚠️ Groups {empty_groups} have no filters. Add filters or remove empty groups.")