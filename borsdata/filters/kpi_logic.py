import pandas as pd

def convert_groups_to_old_format(filter_groups):
    """Convert the new group format to the old kpi_filters format for compatibility."""
    old_filters = []
    for group_idx, group in enumerate(filter_groups):
        for kpi_idx, kpi_name in enumerate(group['filters']):
            kpi_instance_key = f"{kpi_name}_{kpi_idx}"
            kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
            methods = kpi_settings.get('methods', [])
            for method_idx, method_config in enumerate(methods):
                old_filter = {
                    'kpi': kpi_name,
                    'method': method_config.get('type', 'Absolute'),
                    'group_id': group_idx,
                    'group_operator': group['operator'],
                    'method_id': method_idx,
                    'method_operator': kpi_settings.get('method_operator', 'AND')
                }
                # Add method-specific parameters
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


def build_group_logic_tree(filter_groups, kpi_filters, group_relationships='AND'):
    """Build the logic tree for group-based filtering."""
    if not filter_groups:
        return None
    group_nodes = []
    for group_idx, group in enumerate(filter_groups):
        if not group['filters']:
            continue
        if len(group['filters']) == 1:
            kpi_name = group['filters'][0]
            kpi_instance_key = f"{kpi_name}_0"
            kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
            methods = kpi_settings.get('methods', [])
            if len(methods) == 1:
                filter_idx = None
                for old_idx, old_filter in enumerate(kpi_filters):
                    if (old_filter['kpi'] == kpi_name and 
                        old_filter.get('group_id') == group_idx and 
                        old_filter.get('method_id') == 0):
                        filter_idx = old_idx
                        break
                group_node = filter_idx if filter_idx is not None else group_idx
            else:
                method_indices = []
                for method_idx, method_config in enumerate(methods):
                    for old_idx, old_filter in enumerate(kpi_filters):
                        if (old_filter['kpi'] == kpi_name and 
                            old_filter.get('group_id') == group_idx and 
                            old_filter.get('method_id') == method_idx):
                            method_indices.append(old_idx)
                            break
                if method_indices:
                    method_operator = kpi_settings.get('method_operator', 'AND')
                    group_node = {
                        'type': method_operator,
                        'children': method_indices
                    }
                else:
                    group_node = group_idx
        else:
            kpi_indices = []
            for kpi_idx, kpi_name in enumerate(group['filters']):
                kpi_instance_key = f"{kpi_name}_{kpi_idx}"
                kpi_settings = group.get('filter_settings', {}).get(kpi_instance_key, {})
                methods = kpi_settings.get('methods', [])
                if len(methods) == 1:
                    filter_idx = None
                    for old_idx, old_filter in enumerate(kpi_filters):
                        if (old_filter['kpi'] == kpi_name and 
                            old_filter.get('group_id') == group_idx and 
                            old_filter.get('method_id') == 0):
                            filter_idx = old_idx
                            break
                    if filter_idx is not None:
                        kpi_indices.append(filter_idx)
                else:
                    method_indices = []
                    for method_idx, method_config in enumerate(methods):
                        for old_idx, old_filter in enumerate(kpi_filters):
                            if (old_filter['kpi'] == kpi_name and 
                                old_filter.get('group_id') == group_idx and 
                                old_filter.get('method_id') == method_idx):
                                method_indices.append(old_idx)
                                break
                    if method_indices:
                        if len(method_indices) == 1:
                            kpi_indices.append(method_indices[0])
                        else:
                            method_operator = kpi_settings.get('method_operator', 'AND')
                            sub_node = {
                                'type': method_operator,
                                'children': method_indices
                            }
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
    if len(group_nodes) == 1:
        return group_nodes[0]
    else:
        return {
            'type': group_relationships,
            'children': group_nodes
        }


def validate_logic_tree(tree, kpi_filter_settings):
    """Validate that all indices in the logic tree exist in kpi_filter_settings."""
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


