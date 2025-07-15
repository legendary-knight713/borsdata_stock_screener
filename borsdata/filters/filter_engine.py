from typing import Tuple, Optional
import pandas as pd

def parse_quarter_string(quarter_str: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse quarter string in format 'YYYY-Qx' to (year, quarter)"""
    if not quarter_str or len(quarter_str) != 7 or quarter_str[4] != '-':
        return None, None
    
    try:
        year = int(quarter_str[:4])
        quarter = int(quarter_str[6])
        if quarter not in [1, 2, 3, 4]:
            return None, None
        return year, quarter
    except ValueError:
        return None, None

def filter_data_by_time_range(kpi_data: pd.DataFrame, duration_type: str, last_n: Optional[int] = None, 
                             start_quarter: Optional[str] = None, end_quarter: Optional[str] = None) -> pd.DataFrame:
    """Filter KPI data based on time range settings (quarterly or yearly)"""
    if kpi_data.empty:
        return kpi_data

    has_period = 'period' in kpi_data.columns

    if (
        isinstance(start_quarter, str) and len(start_quarter) == 7 and
        isinstance(end_quarter, str) and len(end_quarter) == 7
    ):
        is_quarterly = True
    else:
        is_quarterly = False

    if duration_type == 'Last N Quarters':
        if last_n and last_n > 0:
            # .tail() on a DataFrame always returns a DataFrame
            return kpi_data.tail(last_n)
        else:
            # Always return a DataFrame (last row)
            if len(kpi_data) > 0:
                return kpi_data.iloc[[-1]]
            else:
                return pd.DataFrame(columns=kpi_data.columns)

    # Example: filter by custom range (if implemented)
    # If 'period' exists, filter by both year and period; otherwise, only by year
    if start_quarter and end_quarter:
        try:
            start_year, start_period = map(int, start_quarter.split('Q')) if 'Q' in start_quarter else (int(start_quarter), None)
            end_year, end_period = map(int, end_quarter.split('Q')) if 'Q' in end_quarter else (int(end_quarter), None)
        except Exception:
            start_year, start_period, end_year, end_period = None, None, None, None
        if has_period and start_period is not None and end_period is not None:
            # Quarterly: filter by year and period
            result = kpi_data[
                ((kpi_data['year'] > start_year) | ((kpi_data['year'] == start_year) & (kpi_data['period'] >= start_period))) &
                ((kpi_data['year'] < end_year) | ((kpi_data['year'] == end_year) & (kpi_data['period'] <= end_period)))
            ]
            return result
        else:
            # Yearly: filter by year only
            result = kpi_data[(kpi_data['year'] >= start_year) & (kpi_data['year'] <= end_year)]
            return result

    return kpi_data

def evaluate_kpi_filter(kpi_id: int, kpi_settings: dict, kpi_data: pd.DataFrame) -> bool:
    """
    Evaluate a single KPI filter for a stock's KPI data.
    kpi_data: DataFrame with rows for this KPI and stock, indexed by quarter or year.
    """
    
    duration_type = kpi_settings.get('duration_type', 'Last N Quarters')
    last_n = kpi_settings.get('last_n', 1)
    start_quarter = kpi_settings.get('start_quarter')
    end_quarter = kpi_settings.get('end_quarter')
    trend_enabled = kpi_settings.get('trend_enabled')
    if trend_enabled:
        duration_type = 'Last N Quarters'
        last_n = kpi_settings.get('trend_n') 
        kpi_data = filter_data_by_time_range(kpi_data, duration_type, last_n or 1, start_quarter or '', end_quarter or '')
    else:
        kpi_data = filter_data_by_time_range(kpi_data, duration_type, last_n or 1, start_quarter or '', end_quarter or '')
    if kpi_data.empty:
        return False
    # Exclude stock if any KPI value is missing (nan or None) in the relevant time window
    if 'kpiValue' in kpi_data.columns:
        if kpi_data['kpiValue'].isnull().any():
            return False
    if (
        isinstance(start_quarter, str) and len(start_quarter) == 7 and
        isinstance(end_quarter, str) and len(end_quarter) == 7
    ):
        is_quarterly = True
    else:
        is_quarterly = False

    # Absolute filter
    if kpi_settings.get('abs_enabled'):
        op = kpi_settings['abs_operator']
        val = kpi_settings['abs_value']
        duration_type = kpi_settings.get('duration_type', 'Last N Quarters')
        if not kpi_data.empty:
            if duration_type == 'Last N Quarters':
                last_n = kpi_settings.get('last_n') or 1
                values_to_check = kpi_data.tail(last_n)['kpiValue'].values
            else:  # Custom Range
                values_to_check = kpi_data['kpiValue'].values
            condition_met = all(
                (kpi_value > val) if op == '>' else
                (kpi_value >= val) if op == '>=' else
                (kpi_value < val) if op == '<' else
                (kpi_value <= val) if op == '<=' else False
                for kpi_value in values_to_check
            )
            if not condition_met:
                return False
        else:
            return False
    # Relative filter (YoY or QoQ, all consecutive steps in range)
    if kpi_settings.get('rel_enabled'):
        rel_operator = kpi_settings.get('rel_operator', '>=')
        val = kpi_settings['rel_value']
        values = kpi_data['kpiValue'].tolist()
        if len(values) < 2:
            return False
        for i in range(1, len(values)):
            curr = values[i]
            prev = values[i-1]
            if prev == 0:
                return False
            pct_change = (curr - prev) / abs(prev) * 100
            if rel_operator == '>':
                if not pct_change > val:
                    return False
            elif rel_operator == '>=':
                if not pct_change >= val:
                    return False
            elif rel_operator == '<':
                if not pct_change < val:
                    return False
            elif rel_operator == '<=':
                if not pct_change <= val:
                    return False
            elif rel_operator == '=':
                if not pct_change == val:
                    return False
        return True
    # Trend filter
    if kpi_settings.get('trend_enabled'):
        trend_type = kpi_settings.get('trend_type', 'Positive')
        n = int(kpi_settings['trend_n'])
        m = kpi_settings.get('trend_m')  # Can be None
        
        if len(kpi_data) < n:
            return False
        
        vals = kpi_data['kpiValue'].tail(n).values
        
        if trend_type == 'Positive':
            # Check for consistent growth
            return all(x > y for x, y in zip(vals[1:], vals[:-1]))
        
        elif trend_type == 'Negative':
            # Check for consistent decline
            return all(x < y for x, y in zip(vals[1:], vals[:-1]))
        
        elif trend_type == 'Positive-to-Negative':
            # Check for m quarters of growth followed by decline within n periods
            if m is not None and m > 0:
                # Need at least m+1 quarters to have m quarters of growth + decline
                if len(vals) < m + 1:
                    return False
                
                # Look for pattern: growth for m quarters, then decline
                for i in range(len(vals) - m):
                    # Check if next m quarters show growth
                    growth_periods = vals[i:i+m]
                    if all(growth_periods[j] > growth_periods[j-1] for j in range(1, len(growth_periods))):
                        # Check if the value after growth periods shows decline
                        if i + m < len(vals) and vals[i + m] < vals[i + m - 1]:
                            return True
                return False
            else:
                # Simple transition: any positive to negative within n periods
                for i in range(len(vals) - 1):
                    if vals[i] > 0 and vals[i+1] <= 0:
                        return True
                return False
        
        elif trend_type == 'Negative-to-Positive':
            # Check for m quarters of decline followed by increase within n periods
            if m is not None and m > 0:
                # Need at least m+1 quarters to have m quarters of decline + increase
                if len(vals) < m + 1:
                    return False
                
                # Look for pattern: decline for m quarters, then increase
                for i in range(len(vals) - m):
                    # Check if next m quarters show decline
                    decline_periods = vals[i:i+m]
                    if all(decline_periods[j] < decline_periods[j-1] for j in range(1, len(decline_periods))):
                        # Check if the value after decline periods shows increase
                        if i + m < len(vals) and vals[i + m] > vals[i + m - 1]:
                            return True
                return False
            else:
                # Simple transition: any negative to positive within n periods
                for i in range(len(vals) - 1):
                    if vals[i] < 0 and vals[i+1] >= 0:
                        return True
                return False
    # Direction flag (checks if value is increasing/decreasing)
    direction_enabled = kpi_settings.get('direction_enabled', False)
    direction = kpi_settings.get('direction', 'either')
    if direction_enabled and not kpi_data.empty and len(kpi_data) >= 2:
        # For direction filters, compare start and end value in the filtered range
        if 'period' in kpi_data.columns:
            # Sort by year, period if available
            kpi_data = kpi_data.sort_values(['year', 'period'])
        else:
            kpi_data = kpi_data.sort_values(['year'])
        start_value = kpi_data.iloc[0]['kpiValue']
        end_value = kpi_data.iloc[-1]['kpiValue']
        if direction == 'positive' and end_value <= start_value:
            return False
        if direction == 'negative' and end_value >= start_value:
            return False
    return True

def filter_by_metadata(df, country_ids=None, market_ids=None, sector_ids=None, industry_ids=None):
    if country_ids is not None:
        before_count = len(df)
        df = df[df['countryId'].isin(country_ids)]
        after_count = len(df)
    
    if market_ids is not None:
        before_count = len(df)
        df = df[df['marketId'].isin(market_ids)]
        after_count = len(df)
    
    if sector_ids is not None:
        before_count = len(df)
        df = df[df['sectorId'].isin(sector_ids)]
        after_count = len(df)
    
    if industry_ids is not None:
        before_count = len(df)
        df = df[df['branchId'].isin(industry_ids)]
        after_count = len(df)
    
    return df

def evaluate_filter_tree(tree, kpi_filter_settings, stock_kpi_data):
    """
    Recursively evaluate a logic tree of KPI filters for a single stock.
    tree: dict (AND/OR node) or int (leaf index)
    kpi_filter_settings: dict of filter settings, indexed by leaf index
    stock_kpi_data: dict of {kpi_name: DataFrame} for this stock
    Returns True if the stock passes the filter tree, else False.
    """
    if isinstance(tree, int):
        # Leaf node: evaluate the corresponding KPI filter
        kpi_settings = kpi_filter_settings[tree]
        kpi_name = kpi_settings.get('kpi_name')
        kpi_data = stock_kpi_data.get(kpi_name, pd.DataFrame())
        return evaluate_kpi_filter(tree, kpi_settings, kpi_data)
    elif isinstance(tree, dict) and 'type' in tree and 'children' in tree:
        node_type = tree['type']
        children = tree['children']
        if node_type == 'AND':
            return all(evaluate_filter_tree(child, kpi_filter_settings, stock_kpi_data) for child in children)
        elif node_type == 'OR':
            return any(evaluate_filter_tree(child, kpi_filter_settings, stock_kpi_data) for child in children)
        else:
            # Unknown node type, treat as fail-safe (do not pass)
            return False
    else:
        # Invalid tree node
        return False 