import streamlit as st
import pandas as pd
from borsdata.api.borsdata_api import BorsdataAPI

# --- Single cache function for all initial data ---
@st.cache_data
def fetch(_api):
    base_df_global = _api.get_instruments_global()
    base_df_local = _api.get_instruments()
    if not isinstance(base_df_global, pd.DataFrame):
        base_df_global = pd.DataFrame(base_df_global)
    if not isinstance(base_df_local, pd.DataFrame):
        base_df_local = pd.DataFrame(base_df_local)
    all_instruments_df = pd.concat([base_df_global, base_df_local], ignore_index=True)
    all_countries_df = _api.get_countries().reset_index()
    all_markets_df = _api.get_markets().reset_index()
    all_sectors_df = _api.get_sectors().reset_index()
    all_branches_df = _api.get_branches().reset_index()
    df_kpis = _api.get_kpi_metadata().reset_index()
    return (all_instruments_df, all_countries_df, all_markets_df, all_sectors_df, all_branches_df, df_kpis)

# --- Fetch all stocks (no pagination here) ---
def get_filtered_stocks(all_instruments_df, country_ids=None, market_ids=None) -> pd.DataFrame:
    df = all_instruments_df.copy()
    if country_ids is not None:
        country_ids = [int(x) for x in list(country_ids)]
        df = pd.DataFrame(df)
        df = df[df['countryId'].isin(country_ids)]
    if market_ids is not None:
        market_ids = [int(x) for x in list(market_ids)]
        df = pd.DataFrame(df)
        available_market_ids = set(df['marketId'].dropna().unique())
        if set(market_ids) == set(available_market_ids):
            df = df[df['marketId'].isin(market_ids) | df['marketId'].isnull()]
        else:
            df = df[df['marketId'].isin(market_ids)]
    return pd.DataFrame(df)
