# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import requests
import plotly.express as px
import wgs84_ch1903 # for cooridnate conversion. See: https://github.com/ValentinMinder/Swisstopo-WGS84-LV03
import datetime


tabtitle = 'Verkehrslage Zürich'
intro_text = '''
Sie möchten verstopfte Strassen zur Rush Hour vermeiden, oder wissen, ob es in Ihrem Quartier mehr Vekehr gibt als anderswo?

Wählen Sie einen Tag und sehen Sie, wie sich die Verkehrslage in der Stadt Zürich im Laufe des Tages entwickelt hat.

Die dargestellten Daten beruhen auf Messwerten zum motorisierten Individualverkehr (MIV) der Stad Zürich (mehr Informationen dazu finden Sie [hier](https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031)).
'''
footnotes = '''Datenquelle: https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031/resource/44607195-a2ad-4f9b-b6f1-d26c003d85a2

Erstellt durch: Alexander Güntert (https://github.com/alexanderguentert)'''

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
    from "44607195-a2ad-4f9b-b6f1-d26c003d85a2"
WHERE REPLACE("MessungDatZeit",'T',' ')::DATE = '{}'
AND "AnzFahrzeuge" IS NOT NULL
--LIMIT 1000
;'''

url_dates='''https://data.stadt-zuerich.ch/api/3/action/datastore_search_sql?sql=
SELECT 
    DISTINCT REPLACE("MessungDatZeit",'T',' ')::DATE AS datum
    from "44607195-a2ad-4f9b-b6f1-d26c003d85a2"
WHERE "AnzFahrzeuge" IS NOT NULL
ORDER BY 1 DESC'''
url_dates='''https://data.stadt-zuerich.ch/api/3/action/datastore_search_sql?sql=
SELECT 
    MIN(REPLACE("MessungDatZeit",'T',' ')::DATE) AS datum_min,
    MAX(REPLACE("MessungDatZeit",'T',' ')::DATE) AS datum_max
    from "44607195-a2ad-4f9b-b6f1-d26c003d85a2"
WHERE "AnzFahrzeuge" IS NOT NULL
ORDER BY 1 DESC'''



# functions
def download_data(url):
    r = requests.get(url)
    df=pd.read_json(r.text,)
    if df['success'].unique()==True:
        error_status = False
        return (error_status,df)
    else:
        error_status = True
        return (error_status,df['error'])

def extract_data(df):
    # extract relevant data
    df2= df.loc['records','result']
    df3=pd.DataFrame.from_dict(df2)
    return df3

def convert_lat(row):
    return converter.CHtoWGSlat(row['ekoord_strip'],row['nkoord_strip'])

def convert_lon(row):
    return converter.CHtoWGSlng(row['ekoord_strip'],row['nkoord_strip'])

def data_preparation(df):
    df['Zeit']=df['MessungDatZeit']
    df['Uhrzeit'] = pd.to_datetime(df['Zeit']).dt.time.astype(str)
    df['MessungDatZeit'] = pd.to_datetime(df['MessungDatZeit'])
    df['ekoord_strip'] = df['ekoord_strip'].astype(float)
    df['nkoord_strip'] = df['nkoord_strip'].astype(float)
    df['AnzFahrzeuge'] = df['AnzFahrzeuge'].astype(float)
    df['stunde'] = df['MessungDatZeit'].dt.hour
    # convertiere Koordinaten
    df['lat'] = df.apply(convert_lat, axis=1)
    df['lon'] = df.apply(convert_lon, axis=1)
    return df

#preparations
# coordinate conversion
converter = wgs84_ch1903.GPSConverter()

# Load available date for datepicker
error_status, df_dates = download_data(url_dates)
dates = extract_data(df_dates)

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server
app.title=tabtitle

app.layout = html.Div(children=[
    html.H1(children='Vehrkehrsaufkommen in Zürich'),
	
    dcc.Markdown(children=intro_text),
    html.Label('Tag auswählen:'),
    dcc.DatePickerSingle(
        id='date-picker',
        min_date_allowed=dates['datum_min'][0],
        max_date_allowed=dates['datum_max'][0],
        display_format='YYYY-MM-DD',
        date=dates['datum_max'][0]
    ),

	dcc.Graph(id='map'),
    html.Div([
    dcc.Markdown(children=footnotes)
	])
])

@app.callback(
	dash.dependencies.Output('map', 'figure'),
	[dash.dependencies.Input('date-picker', 'date')]
	)

def update_map(date):
	# download
	error_status, df = download_data(url.format(date))
	# check if download correct
	if error_status == False:
		# no error
		miv_data = extract_data(df)
	else:
		pass
	
	miv_data = data_preparation(miv_data)
	
	fig = px.scatter_mapbox(miv_data, lat="lat", lon="lon", size="AnzFahrzeuge",
                        animation_frame='Uhrzeit',
                        hover_data=['AnzFahrzeuge','ZSName','Richtung','Zeit'],
						#title='Verkehrsaufkommen am {}'.format(date),
                        color_continuous_scale=px.colors.diverging.Tealrose,#px.colors.sequential.Plasma_r,#px.colors.cyclical.IceFire, 
                        size_max=30, 
                        zoom=11.5
	)
	fig.update_layout(mapbox_style="carto-positron",height=800) #"open-street-map", "carto-positron", "carto-darkmatter", "stamen-terrain", "stamen-toner" or "stamen-watercolor" 
	return fig


if __name__ == '__main__':
    app.run_server(debug=True)
