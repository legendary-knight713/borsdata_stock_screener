# ui_helpers.py
import pandas as pd
import streamlit as st

def fetch_yearly_kpi_history(api, stock_ids, kpi_id):
    """Fetch yearly KPI history for each stock and return a DataFrame with columns: insId, year, kpiValue"""
    all_rows = []
    for ins_id in stock_ids:
        try:
            df = api.get_kpi_history(ins_id, kpi_id, report_type='year', price_type='mean')
            if df is not None and not df.empty:
                for idx, row in df.iterrows():
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
    df_result = pd.DataFrame(all_rows)
    if not df_result.empty:
        df_result['insId'] = df_result['insId'].astype(int)
        df_result['year'] = df_result['year'].astype(int)
    return df_result

def test_kpi_quarterly_availability(api, kpi_filters, stock_ids, df_kpis, kpi_short_to_borsdata):
    problematic_kpis = []
    skipped_kpis = []
    if not stock_ids:
        return problematic_kpis
    test_stock_id = stock_ids[0]
    for f in kpi_filters:
        freq = f.get('data_frequency', 'Quarterly')
        if str(freq).lower().startswith('quarter'):
            kpi_name = f.get('kpi')
            borsdata_name = kpi_short_to_borsdata.get(kpi_name, kpi_name)
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
            if not kpi_id:
                skipped_kpis.append(kpi_name)
                continue
            try:
                df = api.get_kpi_history(test_stock_id, kpi_id, report_type='quarter', price_type='mean', max_count=1)
                if df is None or (hasattr(df, 'empty') and df.empty):
                    problematic_kpis.append(kpi_name)
            except Exception as e:
                msg = str(e)
                if 'API-Error, status code: 400' in msg or '400' in msg:
                    problematic_kpis.append(kpi_name)
    if skipped_kpis:
        st.warning(f"Could not resolve KPI IDs for: {', '.join(skipped_kpis)}. These KPIs were not tested for quarterly support.")
    return problematic_kpis

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