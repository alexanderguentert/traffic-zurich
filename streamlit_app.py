import pandas as pd
import plotly.express as px
import streamlit as st
import requests
from io import StringIO

from datetime import datetime

import wgs84_ch1903

plot_width = 1200

resources = {
    '2025': 'd96c83ea-8c65-4b6b-991e-fbfeb31a5959',
    '2024': 'c1855626-88e1-4d48-99c8-00b049aae900',
    '2023': '4492d891-a366-49b9-b0f2-fabaa8015d47',
    '2022': 'bc2d7c35-de13-45e9-be21-538d9eab3653',
    '2021': 'b2b5730d-b816-4c20-a3a3-ab2567f81574',
    # '2020': '44607195-a2ad-4f9b-b6f1-d26c003d85a2',
}

url = '''https://data.stadt-zuerich.ch/api/3/action/datastore_search_sql?sql=
SELECT 
    "MSName",
    "ZSName",
    "EKoord",
    substring("EKoord", 2, 10) as ekoord_strip,
    "NKoord",
    substring("NKoord", 2, 10) as nkoord_strip,
    "Richtung",
    "AnzFahrzeuge",
    "AnzFahrzeugeStatus",
    REPLACE("MessungDatZeit",'T',' ') as "MessungDatZeit"
    from "{resource}"
WHERE REPLACE("MessungDatZeit",'T',' ')::DATE = '{date}'
AND "AnzFahrzeuge" IS NOT NULL
'''

url_dates = '''https://data.stadt-zuerich.ch/api/3/action/datastore_search_sql?sql=
SELECT 
    DISTINCT "MessungDatZeit"::DATE AS datum
    from "{resource}"
WHERE "AnzFahrzeuge" IS NOT NULL 
ORDER BY 1 DESC'''



# functions
def download_data(url):
    r = requests.get(url)
    df = pd.read_json(StringIO(r.text),)
    if df['success'].unique():
        error_status = False
        return error_status, df
    else:
        error_status = True
        print(url)
        return error_status, df['error']


def extract_data(df):
    # extract relevant data
    df2 = df.loc['records', 'result']
    df3 = pd.DataFrame.from_dict(df2)
    return df3


def convert_lat(row):
    return converter.CHtoWGSlat(row['ekoord_strip'], row['nkoord_strip'])


def convert_lon(row):
    return converter.CHtoWGSlng(row['ekoord_strip'], row['nkoord_strip'])


def data_preparation(df):
    df['Zeit'] = df['MessungDatZeit']
    df['Uhrzeit'] = pd.to_datetime(df['Zeit']).dt.time.astype(str)
    df['MessungDatZeit'] = pd.to_datetime(df['MessungDatZeit'])
    df['ekoord_strip'] = df['ekoord_strip'].astype(float)
    df['nkoord_strip'] = df['nkoord_strip'].astype(float)
    df['AnzFahrzeuge'] = df['AnzFahrzeuge'].astype(float)
    df['stunde'] = df['MessungDatZeit'].dt.hour
    # convertiere Koordinaten
    df['lat'] = df.apply(convert_lat, axis=1)
    df['lon'] = df.apply(convert_lon, axis=1)
    df = df.sort_values('MessungDatZeit')
    return df


def load_avlailable_dates():
    # Load available date for datepicker
    dates = pd.DataFrame()
    for resource in resources:
        error_status, df_dates = download_data(url_dates.format(resource=resources[resource]))
        df_dates = extract_data(df_dates)
        dates = pd.concat([dates, df_dates])
    dates['datum'] = pd.to_datetime(dates['datum'])
    return dates


def update_map(date):
    date_str = date.strftime('%Y-%m-%d')
    year = date_str[0:4]
    # download
    error_status, df = download_data(url.format(date=date_str, resource=resources[year]))
    # check if download correct
    if error_status == False:
        # no error
        miv_data = extract_data(df)
    else:
        return px.bar(title='Fehler bei Datenabfrage')

    miv_data = data_preparation(miv_data)

    fig = px.scatter_mapbox(miv_data, lat="lat", lon="lon", size="AnzFahrzeuge",
                            animation_frame='Uhrzeit',
                            hover_data=['AnzFahrzeuge', 'ZSName', 'Richtung', 'Zeit'],
                            title='Verkehrsaufkommen am {}'.format(date),
                            color_continuous_scale=px.colors.diverging.Tealrose, #px.colors.sequential.Plasma_r,#px.colors.cyclical.IceFire,
                            size_max=30,
                            zoom=11.5
    )
    fig.update_layout(mapbox_style="carto-positron", height=800, width=plot_width) #"open-street-map", "carto-positron", "carto-darkmatter", "stamen-terrain", "stamen-toner" or "stamen-watercolor"
    return fig, miv_data


def bar_chart_day(miv_data):
    fig = px.bar(miv_data.groupby(['MessungDatZeit'])['AnzFahrzeuge'].sum(),
                    title='Tagestrend',
                    labels={
                        'MessungDatZeit': 'Stunde',
                        'value': 'Summe der Fahrzeuge',
                    })
    fig.update_layout(width=plot_width)
    return fig


def plot_longterm():
    url_year = """https://data.stadt-zuerich.ch/api/3/action/datastore_search_sql?sql=
    SELECT 
        DATE_TRUNC('MONTH', "MessungDatZeit"::TIMESTAMP) AS monat,
        SUM("AnzFahrzeuge"::INT) AS "AnzFahrzeuge"
        FROM "{resource}" 
    WHERE "AnzFahrzeuge" IS NOT NULL 
    GROUP BY 1
    """
    
    df_years = pd.DataFrame() # columns=['zeit', 'AnzFahrzeuge'])
    for resource in resources:
        try:
            error_status, df_year = download_data(url_year.format(resource=resources[resource]))
            df_year = extract_data(df_year)
            df_years = pd.concat([df_years, df_year], ignore_index=True,)
        except:
            continue
    
    df_years['monat'] = pd.to_datetime(df_years['monat'])
    
    fig = px.area(df_years.sort_values(by='monat'), x='monat', y='AnzFahrzeuge',
                  title='Langzeittrend (Fahrzeuge je Monat)')
    fig.update_layout(width=plot_width)
    
    return fig


#preparations
# coordinate conversion
converter = wgs84_ch1903.GPSConverter()


st.set_page_config('Verkehrslage Zürich', layout="wide")
st.title('Verkehrslage Zürich')
st.markdown("""Sie möchten verstopfte Strassen zur Rush Hour vermeiden, oder wissen, ob es in Ihrem Quartier mehr Vekehr gibt als anderswo?

Wählen Sie einen Tag und sehen Sie, wie sich die Verkehrslage in der Stadt Zürich im Laufe des Tages entwickelt hat.

Die dargestellten Daten beruhen auf Messwerten zum motorisierten Individualverkehr (MIV) der Stad Zürich (mehr Informationen dazu finden Sie [hier](https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031)).""")

dates = load_avlailable_dates()

chosen_date = st.date_input('Wähle Tag:', 
                            value=dates['datum'].max(),
                            min_value=dates['datum'].min(),
                            max_value=dates['datum'].max())


map_fig, miv_data = update_map(chosen_date)
st.plotly_chart(map_fig)
st.plotly_chart(bar_chart_day(miv_data))
st.plotly_chart(plot_longterm())

st.markdown('''Erstellt durch: Alexander Güntert 
            ([Mastodon](https://mastodon.social/@gntert), [Twitter](https://twitter.com/TrickTheTurner))  
            Rohdaten- und Bildquelle: https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031  
            Quellcode: https://github.com/alexanderguentert/traffic-zurich''')



