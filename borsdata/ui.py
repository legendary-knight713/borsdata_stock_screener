import streamlit as st
import pandas as pd
from borsdata_api import BorsdataAPI
from constants import API_KEY
from filter_engine import filter_by_metadata, evaluate_filter_tree, filter_data_by_time_range
import json
import os
import datetime
import tempfile

# --- Helper: Fetch yearly KPI history for multiple stocks ---
def fetch_yearly_kpi_history(api, stock_ids, kpi_id):
    """Fetch yearly KPI history for each stock and return a DataFrame with columns: insId, year, kpiValue"""
    all_rows = []
    for ins_id in stock_ids:
        try:
            df = api.get_kpi_history(ins_id, kpi_id, report_type='year', price_type='mean')
            if df is not None and not df.empty:
                for idx, row in df.iterrows():
                    # idx is (year, period) or just year
                    if isinstance(idx, tuple):
                        year = idx[0]
                    else:
                        year = idx
                    kpi_value = row.get('kpiValue') or row.get('value') or row.get('v')
                    if year is not None and kpi_value is not None:
                        try:
                            year_int = int(year) if year is not None else None
                            ins_id_int = int(ins_id) if ins_id is not None else None
                            if year_int is not None and ins_id_int is not None:
                                all_rows.append({
                                    'insId': ins_id_int,
                                    'year': year_int,
                                    'kpiValue': kpi_value
                                })
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            continue
    
    # Build DataFrame and ensure integer types
    df_result = pd.DataFrame(all_rows)
    if not df_result.empty:
        df_result['insId'] = df_result['insId'].astype(int)
        df_result['year'] = df_result['year'].astype(int)
    
    return df_result

def test_kpi_quarterly_availability(api, kpi_filters, stock_ids):
    problematic_kpis = []
    if not stock_ids:
        return problematic_kpis
    test_stock_id = stock_ids[0]  # Use the first stock for testing
    for f in kpi_filters:
        freq = f.get('data_frequency', 'Quarterly')
        if str(freq).lower().startswith('quarter'):
            kpi_id = f.get('kpi_id') or f.get('kpiId') or f.get('kpi')
            kpi_name = f.get('kpi_name') or f.get('kpi') or str(kpi_id)
            if not kpi_id:
                continue
            try:
                df = api.get_kpi_history(test_stock_id, kpi_id, report_type='quarter', price_type='mean', max_count=1)
                # If the result is None or empty, treat as unsupported
                if df is None or (hasattr(df, 'empty') and df.empty):
                    problematic_kpis.append(kpi_name)
            except Exception as e:
                msg = str(e)
                st.write(f"Test fetch for KPI {kpi_name} ({kpi_id}) failed: {msg}")
                # Check for 400 error or log message
                if 'API-Error, status code: 400' in msg or '400' in msg:
                    problematic_kpis.append(kpi_name)
    return problematic_kpis

# --- Helper Functions for UI Components ---
def create_method_config(method_type, kpi_name, method_count):
    """Create a new method configuration with None defaults"""
    return {
        'type': method_type,
        'id': f'{kpi_name}_{method_type}_{method_count}',
        # Initialize with None/empty values - will be set when user interacts
        'operator_abs': None,
        'value': None,
        'duration_type': None,
        'last_n': None,
        'start_quarter': '',
        'end_quarter': '',
        'rel_operator': None,
        'rel_value': None,
        'rel_period': None,
        'direction': None,
        'trend_type': None,
        'trend_n': None,
        'trend_m': None,
        'data_frequency': 'Quarterly'
    }

def render_method_selector(group_idx, kpi_idx, kpi_name, kpi_settings):
    """Render the method selection UI (no Remove Method button here)"""
    add_method_cols = st.columns([1])
    with add_method_cols[0]:
        existing_methods = [method['type'] for method in kpi_settings['methods']]
        available_methods = [''] + [method for method in ['Absolute', 'Relative', 'Direction', 'Trend'] if method not in existing_methods]
        if len(existing_methods) >= 4:
            st.info("All methods already added for this KPI")
        else:
            new_method = st.selectbox(
                'Add Method',
                available_methods,
                key=f'add_method_{group_idx}_{kpi_idx}_{kpi_name}'
            )
            if new_method:
                method_config = create_method_config(new_method, kpi_name, len(kpi_settings["methods"]))
                kpi_settings['methods'].append(method_config)
                reset_results()
    return None