def fetch_kpi_data_for_calculation(api, kpi_names, stock_ids, kpi_frequency_map, df_kpis, kpi_short_to_borsdata, st=None, fetch_yearly_kpi_history=None, test_kpi_quarterly_availability=None, client=None, kpi_name_to_short=None):
    """Fetch KPI data needed for calculations, using correct frequency for each KPI. Uses BorsdataClient for parallel fetching if possible. Always uses short name as key."""
    if kpi_name_to_short is None:
        # Build mapping from borsdata name and English name to short name
        kpi_name_to_short = {}
        for short, borsdata in kpi_short_to_borsdata.items():
            kpi_name_to_short[borsdata] = short
            kpi_name_to_short[short] = short
        # Also add English and Swedish names from df_kpis if available
        for _, row in df_kpis.iterrows():
            short = None
            for s, b in kpi_short_to_borsdata.items():
                if b == row.get('nameEn') or b == row.get('nameSv'):
                    short = s
                    break
            if short:
                if 'nameEn' in row:
                    kpi_name_to_short[row['nameEn']] = short
                if 'nameSv' in row:
                    kpi_name_to_short[row['nameSv']] = short
    kpi_data = {}
    if kpi_frequency_map is None:
        kpi_frequency_map = {k: 'Quarterly' for k in kpi_names}
    max_stocks = 1000
    if len(stock_ids) > max_stocks and st:
        st.warning(f"Too many stocks ({len(stock_ids)}). Processing first {max_stocks} stocks only.")
        stock_ids = stock_ids[:max_stocks]

    # Fast path: all KPIs are quarterly
    if client is not None and all(freq == 'Quarterly' for freq in kpi_frequency_map.values()):
        kpi_ids = []
        kpi_name_to_borsdata = {k: kpi_short_to_borsdata.get(k, k) for k in kpi_names}
        for kpi_name in kpi_names:
            borsdata_name = kpi_name_to_borsdata[kpi_name]
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
            if kpi_id is not None:
                kpi_ids.append(int(kpi_id))
        if st:
            st.info(f"Fetching all KPI data in parallel for {len(kpi_ids)} KPIs and {len(stock_ids)} stocks (quarterly)...")
        kpi_df = client.fetch_kpi_data_for_stocks(kpi_ids, stock_ids, num_quarters=20)
        for kpi_id, kpi_name in zip(kpi_ids, kpi_names):
            # Always use short name as key
            short_name = kpi_name_to_short.get(kpi_name, kpi_name)
            kpi_data[short_name] = kpi_df[kpi_df['kpi_id'] == kpi_id].rename(columns={'stock_id': 'insId'})
        return kpi_data

    # Fast path: all KPIs are yearly
    if client is not None and all(freq == 'Yearly' for freq in kpi_frequency_map.values()):
        kpi_ids = []
        kpi_name_to_borsdata = {k: kpi_short_to_borsdata.get(k, k) for k in kpi_names}
        for kpi_name in kpi_names:
            borsdata_name = kpi_name_to_borsdata[kpi_name]
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
            if kpi_id is not None:
                kpi_ids.append(int(kpi_id))
        if st:
            st.info(f"Fetching all KPI data in parallel for {len(kpi_ids)} KPIs and {len(stock_ids)} stocks (yearly)...")
        kpi_df = client.fetch_kpi_data_for_stocks_yearly(kpi_ids, stock_ids, num_years=20)
        for kpi_id, kpi_name in zip(kpi_ids, kpi_names):
            short_name = kpi_name_to_short.get(kpi_name, kpi_name)
            kpi_data[short_name] = kpi_df[kpi_df['kpi_id'] == kpi_id].rename(columns={'stock_id': 'insId'})
        return kpi_data

    # Mixed: some quarterly, some yearly (fetch both in parallel, then merge)
    if client is not None and set(kpi_frequency_map.values()).issubset({'Quarterly', 'Yearly'}):
        quarterly_kpis = [k for k, freq in kpi_frequency_map.items() if freq == 'Quarterly']
        yearly_kpis = [k for k, freq in kpi_frequency_map.items() if freq == 'Yearly']
        kpi_name_to_borsdata = {k: kpi_short_to_borsdata.get(k, k) for k in kpi_names}
        kpi_id_map = {}
        for kpi_name in kpi_names:
            borsdata_name = kpi_name_to_borsdata[kpi_name]
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
            if kpi_id is not None:
                kpi_id_map[kpi_name] = int(kpi_id)
        import concurrent.futures
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            if quarterly_kpis:
                quarterly_ids = [kpi_id_map[k] for k in quarterly_kpis]
                futures['quarterly'] = executor.submit(client.fetch_kpi_data_for_stocks, quarterly_ids, stock_ids, num_quarters=20)
            if yearly_kpis:
                yearly_ids = [kpi_id_map[k] for k in yearly_kpis]
                futures['yearly'] = executor.submit(client.fetch_kpi_data_for_stocks_yearly, yearly_ids, stock_ids, num_years=20)
            for key, future in futures.items():
                results[key] = future.result()
        if 'quarterly' in results:
            for kpi_name in quarterly_kpis:
                kpi_id = kpi_id_map[kpi_name]
                short_name = kpi_name_to_short.get(kpi_name, kpi_name)
                kpi_data[short_name] = results['quarterly'][results['quarterly']['kpi_id'] == kpi_id].rename(columns={'stock_id': 'insId'})
        if 'yearly' in results:
            for kpi_name in yearly_kpis:
                kpi_id = kpi_id_map[kpi_name]
                short_name = kpi_name_to_short.get(kpi_name, kpi_name)
                kpi_data[short_name] = results['yearly'][results['yearly']['kpi_id'] == kpi_id].rename(columns={'stock_id': 'insId'})
        return kpi_data

    # Fallback: original logic
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
                rel_mode = None
                if st:
                    for kf in st.session_state.get('kpi_filters', []):
                        if kf['kpi'] == kpi_name and kf.get('method') == 'Relative':
                            rel_mode = kf.get('rel_mode', 'Year-over-Year (YoY)')
                            break
                if rel_mode == 'Year-over-Year (YoY)' and freq == 'Yearly' and fetch_yearly_kpi_history:
                    if st:
                        st.info(f"Fetching YEARLY data for KPI ID {kpi_id} ({kpi_name}) [YoY mode]")
                    kpi_df = fetch_yearly_kpi_history(api, stock_ids, kpi_id)
                    kpi_data[borsdata_name] = kpi_df
                else:
                    if st:
                        st.info(f"Fetching {freq} data for KPI ID {kpi_id} ({kpi_name})")
                    all_rows = []
                    batch_size = 50
                    for i in range(0, len(stock_ids), batch_size):
                        batch_stocks = stock_ids[i:i+batch_size]
                        for ins_id in batch_stocks:
                            try:
                                df = api.get_kpi_history(ins_id, kpi_id, report_type='quarter' if freq == 'Quarterly' else 'year', price_type='mean')
                                if df is not None and not df.empty:
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
                                if st:
                                    st.warning(f"Error fetching data for stock {ins_id}: {e}")
                                continue
                        if st and len(stock_ids) > 100:
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
                if st:
                    st.warning(f"KPI ID not found for: {kpi_name}")
        except Exception as e:
            if st:
                st.error(f"Error in KPI processing for {kpi_name}: {e}")
                st.error(f"Error type: {type(e).__name__}")
    return kpi_data 