import requests
import pandas as pd
import time
import logging
from typing import Optional, List, Dict, Any, Union
from borsdata.api import constants

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# pandas options for string representation of data frames (print)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


class BorsdataAPI:
    def __init__(self, _api_key: str):
        self._api_key = _api_key
        self._url_root = "https://apiservice.borsdata.se/v1/"
        self._last_api_call = 0
        self._api_calls_per_second = 10
        self._params = {'authKey': self._api_key, 'maxYearCount': 20, 'maxR12QCount': 40, 'maxCount': 20}

    def _call_api(self, url: str, **kwargs) -> Any:
        """
        Internal function for API calls
        :param url: URL add to URL root
        :param kwargs: Additional URL parameters
        :return: JSON-encoded content, if any
        """
        current_time = time.time()
        time_delta = current_time - self._last_api_call
        if time_delta < 1 / self._api_calls_per_second:
            time.sleep(1 / self._api_calls_per_second - time_delta)
        response = requests.get(self._url_root + url, self._get_params(**kwargs))
        logger.debug(f"API call: {response.url}")
        self._last_api_call = time.time()
        if response.status_code != 200:
            logger.error(f"API-Error, status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            # Return empty dict instead of response object to prevent TypeError
            return {}
        return response.json()

    def _get_params(self, **kwargs) -> Dict[str, Any]:
        params = self._params.copy()
        for key, value in kwargs.items():
            if value is not None:
                # fix for reserved keyword 'from' in python.
                if key == "from_date":
                    params['from'] = value
                elif key == "to" or key == "date":
                    params[key] = value
                elif key == "instList":
                    params[key] = ",".join(str(stock_id) for stock_id in value)
                else:
                    logger.warning(f"BorsdataAPI >> Unknown param: {key}={value}")
        return params

    @staticmethod
    def _set_index(df: pd.DataFrame, index: Union[str, List[str]], ascending: bool = True) -> None:
        """
        Set index(es) and sort by index
        :param df: pd.DataFrame
        :param index: Column name to set to index
        :param ascending: True to sort index ascending
        """
        if isinstance(index, list):
            for idx in index:
                if idx not in df.columns:
                    return
        else:
            if index not in df.columns:
                return

        df.set_index(index, inplace=True)
        df.sort_index(inplace=True, ascending=ascending)

    @staticmethod
    def _parse_date(df: pd.DataFrame, key: str) -> None:
        """
        Parse date string as pd.datetime, if available
        :param df: pd.DataFrame
        :param key: Column name
        """
        if key in df:
            # df[key] = pd.to_datetime(df[key])
            df[key] = pd.to_datetime(df[key], errors="coerce", format="mixed")


    def _get_base_params(self) -> Dict[str, Any]:
        """
        Get URL parameter base
        :return: Parameters dict
        """
        return {
            "authKey": self._api_key,
            "version": 1,
            'maxYearCount': 20,
            'maxR12QCount': 40,
            'maxCount': 20
        }

    """
    Instrument Metadata
    """

    def get_branches(self):
        """
        Get branch data
        :return: pd.DataFrame
        """
        url = "branches"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["branches"])
        self._set_index(df, "id")
        return df

    def get_countries(self):
        """
        Get country data
        :return: pd.DataFrame
        """
        url = "countries"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["countries"])
        self._set_index(df, "id")
        return df

    def get_markets(self):
        """
        Get market data
        :return: pd.DataFrame
        """
        url = "markets"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["markets"])
        self._set_index(df, "id")
        return df

    def get_sectors(self):
        """
        Get sector data
        :return: pd.DataFrame
        """
        url = "sectors"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["sectors"])
        self._set_index(df, "id")
        return df

    def get_translation_metadata(self):
        """
        Get translation metadata
        :return: pd.DataFrame
        """
        url = "translationmetadata"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["translationMetadatas"])
        self._set_index(df, "translationKey")
        return df

    """
    Instruments
    """

    def get_instruments(self):
        """
        Get instrument data
        :return: pd.DataFrame
        """
        url = "instruments"
        json_data = self._call_api(url)
        if not isinstance(json_data, dict) or "instruments" not in json_data:
            logger.error("Failed to get instruments data - API returned invalid response")
            return pd.DataFrame()
        df = pd.json_normalize(json_data["instruments"])
        self._parse_date(df, "listingDate")
        # Don't set insId as index - keep it as a column for easier access
        return df

    def get_instruments_updated(self):
        """
        Get all updated instruments
        :return: pd.DataFrame
        """
        url = "instruments/updated"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["instruments"])
        self._parse_date(df, "updatedAt")
        self._set_index(df, "insId")
        return df

    def get_instruments_global(self):
        """
        Get global instrument data
        :return: pd.DataFrame
        """
        url = "instruments/global"
        json_data = self._call_api(url)
        if not isinstance(json_data, dict) or "instruments" not in json_data:
            logger.error("Failed to get instruments global data - API returned invalid response")
            return pd.DataFrame()
        df = pd.json_normalize(json_data["instruments"])
        self._parse_date(df, "listingDate")
        # Don't set insId as index - keep it as a column for easier access
        return df

    """
    KPIs
    """

    def get_kpi_history(self, ins_id, kpi_id, report_type, price_type, max_count=None):
        """
        Get KPI history for an instrument
        :param ins_id: Instrument ID
        :param kpi_id: KPI ID
        :param report_type: ['quarter', 'year', 'r12']
        :param price_type: ['mean', 'high', 'low']
        :param max_count: Max. number of history (quarters/years) to get
        :return: pd.DataFrame
        """
        url = f"instruments/{ins_id}/kpis/{kpi_id}/{report_type}/{price_type}/history"
        params = self._get_base_params()
        if max_count is not None:
            params["maxCount"] = max_count
        json_data = self._call_api(url)
        if not isinstance(json_data, dict):
            return pd.DataFrame({col: [] for col in ["year", "period", "kpiValue"]})
        if "values" not in json_data or not json_data["values"]:
            return pd.DataFrame({col: [] for col in ["year", "period", "kpiValue"]})
        df = pd.json_normalize(json_data["values"])
        for old, new in {"y": "year", "p": "period", "v": "kpiValue"}.items():
            if old in df.columns:
                df.rename(columns={old: new}, inplace=True)
        if "year" in df.columns and "period" in df.columns:
            self._set_index(df, ["year", "period"], ascending=False)
        return df

    def get_kpi_summary(self, ins_id, report_type, max_count=None):
        """
        Get KPI summary for instrument
        :param ins_id: Instrument ID
        :param report_type: Report type ['quarter', 'year', 'r12']
        :param max_count: Max. number of history (quarters/years) to get
        :return: pd.DataFrame
        """
        url = f"instruments/{ins_id}/kpis/{report_type}/summary"
        if max_count is not None:
            self._params["maxCount"] = max_count
        json_data = self._call_api(url)
        if not isinstance(json_data, dict):
            return pd.DataFrame()
        if "kpis" not in json_data or not json_data["kpis"]:
            return pd.DataFrame()
        df = pd.json_normalize(json_data["kpis"], record_path="values", meta="KpiId")
        for old, new in {"y": "year", "p": "period", "v": "kpiValue", "KpiId": "kpiId"}.items():
            if old in df.columns:
                df.rename(columns={old: new}, inplace=True)
        if all(col in df.columns for col in ["year", "period", "kpiId", "kpiValue"]):
            df = df.pivot_table(index=["year", "period"], columns="kpiId", values="kpiValue")
            self._set_index(df, ["year", "period"], ascending=False)
        return df

    def get_kpi_data_instrument(self, ins_id, kpi_id, calc_group, calc):
        """
        Get screener data, for more information: https://github.com/Borsdata-Sweden/API/wiki/KPI-Screener
        :param ins_id: Instrument ID
        :param kpi_id: KPI ID
        :param calc_group: ['1year', '3year', '5year', '7year', '10year', '15year']
        :param calc: ['high', 'latest', 'mean', 'low', 'sum', 'cagr']
        :return: pd.DataFrame
        """
        url = f"instruments/{ins_id}/kpis/{kpi_id}/{calc_group}/{calc}"
        json_data = self._call_api(url)
        if not isinstance(json_data, dict):
            return pd.DataFrame()
        if "value" not in json_data or not json_data["value"]:
            return pd.DataFrame()
        df = pd.json_normalize(json_data["value"])
        for old, new in {"i": "insId", "n": "valueNum", "s": "valueStr"}.items():
            if old in df.columns:
                df.rename(columns={old: new}, inplace=True)
        if "insId" in df.columns:
            self._set_index(df, "insId")
        return df

    def get_kpi_data_all_instruments(self, kpi_id, calc_group, calc):
        """
        Get KPI data for all instruments
        :param kpi_id: KPI ID
        :param calc_group: ['1year', '3year', '5year', '7year', '10year', '15year']
        :param calc: ['high', 'latest', 'mean', 'low', 'sum', 'cagr']
        :return: pd.DataFrame
        """
        url = f"instruments/kpis/{kpi_id}/{calc_group}/{calc}"
        json_data = self._call_api(url)
        if not isinstance(json_data, dict):
            return pd.DataFrame()
        if "values" not in json_data or not json_data["values"]:
            return pd.DataFrame()
        df = pd.json_normalize(json_data["values"])
        for old, new in {"i": "insId", "n": "valueNum", "s": "valueStr"}.items():
            if old in df.columns:
                df.rename(columns={old: new}, inplace=True)
        if "insId" in df.columns:
            self._set_index(df, "insId")
        return df

    def get_kpi_data_global_instruments(self, kpi_id, calc_group, calc):
        """
        Get KPI data for global instruments
        :param kpi_id: KPI ID
        :param calc_group: ['1year', '3year', '5year', '7year', '10year', '15year']
        :param calc: ['high', 'latest', 'mean', 'low', 'sum', 'cagr']
        :return: pd.DataFrame
        """
        url = f"instruments/global/kpis/{kpi_id}/{calc_group}/{calc}"
        json_data = self._call_api(url)
        if not isinstance(json_data, dict):
            return pd.DataFrame()
        if "values" not in json_data or not json_data["values"]:
            return pd.DataFrame()
        df = pd.json_normalize(json_data["values"])
        for old, new in {"i": "insId", "n": "valueNum", "s": "valueStr"}.items():
            if old in df.columns:
                df.rename(columns={old: new}, inplace=True)
        if "insId" in df.columns:
            self._set_index(df, "insId")
        return df

    def get_updated_kpis(self):
        """
        Get latest calculation date and time for KPIs
        :return: pd.datetime
        """
        url = "instruments/kpis/updated"
        json_data = self._call_api(url)
        return pd.to_datetime(json_data["kpisCalcUpdated"])

    def get_kpi_metadata(self):
        """
        Get KPI metadata
        :return: pd.DataFrame
        """
        url = "instruments/kpis/metadata"
        json_data = self._call_api(url)
        if not isinstance(json_data, dict):
            return pd.DataFrame()
        if "kpiHistoryMetadatas" not in json_data or not json_data["kpiHistoryMetadatas"]:
            return pd.DataFrame()
        df = pd.json_normalize(json_data["kpiHistoryMetadatas"])
        if "kpiId" in df.columns:
            self._set_index(df, "kpiId")
        return df

    """
    Reports
    """

    def get_instrument_report(self, ins_id, report_type, max_count=None):
        """
        Get specific report data
        :param ins_id: Instrument ID
        :param report_type: ['quarter', 'year', 'r12']
        :param max_count: Max. number of history (quarters/years) to get
        :return: pd.DataFrame of report data
        """
        url = f"instruments/{ins_id}/reports/{report_type}"

        params = self._get_base_params()
        if max_count is not None:
            params["maxCount"] = max_count
        json_data = self._call_api(url)

        df = pd.json_normalize(json_data["reports"])
        df.columns = [x.replace("_", "") for x in df.columns]
        self._parse_date(df, "reportStartDate")
        self._parse_date(df, "reportEndDate")
        self._parse_date(df, "reportDate")
        self._set_index(df, ["year", "period"], ascending=False)
        return df

    def get_instrument_reports(self, ins_id):
        """
        Get all report data
        :param ins_id: Instrument ID
        :return: [pd.DataFrame quarter, pd.DataFrame year, pd.DataFrame r12]
        """
        # constructing url for api-call, adding ins_id
        url = f"instruments/{ins_id}/reports"
        json_data = self._call_api(url)
        dfs = []
        for report_type in ["reportsQuarter", "reportsYear", "reportsR12"]:
            df = pd.json_normalize(json_data[report_type])
            df.columns = [x.replace("_", "") for x in df.columns]
            self._parse_date(df, "reportStartDate")
            self._parse_date(df, "reportEndDate")
            self._parse_date(df, "reportDate")
            self._set_index(df, ["year", "period"], ascending=False)
            dfs.append(df)
        return dfs

    def get_instrument_report_list(self, stock_id_list):
        """
        Get all report data for Stocks in stock_id_list
        :param stock_id_list: Instrument ID list
        :return: [pd.DataFrame quarter, pd.DataFrame year, pd.DataFrame r12]
        """
        url = f"instruments/reports"
        json_data = self._call_api(url, instList=stock_id_list)
        r12 = pd.json_normalize(json_data['reportList'], record_path="reportsR12", meta=["instrument"])
        r12 = r12.rename(columns=str.lower)
        r12 = r12.rename(columns={'instrument': 'stock_id'})
        r12.fillna(0, inplace=True)
        quarter = pd.json_normalize(json_data['reportList'], record_path="reportsQuarter", meta=["instrument"])
        quarter = quarter.rename(columns=str.lower)
        quarter = quarter.rename(columns={'instrument': 'stock_id'})
        quarter.fillna(0, inplace=True)
        year = pd.json_normalize(json_data['reportList'], record_path="reportsYear", meta=["instrument"])
        year = year.rename(columns=str.lower)
        year = year.rename(columns={'instrument': 'stock_id'})
        year.fillna(0, inplace=True)
        return quarter, year, r12

    def get_reports_metadata(self):
        """
        Get reports metadata
        :return: pd.DataFrame
        """
        url = "instruments/reports/metadata"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["reportMetadatas"])
        # Fix probable misspelling 'propery' -> 'property'
        df.rename(
            columns={"reportPropery": "reportProperty"},
            inplace=True,
        )
        df["reportProperty"] = df["reportProperty"].apply(lambda x: x.replace("_", ""))
        self._set_index(df, "reportProperty")
        return df

    """
    Stock prices
    """

    def get_instrument_stock_prices(self, ins_id, from_date=None, to_date=None, max_count=None):
        """
        Get stock prices for instrument ID
        :param ins_id: Instrument ID
        :param from_date: Start date in string format, e.g. '2000-01-01'
        :param to_date: Stop date in string format, e.g. '2000-01-01'
        :param max_count: Max. number of history (quarters/years) to get
        :return: pd.DataFrame
        """
        url = f"instruments/{ins_id}/stockprices"
        json_data = self._call_api(url, from_date=from_date, to=to_date)
        df = pd.json_normalize(json_data["stockPricesList"])
        df.rename(
            columns={
                "d": "date",
                "c": "close",
                "h": "high",
                "l": "low",
                "o": "open",
                "v": "volume",
            },
            inplace=True,
        )
        self._parse_date(df, "date")
        self._set_index(df, "date", ascending=False)
        return df

    def get_instrument_stock_prices_list(self, stock_id_list, from_date=None, to_date=None):
        """
        Get stock prices for instrument ID
        :param stock_id_list: Instrument ID list
        :param from_date: Start date in string format, e.g. '2000-01-01'
        :param to_date: Stop date in string format, e.g. '2000-01-01'
        :return: pd.DataFrame
        """
        url = 'instruments/stockprices'
        json_data = self._call_api(url, from_date=from_date, to=to_date, instList=stock_id_list)
        stock_prices = pd.json_normalize(json_data['stockPricesArrayList'], "stockPricesList", ['instrument'])
        stock_prices.rename(columns={'d': 'date', 'c': 'close', 'h': 'high', 'l': 'low',
                                    'o': 'open', 'v': 'volume', 'instrument': 'stock_id'}, inplace=True)
        stock_prices.fillna(0, inplace=True)
        return stock_prices

    def get_instruments_stock_prices_last(self):
        """
        Get last days' stock prices for all instruments
        :return: pd.DataFrame
        """
        url = "instruments/stockprices/last"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["stockPricesList"])
        df.rename(
            columns={
                "d": "date",
                "i": "insId",
                "c": "close",
                "h": "high",
                "l": "low",
                "o": "open",
                "v": "volume",
            },
            inplace=True,
        )
        self._parse_date(df, "date")
        self._set_index(df, "date", ascending=False)
        return df

    def get_stock_prices_date(self, date):
        """
        Get all instrument stock prices for given date
        :param date: Date in string format, e.g. '2000-01-01'
        :return: pd.DataFrame
        """
        url = "instruments/stockprices/date"

        json_data = self._call_api(url, date=date)
        df = pd.json_normalize(json_data["stockPricesList"])
        df.rename(
            columns={
                "d": "date",
                "i": "insId",
                "c": "close",
                "h": "high",
                "l": "low",
                "o": "open",
                "v": "volume",
            },
            inplace=True,
        )
        self._parse_date(df, "date")
        self._set_index(df, "insId")
        return df

    """
    Stock splits
    """

    def get_stock_splits(self):
        """
        Get stock splits
        :return: pd.DataFrame
        """
        url = "instruments/stocksplits"
        json_data = self._call_api(url)
        df = pd.json_normalize(json_data["stockSplitList"])
        df.rename(
            columns={"instrumentId": "insId"},
            inplace=True,
        )
        self._parse_date(df, "splitDate")
        self._set_index(df, "insId")
        return df

    def get_english_name(self, entity: str, id_: int, df_trans: pd.DataFrame) -> str:
        key = f"{entity}.{id_}.Name"
        if key in df_trans.index and 'nameEn' in df_trans.columns:
            return df_trans.loc[key, 'nameEn']
        print(f"DEBUG: Key '{key}' not found in df_trans.index or 'nameEn' not in columns.")
        return str(id_)


if __name__ == "__main__":
    # Main, call functions here.
    api = BorsdataAPI(constants.API_KEY)
    api.get_translation_metadata()
    api.get_instruments_updated()
    api.get_kpi_summary(3, "year")
    api.get_kpi_data_instrument(3, 10, '1year', 'mean')
    api.get_kpi_data_all_instruments(10, '1year', 'mean')
    api.get_updated_kpis()
    api.get_kpi_metadata()
    api.get_instrument_report(3, 'year')
    api.get_reports_metadata()
    api.get_stock_prices_date('2020-09-25')
    api.get_stock_splits()
    api.get_instrument_stock_prices(2, from_date="2022-01-01", to_date="2023-01-01")
    api.get_instrument_stock_prices_list([2, 3, 4, 5])
    api.get_instruments_global()
    api.get_kpi_data_global_instruments(10, '1year', 'mean')