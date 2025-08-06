import streamlit as st
import os
import json
from borsdata.api.borsdata_api import BorsdataAPI
from borsdata.api.constants import API_KEY
from borsdata.ui.ui_layout import setup_page, apply_custom_css, kpi_filter_help
from borsdata.ui.ui_state import initialize_session_state, kpi_filter_validate, reset_pagination, pagination_controls
from borsdata.ui.ui_constants import PAGE_SIZE
from borsdata.ui.ui_data import fetch, get_filtered_stocks
from borsdata.ui.ui_filters import render_filters, render_kpi_filter_groups, render_stock_index_filter
from borsdata.ui.ui_results import show_results
from borsdata.ui.ui_components import render_filter_group, reset_results, render_kpi_multiselect
from borsdata.filters.filter_engine import filter_by_metadata
from borsdata.filters.kpi_logic import (
    convert_groups_to_old_format,
    build_group_logic_tree,
    validate_logic_tree,
    fetch_kpi_data_for_calculation,
)
from borsdata.ui.ui_helpers import fetch_yearly_kpi_history, test_kpi_quarterly_availability
from borsdata.ui.ui_presets import render_preset_management, apply_pending_preset
from borsdata.api.borsdata_client import BorsdataClient

def main():
    setup_page()
    apply_custom_css()
    initialize_session_state()
    
    # Apply any pending preset before rendering widgets
    apply_pending_preset()

    api = BorsdataAPI(API_KEY)
    client = BorsdataClient()
    (all_instruments_df, all_countries_df, all_markets_df, all_sectors_df, all_branches_df, kpis_df) = fetch(api)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PACKAGE_ROOT = os.path.dirname(BASE_DIR)
    kpi_json_path = os.path.join(PACKAGE_ROOT, 'data', 'kpi_options.json')
    with open(kpi_json_path, 'r') as f:
        kpi_json = json.load(f)
    kpi_options = [item['short'] for item in kpi_json]
    kpi_short_to_borsdata = {item['short']: item['borsdata'] for item in kpi_json}

    selected_countries, selected_markets, selected_sectors, selected_industries, selected_stock_indice, country_id_name_map, sector_id_name_map = render_filters(
        all_instruments_df,
        all_countries_df,
        all_markets_df,
        all_sectors_df,
        all_branches_df
    )

    render_kpi_filter_groups(render_filter_group, kpi_options)
    kpi_filter_validate()
    kpi_filter_help()
    stock_index, stock_from_date, stock_to_date, better_rate = render_stock_index_filter()

    # Add preset management functionality
    render_preset_management()

    fetch_clicked = st.button('Fetch Results', key='fetch_results')

    if fetch_clicked and not selected_countries and not selected_sectors and not selected_stock_indice:
        st.info("Fetching results for all countries and all sectors. This may take a moment...")
        
    if fetch_clicked and (selected_countries or selected_sectors or (not selected_countries and not selected_sectors) or selected_stock_indice):
        reset_pagination()

        # Always start with full dataset
        base_df = all_instruments_df.copy()

        # Apply stock index filter FIRST
        if selected_stock_indice and not (better_rate > 0.0):
            base_df = get_filtered_stocks(base_df, selected_stock_indice=selected_stock_indice)

        # Apply country filter (if any)
        if selected_countries:
            country_ids_to_filter = [country_id_name_map[c] for c in selected_countries if c in country_id_name_map]
            base_df = base_df[base_df['countryId'].isin(country_ids_to_filter)]

        # Apply market filter (if any)
        if selected_markets:
            market_ids_to_filter = [int(x) for x in selected_markets]
            available_market_ids = set(base_df['marketId'].dropna().unique())
            if set(market_ids_to_filter) == available_market_ids:
                base_df = base_df[base_df['marketId'].isin(market_ids_to_filter) | base_df['marketId'].isnull()]
            else:
                base_df = base_df[base_df['marketId'].isin(market_ids_to_filter)]

        # If it's not a DataFrame already
        if not isinstance(base_df, type(all_instruments_df)):
            base_df = type(all_instruments_df)(base_df)

        # Apply sector/industry filters
        sector_ids_to_filter = [sector_id_name_map[s] for s in selected_sectors if s in sector_id_name_map]
        industry_ids_to_filter = list(selected_industries) if selected_industries else None

        if sector_ids_to_filter or industry_ids_to_filter:
            filtered_instruments = filter_by_metadata(
                base_df,
                country_ids=None,
                market_ids=None,
                sector_ids=sector_ids_to_filter if sector_ids_to_filter else None,
                industry_ids=industry_ids_to_filter if industry_ids_to_filter else None,
            )
        else:
            filtered_instruments = base_df
        
        if not isinstance(filtered_instruments, type(all_instruments_df)):
            filtered_instruments = type(all_instruments_df)(filtered_instruments)
        if len(filtered_instruments) == 0:
            st.warning("No stocks found after sector/industry filtering. Check your sector/industry selections.")
            st.session_state['filtered_instruments'] = type(all_instruments_df)()
            st.session_state['results_ready'] = True
            st.stop()
        st.session_state['kpi_filters'] = convert_groups_to_old_format(st.session_state['filter_groups'])
        if st.session_state['filter_groups']:
            group_relationships = st.session_state.get('group_relationships', 'AND')
            st.session_state['kpi_logic_tree'] = build_group_logic_tree(
                st.session_state['filter_groups'], 
                st.session_state['kpi_filters'],
                group_relationships
            )
        if st.session_state['kpi_filters'] and 'kpi_logic_tree' in st.session_state:
            id_col = None
            for candidate in ['id', 'insId', 'instrumentId']:
                if candidate in filtered_instruments.columns:
                    id_col = candidate
                    break
            if id_col is None:
                st.error(f"No instrument ID column found in filtered_instruments. Columns: {filtered_instruments.columns.tolist()}")
                st.stop()
            unique_kpis = list(set([kf['kpi'] for kf in st.session_state['kpi_filters']]))
            stock_ids = list(filtered_instruments[id_col])
            kpi_frequency_map = {}
            for idx, kf in enumerate(st.session_state['kpi_filters']):
                kpi_name = kf['kpi']
                freq = kf.get('data_frequency', 'Quarterly')
                kpi_frequency_map[kpi_name] = freq
            problematic_kpis = test_kpi_quarterly_availability(api, st.session_state['kpi_filters'], stock_ids, kpis_df, kpi_short_to_borsdata)
            if problematic_kpis:
                st.warning(f"The following KPIs do not support quarterly data: {', '.join(problematic_kpis)}. Please change their frequency to 'Yearly' or remove them from your filter.")
                st.stop()
            with st.spinner('Processing KPI data...'):
                try:
                    # Build mapping from borsdata name and short name to short name
                    kpi_name_to_short = {}
                    for item in kpi_json:
                        kpi_name_to_short[item['borsdata']] = item['short']
                        kpi_name_to_short[item['short']] = item['short']
                    all_kpi_data = fetch_kpi_data_for_calculation(
                        api, unique_kpis, stock_ids, kpi_frequency_map, kpis_df, kpi_short_to_borsdata, st=st,
                        fetch_yearly_kpi_history=fetch_yearly_kpi_history,
                        test_kpi_quarterly_availability=test_kpi_quarterly_availability,
                        client=client,
                        kpi_name_to_short=kpi_name_to_short
                    )
                    
                except Exception as e:
                    st.error(f"Error fetching KPI data: {e}")
                    st.stop()
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
            stock_kpi_data = {stock_id: {} for stock_id in stock_ids}
            for kpi_name, kpi_df in all_kpi_data.items():
                # Always use the short name as the key
                short_name = None
                # Find the short name for this kpi_name (which may be English name or borsdata name)
                for item in kpi_json:
                    if item['borsdata'] == kpi_name or item['short'] == kpi_name:
                        short_name = item['short']
                        break
                if short_name is None:
                    short_name = kpi_name  # fallback
                for stock_id in stock_ids:
                    if not kpi_df.empty:
                        stock_df = kpi_df[kpi_df['insId'] == stock_id].copy()
                        if not stock_df.empty:
                            if 'period' in stock_df.columns:
                                stock_df = stock_df.sort_values(['year', 'period'])
                            else:
                                stock_df = stock_df.sort_values('year')
                            stock_kpi_data[stock_id][short_name] = stock_df
            st.session_state['kpi_data'] = stock_kpi_data
            tree = st.session_state['kpi_logic_tree']
            if isinstance(tree, int):
                tree = {'type': 'AND', 'children': [tree]}
            if not (isinstance(tree, dict) and 'children' in tree):
                st.warning("Invalid KPI logic tree. Skipping KPI filtering.")
                final_stock_ids = list(filtered_instruments[id_col])
            else:
                if not validate_logic_tree(tree, kpi_filter_settings):
                    st.error("Logic tree validation failed. Some filter indices are missing. Please check your filter configuration.")
                    st.stop()
                final_stock_ids = []
                passed_count = 0
                total_stocks = len(filtered_instruments[id_col])
                progress_bar = st.progress(0)
                status_text = st.empty()
                for i, stock_id in enumerate(filtered_instruments[id_col]):
                    try:
                        from borsdata.filters.filter_engine import evaluate_filter_tree
                        result = evaluate_filter_tree(
                            tree,
                            kpi_filter_settings,
                            stock_kpi_data[stock_id]
                        )
                        if result:
                            final_stock_ids.append(stock_id)
                            passed_count += 1
                        if i % 100 == 0 or i == total_stocks - 1:
                            progress = (i + 1) / total_stocks
                            progress_bar.progress(progress)
                            status_text.text(f"Filtering stocks: {i + 1}/{total_stocks} ({passed_count} passed)")
                    except Exception as e:
                        st.error(f"Error evaluating stock {stock_id}: {e}")
                        continue
                progress_bar.empty()
                status_text.empty()
            if not isinstance(filtered_instruments, type(all_instruments_df)):
                filtered_instruments = type(all_instruments_df)(filtered_instruments)
            if not isinstance(filtered_instruments[id_col], type(all_instruments_df[id_col])):
                filtered_instruments[id_col] = type(all_instruments_df[id_col])(filtered_instruments[id_col])
            filtered_instruments = filtered_instruments[filtered_instruments[id_col].isin(list(final_stock_ids))]
            st.session_state['kpi_data'] = stock_kpi_data
        # Apply stock index filter after KPI filtering    
        if stock_index and stock_from_date and stock_to_date is not None and better_rate > 0.0:
            with st.spinner("Filtering by stock index performance..."):
                # Get index insId from ticker
                index_row = all_instruments_df[all_instruments_df['ticker'] == stock_index]
                if index_row.empty:
                    st.warning(f"Index '{stock_index}' not found in instruments data.")
                else:
                    index_ins_id = int(index_row.iloc[0]['insId'])
                    index_prices = api.get_instrument_stock_prices(index_ins_id, from_date=stock_from_date, to_date=stock_to_date)

                    if index_prices.empty:
                        st.warning(f"No price data found for selected index '{stock_index}' between {stock_from_date} and {stock_to_date}.")
                    else:
                        index_return = (index_prices['close'].iloc[0] - index_prices['close'].iloc[-1]) / index_prices['close'].iloc[-1]

                        passed_ids = []
                        # filtered_instruments = get_filtered_stocks(filtered_instruments, selected_stock_indice=stock_index)
                        for _, row in filtered_instruments.iterrows():
                            stock_id = row['insId']
                            stock_prices = api.get_instrument_stock_prices(stock_id, from_date=stock_from_date, to_date=stock_to_date)
                            if stock_prices.empty or len(stock_prices) < 2:
                                continue
                            stock_return = (stock_prices['close'].iloc[0] - stock_prices['close'].iloc[-1]) / stock_prices['close'].iloc[-1]
                            if index_return != 0:
                                relative_outperformance = (stock_return - index_return) / abs(index_return) * 100
                            else:
                                relative_outperformance = float('inf') if stock_return > 0 else float('-inf')
                            if relative_outperformance >= better_rate:
                                passed_ids.append(stock_id)

                        filtered_instruments = filtered_instruments[filtered_instruments['insId'].isin(passed_ids)]

        st.session_state['filtered_instruments'] = filtered_instruments
        st.session_state['results_ready'] = True
    if st.session_state.get('results_ready') and st.session_state.get('filtered_instruments') is not None:
        filtered_instruments = st.session_state['filtered_instruments']
        show_results(
            filtered_instruments,
            kpi_short_to_borsdata,
            kpis_df,
            all_markets_df,
            all_sectors_df,
            all_countries_df,
            all_branches_df,
            PAGE_SIZE,
            st.session_state['current_page'],
            pagination_controls,
            api,
        )
    elif fetch_clicked:
        st.write("\n_No country or market selected. Please choose at least one country and one market.")

main()
