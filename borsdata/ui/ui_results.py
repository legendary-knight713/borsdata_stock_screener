import streamlit as st
import tempfile
from borsdata.ui.ui_helpers import fetch_yearly_kpi_history
from borsdata.filters.filter_engine import filter_data_by_time_range

def show_results(
    filtered_instruments,
    kpi_short_to_borsdata,
    df_kpis,
    all_markets_df,
    all_sectors_df,
    all_countries_df,
    all_branches_df,
    PAGE_SIZE,
    current_page,
    pagination_controls,
    api,
):
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

    def show_cagr_options(kpi_options):
        import datetime
        cagr_kpi = st.selectbox('CAGR KPI', [''] + kpi_options, key='cagr_kpi_stable')
        years = [''] + list(range(1995, datetime.datetime.now().year + 1))
        start_year = st.selectbox('CAGR Start Year', years, key='cagr_start_year_stable')
        end_year = st.selectbox('CAGR End Year', years, key='cagr_end_year_stable')
        calculate_cagr_clicked = st.button('Calculate CAGR', key='calculate_cagr_btn_stable')
        return cagr_kpi, start_year, end_year, calculate_cagr_clicked

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

    sorter = st.session_state['sorter']
    cagr_kpi, cagr_start_year, cagr_end_year, calculate_cagr_clicked = None, None, None, False
    if sorter == 'CAGR':
        st.subheader('CAGR Calculation Settings')
        kpi_options = list(kpi_short_to_borsdata.keys())
        cagr_kpi, cagr_start_year, cagr_end_year, calculate_cagr_clicked = show_cagr_options(kpi_options)

    total_results = len(filtered_instruments)
    total_pages = max(1, (total_results + PAGE_SIZE - 1) // PAGE_SIZE)
    if current_page >= total_pages:
        st.session_state['current_page'] = total_pages - 1
        st.rerun()
    start = current_page * PAGE_SIZE
    end = start + PAGE_SIZE
    paginated_instruments = filtered_instruments.iloc[start:end].copy()

    sort_columns = []
    ascending = []
    cagr_col = None
    market_id_to_name = {row['id']: row['name'] for _, row in all_markets_df.iterrows()}
    if 'marketId' in paginated_instruments.columns:
        paginated_instruments['market'] = paginated_instruments['marketId'].map(market_id_to_name)

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
    if sorter == 'Market':
        market_cap_col = None
        for col in ['market', 'Market']:
            if col in paginated_instruments.columns:
                market_cap_col = col
                break
        if market_cap_col:
            sort_columns.append(market_cap_col)
            ascending.append(False)
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
                            if not kpi_df.empty and 'kpiValue' in kpi_df.columns:
                                values = kpi_df['kpiValue'].tolist()
                            else:
                                values = []
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
    # Show the results table
    paginated_instruments_display = paginated_instruments.copy().reset_index(drop=True)
    st.dataframe(paginated_instruments_display[display_columns])

    if total_pages > 1:
        pagination_controls(st.session_state['current_page'], total_pages, total_results)

    # --- Historical Price Export Date Range Selection ---
    import datetime
    st.markdown('---')
    st.subheader('Export Historical Stock Prices')
    today = datetime.date.today()
    default_from = today.replace(year=today.year-20) if today.year > 20 else today
    from_date = st.date_input('From date', value=default_from, key='price_history_from_date', max_value=today)
    to_date = st.date_input('To date (optional)', value=today, key='price_history_to_date', max_value=today)
    # If user selects a future to_date, reset to today
    if to_date > today:
        to_date = today

    # --- Date range validation ---
    valid_date_range = True
    if from_date and to_date and from_date > to_date:
        st.warning('From date cannot be after To date.')
        valid_date_range = False
    export_to_date = to_date if to_date and from_date <= to_date else today
    export_from_date = from_date
    # The export button and logic will use export_from_date and export_to_date
    # Build mapping dictionaries for export
    sector_id_to_name = {row['id']: row['name'] for _, row in all_sectors_df.iterrows()}
    market_id_to_name = {row['id']: row['name'] for _, row in all_markets_df.iterrows()}
    country_id_to_name = {row['id']: row['name'] for _, row in all_countries_df.iterrows()}
    branch_id_to_name = {row['id']: row['name'] for _, row in all_branches_df.iterrows()}

    # --- Export to Excel button and batch price fetching logic ---
    export_enabled = valid_date_range and not paginated_instruments.empty
    export_clicked = st.button('Export to Excel', disabled=not export_enabled)
    price_history_data = None
    if export_clicked and export_enabled:
        st.info('Fetching historical price data. This may take a while for many stocks...')
        import pandas as pd
        import concurrent.futures
        import tempfile
        import io
        BATCH_SIZE = 20
        id_col = None
        for candidate in ['insId', 'id', 'instrumentId']:
            if candidate in paginated_instruments.columns:
                id_col = candidate
                break
        stock_ids = list(paginated_instruments[id_col])
        batches = [stock_ids[i:i+BATCH_SIZE] for i in range(0, len(stock_ids), BATCH_SIZE)]
        price_frames = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_batches = len(batches)
        def fetch_batch(batch):
            return api.get_instrument_stock_prices_list(batch, from_date=export_from_date.strftime('%Y-%m-%d'), to_date=export_to_date.strftime('%Y-%m-%d'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_batch, batch): idx for idx, batch in enumerate(batches)}
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    df = future.result()
                    if df is not None and not df.empty:
                        price_frames.append(df)
                except Exception as e:
                    st.warning(f'Error fetching a batch of stock prices: {e}')
                progress = (i + 1) / total_batches
                progress_bar.progress(progress)
                status_text.text(f'Fetching batch {i + 1} of {total_batches}')
        progress_bar.empty()
        status_text.empty()
        if price_frames:
            price_history_data = pd.concat(price_frames, ignore_index=True)
        else:
            price_history_data = pd.DataFrame()
        st.success(f'Fetched price history for {len(stock_ids)} stocks.')

        # --- Excel export logic ---
        try:
            if price_history_data is not None and not price_history_data.empty:
                # Prepare summary sheet (filtered stocks, as before)
                summary_df = paginated_instruments_display.copy()
                # Prepare price history sheets
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    with pd.ExcelWriter(tmp.name, engine='xlsxwriter') as writer:
                        summary_df.to_excel(writer, sheet_name='Summary', index=False)
                        workbook  = writer.book
                        # Format for bold header
                        header_format = workbook.add_format({'bold': True})
                        # Autofit columns for summary sheet
                        worksheet = writer.sheets['Summary']
                        for i, col in enumerate(summary_df.columns):
                            max_len = max(
                                summary_df[col].astype(str).map(len).max(),
                                len(str(col))
                            ) + 2
                            worksheet.set_column(i, i, max_len)
                        # Apply bold to header row
                        for col_num, value in enumerate(summary_df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        # Group price data by stock_id
                        for stock_id, stock_df in price_history_data.groupby('stock_id'):
                            # Try to get stock name or ticker for sheet name
                            stock_row = summary_df[summary_df[id_col] == stock_id]
                            sheet_name = str(stock_id)
                            if not stock_row.empty:
                                if 'ticker' in stock_row.columns:
                                    sheet_name = str(stock_row['ticker'].iloc[0])
                                elif 'name' in stock_row.columns:
                                    sheet_name = str(stock_row['name'].iloc[0])
                            # Excel sheet names max 31 chars, no special chars
                            sheet_name = sheet_name[:31].replace('/', '_').replace('\\', '_')
                            # Write price history for this stock
                            stock_df = stock_df.copy()
                            # Ensure columns order
                            price_cols = ['date', 'close', 'open', 'high', 'low', 'volume']
                            stock_df = stock_df[[col for col in price_cols if col in stock_df.columns]]
                            stock_df.to_excel(writer, sheet_name=sheet_name, index=False)
                            ws = writer.sheets[sheet_name]
                            for i, col in enumerate(stock_df.columns):
                                max_len = max(
                                    stock_df[col].astype(str).map(len).max(),
                                    len(str(col))
                                ) + 2
                                ws.set_column(i, i, max_len)
                            for col_num, value in enumerate(stock_df.columns.values):
                                ws.write(0, col_num, value, header_format)
                    tmp.seek(0)
                    excel_bytes = tmp.read()
                st.download_button(
                    label='Download Excel File',
                    data=excel_bytes,
                    file_name='filtered_stocks_with_price_history.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                st.warning('No price history data was fetched for the selected stocks and date range.')
        except Exception as e:
            st.error(f'Error during Excel export: {e}')

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