def render_method_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render method-specific parameter inputs with Remove Method button in the same row"""
    method_row_cols = st.columns([4, 1])
    with method_row_cols[0]:
        param_cols = st.columns([1, 1])
        with param_cols[0]:
            if method_config['type'] == 'Absolute':
                render_absolute_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config)
            elif method_config['type'] == 'Relative':
                render_relative_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config)
            elif method_config['type'] == 'Direction':
                render_direction_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config)
            elif method_config['type'] == 'Trend':
                render_trend_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config)
        with param_cols[1]:
            render_method_values(group_idx, kpi_idx, method_idx, kpi_name, method_config)
    with method_row_cols[1]:
        st.markdown("<div style='height: 1.7em'></div>", unsafe_allow_html=True)
        remove_method_clicked = st.button('Remove Method', key=f'remove_method_{group_idx}_{kpi_idx}_{method_idx}')
        if remove_method_clicked:
            return True  # Signal to remove method
    return False

def render_absolute_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render Absolute method parameters"""
    # Operator
    current_operator = method_config.get('operator_abs')
    if current_operator is None:
        current_operator = '>'
    elif current_operator not in ['>', '>=', '<', '<=', '=']:
        current_operator = '>'
    selected_operator = st.selectbox(
        'Operator',
        ['>', '>=', '<', '<=', '='],
        index=['>', '>=', '<', '<=', '='].index(current_operator),
        key=f'op_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['operator_abs'] = selected_operator

def render_relative_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render Relative method parameters"""
    # Operator
    current_operator = method_config.get('rel_operator')
    if current_operator is None:
        current_operator = '>='
    elif current_operator not in ['>', '>=', '<', '<=', '=']:
        current_operator = '>='
    selected_operator = st.selectbox(
        'Operator',
        ['>', '>=', '<', '<=', '='],
        index=['>', '>=', '<', '<=', '='].index(current_operator),
        key=f'rel_op_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['rel_operator'] = selected_operator

def render_direction_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render Direction method parameters"""
    # Direction
    current_direction = method_config.get('direction')
    if current_direction is None:
        current_direction = 'positive'
    elif current_direction not in ['positive', 'negative', 'either']:
        current_direction = 'positive'
    selected_direction = st.selectbox(
        'Direction',
        ['positive', 'negative', 'either'],
        index=['positive', 'negative', 'either'].index(current_direction),
        key=f'dir_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['direction'] = selected_direction

def render_trend_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render Trend method parameters: type select, then delegate to settings."""
    # Trend type selectbox
    current_trend_type = method_config.get('trend_type')
    if current_trend_type not in [
        'Positive', 'Negative', 'Positive-to-Negative', 'Negative-to-Positive']:
        current_trend_type = 'Positive'
    selected_trend_type = st.selectbox(
        'Trend Type',
        ['Positive', 'Negative', 'Positive-to-Negative', 'Negative-to-Positive'],
        index=['Positive', 'Negative', 'Positive-to-Negative', 'Negative-to-Positive'].index(current_trend_type),
        key=f'trend_type_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['trend_type'] = selected_trend_type
    render_trend_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config)

def render_method_values(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render method value inputs"""
    if method_config['type'] == 'Absolute':
        current_value = method_config.get('value')
        if current_value is None:
            current_value = 0.0
        input_value = st.number_input(
            'Value',
            value=current_value,
            key=f'val_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['value'] = input_value
    elif method_config['type'] == 'Relative':
        current_value = method_config.get('rel_value')
        if current_value is None:
            current_value = 0.0
        input_value = st.number_input(
            'Value (%)',
            value=current_value,
            key=f'rel_val_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['rel_value'] = input_value
    elif method_config['type'] == 'Trend':
        st.write("Configure in settings below")

def render_time_range_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render time range settings for methods that need them"""
    if method_config['type'] in ['Absolute', 'Relative', 'Direction']:
        st.markdown("**Time Range:**")
        
        # Radio button for duration type
        current_duration_type = method_config.get('duration_type')
        if current_duration_type is None:
            current_duration_type = 'Last N Quarters'
        elif current_duration_type not in ['Last N Quarters', 'Custom Range']:
            current_duration_type = 'Last N Quarters'
        
        selected_duration_type = st.radio(
            'Duration Type',
            ['Last N Quarters', 'Custom Range'],
            index=['Last N Quarters', 'Custom Range'].index(current_duration_type),
            key=f'durtype_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['duration_type'] = selected_duration_type
        
        # Data frequency selector (Quarterly/Yearly)
        current_frequency = method_config.get('data_frequency', 'Quarterly')
        selected_frequency = st.selectbox(
            'Data Frequency',
            ['Quarterly', 'Yearly'],
            index=['Quarterly', 'Yearly'].index(current_frequency),
            key=f'datafreq_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['data_frequency'] = selected_frequency
        
        # Clear conflicting parameters when switching duration type
        if selected_duration_type == 'Last N Quarters':
            # Clear custom range parameters
            method_config.pop('start_quarter', None)
            method_config.pop('end_quarter', None)
            if method_config.get('last_n') is None:
                method_config['last_n'] = 1
        else:
            # Clear last N quarters parameter
            method_config['last_n'] = None
        
        # Render appropriate inputs based on selection
        if method_config['duration_type'] == 'Last N Quarters':
            current_value = method_config.get('last_n')
            if current_value is None or current_value == 0:
                current_value = 1  # Default to 1 quarter
            input_value = st.number_input(
                'Last N Quarters',
                min_value=1,
                max_value=40,
                value=current_value,
                key=f'lastn_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
            )
            method_config['last_n'] = input_value
        else:
            # Custom range inputs with proper format validation
            custom_cols = st.columns([2, 2])
            with custom_cols[0]:
                current_start_quarter = method_config.get('start_quarter', '')
                selected_start_quarter = st.text_input(
                    'Start Quarter (e.g., 2023-Q1 or 2023)',
                    value=current_start_quarter,
                    placeholder='2023-Q1 or 2023',
                    key=f'startq_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
                )
                method_config['start_quarter'] = selected_start_quarter
                freq = method_config.get('data_frequency', 'Quarterly')
                # Validate format based on frequency
                if selected_start_quarter:
                    if freq == 'Quarterly':
                        if not (len(selected_start_quarter) == 7 and 
                                selected_start_quarter[4] == '-' and 
                                selected_start_quarter[6] in ['1','2','3','4']):
                            st.error("Format should be YYYY-Qx (e.g., 2023-Q1) for Quarterly frequency.")
                    elif freq == 'Yearly':
                        if not (len(selected_start_quarter) == 4 and selected_start_quarter.isdigit()):
                            st.error("Format should be YYYY (e.g., 2023) for Yearly frequency.")
            
            with custom_cols[1]:
                current_end_quarter = method_config.get('end_quarter', '')
                selected_end_quarter = st.text_input(
                    'End Quarter (e.g., 2023-Q4 or 2023)',
                    value=current_end_quarter,
                    placeholder='2023-Q4 or 2023',
                    key=f'endq_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
                )
                method_config['end_quarter'] = selected_end_quarter
                freq = method_config.get('data_frequency', 'Quarterly')
                # Validate format based on frequency
                if selected_end_quarter:
                    if freq == 'Quarterly':
                        if not (len(selected_end_quarter) == 7 and 
                                selected_end_quarter[4] == '-' and 
                                selected_end_quarter[6] in ['1','2','3','4']):
                            st.error("Format should be YYYY-Qx (e.g., 2023-Q4) for Quarterly frequency.")
                    elif freq == 'Yearly':
                        if not (len(selected_end_quarter) == 4 and selected_end_quarter.isdigit()):
                            st.error("Format should be YYYY (e.g., 2023) for Yearly frequency.")

        # Validation: warn if custom range format and frequency mismatch
        if method_config['duration_type'] == 'Custom Range':
            start_q = method_config.get('start_quarter', '')
            end_q = method_config.get('end_quarter', '')
            freq = method_config.get('data_frequency', 'Quarterly')
            # If either start or end looks like a quarter (YYYY-Qx)
            is_quarter_range = (start_q and len(start_q) == 7 and start_q[4] == '-' and start_q[6] in ['1','2','3','4']) or \
                               (end_q and len(end_q) == 7 and end_q[4] == '-' and end_q[6] in ['1','2','3','4'])
            # If both are just years (YYYY)
            is_year_range = (start_q and len(start_q) == 4 and start_q.isdigit()) and (end_q and len(end_q) == 4 and end_q.isdigit())
            if is_quarter_range and freq != 'Quarterly':
                st.warning('Custom range uses quarters (e.g., 2023-Q1), but frequency is not Quarterly. Please set frequency to Quarterly.')
            if is_year_range and freq != 'Yearly':
                st.warning('Custom range uses years (e.g., 2023), but frequency is not Yearly. Please set frequency to Yearly.')

def render_relative_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render additional parameters for Relative method"""
    if method_config['type'] == 'Relative':
        st.markdown("**Relative Settings:**")
        rel_cols = st.columns([2, 2])
        with rel_cols[0]:
            # New: Let user choose YoY or QoQ
            rel_mode = method_config.get('rel_mode', 'Year-over-Year (YoY)')
            rel_mode = st.selectbox(
                'Comparison Type',
                ['Year-over-Year (YoY)', 'Quarter-over-Quarter (QoQ)'],
                index=['Year-over-Year (YoY)', 'Quarter-over-Quarter (QoQ)'].index(rel_mode),
                key=f'rel_mode_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
            )
            method_config['rel_mode'] = rel_mode

def render_trend_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    """Render detailed settings for the selected trend type (n, m, etc.), with n full width if alone, or n and m half width if both."""
    selected_trend_type = method_config.get('trend_type', 'Positive')
    if selected_trend_type in ['Positive-to-Negative', 'Negative-to-Positive']:
        cols = st.columns(2)
        with cols[0]:
            trend_n = method_config.get('trend_n', 3)
            trend_n = st.number_input(
                'Periods (n)',
                min_value=2,
                max_value=40,
                value=int(trend_n) if trend_n is not None else 3,
                step=1,
                key=f'trend_n_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
            )
            method_config['trend_n'] = trend_n
        with cols[1]:
            trend_m = method_config.get('trend_m', None)
            trend_m = st.number_input(
                'Growth/Decline after m Q',
                min_value=0,
                max_value=trend_n,
                value=int(trend_m) if trend_m not in (None, "") else 0,
                step=1,
                key=f'trend_m_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}',
                help='Optional: m is the number of growth (or decline) quarters within the n-quarter window. Leave as 0 to ignore.'
            )
            if trend_m == 0:
                method_config['trend_m'] = None
            else:
                method_config['trend_m'] = trend_m
    else:
        trend_n = method_config.get('trend_n', 3)
        trend_n = st.number_input(
            'Periods (n)',
            min_value=2,
            max_value=40,
            value=int(trend_n) if trend_n is not None else 3,
            step=1,
            key=f'trend_n_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['trend_n'] = trend_n
        method_config['trend_m'] = None

def render_kpi_instance(group_idx, kpi_idx, kpi_name, group):
    kpi_instance_key = f"{kpi_name}_{kpi_idx}"
    kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
    if 'methods' not in kpi_settings:
        kpi_settings['methods'] = []
    methods = kpi_settings.get('methods', [])
    # KPI header with name and remove button in same row, with less vertical space
    kpi_header_cols = st.columns([3, 1])
    with kpi_header_cols[0]:
        st.markdown(f"**{kpi_name}**", unsafe_allow_html=True)
    with kpi_header_cols[1]:
        remove_kpi_clicked = st.button('Remove KPI', key=f'remove_kpi_{group_idx}_{kpi_idx}')
        if remove_kpi_clicked:
            group['filters'].pop(kpi_idx)
            if kpi_instance_key in group['filter_settings']:
                del group['filter_settings'][kpi_instance_key]
            reset_results()
    # Tighter spacing before method selector
    st.markdown("<div style='margin-bottom: -1.5em'></div>", unsafe_allow_html=True)
    method_removed = render_method_selector(group_idx, kpi_idx, kpi_name, kpi_settings)
    group['filter_settings'][kpi_instance_key] = kpi_settings
    if method_removed:
        return
    if len(methods) > 1:
        current_operator = kpi_settings.get('method_operator', 'AND')
        selected_operator = st.radio(
            'Combine methods with:',
            ['AND', 'OR'],
            index=['AND', 'OR'].index(current_operator),
            key=f'method_operator_{group_idx}_{kpi_idx}_{kpi_name}'
        )
        kpi_settings['method_operator'] = selected_operator
        group['filter_settings'][kpi_instance_key] = kpi_settings
    if methods:
        for method_idx, method_config in enumerate(methods):
            st.markdown(f"**{method_config['type']} Method**")
            should_remove = render_method_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config)
            if should_remove:
                methods.pop(method_idx)
                reset_results()
            render_time_range_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config)
            render_relative_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config)
            st.markdown("---")

def render_filter_group(group_idx, group):
    """Render a single filter group"""
    st.markdown(f"**Group {group_idx + 1}**")
    
    # Group header with controls
    group_cols = st.columns([2, 1, 1])
    
    with group_cols[0]:
        # KPI selection within group - allow duplicates for multiple method configurations
        if st.session_state['selected_kpis']:
            # Use a unique key that changes when the group changes
            new_kpi = st.selectbox(
                f'Add KPI to Group {group_idx + 1}',
                [''] + st.session_state['selected_kpis'],
                key=f'add_kpi_{group_idx}_{group["id"]}_{len(group["filters"])}'
            )
            if new_kpi:
                group['filters'].append(new_kpi)
                # Don't reset results when just adding a KPI without methods
    
    with group_cols[1]:
        # Within-group operator (AND/OR)
        group['operator'] = st.selectbox(
            'Within Group',
            ['AND', 'OR'],
            index=['AND', 'OR'].index(group['operator']),
            key=f'group_op_{group_idx}'
        )
    
    with group_cols[2]:
        # Remove group button
        st.markdown("<div style='height: 1.7em'></div>", unsafe_allow_html=True)
        remove_group_clicked = st.button('Remove Group', key=f'remove_group_{group_idx}')
        if remove_group_clicked:
            st.session_state['filter_groups'].pop(group_idx)
            # Only reset results when a group is actually removed
            reset_results()
    
    # Display KPIs in this group
    if group['filters']:
        st.markdown("**KPIs in this group:**")
        
        # Initialize filter settings if not exists
        if 'filter_settings' not in group:
            group['filter_settings'] = {}
        
        for kpi_idx, kpi_name in enumerate(group['filters']):
            render_kpi_instance(group_idx, kpi_idx, kpi_name, group)
        
        st.markdown("---")

# --- Configure Streamlit layout for wider container ---
st.set_page_config(
    page_title="Borsdata Stock Screener",
    page_icon="📊",
    layout="wide",  # Use wide layout instead of centered
    initial_sidebar_state="expanded"
)

# --- Custom CSS to maximize container width and hide header elements ---
st.markdown("""
<style>
    /* Hide Streamlit header elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Hide deploy button and other header buttons */
    .stDeployButton {display: none;}
    .stApp > header {display: none;}
    
    /* Maximize container width */
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

# --- Ensure session state is initialized before any function or logic tree code ---
if 'kpi_filters' not in st.session_state:
    st.session_state['kpi_filters'] = []
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 0

# --- Config ---
PAGE_SIZE = 50

# --- Initialize API ---
api = BorsdataAPI(API_KEY)

# --- Single cache function for all initial data ---
@st.cache_data
def fetch():
    base_df_global = api.get_instruments_global()
    base_df_local = api.get_instruments()
    if not isinstance(base_df_global, pd.DataFrame):
        base_df_global = pd.DataFrame(base_df_global)
    if not isinstance(base_df_local, pd.DataFrame):
        base_df_local = pd.DataFrame(base_df_local)
    all_instruments_df = pd.concat([base_df_global, base_df_local], ignore_index=True)
    all_countries_df = api.get_countries().reset_index()
    all_markets_df = api.get_markets().reset_index()
    all_sectors_df = api.get_sectors().reset_index()
    all_branches_df = api.get_branches().reset_index()
    df_kpis = api.get_kpi_metadata().reset_index()
    return (all_instruments_df, all_countries_df, all_markets_df, all_sectors_df, all_branches_df, df_kpis)

# --- Unified data fetch for all initial data (no spinner) ---
(all_instruments_df, all_countries_df, all_markets_df, all_sectors_df, all_branches_df, df_kpis) = fetch()

# --- Fetch all stocks (no pagination here) ---
def get_filtered_stocks(country_ids=None, market_ids=None) -> pd.DataFrame:
    # Use the combined DataFrame of global and local instruments
    df = all_instruments_df.copy()
    if country_ids is not None:
        country_ids = [int(x) for x in list(country_ids)]
        df = pd.DataFrame(df)
        df = df[df['countryId'].isin(country_ids)]
    if market_ids is not None:
        market_ids = [int(x) for x in list(market_ids)]
        df = pd.DataFrame(df)
        # Check if all available marketIds for the filtered country are selected
        available_market_ids = set(df['marketId'].dropna().unique())
        if set(market_ids) == set(available_market_ids):
            # 'Select All' case: include NaNs
            df = df[df['marketId'].isin(market_ids) | df['marketId'].isnull()]
        else:
            df = df[df['marketId'].isin(market_ids)]
    return pd.DataFrame(df)

# --- Pagination UI Functions ---
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

def reset_pagination():
    st.session_state['current_page'] = 0

# --- Main UI ---
st.title("Borsdata Stock Screener")

# Helper to safely get first value from DataFrame/Series
def get_first_value(df, col):
    if isinstance(df, pd.DataFrame):
        val = df[col].iloc[0]
    elif isinstance(df, pd.Series):
        val = df.iloc[0]
    else:
        val = list(df)[0] if len(df) > 0 else None
    return val

# Countries (from API master list)
df_countries = all_countries_df
if 'name' in df_countries.columns:
    df_countries = df_countries.sort_values(by='name')
country_options = list(df_countries['name'])
country_ids = list(df_countries['id'])
# Build mapping from name to ID, but only for IDs present in the combined data
available_country_ids = set(pd.Series(all_instruments_df['countryId']).tolist())
country_id_name_map = {row['name']: row['id'] for _, row in df_countries.iterrows() if row['id'] in available_country_ids}

# Sectors (from API master list)
df_sectors = all_sectors_df
if 'name' in df_sectors.columns:
    df_sectors = df_sectors.sort_values(by='name')
sector_options = list(df_sectors['name'])
sector_ids = list(df_sectors['id'])
# Only show sectors present in the combined data
available_sector_ids = set(pd.Series(all_instruments_df['sectorId']).tolist())
sector_id_name_map = {row['name']: row['id'] for _, row in df_sectors.iterrows() if row['id'] in available_sector_ids}

# --- Helper to reset results if filters change ---
def reset_results():
    st.session_state['results_ready'] = False
    st.session_state['filtered_instruments'] = None
    st.session_state['current_page'] = 0

selected_countries = st.multiselect(
    'Countries',
    options=country_options,
    format_func=lambda x: x,
    placeholder='--- Choose countries ---',
    key='selected_countries'
)
# Markets (from API master list, only for selected countries)
df_markets = all_markets_df
if not isinstance(df_markets, pd.DataFrame):
    df_markets = pd.DataFrame(df_markets)
selected_markets = set()
if selected_countries:
    for country_id in [country_id_name_map[c] for c in selected_countries if c in country_id_name_map]:
        country_name = get_first_value(df_countries[df_countries['id'] == country_id], 'name')
        df_markets_country = df_markets[df_markets['countryId'] == country_id]
        df_markets_country = pd.DataFrame(df_markets_country) if not isinstance(df_markets_country, pd.DataFrame) else df_markets_country
        if 'name' in df_markets_country.columns:
            df_markets_country = df_markets_country.sort_values(by='name')
        available_market_ids = set(pd.Series(all_instruments_df[all_instruments_df['countryId'] == country_id]['marketId']).tolist())
        market_options = [row['name'] for _, row in df_markets_country.iterrows() if row['id'] in available_market_ids]
        market_ids = [row['id'] for _, row in df_markets_country.iterrows() if row['id'] in available_market_ids]
        market_id_name_map = dict(zip(market_options, market_ids))
        st.write(f"Markets in {country_name}")
        select_all_key = f"select_all_markets_{country_id}"
        if st.button("Select All", key=select_all_key):
            for m_id in market_ids:
                st.session_state[f"market_{country_id}_{m_id}"] = True
        for i in range(0, len(market_options), 3):
            cols = st.columns(3)
            for j, m_name in enumerate(market_options[i:i+3]):
                m_id = market_id_name_map[m_name]
                key = f"market_{country_id}_{m_id}"
                if key not in st.session_state:
                    st.session_state[key] = False
                cb = cols[j].checkbox(str(m_name), key=key)
                if st.session_state[key]:
                    selected_markets.add(m_id)
                else:
                    selected_markets.discard(m_id)
    
selected_sectors = st.multiselect(
    'Sectors', 
    options=sector_options, 
    key='selected_sectors', 
    placeholder='--- Choose sectors ---')
# Industries (from API master list, only for selected sectors)
selected_industries = set()
if selected_sectors:
    df_branches = all_branches_df
    if 'name' in df_branches.columns:
        df_branches = df_branches.sort_values(by='name')
    
    # Process each selected sector
    for sector_id in [sector_id_name_map[s] for s in selected_sectors if s in sector_id_name_map]:
        sector_name = get_first_value(df_sectors[df_sectors['id'] == sector_id], 'name')
        df_industries_sector = df_branches[df_branches['sectorId'] == sector_id]
        
        # Get the actual industry IDs that exist in the data for this sector
        available_branch_ids = set(pd.Series(all_instruments_df[all_instruments_df['sectorId'] == sector_id]['branchId']).tolist())
        
        # Create industry options using the actual IDs from the data
        industry_options = []
        industry_ids = []
        industry_id_name_map = {}
        
        # Get unique industry names and their corresponding IDs from the data
        sector_data = pd.DataFrame(all_instruments_df[all_instruments_df['sectorId'] == sector_id])
        
        # Get unique industry IDs from the data
        unique_branch_ids = set(pd.Series(sector_data['branchId']).dropna().unique())
        
        # Create industry options using the actual IDs from the data
        industry_options = []
        industry_ids = []
        industry_id_name_map = {}
        
        # Get industry names from the master data for the IDs that exist in our data
        for branch_id in unique_branch_ids:
            if pd.notna(branch_id):
                # Find the industry name from the master data
                branch_info = df_branches[df_branches['id'] == branch_id]
                if not branch_info.empty:
                    industry_name = branch_info.iloc[0]['name']
                    industry_id = int(branch_id)
                    industry_options.append(industry_name)
                    industry_ids.append(industry_id)
                    industry_id_name_map[industry_name] = industry_id
        
        st.write(f"Industries in {sector_name}")
        select_all_ind_key = f"select_all_industries_{sector_id}"
        if st.button("Select All", key=select_all_ind_key):
            for i_id in industry_ids:
                st.session_state[f"industry_{sector_id}_{i_id}"] = True
        
        # Build selected_industries from session state for this sector
        for i_id in industry_ids:
            key = f"industry_{sector_id}_{i_id}"
            if key not in st.session_state:
                st.session_state[key] = False
            if st.session_state[key]:
                selected_industries.add(i_id)
        
        # Render checkboxes for this sector
        for i in range(0, len(industry_options), 3):
            cols = st.columns(3)
            for j, i_name in enumerate(industry_options[i:i+3]):
                i_id = industry_id_name_map[i_name]
                key = f"industry_{sector_id}_{i_id}"
                cb = cols[j].checkbox(str(i_name), key=key)
else:
    selected_industries = set()

# --- Stock Indice Combo Box ---
# Get the directory of the current file (ui.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(BASE_DIR, 'stock_indices.json')

with open(json_path, 'r') as f:
    stock_indice_options = json.load(f)
stock_indice_options = ['--- Choose stock indice ---'] + stock_indice_options
selected_stock_indice = st.selectbox(
    'Select stock indice', 
    stock_indice_options, 
    key='stock_indice',
    index=0
)

# --- KPI Options from JSON file ---
kpi_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kpi_options.json')
with open(kpi_json_path, 'r') as f:
    kpi_json = json.load(f)
kpi_options = [item['short'] for item in kpi_json]
kpi_short_to_borsdata = {item['short']: item['borsdata'] for item in kpi_json}

def fetch_kpi_data_for_calculation(api, kpi_names: list, stock_ids: list, kpi_frequency_map=None) -> dict:
    """Fetch KPI data needed for calculations, using correct frequency for each KPI"""
    kpi_data = {}
    if kpi_frequency_map is None:
        kpi_frequency_map = {k: 'Quarterly' for k in kpi_names}
    
    # Limit the number of stocks to process to prevent timeouts
    max_stocks = 1000  # Adjust this based on your API limits
    if len(stock_ids) > max_stocks:
        st.warning(f"Too many stocks ({len(stock_ids)}). Processing first {max_stocks} stocks only.")
        stock_ids = stock_ids[:max_stocks]
    
    for kpi_name in kpi_names:
        borsdata_name = kpi_short_to_borsdata.get(kpi_name, kpi_name)
        try:
            kpi_id = None
            target = borsdata_name.strip().lower()
            for _, row in df_kpis.iterrows():
                name_en = str(row.get('nameEn', '')).strip().lower()
                name_sv = str(row.get('nameSv', '')).strip().lower()
                if target == name_en or target == name_sv:
                    kpi_id = row.get('kpiId')
                    break
                target_no_space = target.replace(" ", "")
                name_en_no_space = name_en.replace(" ", "")
                name_sv_no_space = name_sv.replace(" ", "")
                if target_no_space == name_en_no_space or target_no_space == name_sv_no_space:
                    kpi_id = row.get('kpiId')
                    break
            if kpi_id:
                freq = kpi_frequency_map.get(kpi_name, 'Quarterly')
                # --- Relative filter special handling ---
                rel_mode = None
                for kf in st.session_state.get('kpi_filters', []):
                    if kf['kpi'] == kpi_name and kf.get('method') == 'Relative':
                        rel_mode = kf.get('rel_mode', 'Year-over-Year (YoY)')
                        break
                if rel_mode == 'Year-over-Year (YoY)' and freq == 'Yearly':
                    # Fetch yearly data using fetch_yearly_kpi_history
                    st.info(f"Fetching YEARLY data for KPI ID {kpi_id} ({kpi_name}) [YoY mode]")
                    kpi_df = fetch_yearly_kpi_history(api, stock_ids, kpi_id)
                    kpi_data[borsdata_name] = kpi_df
                else:
                    # Fetch as usual (quarterly or other)
                    st.info(f"Fetching {freq} data for KPI ID {kpi_id} ({kpi_name})")
                    all_rows = []
                    successful_fetches = 0
                    
                    # Process stocks in batches to avoid timeouts
                    batch_size = 50
                    for i in range(0, len(stock_ids), batch_size):
                        batch_stocks = stock_ids[i:i+batch_size]
                        for ins_id in batch_stocks:
                            try:
                                df = api.get_kpi_history(ins_id, kpi_id, report_type='quarter' if freq == 'Quarterly' else 'year', price_type='mean')
                                if df is not None and not df.empty:
                                    successful_fetches += 1
                                    for idx, row in df.iterrows():
                                        available_cols = list(row.index)
                                        year = None
                                        period = None
                                        kpi_value = None
                                        for year_col in ['year', 'Year', 'YEAR', 'periodYear', 'reportYear']:
                                            if year_col in available_cols:
                                                year = row[year_col]
                                                break
                                        for period_col in ['period', 'Period', 'PERIOD', 'quarter', 'Quarter', 'QUARTER']:
                                            if period_col in available_cols:
                                                period = row[period_col]
                                                break
                                        for value_col in ['kpiValue', 'value', 'v', 'Value', 'VALUE', 'kpi_value']:
                                            if value_col in available_cols:
                                                kpi_value = row[value_col]
                                                break
                                        if kpi_value is not None:
                                            try:
                                                ins_id_int = int(ins_id)
                                                if year is not None:
                                                    year_int = int(year)
                                                    if period is not None:
                                                        period_int = int(period)
                                                        all_rows.append({'insId': ins_id_int, 'year': year_int, 'period': period_int, 'kpiValue': kpi_value})
                                                    else:
                                                        all_rows.append({'insId': ins_id_int, 'year': year_int, 'kpiValue': kpi_value})
                                                else:
                                                    if isinstance(idx, tuple) and len(idx) >= 2:
                                                        year_int = int(idx[0])
                                                        period_int = int(idx[1])
                                                        all_rows.append({'insId': ins_id_int, 'year': year_int, 'period': period_int, 'kpiValue': kpi_value})
                                                    elif isinstance(idx, (int, float)):
                                                        year_int = int(idx)
                                                        all_rows.append({'insId': ins_id_int, 'year': year_int, 'kpiValue': kpi_value})
                                                    else:
                                                        current_year = 2024
                                                        quarters_back = 0
                                                        if isinstance(idx, (int, float)):
                                                            quarters_back = int(idx)
                                                        year_int = current_year - (quarters_back // 4)
                                                        quarter_int = 4 - (quarters_back % 4)
                                                        if quarter_int == 0:
                                                            quarter_int = 4
                                                            year_int -= 1
                                                        all_rows.append({'insId': ins_id_int, 'year': year_int, 'period': quarter_int, 'kpiValue': kpi_value})
                                            except (ValueError, TypeError):
                                                continue
                            except Exception as e:
                                # Log error but continue processing
                                st.warning(f"Error fetching data for stock {ins_id}: {e}")
                                continue
                        
                        # Show progress for large datasets
                        if len(stock_ids) > 100:
                            progress = (i + batch_size) / len(stock_ids)
                            st.progress(min(progress, 1.0))
                    
                    df_result = pd.DataFrame(all_rows)
                    if not df_result.empty:
                        df_result['insId'] = df_result['insId'].astype(int)
                        df_result['year'] = df_result['year'].astype(int)
                        if 'period' in df_result.columns:
                            df_result['period'] = df_result['period'].astype(int)
                    kpi_data[borsdata_name] = df_result
            else:
                st.warning(f"KPI ID not found for: {kpi_name}")
        except Exception as e:
            st.error(f"Error in KPI processing for {kpi_name}: {e}")
            st.error(f"Error type: {type(e).__name__}")
    return kpi_data

def process_calculated_kpis(api, selected_kpis: list, stock_ids: list, kpi_frequency_map=None) -> dict:
    """Process calculated KPIs and return all KPI data"""
    all_kpi_data = {}
    
    # First, identify which KPIs need calculation
    direct_kpis = []
    
    for kpi_name in selected_kpis:
        direct_kpis.append(kpi_name)
    
    # Fetch direct KPIs first
    direct_data = fetch_kpi_data_for_calculation(api, direct_kpis, stock_ids, kpi_frequency_map)
    all_kpi_data.update(direct_data)
    
    return all_kpi_data

# --- Initialize session state for new group-based filtering ---
if 'filter_groups' not in st.session_state:
    st.session_state['filter_groups'] = []
if 'group_relationships' not in st.session_state:
    st.session_state['group_relationships'] = 'AND'
if 'selected_kpis' not in st.session_state:
    st.session_state['selected_kpis'] = []
if 'logic_preview' not in st.session_state:
    st.session_state['logic_preview'] = ''

st.subheader('KPI Filter Groups')

# --- KPI Selection and Group Management ---
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("""
        <style>
        div[data-testid="stMultiSelect"] > label {
            display: none !important;
            height: 0px !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    selected_kpis = st.multiselect(
        label='Select KPI Filters',
        options=kpi_options,
        key='selected_kpis',  # Use the same key as session state
        placeholder='---choose KPIs---'
    )

with col2:
    st.markdown(
        """
        <div style='display:flex; flex-direction:column; justify-content:flex-end;'>
        </div>
        """,
        unsafe_allow_html=True
    )
    add_group_clicked = st.button('Add Group', key='add_group')
    if add_group_clicked:
        st.session_state['filter_groups'].append({
            'id': f'group_{len(st.session_state["filter_groups"])}',
            'filters': [],
            'operator': 'AND',  # AND/OR within group
            'filter_settings': {}  # Individual filter settings will be stored here
        })
        # Don't reset results when just adding an empty group

with col3:
    st.markdown(
        """
        <div style='display:flex; flex-direction:column; justify-content:flex-end;'>
        </div>
        """,
        unsafe_allow_html=True
    )
    clear_groups_clicked = st.button('Clear All Groups', key='clear_groups')
    if clear_groups_clicked:
        st.session_state['filter_groups'] = []
        # Only reset results when groups are actually cleared
        reset_results()

# --- Between-group relationship ---
if len(st.session_state['filter_groups']) > 1:
    st.session_state['group_relationships'] = st.selectbox(
        'Relationship between groups',
        ['AND', 'OR'],
        index=['AND', 'OR'].index(st.session_state['group_relationships']),
        key='group_relationships_select'
    )

# --- Display and manage filter groups ---
for group_idx, group in enumerate(st.session_state['filter_groups']):
    render_filter_group(group_idx, group)

# --- Logic Preview ---
def generate_logic_preview():
    """Generate a human-readable preview of the filter logic/formula in infix style."""
    group_expressions = []
    for group in st.session_state['filter_groups']:
        kpi_expressions = []
        for kpi_name, kpi_settings in group.get('filter_settings', {}).items():
            methods = kpi_settings.get('methods', [])
            if len(methods) == 1:
                method_config = methods[0]
                method_type = method_config.get('type', 'Absolute')
                if method_type == 'Absolute':
                    op = method_config.get('operator_abs', '>')
                    val = method_config.get('value', 0.0)
                    kpi_expressions.append(f"{kpi_name} {op} {val}")
                elif method_type == 'Relative':
                    op = method_config.get('rel_operator', '>=')
                    val = method_config.get('rel_value', 0.0)
                    kpi_expressions.append(f"{kpi_name} {op} {val}%")
                elif method_type == 'Direction':
                    direction = method_config.get('direction', 'positive')
                    kpi_expressions.append(f"{kpi_name} Direction: {direction}")
                elif method_type == 'Trend':
                    trend_type = method_config.get('trend_type', 'Positive')
                    kpi_expressions.append(f"{kpi_name} Trend: {trend_type}")
            else:
                # Multiple methods for this KPI - combine with selected operator
                method_expressions = []
                for method_config in methods:
                    method_type = method_config.get('type', 'Absolute')
                    if method_type == 'Absolute':
                        op = method_config.get('operator_abs', '>')
                        val = method_config.get('value', 0.0)
                        method_expressions.append(f"{kpi_name} {op} {val}")
                    elif method_type == 'Relative':
                        op = method_config.get('rel_operator', '>=')
                        val = method_config.get('rel_value', 0.0)
                        method_expressions.append(f"{kpi_name} {op} {val}%")
                    elif method_type == 'Direction':
                        direction = method_config.get('direction', 'positive')
                        method_expressions.append(f"{kpi_name} Direction: {direction}")
                    elif method_type == 'Trend':
                        trend_type = method_config.get('trend_type', 'Positive')
                        method_expressions.append(f"{kpi_name} Trend: {trend_type}")
                
                # Use the selected method operator (AND/OR) for multiple methods
                method_operator = kpi_settings.get('method_operator', 'AND')
                kpi_expressions.append(f" {method_operator} ".join(method_expressions))
        if kpi_expressions:
            if len(kpi_expressions) == 1:
                group_expr = f"({kpi_expressions[0]})"
            else:
                joiner = f" {group['operator']} "
                group_expr = f"({joiner.join(kpi_expressions)})"
            group_expressions.append(group_expr)
    if group_expressions:
        if len(group_expressions) == 1:
            return group_expressions[0]
        else:
            rel = st.session_state.get('group_relationships', 'AND')
            return f" {rel} ".join(group_expressions)
    return ''

# Display logic preview
st.session_state['logic_preview'] = generate_logic_preview()
st.info(f"**Filter Formula:** {st.session_state['logic_preview']}")

# --- Validation and Help ---
if st.session_state['filter_groups']:
    # Check for empty groups
    empty_groups = [i+1 for i, group in enumerate(st.session_state['filter_groups']) if not group['filters']]
    if empty_groups:
        st.warning(f"⚠️ Groups {empty_groups} have no filters. Add filters or remove empty groups.")
    
# --- Help section ---
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

# --- Convert groups to old format for compatibility ---
def convert_groups_to_old_format():
    """Convert the new group format to the old kpi_filters format for compatibility"""
    old_filters = []
    
    for group_idx, group in enumerate(st.session_state['filter_groups']):
        for kpi_idx, kpi_name in enumerate(group['filters']):
            # Get KPI settings using the instance key
            kpi_instance_key = f"{kpi_name}_{kpi_idx}"
            kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
            methods = kpi_settings.get('methods', [])
            
            # Convert each method to a separate filter in old format
            for method_idx, method_config in enumerate(methods):
                old_filter = {
                    'kpi': kpi_name,
                    'method': method_config.get('type', 'Absolute'),
                    'group_id': group_idx,  # Track which group this belongs to
                    'group_operator': group['operator'],  # Track within-group operator
                    'method_id': method_idx,  # Track which method this is for the KPI
                    'method_operator': kpi_settings.get('method_operator', 'AND')  # Track method operator for multiple methods
                }
                
                # Add method-specific parameters (only if not None)
                if method_config.get('type') == 'Absolute':
                    if method_config.get('operator_abs') is not None:
                        old_filter['operator'] = method_config.get('operator_abs')
                    if method_config.get('value') is not None:
                        old_filter['value'] = method_config.get('value')
                    if method_config.get('duration_type') is not None:
                        old_filter['duration_type'] = method_config.get('duration_type')
                    if method_config.get('last_n') is not None:
                        old_filter['last_n'] = method_config.get('last_n')
                    if method_config.get('start_quarter'):
                        old_filter['start_quarter'] = method_config.get('start_quarter')
                    if method_config.get('end_quarter'):
                        old_filter['end_quarter'] = method_config.get('end_quarter')
                    if method_config.get('data_frequency') is not None:
                        old_filter['data_frequency'] = method_config.get('data_frequency')
                elif method_config.get('type') == 'Relative':
                    if method_config.get('rel_operator') is not None:
                        old_filter['rel_operator'] = method_config.get('rel_operator')
                    if method_config.get('rel_value') is not None:
                        old_filter['rel_value'] = method_config.get('rel_value')
                    if method_config.get('rel_mode') is not None:
                        old_filter['rel_mode'] = method_config.get('rel_mode')
                    if method_config.get('duration_type') is not None:
                        old_filter['duration_type'] = method_config.get('duration_type')
                    if method_config.get('last_n') is not None:
                        old_filter['last_n'] = method_config.get('last_n')
                    if method_config.get('start_quarter'):
                        old_filter['start_quarter'] = method_config.get('start_quarter')
                    if method_config.get('end_quarter'):
                        old_filter['end_quarter'] = method_config.get('end_quarter')
                    if method_config.get('data_frequency') is not None:
                        old_filter['data_frequency'] = method_config.get('data_frequency')
                elif method_config.get('type') == 'Direction':
                    if method_config.get('direction') is not None:
                        old_filter['direction'] = method_config.get('direction')
                    if method_config.get('duration_type') is not None:
                        old_filter['duration_type'] = method_config.get('duration_type')
                    if method_config.get('last_n') is not None:
                        old_filter['last_n'] = method_config.get('last_n')
                    if method_config.get('start_quarter'):
                        old_filter['start_quarter'] = method_config.get('start_quarter')
                    if method_config.get('end_quarter'):
                        old_filter['end_quarter'] = method_config.get('end_quarter')
                    if method_config.get('data_frequency') is not None:
                        old_filter['data_frequency'] = method_config.get('data_frequency')
                elif method_config.get('type') == 'Trend':
                    if method_config.get('trend_type') is not None:
                        old_filter['trend_type'] = method_config.get('trend_type')
                    if method_config.get('trend_n') is not None:
                        old_filter['trend_n'] = method_config.get('trend_n')
                    if method_config.get('trend_m') is not None:
                        old_filter['trend_m'] = method_config.get('trend_m')
                    if method_config.get('data_frequency') is not None:
                        old_filter['data_frequency'] = method_config.get('data_frequency')
                
                old_filters.append(old_filter)
    
    return old_filters

def validate_logic_tree(tree, kpi_filter_settings):
    """Validate that all indices in the logic tree exist in kpi_filter_settings"""
    if isinstance(tree, int):
        if tree not in kpi_filter_settings:
            print(f"WARNING: Logic tree index {tree} not found in kpi_filter_settings")
            return False
        return True
    elif isinstance(tree, dict) and 'children' in tree:
        for child in tree['children']:
            if not validate_logic_tree(child, kpi_filter_settings):
                return False
        return True
    return False

# --- Build logic tree for group-based filtering ---
def build_group_logic_tree():
    """Build the logic tree for group-based filtering"""
    if not st.session_state['filter_groups']:
        return None
    
    # Convert groups to logic tree
    group_nodes = []
    
    for group_idx, group in enumerate(st.session_state['filter_groups']):
        if not group['filters']:
            continue
        
        # Create node for this group
        if len(group['filters']) == 1:
            # Single KPI in group - check if it has multiple methods
            kpi_name = group['filters'][0]
            kpi_instance_key = f"{kpi_name}_0"  # First (and only) instance
            kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
            methods = kpi_settings.get('methods', [])
            
            if len(methods) == 1:
                # Single method - find the correct filter index
                filter_idx = None
                for old_idx, old_filter in enumerate(st.session_state['kpi_filters']):
                    if (old_filter['kpi'] == kpi_name and 
                        old_filter.get('group_id') == group_idx and 
                        old_filter.get('method_id') == 0):
                        filter_idx = old_idx
                        break
                group_node = filter_idx if filter_idx is not None else group_idx
            else:
                # Multiple methods - create node with selected operator for methods
                method_indices = []
                for method_idx, method_config in enumerate(methods):
                    # Find the filter index in the old format
                    for old_idx, old_filter in enumerate(st.session_state['kpi_filters']):
                        if (old_filter['kpi'] == kpi_name and 
                            old_filter.get('group_id') == group_idx and 
                            old_filter.get('method_id') == method_idx):
                            method_indices.append(old_idx)
                            break
                
                if method_indices:
                    # Use the selected method operator (AND/OR) for multiple methods
                    method_operator = kpi_settings.get('method_operator', 'AND')
                    group_node = {
                        'type': method_operator,
                        'children': method_indices
                    }
                else:
                    group_node = group_idx
        else:
            # Multiple KPIs in group - create AND/OR node
            kpi_indices = []
            for kpi_idx, kpi_name in enumerate(group['filters']):
                kpi_instance_key = f"{kpi_name}_{kpi_idx}"
                kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
                methods = kpi_settings.get('methods', [])
                
                if len(methods) == 1:
                    # Single method for this KPI
                    filter_idx = None
                    for old_idx, old_filter in enumerate(st.session_state['kpi_filters']):
                        if (old_filter['kpi'] == kpi_name and 
                            old_filter.get('group_id') == group_idx and 
                            old_filter.get('method_id') == 0):
                            filter_idx = old_idx
                            break
                    if filter_idx is not None:
                        kpi_indices.append(filter_idx)
                else:
                    # Multiple methods for this KPI - create sub-node with selected operator
                    method_indices = []
                    for method_idx, method_config in enumerate(methods):
                        for old_idx, old_filter in enumerate(st.session_state['kpi_filters']):
                            if (old_filter['kpi'] == kpi_name and 
                                old_filter.get('group_id') == group_idx and 
                                old_filter.get('method_id') == method_idx):
                                method_indices.append(old_idx)
                                break
                    
                    if method_indices:
                        if len(method_indices) == 1:
                            kpi_indices.append(method_indices[0])
                        else:
                            # Create sub-node for multiple methods with selected operator
                            method_operator = kpi_settings.get('method_operator', 'AND')
                            sub_node = {
                                'type': method_operator,
                                'children': method_indices
                            }
                            # Add this sub-node to the group_nodes list
                            group_nodes.append(sub_node)
                            kpi_indices.append(len(group_nodes) - 1)
            
            if kpi_indices:
                if len(kpi_indices) == 1:
                    group_node = kpi_indices[0]
                else:
                    group_node = {
                        'type': group['operator'],
                        'children': kpi_indices
                    }
            else:
                group_node = group_idx
        
        group_nodes.append(group_node)
    
    # Combine groups with the group relationship
    if len(group_nodes) == 1:
        return group_nodes[0]
    else:
        return {
            'type': st.session_state['group_relationships'],
            'children': group_nodes
        }

# Store the logic tree
if st.session_state['filter_groups']:
    # Don't build the logic tree here - it will be built after convert_groups_to_old_format()
    pass

fetch_clicked = st.button('Fetch Results', key='fetch_results')

# Show validation message if no countries AND no sectors selected
if fetch_clicked and not selected_countries and not selected_sectors:
    st.info("Fetching results for all countries and all sectors. This may take a moment...")

# --- Main results logic ---
if fetch_clicked and (selected_countries or selected_sectors or (not selected_countries and not selected_sectors)):
    reset_pagination()
    # Get base data with country and market filtering
    country_ids_to_filter = [country_id_name_map[c] for c in selected_countries if c in country_id_name_map]
    market_ids_to_filter = list(selected_markets) if selected_markets else None
    
    # Show what filters are being applied
    if selected_countries:
        filter_info = f"Countries: {', '.join(selected_countries)}"
        if selected_markets:
            filter_info += f" | Markets: {len(selected_markets)} selected"
        else:
            filter_info += f" | Markets: All markets in selected countries"
    else:
        filter_info = "Countries: All countries"
        if selected_markets:
            filter_info += f" | Markets: {len(selected_markets)} selected"
        else:
            filter_info += f" | Markets: All markets"
    
    if selected_sectors:
        filter_info += f" | Sectors: {', '.join(selected_sectors)}"
    else:
        filter_info += f" | Sectors: All sectors"
    
    # Add note for large datasets
    if not selected_countries and not selected_sectors:
        filter_info += " (Large dataset - results will be paginated)"
    
    st.info(filter_info)
    
    # Get base data - if no countries selected, get all stocks
    if selected_countries:
        base_df = get_filtered_stocks(
            country_ids=country_ids_to_filter,
            market_ids=market_ids_to_filter
        )
    else:
        # No countries selected, get all stocks for sector filtering
        base_df = get_filtered_stocks(
            country_ids=None,  # Get all countries
            market_ids=market_ids_to_filter
        )
    if not isinstance(base_df, pd.DataFrame):
        base_df = pd.DataFrame(base_df)
    
    if len(base_df) == 0:
        st.warning("No stocks found after country/market filtering. Check your country/market selections.")
        st.session_state['filtered_instruments'] = pd.DataFrame()
        st.session_state['results_ready'] = True
        st.stop()
    
            # Apply sector and industry filtering
    sector_ids_to_filter = [sector_id_name_map[s] for s in selected_sectors if s in sector_id_name_map]
    industry_ids_to_filter = list(selected_industries) if selected_industries is not None else None
    
    # Apply sector/industry filtering if sectors or industries are selected
    if sector_ids_to_filter or industry_ids_to_filter:
        filtered_instruments = filter_by_metadata(
            base_df,
            country_ids=None,  # Already filtered in get_filtered_stocks() or getting all
            market_ids=None,   # Already filtered in get_filtered_stocks() or getting all
            sector_ids=sector_ids_to_filter if sector_ids_to_filter else None,
            industry_ids=industry_ids_to_filter if industry_ids_to_filter else None
        )
    else:
        # No sector/industry filtering needed, use base_df directly
        filtered_instruments = base_df
    

    if not isinstance(filtered_instruments, pd.DataFrame):
        filtered_instruments = pd.DataFrame(filtered_instruments)
    
    if len(filtered_instruments) == 0:
        st.warning("No stocks found after sector/industry filtering. Check your sector/industry selections.")
        st.session_state['filtered_instruments'] = pd.DataFrame()
        st.session_state['results_ready'] = True
        st.stop()
    # --- KPI Filtering (before pagination) ---
    # Convert groups to old format for compatibility
    st.session_state['kpi_filters'] = convert_groups_to_old_format()
    
    # Build the logic tree AFTER converting to old format
    if st.session_state['filter_groups']:
        st.session_state['kpi_logic_tree'] = build_group_logic_tree()
    
    if st.session_state['kpi_filters'] and 'kpi_logic_tree' in st.session_state:
        if not isinstance(filtered_instruments, pd.DataFrame):
            filtered_instruments = pd.DataFrame(filtered_instruments)
        id_col = None
        for candidate in ['id', 'insId', 'instrumentId']:
            if candidate in filtered_instruments.columns:
                id_col = candidate
                break
        if id_col is None:
            st.error(f"No instrument ID column found in filtered_instruments. Columns: {filtered_instruments.columns.tolist()}")
            st.stop()
        
        # Get unique KPIs from all filters
        unique_kpis = list(set([kf['kpi'] for kf in st.session_state['kpi_filters']]))
        stock_ids = list(filtered_instruments[id_col])
        
        # Build a frequency map for each KPI from the filter settings
        kpi_frequency_map = {}
        for idx, kf in enumerate(st.session_state['kpi_filters']):
            kpi_name = kf['kpi']
            freq = kf.get('data_frequency', 'Quarterly')
            kpi_frequency_map[kpi_name] = freq

        # Use the frequency map when fetching KPI data
        # --- Insert pre-fetch check for quarterly KPIs here ---
        problematic_kpis = test_kpi_quarterly_availability(api, st.session_state['kpi_filters'], stock_ids)
        if problematic_kpis:
            st.warning(f"The following KPIs do not support quarterly data: {', '.join(problematic_kpis)}. Please change their frequency to 'Yearly' or remove them from your filter.")
            st.stop()
        # ------------------------------------------------------
        with st.spinner('Processing KPI data...'):
            try:
                all_kpi_data = fetch_kpi_data_for_calculation(api, unique_kpis, stock_ids, kpi_frequency_map)
            except Exception as e:
                st.error(f"Error fetching KPI data: {e}")
                st.stop()
            
        # Prepare filter settings
        kpi_filter_settings = {}
        for idx, kf in enumerate(st.session_state['kpi_filters']):
            kpi_name = kf['kpi']
            borsdata_name = kpi_short_to_borsdata.get(kpi_name, kpi_name)
            
            kpi_filter_settings[idx] = {
                'abs_enabled': kf['method'] == 'Absolute',
                'abs_operator': kf.get('operator'),
                'abs_value': kf.get('value'),
                'last_n': kf.get('last_n') if kf.get('duration_type', 'Last N Quarters') == 'Last N Quarters' else None,
                'rel_enabled': kf['method'] == 'Relative',
                'rel_value': kf.get('rel_value'),
                'trend_enabled': kf['method'] == 'Trend',
                'trend_type': kf.get('trend_type'),
                'trend_n': kf.get('trend_n'),
                'trend_m': kf.get('trend_m'),
                'direction_enabled': kf['method'] == 'Direction',
                'direction': kf.get('direction', 'either'),
                'kpi_name': kpi_name,
                'borsdata_name': borsdata_name,
                'duration_type': kf.get('duration_type', 'Last N Quarters'),
                'start_quarter': kf.get('start_quarter'),
                'end_quarter': kf.get('end_quarter'),
            }
        
        # Prepare stock KPI data in the format expected by evaluate_kpi_filter
        stock_kpi_data = {stock_id: {} for stock_id in stock_ids}
        for kpi_name, kpi_df in all_kpi_data.items():
            # Map Borsdata name back to short name for storage
            short_name = None
            for short, borsdata in kpi_short_to_borsdata.items():
                if borsdata == kpi_name:
                    short_name = short
                    break
            
            if short_name is None:
                # If no mapping found, use the Borsdata name as is
                short_name = kpi_name
            
            for stock_id in stock_ids:
                if not kpi_df.empty:
                    stock_df = kpi_df[kpi_df['insId'] == stock_id].copy()
                    if not stock_df.empty:
                        # Sort by year and period if available
                        if 'period' in stock_df.columns:
                            stock_df = stock_df.sort_values(['year', 'period'])
                        else:
                            stock_df = stock_df.sort_values('year')
                        stock_kpi_data[stock_id][short_name] = stock_df
        
        # Save KPI data to session state for display in results table
        st.session_state['kpi_data'] = stock_kpi_data
        
        # Apply filtering logic
        tree = st.session_state['kpi_logic_tree']
        
        if isinstance(tree, int):
            tree = {'type': 'AND', 'children': [tree]}
        if not (isinstance(tree, dict) and 'children' in tree):
            st.warning("Invalid KPI logic tree. Skipping KPI filtering.")
            final_stock_ids = list(filtered_instruments[id_col])
        else:
            # Validate the logic tree before using it
            if not validate_logic_tree(tree, kpi_filter_settings):
                st.error("Logic tree validation failed. Some filter indices are missing. Please check your filter configuration.")
                st.stop()
            
            final_stock_ids = []
            passed_count = 0
            total_stocks = len(filtered_instruments[id_col])
            
            # Add progress bar for filtering
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, stock_id in enumerate(filtered_instruments[id_col]):
                try:
                    result = evaluate_filter_tree(
                        tree,
                        kpi_filter_settings,
                        stock_kpi_data[stock_id]
                    )
                    if result:
                        final_stock_ids.append(stock_id)
                        passed_count += 1
                    
                    # Update progress every 100 stocks
                    if i % 100 == 0 or i == total_stocks - 1:
                        progress = (i + 1) / total_stocks
                        progress_bar.progress(progress)
                        status_text.text(f"Filtering stocks: {i + 1}/{total_stocks} ({passed_count} passed)")
                except Exception as e:
                    st.error(f"Error evaluating stock {stock_id}: {e}")
                    continue
            
            progress_bar.empty()
            status_text.empty()
        
        if not isinstance(filtered_instruments, pd.DataFrame):
            filtered_instruments = pd.DataFrame(filtered_instruments)
        if not isinstance(filtered_instruments[id_col], pd.Series):
            filtered_instruments[id_col] = pd.Series(filtered_instruments[id_col])
        filtered_instruments = filtered_instruments[filtered_instruments[id_col].isin(list(final_stock_ids))]
        
        # Save KPI data to session state for display in results table
        st.session_state['kpi_data'] = stock_kpi_data
    
    st.session_state['filtered_instruments'] = filtered_instruments
    st.session_state['results_ready'] = True

def show_cagr_options():
    cagr_kpi = st.selectbox('CAGR KPI', [''] + kpi_options, key='cagr_kpi_stable')
    years = [''] + list(range(1995, datetime.datetime.now().year + 1))
    start_year = st.selectbox('CAGR Start Year', years, key='cagr_start_year_stable')
    end_year = st.selectbox('CAGR End Year', years, key='cagr_end_year_stable')
    calculate_cagr_clicked = st.button('Calculate CAGR', key='calculate_cagr_btn_stable')
    return cagr_kpi, start_year, end_year, calculate_cagr_clicked

# --- Sorting UI Controls ---
st.subheader('Sorting Options')
sorter_options = ['None', 'CAGR', 'Market', 'Ticker']

if 'sorter' not in st.session_state:
    st.session_state['sorter'] = 'None'

st.session_state['sorter'] = st.selectbox(
    'Sort Option',
    sorter_options,
    index=sorter_options.index(st.session_state['sorter']) if st.session_state['sorter'] in sorter_options else 0,
    key='sorter_select'
)

# Show CAGR options if CAGR is selected
cagr_kpi, cagr_start_year, cagr_end_year, calculate_cagr_clicked = None, None, None, False
if st.session_state['sorter'] == 'CAGR':
    st.subheader('CAGR Calculation Settings')
    cagr_kpi, cagr_start_year, cagr_end_year, calculate_cagr_clicked = show_cagr_options()

# --- Show results if ready ---
if st.session_state.get('results_ready') and st.session_state.get('filtered_instruments') is not None:
    filtered_instruments = st.session_state['filtered_instruments']

    # --- Backend Sorting Logic ---
    sorter = st.session_state['sorter']
    sort_columns = []
    ascending = []
    cagr_col = None

    # Always map marketId to market name for sorting and export
    market_id_to_name = {row['id']: row['name'] for _, row in all_markets_df.iterrows()}
    if 'marketId' in filtered_instruments.columns:
        filtered_instruments['market'] = filtered_instruments['marketId'].map(market_id_to_name)

    # CAGR calculation helper
    def calculate_cagr(start, end, n_years):
        try:
            if start is None or end is None or n_years <= 0:
                return None
            if start == 0:
                return None
            if (start < 0 and end > 0) or (start > 0 and end < 0):
                return None
            result = (end / start) ** (1 / n_years) - 1
            if isinstance(result, complex):
                return None
            return result
        except Exception:
            return None

    # Apply pagination first to get current page
    total_results = len(filtered_instruments)
    total_pages = max(1, (total_results + PAGE_SIZE - 1) // PAGE_SIZE)
    current_page = st.session_state['current_page']
    if current_page >= total_pages:
        st.session_state['current_page'] = total_pages - 1
        st.rerun()
    start = current_page * PAGE_SIZE
    end = start + PAGE_SIZE
    paginated_instruments = filtered_instruments.iloc[start:end].copy()

    # If CAGR is selected, calculate CAGR only for current page stocks (batch processing)
    if sorter == 'CAGR':
        if calculate_cagr_clicked and cagr_kpi and cagr_start_year and cagr_end_year:
            st.info(f"Calculating CAGR for {cagr_kpi} from {cagr_start_year} to {cagr_end_year}...")
            cagr_kpi_borsdata = kpi_short_to_borsdata.get(cagr_kpi, cagr_kpi)
            if cagr_kpi_borsdata is not None:
                n_years = int(cagr_end_year) - int(cagr_start_year)
                cagr_col = f'CAGR_{cagr_kpi}_{cagr_start_year}_{cagr_end_year}'
                if n_years > 0:
                    id_col = None
                    for candidate in ['insId', 'id', 'instrumentId']:
                        if candidate in paginated_instruments.columns:
                            id_col = candidate
                            break
                    page_stock_ids = list(paginated_instruments[id_col])
                    kpi_id = None
                    target = cagr_kpi_borsdata.strip().lower()
                    for _, row in df_kpis.iterrows():
                        name_en = str(row.get('nameEn', '')).strip().lower()
                        name_sv = str(row.get('nameSv', '')).strip().lower()
                        if target == name_en or target == name_sv:
                            kpi_id = row.get('kpiId')
                            break
                        target_no_space = target.replace(" ", "")
                        name_en_no_space = name_en.replace(" ", "")
                        name_sv_no_space = name_sv.replace(" ", "")
                        if target_no_space == name_en_no_space or target_no_space == name_sv_no_space:
                            kpi_id = row.get('kpiId')
                            break
                    if kpi_id is None:
                        st.warning(f"Could not find KPI ID for {cagr_kpi} (mapped: {cagr_kpi_borsdata})")
                    else:
                        kpi_df = fetch_yearly_kpi_history(api, page_stock_ids, kpi_id)
                        kpi_lookup = {}
                        if kpi_df is not None and not kpi_df.empty:
                            for _, row in kpi_df.iterrows():
                                stock = int(row.get('insId'))
                                year = int(row.get('year'))
                                value = row.get('kpiValue')
                                if stock is not None and year is not None and value is not None:
                                    try:
                                        kpi_lookup[(stock, year)] = float(value)
                                    except Exception as e:
                                        continue
                        cagr_values = []
                        for idx, row in paginated_instruments.iterrows():
                            stock = row[id_col]
                            try:
                                stock_int = int(stock) if stock is not None else None
                                start_val = kpi_lookup.get((stock_int, int(cagr_start_year))) if stock_int is not None else None
                                end_val = kpi_lookup.get((stock_int, int(cagr_end_year))) if stock_int is not None else None
                            except Exception as e:
                                start_val = None
                                end_val = None
                            cagr = calculate_cagr(start_val, end_val, n_years)
                            cagr_values.append(cagr)
                        paginated_instruments[cagr_col] = cagr_values
                        sort_columns.append(cagr_col)
                        ascending.append(False)
    # Market Cap
    if sorter == 'Market':
        market_cap_col = None
        for col in ['market', 'Market']:
            if col in paginated_instruments.columns:
                market_cap_col = col
                break
        if market_cap_col:
            sort_columns.append(market_cap_col)
            ascending.append(False)
    # Ticker
    if sorter == 'Ticker':
        ticker_col = None
        for col in ['ticker', 'Ticker', 'symbol', 'Symbol', 'ticker_symbol']:
            if col in paginated_instruments.columns:
                ticker_col = col
                break
        if ticker_col:
            sort_columns.append(ticker_col)
            ascending.append(True)
        else:
            st.warning("Ticker column not found. Available columns: " + ", ".join(paginated_instruments.columns))
    # Only sort if at least one valid column
    if sort_columns:
        paginated_instruments = paginated_instruments.sort_values(by=sort_columns, ascending=ascending, na_position='last')

    # Prepare columns to display in the table
    display_columns = ['name', 'ticker']
    
    # Show market column if sorting by Market
    if sorter == 'Market' and 'market' in paginated_instruments.columns:
        display_columns.append('market')

    # Add KPI filter value columns if KPI filters were applied and data is available
    if st.session_state.get('kpi_filters') and len(st.session_state['kpi_filters']) > 0:
        # Get KPI data for current page stocks
        id_col = None
        for candidate in ['insId', 'id', 'instrumentId']:
            if candidate in paginated_instruments.columns:
                id_col = candidate
                break
        
        # Only add KPI columns if we have the KPI data available
        if id_col and 'kpi_data' in st.session_state:
            # Add a column for each KPI filter showing the actual values
            for kf in st.session_state['kpi_filters']:
                kpi_name = kf['kpi']
                duration_type = kf.get('duration_type', 'Last N Quarters')
                operator = kf.get('operator', '')
                value = kf.get('value', '')
                last_n = kf.get('last_n', 1)
                method = kf.get('method', '')

                # Build duration string
                if duration_type == 'Custom Range' and kf.get('start_quarter') and kf.get('end_quarter'):
                    duration_str = f"({kf['start_quarter']} → {kf['end_quarter']})"
                else:
                    duration_str = f"(last {last_n} quarters)"

                # Build method-specific header
                if method == 'Absolute':
                    operator = kf.get('operator', '')
                    value = kf.get('value', '')
                    column_header = f"{kpi_name} {operator} {value} {duration_str}"
                elif method == 'Relative':
                    rel_operator = kf.get('rel_operator', '')
                    rel_value = kf.get('rel_value', '')
                    rel_mode = kf.get('rel_mode', 'Year-over-Year (YoY)')
                    # Use shorter version for display
                    if rel_mode == 'Quarter-over-Quarter (QoQ)':
                        display_mode = 'QoQ'
                    elif rel_mode == 'Year-over-Year (YoY)':
                        display_mode = 'YoY'
                    else:
                        display_mode = rel_mode
                    column_header = f"{kpi_name} {display_mode} {rel_operator} {rel_value}% {duration_str}"
                elif method == 'Direction':
                    direction = kf.get('direction', 'either')
                    column_header = f"{kpi_name} Direction: {direction} {duration_str}"
                else:
                    column_header = f"{kpi_name} {duration_str}"
                
                # Get actual KPI values for each stock
                kpi_values = []
                for _, stock in paginated_instruments.iterrows():
                    stock_id = stock[id_col]
                    if stock_id in st.session_state['kpi_data'] and kpi_name in st.session_state['kpi_data'][stock_id]:
                        kpi_df = st.session_state['kpi_data'][stock_id][kpi_name]
                        if not kpi_df.empty:
                            if method == 'Trend':
                                duration_type = 'Last N Quarters'
                                last_n = kf.get('trend_n') 
                                kpi_df = filter_data_by_time_range(
                                    kpi_df, 
                                    duration_type, 
                                    last_n, 
                                    start_quarter=kf.get('start_quarter'),
                                    end_quarter=kf.get('end_quarter'))
                            else:
                                kpi_df = filter_data_by_time_range(
                                    kpi_df, 
                                    duration_type=duration_type,
                                    last_n=kf.get('last_n', 1),
                                    start_quarter=kf.get('start_quarter'),
                                    end_quarter=kf.get('end_quarter')
                                )
                            values = kpi_df['kpiValue'].tolist()
                            # Format values based on method type
                            if method == 'Trend':
                                values = values[-last_n:]
                                if len(values) > 1:
                                    values_str = ' → '.join([f"{v:.4f}" for v in values])
                                else:
                                    values_str = f"{values[0]:.4f}" if values else 'N/A'
                            elif method == 'Relative':
                                # For relative, show all values in the selected range
                                if len(values) > 1:
                                    values_str = ' → '.join([f"{v:.4f}" for v in values])
                                else:
                                    values_str = f"{values[0]:.4f}" if values else 'N/A'
                            else:
                                values_str = ', '.join([f"{v:.4f}" for v in values])
                            kpi_values.append(values_str)
                        else:
                            kpi_values.append('N/A')
                    else:
                        kpi_values.append('N/A')
                
                # Add the column to the DataFrame
                paginated_instruments[column_header] = kpi_values
                display_columns.append(column_header)
    
    if cagr_col is not None and cagr_col in paginated_instruments.columns:
        display_columns.append(cagr_col)
    # Only include columns that exist in the DataFrame
    display_columns = [col for col in display_columns if col in paginated_instruments.columns]

    st.write(f"Showing {len(paginated_instruments)} stocks for selected countries")
    # Reset index to start from 1 for display
    paginated_instruments_display = paginated_instruments.copy()
    paginated_instruments_display.index = paginated_instruments_display.index + 1
    st.dataframe(paginated_instruments_display[display_columns])
    # Build mapping dictionaries for export
    sector_id_to_name = {row['id']: row['name'] for _, row in all_sectors_df.iterrows()}
    market_id_to_name = {row['id']: row['name'] for _, row in all_markets_df.iterrows()}
    country_id_to_name = {row['id']: row['name'] for _, row in all_countries_df.iterrows()}
    branch_id_to_name = {row['id']: row['name'] for _, row in all_branches_df.iterrows()}

    if not paginated_instruments.empty:
        # Map IDs to names for export
        if 'sectorId' in paginated_instruments.columns:
            paginated_instruments['sector'] = paginated_instruments['sectorId'].map(sector_id_to_name)
        if 'marketId' in paginated_instruments.columns:
            paginated_instruments['market'] = paginated_instruments['marketId'].map(market_id_to_name)
        if 'countryId' in paginated_instruments.columns:
            paginated_instruments['country'] = paginated_instruments['countryId'].map(country_id_to_name)
        if 'branchId' in paginated_instruments.columns:
            paginated_instruments['branch'] = paginated_instruments['branchId'].map(branch_id_to_name)
        # Optionally drop the ID columns
        paginated_instruments = paginated_instruments.drop(columns=['sectorId', 'marketId', 'countryId', 'branchId'], errors='ignore')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            paginated_instruments.to_excel(tmp.name, index=False, engine='xlsxwriter')
            tmp.seek(0)
            excel_bytes = tmp.read()
        st.download_button(
            label="Export to Excel",
            data=excel_bytes,
            file_name="filtered_kpi_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    if total_pages > 1:
        pagination_controls(st.session_state['current_page'], total_pages, total_results)
elif fetch_clicked:
    st.write("\n_No country or market selected. Please choose at least one country and one market.") 

