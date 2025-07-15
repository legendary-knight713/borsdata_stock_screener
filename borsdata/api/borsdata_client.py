from borsdata.api.borsdata_api import BorsdataAPI
import pandas as pd
import matplotlib.pylab as plt
import datetime as dt
from borsdata.api.constants import API_KEY
import numpy as np
import concurrent.futures
from typing import Callable, Optional, List, Dict, Any, Union, Tuple
import logging
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# pandas options for string representation of data frames (print)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


class BorsdataClient:
    """
    A client for interacting with Borsdata API with additional functionality
    for data analysis and visualization.
    """
    
    def __init__(self) -> None:
        """
        Initialize the Borsdata client.
        
        Raises:
            ValueError: If API_KEY is not found in constants file.
            ValueError: If API_KEY is empty or None.
        """
        api_key = API_KEY
        if not api_key:
            raise ValueError("API_KEY not found or empty in constants file")
        try:
            self._borsdata_api = BorsdataAPI(api_key)
            self._instruments_with_meta_data = pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to initialize BorsdataAPI: {str(e)}")
            raise
        
    def instruments_with_meta_data(self) -> pd.DataFrame:
        """
        Get instrument data with metadata from the API.
        
        Returns:
            DataFrame containing instrument data with metadata.
            
        Raises:
            RequestException: If API request fails.
        """
        try:
            if self._instruments_with_meta_data.empty:
                self._instruments_with_meta_data = self._borsdata_api.get_instruments()
            return self._instruments_with_meta_data
        except RequestException as e:
            logger.error(f"Failed to fetch instrument data: {str(e)}")
            raise

    def plot_stock_prices(self, ins_id: int) -> None:
        """
        Plot stock prices and 50-day moving average for a given instrument.
        
        Args:
            ins_id: Instrument ID to plot.
            
        Raises:
            RequestException: If API request fails.
            ValueError: If no data is available for the instrument.
        """
        try:
            stock_prices = self._borsdata_api.get_instrument_stock_prices(ins_id)
            if stock_prices.empty:
                raise ValueError(f"No price data available for instrument {ins_id}")
                
            stock_prices['sma50'] = stock_prices['close'].rolling(window=50).mean()
            filtered_data = stock_prices[stock_prices.index > dt.datetime(2015, 1, 1)]
            
            plt.figure(figsize=(12, 6))
            plt.plot(filtered_data['close'], color='blue', label='Close Price')
            plt.plot(filtered_data['sma50'], color='black', label='50-day MA')
            plt.title(f'Stock Price History - Instrument {ins_id}')
            plt.xlabel('Date')
            plt.ylabel('Price')
            plt.legend()
            plt.grid(True)
            plt.show()
            
        except RequestException as e:
            logger.error(f"Failed to fetch stock prices for instrument {ins_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error plotting stock prices for instrument {ins_id}: {str(e)}")
            raise

    def top_performers(self, market: str, country: str, number_of_stocks: int = 5, percent_change: int = 1) -> pd.DataFrame:
        """
        Get top performing stocks for given parameters
        :param market: Market to search in (e.g. 'Large Cap')
        :param country: Country to search in (e.g. 'Sverige')
        :param number_of_stocks: Number of stocks to return (default 5)
        :param percent_change: Number of days for percent change calculation
        :return: DataFrame with top performing stocks
        """
        instruments = self.instruments_with_meta_data()
        filtered_instruments = instruments.loc[(instruments['market'] == market) & (instruments['country'] == country)]
        stock_prices = pd.DataFrame()
        
        for _, instrument in filtered_instruments.iterrows():
            instrument_stock_price = self._borsdata_api.get_instrument_stock_prices(int(instrument['ins_id']))
            instrument_stock_price.sort_index(inplace=True)
            instrument_stock_price['pct_change'] = instrument_stock_price['close'].pct_change(percent_change)
            
            last_row = instrument_stock_price.iloc[[-1]]
            df_temp = pd.DataFrame([{
                'stock': instrument['name'], 
                'pct_change': round(last_row['pct_change'].values[0] * 100, 2)
            }])
            stock_prices = pd.concat([stock_prices, df_temp], ignore_index=True)
        
        logger.info(f"Top performers: {stock_prices.sort_values('pct_change', ascending=False).head(number_of_stocks)}")
        return stock_prices

    def history_kpi(self, kpi: int, market: str, country: str, year: int) -> pd.DataFrame:
        """
        Gather and concatenate historical KPI values for provided KPI, market and country
        :param kpi: KPI ID (see https://github.com/Borsdata-Sweden/API/wiki/KPI-History)
        :param market: Market to gather KPI values from
        :param country: Country to gather KPI values from
        :param year: Year for terminal print of KPI values
        :return: DataFrame of historical KPI values
        """
        instruments = self.instruments_with_meta_data()
        filtered_instruments = instruments.loc[(instruments['market'] == market) & (instruments['country'] == country)]
        frames = []
        
        for _, instrument in filtered_instruments.iterrows():
            instrument_kpi_history = self._borsdata_api.get_kpi_history(int(instrument['ins_id']), kpi, 'year', 'mean')
            if len(instrument_kpi_history) > 0:
                instrument_kpi_history.reset_index(inplace=True)
                instrument_kpi_history.set_index('year', inplace=True)
                instrument_kpi_history['name'] = instrument['name']
                frames.append(pd.DataFrame({
                    col: instrument_kpi_history[col].values 
                    for col in ['year', 'period', 'kpi_value', 'name']
                }))
        
        symbols_df = pd.concat(frames) if frames else pd.DataFrame()
        df_year = symbols_df[symbols_df.index == year] if not symbols_df.empty else pd.DataFrame()
        
        if 'kpiValue' in df_year.columns:
            try:
                if isinstance(df_year, pd.DataFrame):
                    df_year = df_year.copy()
                    df_year['kpiValue'] = pd.to_numeric(df_year['kpiValue'], errors='coerce')
                    logger.info(f"Top KPI values: {df_year.sort_values(by='kpiValue', ascending=False).head(5)}")
                else:
                    logger.warning("df_year is not a DataFrame, cannot sort.")
            except Exception as e:
                logger.error(f"Error sorting kpiValue: {e}")
        else:
            logger.warning("kpiValue column not found for sorting.")
        
        return symbols_df

    def get_latest_pe(self, ins_id: int) -> Optional[float]:
        """
        Get the PE ratio of the provided instrument ID
        :param ins_id: Instrument ID to calculate PE ratio for
        :return: PE ratio if available, None otherwise
        """
        try:
            reports_quarter, reports_year, reports_r12 = self._borsdata_api.get_instrument_reports(ins_id)
            reports_r12.sort_index(inplace=True)
            logger.info(f"Latest reports: {reports_r12.tail()}")
            
            last_eps = reports_r12['earningsPerShare'].values[-1]
            stock_prices = self._borsdata_api.get_instrument_stock_prices(ins_id)
            stock_prices.sort_index(inplace=True)
            
            last_close = stock_prices['close'].values[-1]
            last_date = stock_prices.index.values[-1]
            
            instruments = self._borsdata_api.get_instruments()
            instrument_row = instruments[instruments.index == ins_id]
            instrument_name = str(ins_id)
            
            if isinstance(instrument_row, pd.DataFrame) and not instrument_row.empty and 'name' in instrument_row.columns:
                instrument_name = instrument_row['name'].iloc[0]
            elif isinstance(instrument_row, pd.Series) and 'name' in instrument_row:
                instrument_name = instrument_row['name']
            elif isinstance(instrument_row, np.ndarray) and instrument_row.size > 0:
                instrument_name = instrument_row[0]
            
            pe_ratio = round(last_close / last_eps, 1)
            logger.info(f"PE for {instrument_name} is {pe_ratio} with data from {str(last_date)[:10]}")
            return pe_ratio
            
        except Exception as e:
            logger.error(f"Error calculating PE ratio for instrument {ins_id}: {e}")
            return None

    def breadth_large_cap_sweden(self) -> pd.DataFrame:
        """
        Plot the breadth (number of stocks above moving-average 40) for Large Cap Sweden compared
        to Large Cap Sweden Index
        :return: DataFrame with breadth data
        """
        instruments = self.instruments_with_meta_data()
        filtered_instruments = instruments.loc[
            (instruments['market'] == "Large Cap") & (instruments['country'] == "Sverige")
        ]
        frames = []
        
        for _, instrument in filtered_instruments.iterrows():
            instrument_stock_prices = self._borsdata_api.get_instrument_stock_prices(int(instrument['ins_id']))
            instrument_stock_prices[f'above_ma40'] = np.where(
                instrument_stock_prices['close'] > instrument_stock_prices['close'].rolling(window=40).mean(), 1, 0
            )
            instrument_stock_prices['name'] = instrument['name']
            
            if len(instrument_stock_prices) > 0:
                frames.append(pd.DataFrame({
                    col: instrument_stock_prices[col].values 
                    for col in ['date', 'above_ma40', 'name']
                }))
        
        symbols_df = pd.concat(frames) if frames else pd.DataFrame()
        if not symbols_df.empty:
            symbols_df = symbols_df.groupby('date').sum()
            symbols_df = symbols_df.to_frame()
            
            omx = self._borsdata_api.get_instrument_stock_prices(643)
            omx = omx[omx.index > '2015-01-01']
            symbols_df = symbols_df[symbols_df.index > '2015-01-01']
            
            fig, (ax1, ax2) = plt.subplots(2, sharex=True)
            ax1.plot(omx['close'], label="OMXSLCPI")
            ax2.plot(symbols_df[f'above_ma40'], label="number of stocks above ma40")
            ax1.legend()
            ax2.legend()
            plt.show()
        
        return symbols_df

    def get_all_kpi_metadata(self) -> pd.DataFrame:
        """
        Fetch all available KPI metadata from the Borsdata API.
        :return: pd.DataFrame of KPI metadata
        """
        return self._borsdata_api.get_kpi_metadata()

    def fetch_kpi_data_for_stocks(self, kpi_ids: List[int], stock_ids: List[int], num_quarters: int = 20, cancel_check: Optional[Callable[[], bool]] = None) -> pd.DataFrame:
        """
        Fetch quarterly data for the given KPIs and stocks for the last num_quarters quarters.
        Returns a DataFrame with columns: ['stock_id', 'kpi_id', 'year', 'period', 'kpiValue']
        Uses parallel requests for speed (max 10 concurrent).
        If cancel_check is provided, will abort fetching if cancel_check() returns True.
        """
        frames = []
        required_cols = ['stock_id', 'kpi_id', 'year', 'period', 'kpiValue']
        tasks = [(stock_id, kpi_id) for stock_id in stock_ids for kpi_id in kpi_ids]
        def fetch_one(args: Tuple[int, int]) -> Optional[pd.DataFrame]:
            if cancel_check and cancel_check():
                return None  # Early abort
            stock_id, kpi_id = args
            try:
                df = self._borsdata_api.get_kpi_history(stock_id, kpi_id, 'quarter', 'mean', max_count=num_quarters)
                if not df.empty:
                    df = df.reset_index()
                    df['stock_id'] = stock_id
                    df['kpi_id'] = kpi_id
                    # Ensure columns: year, period, kpiValue
                    if 'kpiValue' not in df.columns:
                        value_col = [col for col in df.columns if 'kpi' in col.lower() and 'value' in col.lower()]
                        if value_col:
                            df.rename(columns={value_col[0]: 'kpiValue'}, inplace=True)
                    if all(col in df.columns for col in required_cols):
                        return pd.DataFrame({col: df[col].values for col in required_cols})
            except Exception as e:
                logger.error(f"Error fetching KPI {kpi_id} for stock {stock_id}: {e}")
            return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(fetch_one, tasks))
        frames = [df for df in results if df is not None]
        if frames:
            return pd.concat(frames, ignore_index=True)
        else:
            return pd.DataFrame({col: [] for col in required_cols})

    def fetch_kpi_data_for_stocks_yearly(self, kpi_ids: List[int], stock_ids: List[int], num_years: int = 20, cancel_check: Optional[Callable[[], bool]] = None) -> pd.DataFrame:
        """
        Fetch yearly data for the given KPIs and stocks for the last num_years years.
        Returns a DataFrame with columns: ['stock_id', 'kpi_id', 'year', 'kpiValue']
        Uses parallel requests for speed (max 10 concurrent).
        If cancel_check is provided, will abort fetching if cancel_check() returns True.
        """
        frames = []
        required_cols = ['stock_id', 'kpi_id', 'year', 'kpiValue']
        tasks = [(stock_id, kpi_id) for stock_id in stock_ids for kpi_id in kpi_ids]
        def fetch_one(args: Tuple[int, int]) -> Optional[pd.DataFrame]:
            if cancel_check and cancel_check():
                return None  # Early abort
            stock_id, kpi_id = args
            try:
                df = self._borsdata_api.get_kpi_history(stock_id, kpi_id, 'year', 'mean', max_count=num_years)
                if not df.empty:
                    df = df.reset_index()
                    df['stock_id'] = stock_id
                    df['kpi_id'] = kpi_id
                    # Ensure columns: year, kpiValue
                    if 'kpiValue' not in df.columns:
                        value_col = [col for col in df.columns if 'kpi' in col.lower() and 'value' in col.lower()]
                        if value_col:
                            df.rename(columns={value_col[0]: 'kpiValue'}, inplace=True)
                    if all(col in df.columns for col in required_cols):
                        return pd.DataFrame({col: df[col].values for col in required_cols})
            except Exception as e:
                logger.error(f"Error fetching yearly KPI {kpi_id} for stock {stock_id}: {e}")
            return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(fetch_one, tasks))
        frames = [df for df in results if df is not None]
        if frames:
            return pd.concat(frames, ignore_index=True)
        else:
            return pd.DataFrame({col: [] for col in required_cols})

    def fetch_index_data(self, index_ids: List[int], kpi_ids: List[int], num_quarters: int = 20) -> pd.DataFrame:
        """
        Fetch quarterly data for the given KPIs and indices for the last num_quarters quarters.
        Returns a DataFrame with columns: ['index_id', 'kpi_id', 'year', 'period', 'kpiValue']
        Note: Borsdata API does not provide KPI data for indices - this will return empty DataFrame.
        """
        frames = []
        required_cols = ['index_id', 'kpi_id', 'year', 'period', 'kpiValue']
        
        logger.info(f"Fetching index data for {len(index_ids)} indices: {index_ids}")
        logger.info(f"KPIs to fetch: {kpi_ids}")
        
        # Check if we're trying to fetch KPI data for indices (which is not supported)
        if index_ids and kpi_ids:
            logger.warning("Borsdata API does not provide KPI data for indices. Returning empty DataFrame.")
            return pd.DataFrame({col: [] for col in required_cols})
        
        for index_id in index_ids:
            for kpi_id in kpi_ids:
                try:
                    logger.info(f"Fetching KPI {kpi_id} for index {index_id}")
                    df = self._borsdata_api.get_kpi_history(index_id, kpi_id, 'quarter', 'mean', max_count=num_quarters)
                    logger.info(f"KPI {kpi_id} for index {index_id} returned {len(df)} rows")
                    
                    if not df.empty:
                        df = df.reset_index()
                        df['index_id'] = index_id
                        df['kpi_id'] = kpi_id
                        # Ensure columns: year, period, kpiValue
                        if 'kpiValue' not in df.columns:
                            value_col = [col for col in df.columns if 'kpi' in col.lower() and 'value' in col.lower()]
                            if value_col:
                                df.rename(columns={value_col[0]: 'kpiValue'}, inplace=True)
                        if all(col in df.columns for col in required_cols):
                            frames.append(pd.DataFrame({col: df[col].values for col in required_cols}))
                            logger.info(f"Added {len(df)} rows for KPI {kpi_id}, index {index_id}")
                        else:
                            logger.warning(f"Missing required columns for KPI {kpi_id}, index {index_id}. Available columns: {df.columns.tolist()}")
                    else:
                        logger.warning(f"No data returned for KPI {kpi_id}, index {index_id}")
                except Exception as e:
                    # Don't log 400 errors as they are expected for indices
                    if "400" not in str(e):
                        logger.error(f"Error fetching KPI {kpi_id} for index {index_id}: {e}")
        
        logger.info(f"Total frames collected: {len(frames)}")
        if frames:
            result = pd.concat(frames, ignore_index=True)
            logger.info(f"Final index data shape: {result.shape}")
            return result
        else:
            logger.warning("No index data found - returning empty DataFrame")
            # Use dict comprehension for empty DataFrame
            return pd.DataFrame({col: [] for col in required_cols})

    def filter_kpi_data(self, df: pd.DataFrame, filter_dict: Dict[int, Dict[str, Any]]) -> pd.DataFrame:
        """
        Filter KPI data based on filter dictionary
        :param df: DataFrame with KPI data
        :param filter_dict: Dictionary mapping KPI IDs to filter conditions
        :return: Filtered DataFrame
        """
        filtered = df.copy()
        for kpi_id, logic in filter_dict.items():
            kpi_df = filtered[filtered['kpi_id'] == kpi_id]
            if not isinstance(kpi_df, pd.DataFrame):
                kpi_df = pd.DataFrame(kpi_df)
            if 'min' in logic:
                kpi_df = kpi_df[kpi_df['kpiValue'] >= logic['min']]
            if 'max' in logic:
                kpi_df = kpi_df[kpi_df['kpiValue'] <= logic['max']]
            if logic.get('positive', False):
                kpi_df = kpi_df[kpi_df['kpiValue'] > 0]
            if logic.get('negative', False):
                kpi_df = kpi_df[kpi_df['kpiValue'] < 0]
            if logic.get('growth', False):
                periods = logic.get('periods', 4)
                min_growth = logic.get('min_growth', 0.0)
                growth_stocks = []
                stock_ids = pd.Series(kpi_df['stock_id'])
                for stock_id in stock_ids.unique():
                    stock_kpi = kpi_df[kpi_df['stock_id'] == stock_id]
                    if isinstance(stock_kpi, pd.DataFrame):
                        stock_kpi = stock_kpi.sort_values(by=['year', 'period'])
                        if len(stock_kpi) >= periods:
                            start_val = stock_kpi['kpiValue'].iloc[0]
                            end_val = stock_kpi['kpiValue'].iloc[periods-1]
                            if start_val != 0 and (end_val - start_val) / abs(start_val) >= min_growth:
                                growth_stocks.append(stock_id)
                kpi_df = kpi_df[pd.Series(kpi_df['stock_id']).isin(growth_stocks)]
            stock_ids_to_keep = pd.Series(kpi_df['stock_id'])
            filtered = filtered[(filtered['kpi_id'] != kpi_id) | (pd.Series(filtered['stock_id']).isin(stock_ids_to_keep))]
        return filtered

    def compare_to_index(self, stock_df: pd.DataFrame, index_df: pd.DataFrame, periods: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Compare stock performance to index performance over specified periods.
        :param stock_df: DataFrame with stock data
        :param index_df: DataFrame with index data
        :param periods: List of periods to compare (in quarters). Defaults to [1, 4, 10]
        :return: DataFrame with comparison results
        """
        if periods is None:
            periods = [1, 4, 10]
        results = []
        stock_price_col = 'close' if 'close' in stock_df.columns else 'kpiValue'
        index_price_col = 'close' if 'close' in index_df.columns else 'kpiValue'
        for stock_id in pd.Series(stock_df['stock_id']).unique():
            stock_data = stock_df[stock_df['stock_id'] == stock_id]
            if not isinstance(stock_data, pd.DataFrame):
                stock_data = pd.DataFrame(stock_data)
            stock_data = stock_data.sort_values(by=['year', 'period'])
            for idx, row in stock_data.iterrows():
                start_year, start_period = row['year'], row['period']
                start_val = row[stock_price_col]
                for index_id in pd.Series(index_df['index_id']).unique():
                    index_data = index_df[index_df['index_id'] == index_id]
                    if not isinstance(index_data, pd.DataFrame):
                        index_data = pd.DataFrame(index_data)
                    index_data = index_data.sort_values(by=['year', 'period'])
                    index_start = index_data[(index_data['year'] == start_year) & (index_data['period'] == start_period)]
                    if not isinstance(index_start, pd.DataFrame):
                        index_start = pd.DataFrame(index_start)
                    if index_start.empty:
                        continue
                    index_start_val = index_start[index_price_col].iloc[0]
                    for period in periods:
                        if idx + period < len(stock_data):
                            end_val = stock_data.iloc[idx + period][stock_price_col]
                            stock_return = (end_val - start_val) / start_val if start_val != 0 else None
                        else:
                            stock_return = None
                        index_idx = index_start.index[0] if hasattr(index_start, 'index') and len(index_start.index) > 0 else 0
                        if index_idx + period < len(index_data):
                            index_end_val = index_data.iloc[index_idx + period][index_price_col]
                            index_return = (index_end_val - index_start_val) / index_start_val if index_start_val != 0 else None
                        else:
                            index_return = None
                        if stock_return is not None and index_return is not None:
                            outperformance = stock_return - index_return
                        else:
                            outperformance = None
                        results.append({
                            'stock_id': stock_id,
                            'index_id': index_id,
                            'start_year': start_year,
                            'start_period': start_period,
                            'period': period,
                            'stock_return': stock_return,
                            'index_return': index_return,
                            'outperformance': outperformance
                        })
        return pd.DataFrame(results)

    def export_to_excel(self, df: pd.DataFrame, filename: str, sheet_name: Optional[str] = None) -> None:
        """
        Export DataFrame to Excel file
        :param df: DataFrame to export
        :param filename: Output filename
        :param sheet_name: Name of the sheet. Defaults to 'Sheet1'
        """
        if sheet_name is None:
            sheet_name = 'Sheet1'
        with pd.ExcelWriter(filename) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    def advanced_filter_kpi_data(self, df: pd.DataFrame, filter_list: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Apply advanced filters to KPI data
        :param df: DataFrame with KPI data
        :param filter_list: List of filter dictionaries
        :return: Filtered DataFrame
        """
        filtered_stocks = set(df['stock_id'].unique())
        period_filtered_df = df.copy()
        
        for f in filter_list:
            kpi_id = f['kpi_id']
            kpi_df = df[df['kpi_id'] == kpi_id]
            
            # Apply period filtering first
            if all(k in f for k in ['start_year', 'start_period', 'end_year', 'end_period']):
                kpi_df = kpi_df.copy()
                kpi_df['period_tuple'] = list(zip(kpi_df['year'], kpi_df['period']))
                start_tuple = (f['start_year'], f['start_period'])
                end_tuple = (f['end_year'], f['end_period'])
                kpi_df = kpi_df[(kpi_df['period_tuple'] >= start_tuple) & (kpi_df['period_tuple'] <= end_tuple)]
                
                # Also apply period filter to the main DataFrame
                period_filtered_df = period_filtered_df[
                    (period_filtered_df['kpi_id'] != kpi_id) | 
                    ((period_filtered_df['year'] >= f['start_year']) & 
                     (period_filtered_df['year'] <= f['end_year']) &
                     ((period_filtered_df['year'] > f['start_year']) | (period_filtered_df['period'] >= f['start_period'])) &
                     ((period_filtered_df['year'] < f['end_year']) | (period_filtered_df['period'] <= f['end_period'])))
                ]
            
            # Growth filter
            if f['type'] == 'growth':
                min_growth = f.get('min_growth', 0.0)
                stocks_pass = []
                for stock_id in pd.Series(kpi_df['stock_id']).unique():
                    stock_kpi = kpi_df[kpi_df['stock_id'] == stock_id]
                    if not isinstance(stock_kpi, pd.DataFrame):
                        stock_kpi = pd.DataFrame(stock_kpi)
                    stock_kpi = stock_kpi.sort_values(by=['year', 'period'])
                    if len(stock_kpi) >= 2:
                        start_val = pd.Series(stock_kpi['kpiValue']).iloc[0]
                        end_val = pd.Series(stock_kpi['kpiValue']).iloc[-1]
                        if start_val != 0 and (end_val - start_val) / abs(start_val) >= min_growth:
                            stocks_pass.append(stock_id)
                filtered_stocks &= set(stocks_pass)
            # Sign sequence filter
            elif f['type'] == 'sign_sequence':
                sign_seq = f['sign_sequence']
                stocks_pass = []
                for stock_id in pd.Series(kpi_df['stock_id']).unique():
                    stock_kpi = kpi_df[kpi_df['stock_id'] == stock_id]
                    if not isinstance(stock_kpi, pd.DataFrame):
                        stock_kpi = pd.DataFrame(stock_kpi)
                    match = True
                    for seq in sign_seq:
                        val = stock_kpi[(stock_kpi['year'] == seq['year']) & (stock_kpi['period'] == seq['period'])]['kpiValue']
                        val = pd.Series(val)
                        if val.empty:
                            match = False
                            break
                        v = val.iloc[0]
                        if seq['sign'] == 'positive' and v <= 0:
                            match = False
                            break
                        if seq['sign'] == 'negative' and v >= 0:
                            match = False
                            break
                    if match:
                        stocks_pass.append(stock_id)
                filtered_stocks &= set(stocks_pass)
            # Monotonic increase filter
            elif f['type'] == 'monotonic_increase':
                stocks_pass = []
                for stock_id in pd.Series(kpi_df['stock_id']).unique():
                    stock_kpi = kpi_df[kpi_df['stock_id'] == stock_id]
                    if not isinstance(stock_kpi, pd.DataFrame):
                        stock_kpi = pd.DataFrame(stock_kpi)
                    stock_kpi = stock_kpi.sort_values(by=['year', 'period'])
                    values = pd.Series(stock_kpi['kpiValue']).tolist()
                    if all(x < y for x, y in zip(values, values[1:])):
                        stocks_pass.append(stock_id)
                filtered_stocks &= set(stocks_pass)
            # (Add more filter types as needed)
        
        # Return only stocks that passed all filters AND only data within the period range
        if not filtered_stocks:
            return df.iloc[0:0]  # empty DataFrame with same columns
        
        # Apply both stock filter and period filter
        filtered_stocks_list = list(filtered_stocks)
        stock_id_series: pd.Series = period_filtered_df['stock_id']
        mask: pd.Series = stock_id_series.isin(filtered_stocks_list)
        result_df: pd.DataFrame = period_filtered_df[mask]
        return result_df

    def fetch_one_stock(self, stock_id: int, num_days: int = 252) -> Optional[pd.DataFrame]:
        """
        Fetch price data for a single stock
        :param stock_id: Stock ID to fetch
        :param num_days: Number of days of data to fetch
        :return: DataFrame with price data or None if error
        """
        try:
            df = self._borsdata_api.get_instrument_stock_prices(stock_id)
            if not df.empty:
                df = df.sort_index(ascending=False).head(num_days)
                df['stock_id'] = stock_id
                return df
        except Exception as e:
            logger.error(f"Error fetching stock {stock_id}: {e}")
        return None

    def fetch_one_index(self, index_id: int, num_days: int = 252) -> Optional[pd.DataFrame]:
        """
        Fetch price data for a single index
        :param index_id: Index ID to fetch
        :param num_days: Number of days of data to fetch
        :return: DataFrame with price data or None if error
        """
        try:
            df = self._borsdata_api.get_instrument_stock_prices(index_id)
            if not df.empty:
                df = df.sort_index(ascending=False).head(num_days)
                df['index_id'] = index_id
                return df
        except Exception as e:
            logger.error(f"Error fetching index {index_id}: {e}")
        return None

    def fetch_stock_price_data(
        self, 
        stock_ids: List[int], 
        num_days: int = 252, 
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> pd.DataFrame:
        """
        Fetch price data for multiple stocks in parallel
        :param stock_ids: List of stock IDs to fetch
        :param num_days: Number of days of data to fetch
        :param cancel_check: Optional function to check if operation should be cancelled
        :return: DataFrame with price data for all stocks
        """
        frames = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.fetch_one_stock, stock_id, num_days): stock_id for stock_id in stock_ids}
            for future in concurrent.futures.as_completed(futures):
                if cancel_check and cancel_check():
                    break
                stock_id = futures[future]
                try:
                    df = future.result()
                    if df is not None:
                        frames.append(df)
                except Exception as e:
                    logger.error(f"Error processing stock {stock_id}: {e}")
        
        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame()

    def fetch_index_price_data(
        self, 
        index_ids: List[int], 
        num_days: int = 252, 
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> pd.DataFrame:
        """
        Fetch price data for multiple indices in parallel
        :param index_ids: List of index IDs to fetch
        :param num_days: Number of days of data to fetch
        :param cancel_check: Optional function to check if operation should be cancelled
        :return: DataFrame with price data for all indices
        """
        frames = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.fetch_one_index, index_id, num_days): index_id for index_id in index_ids}
            for future in concurrent.futures.as_completed(futures):
                if cancel_check and cancel_check():
                    break
                index_id = futures[future]
                try:
                    df = future.result()
                    if df is not None:
                        frames.append(df)
                except Exception as e:
                    logger.error(f"Error processing index {index_id}: {e}")
        
        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame()

    def compare_stock_to_index_performance(self, stock_df: pd.DataFrame, index_df: pd.DataFrame, periods: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Compare stock performance to index performance
        :param stock_df: DataFrame with stock data
        :param index_df: DataFrame with index data
        :param periods: List of periods (in days) to compare. Defaults to [30, 90, 252]
        :return: DataFrame with comparison results
        """
        if periods is None:
            periods = [30, 90, 252]
        results = []
        
        for stock_id in stock_df['stock_id'].unique():
            stock_data = stock_df[stock_df['stock_id'] == stock_id].sort_values('date')
            
            for index_id in index_df['index_id'].unique():
                index_data = index_df[index_df['index_id'] == index_id].sort_values('date')
                
                # Find common date range
                common_dates = stock_data['date'].isin(index_data['date'])
                if not common_dates.any():
                    continue
                
                stock_common = stock_data[common_dates]
                index_common = index_data[index_data['date'].isin(stock_common['date'])]
                
                if len(stock_common) < 2 or len(index_common) < 2:
                    continue
                
                # Calculate performance metrics for different periods
                for period in periods:
                    if len(stock_common) >= period:
                        # Stock performance
                        stock_start = stock_common.iloc[-period]['close']
                        stock_end = stock_common.iloc[-1]['close']
                        stock_return = (stock_end - stock_start) / stock_start if stock_start != 0 else 0
                        
                        # Index performance
                        index_start = index_common.iloc[-period]['close']
                        index_end = index_common.iloc[-1]['close']
                        index_return = (index_end - index_start) / index_start if index_start != 0 else 0
                        
                        # Relative performance
                        relative_performance = stock_return - index_return
                        
                        # Volatility (standard deviation of returns)
                        stock_returns = stock_common['close'].pct_change().dropna()
                        index_returns = index_common['close'].pct_change().dropna()
                        
                        stock_volatility = stock_returns.std() * (252 ** 0.5) if len(stock_returns) > 1 else 0
                        index_volatility = index_returns.std() * (252 ** 0.5) if len(index_returns) > 1 else 0
                        
                        results.append({
                            'stock_id': stock_id,
                            'index_id': index_id,
                            'period_days': period,
                            'stock_return': stock_return,
                            'index_return': index_return,
                            'relative_performance': relative_performance,
                            'stock_volatility': stock_volatility,
                            'index_volatility': index_volatility,
                            'volatility_ratio': stock_volatility / index_volatility if index_volatility != 0 else 0,
                            'start_date': stock_common.iloc[-period]['date'],
                            'end_date': stock_common.iloc[-1]['date']
                        })
        
        return pd.DataFrame(results)

    def paginate_df(self, df: pd.DataFrame, page_number: int = 1, page_size: int = 50) -> Tuple[pd.DataFrame, int]:
        """
        Paginate a DataFrame
        :param df: DataFrame to paginate
        :param page_number: Page number (1-based)
        :param page_size: Number of items per page
        :return: Tuple of (paginated DataFrame, total number of pages)
        """
        total = len(df)
        if total == 0:
            return df, 0
        start = (page_number - 1) * page_size
        end = start + page_size
        return df.iloc[start:end], total

    def get_filtered_kpi_results(
        self, 
        filter_list: List[Dict[str, Any]], 
        page_number: int = 1, 
        page_size: int = 50, 
        exclude_missing: bool = True, 
        min_history: int = 0
    ) -> Tuple[pd.DataFrame, int]:
        """
        Get filtered and paginated KPI results
        :param filter_list: List of filter dictionaries
        :param page_number: Page number (1-based)
        :param page_size: Number of items per page
        :param exclude_missing: Whether to exclude missing values
        :param min_history: Minimum number of historical data points required
        :return: Tuple of (filtered DataFrame, total number of pages)
        """
        # Fetch all instruments and KPIs
        instruments = self.instruments_with_meta_data()
        kpi_meta = self.get_all_kpi_metadata()
        # Get all stock IDs
        all_stock_ids = instruments['insId'].tolist()
        # Get all KPI IDs from filters
        kpi_ids = list({f['kpi_id'] for f in filter_list})
        # Fetch KPI data for all stocks
        kpi_df = self.fetch_kpi_data_for_stocks(kpi_ids, all_stock_ids)
        # Apply advanced filters
        filtered_df = self.advanced_filter_kpi_data(kpi_df, filter_list)
        # Exclude missing data if requested
        if exclude_missing:
            filtered_df = filtered_df.dropna()
        # Require minimum history if requested
        if min_history > 0:
            stock_counts = filtered_df['stock_id'].value_counts()
            keep_ids = stock_counts[stock_counts >= min_history].index
            filtered_df = filtered_df[filtered_df['stock_id'].isin(keep_ids)]
        # Paginate
        return self.paginate_df(filtered_df, page_number, page_size)

    def get_comparison_results(
        self, 
        stock_ids: List[int], 
        index_ids: List[int], 
        periods: Optional[List[int]] = None, 
        num_days: int = 252, 
        page_number: int = 1, 
        page_size: int = 50
    ) -> Tuple[pd.DataFrame, int]:
        """
        Get paginated comparison results between stocks and indices
        :param stock_ids: List of stock IDs to compare
        :param index_ids: List of index IDs to compare against
        :param periods: List of periods (in days) to compare. Defaults to [30, 90, 252]
        :param num_days: Number of days of historical data to fetch
        :param page_number: Page number (1-based)
        :param page_size: Number of items per page
        :return: Tuple of (comparison DataFrame, total number of pages)
        """
        if periods is None:
            periods = [30, 90, 252]
        stock_price_df = self.fetch_stock_price_data(stock_ids, num_days)
        index_price_df = self.fetch_index_price_data(index_ids, num_days)
        comparison_df = self.compare_stock_to_index_performance(stock_price_df, index_price_df, periods)
        return self.paginate_df(comparison_df, page_number, page_size)

    def get_merged_kpi_metadata(self) -> pd.DataFrame:
        """
        Merge KPI metadata (full names) with abbreviations (short names) using KPI ID.
        Returns a DataFrame with columns: name (abbr), nameEn (full English), nameSv, format, isString, unit, kpiGroup, type, etc.
        """
        meta_df = self._borsdata_api.get_kpi_metadata()
        abbr_df = self._borsdata_api.get_kpi_abbreviations()
        # Merge on index (KPI ID)
        merged = meta_df.join(abbr_df, how='left', rsuffix='_abbr')
        return merged

if __name__ == "__main__":
    # The main logic is now handled via the Streamlit UI and BorsdataClient methods.
    pass
    
