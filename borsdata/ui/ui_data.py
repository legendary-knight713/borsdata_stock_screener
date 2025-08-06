import streamlit as st
import pandas as pd
import os
import json

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
    kpis_df = _api.get_kpi_metadata().reset_index()
    return (all_instruments_df, all_countries_df, all_markets_df, all_sectors_df, all_branches_df, kpis_df)

def match_country_sector_industry_names(countries_df, sectors_df, industries_df, translation_df):
    #Build a mapping from Swidish to English
    sv_to_en = dict(zip(translation_df['nameSv'], translation_df['nameEn']))

    #Replace in countries
    if 'name' in countries_df.columns:
        countries_df['name'] = countries_df['name'].map(lambda x: sv_to_en.get(x, x))
    
    #Replace in sectors
    if 'name' in sectors_df.columns:
        sectors_df['name'] = sectors_df['name'].map(lambda x: sv_to_en.get(x, x))

    #Replace in industries/branches
    if 'name' in industries_df.columns:
        industries_df['name'] = industries_df['name'].map(lambda x:sv_to_en)

# --- Fetch all stocks (no pagination here) ---
def get_filtered_stocks(all_instruments_df, country_ids=None, market_ids=None, selected_stock_indice=None) -> pd.DataFrame:
    df = all_instruments_df.copy()
    
    # Apply country filter
    if country_ids is not None:
        country_ids = [int(x) for x in list(country_ids)]
        df = df[df['countryId'].isin(country_ids)]

    # Apply market filter
    if market_ids is not None:
        market_ids = [int(x) for x in list(market_ids)]
        available_market_ids = set(df['marketId'].dropna().unique())
        if set(market_ids) == set(available_market_ids):
            df = df[df['marketId'].isin(market_ids) | df['marketId'].isnull()]
        else:
            df = df[df['marketId'].isin(market_ids)]

    # Apply stock index filter by (ticker, name)
    if selected_stock_indice and selected_stock_indice != '--- Choose stock index ---':
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(BASE_DIR, '../data/stock_indices.json')

        with open(json_path, 'r') as f:
            stock_indice_dict = json.load(f)

        selected_pairs = set()
        entries = stock_indice_dict.get(selected_stock_indice, [])
        for entry in entries:
            if isinstance(entry, dict) and 'ticker' in entry and 'name' in entry:
                selected_pairs.add((entry['ticker'], entry['name']))

        # Filter using BOTH ticker and name
        df = df[df.apply(lambda row: (row['ticker'], row['name']) in selected_pairs, axis=1)]

    return df.reset_index(drop=True)

