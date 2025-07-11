# ui_components.py
import streamlit as st
from borsdata.ui.ui_helpers import create_method_config

def render_method_selector(group_idx, kpi_idx, kpi_name, kpi_settings):
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
            return True
    return False

def render_absolute_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    current_operator = method_config.get('operator_abs')
    if current_operator is None or current_operator not in ['>', '>=', '<', '<=', '=']:
        current_operator = '>'
    selected_operator = st.selectbox(
        'Operator',
        ['>', '>=', '<', '<=', '='],
        index=['>', '>=', '<', '<=', '='].index(current_operator),
        key=f'op_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['operator_abs'] = selected_operator

def render_relative_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    current_operator = method_config.get('rel_operator')
    if current_operator is None or current_operator not in ['>', '>=', '<', '<=', '=']:
        current_operator = '>='
    selected_operator = st.selectbox(
        'Operator',
        ['>', '>=', '<', '<=', '='],
        index=['>', '>=', '<', '<=', '='].index(current_operator),
        key=f'rel_op_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['rel_operator'] = selected_operator

def render_direction_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    current_direction = method_config.get('direction')
    if current_direction is None or current_direction not in ['positive', 'negative', 'either']:
        current_direction = 'positive'
    selected_direction = st.selectbox(
        'Direction',
        ['positive', 'negative', 'either'],
        index=['positive', 'negative', 'either'].index(current_direction),
        key=f'dir_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
    )
    method_config['direction'] = selected_direction

def render_trend_parameters(group_idx, kpi_idx, method_idx, kpi_name, method_config):
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
    if method_config['type'] in ['Absolute', 'Relative', 'Direction']:
        st.markdown("**Time Range:**")
        current_duration_type = method_config.get('duration_type')
        if current_duration_type is None or current_duration_type not in ['Last N Quarters', 'Custom Range']:
            current_duration_type = 'Last N Quarters'
        selected_duration_type = st.radio(
            'Duration Type',
            ['Last N Quarters', 'Custom Range'],
            index=['Last N Quarters', 'Custom Range'].index(current_duration_type),
            key=f'durtype_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['duration_type'] = selected_duration_type
        current_frequency = method_config.get('data_frequency', 'Quarterly')
        selected_frequency = st.selectbox(
            'Data Frequency',
            ['Quarterly', 'Yearly'],
            index=['Quarterly', 'Yearly'].index(current_frequency),
            key=f'datafreq_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
        )
        method_config['data_frequency'] = selected_frequency
        if selected_duration_type == 'Last N Quarters':
            method_config.pop('start_quarter', None)
            method_config.pop('end_quarter', None)
            if method_config.get('last_n') is None:
                method_config['last_n'] = 1
        else:
            method_config['last_n'] = None
        if method_config['duration_type'] == 'Last N Quarters':
            current_value = method_config.get('last_n')
            if current_value is None or current_value == 0:
                current_value = 1
            input_value = st.number_input(
                'Last N Quarters',
                min_value=1,
                max_value=40,
                value=current_value,
                key=f'lastn_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
            )
            method_config['last_n'] = input_value
        else:
            custom_cols = st.columns([2, 2])
            with custom_cols[0]:
                start_quarter = st.text_input('Start Quarter (YYYY-Q)', value=method_config.get('start_quarter', ''), key=f'startq_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}')
                method_config['start_quarter'] = start_quarter
            with custom_cols[1]:
                end_quarter = st.text_input('End Quarter (YYYY-Q)', value=method_config.get('end_quarter', ''), key=f'endq_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}')
                method_config['end_quarter'] = end_quarter

def render_relative_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config):
    if method_config['type'] == 'Relative':
        st.markdown("**Relative Settings:**")
        rel_cols = st.columns([2, 2])
        with rel_cols[0]:
            rel_mode = method_config.get('rel_mode', 'Year-over-Year (YoY)')
            rel_mode = st.selectbox(
                'Comparison Type',
                ['Year-over-Year (YoY)', 'Quarter-over-Quarter (QoQ)'],
                index=['Year-over-Year (YoY)', 'Quarter-over-Quarter (QoQ)'].index(rel_mode),
                key=f'rel_mode_{group_idx}_{kpi_idx}_{method_idx}_{kpi_name}'
            )
            method_config['rel_mode'] = rel_mode

def render_trend_settings(group_idx, kpi_idx, method_idx, kpi_name, method_config):
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
    st.markdown("<div style='margin-bottom: -1.5em'></div>", unsafe_allow_html=True)
    render_method_selector(group_idx, kpi_idx, kpi_name, kpi_settings)
    group['filter_settings'][kpi_instance_key] = kpi_settings
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
    st.markdown(f"**Group {group_idx + 1}**")
    group_cols = st.columns([2, 1, 1])
    with group_cols[0]:
        if st.session_state['selected_kpis']:
            new_kpi = st.selectbox(
                f'Add KPI to Group {group_idx + 1}',
                [''] + st.session_state['selected_kpis'],
                key=f'add_kpi_{group_idx}_{group["id"]}_{len(group["filters"])})'
            )
            if new_kpi:
                group['filters'].append(new_kpi)
    with group_cols[1]:
        group['operator'] = st.selectbox(
            'Within Group',
            ['AND', 'OR'],
            index=['AND', 'OR'].index(group['operator']),
            key=f'group_op_{group_idx}'
        )
    with group_cols[2]:
        st.markdown("<div style='height: 1.7em'></div>", unsafe_allow_html=True)
        remove_group_clicked = st.button('Remove Group', key=f'remove_group_{group_idx}')
        if remove_group_clicked:
            st.session_state['filter_groups'].pop(group_idx)
            reset_results()
    if group['filters']:
        st.markdown("**KPIs in this group:**")
        if 'filter_settings' not in group:
            group['filter_settings'] = {}
        for kpi_idx, kpi_name in enumerate(group['filters']):
            render_kpi_instance(group_idx, kpi_idx, kpi_name, group)
        st.markdown("---") 

def render_kpi_multiselect(kpi_options):
    """Render the KPI multi-select widget and return the selected KPIs."""
    return st.multiselect(
        label='Select KPI Filters',
        options=kpi_options,
        key='selected_kpis',
        placeholder='---choose KPIs---'
    )

def reset_results():
    st.session_state['results_ready'] = False
    st.session_state['filtered_instruments'] = None
    st.session_state['current_page'] = 0