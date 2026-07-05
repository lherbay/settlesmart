import streamlit as st

import streamlit as st
import osmnx as ox
import folium
import matplotlib
import matplotlib.colors as colors
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Point

from osm import get_pois
from grid import create_h3_grid
from scoring import compute_global_score

POI_TAGS = {
    "Piscines" : {
        "type" : "osm",
        "tags" : {"leisure":"sport_centre", "sport":"swimming"},
        "color" : "blue",
        "weight":3,
        "scale":1200,
    },
    "Escalade" : {
        "type": "osm",
        "tags" : {"leisure":"sport_centre", "sport":"climbing"},
        "color" : "red",
        "weight":3,
        "scale":1200,
    },
    "Travail": {
        "type" : "address",
        "color" : "green",
        "max_time_min" : 20,
        "bike_speed_m_per_min": 250,
        "scale":1000,
    },
}

def score_to_color(score):
    cmap = matplotlib.colormaps["rainbow"]#jet, rainbow, coolwarm
    rgba = cmap(score)
    return matplotlib.colors.to_hex(rgba)

def normalize_for_display(values):
    low = values.quantile(0.05)
    high = values.quantile(0.95)

    if high == low:
        return values * 0

    normalized = (values - low) / (high - low)
    return normalized.clip(0, 1)

def create_study_area(place_gdf, buffer_km):
    projected = place_gdf.to_crs(epsg=2154)
    study_area = projected.copy()
    study_area["geometry"] = projected.geometry.buffer(buffer_km * 1000)
    return study_area.to_crs(epsg=4326)

st.set_page_config(
    page_title="City Heatmap",
    layout="wide"
)

st.title("🏡 City Heatmap")


with st.sidebar:

    st.subheader("Choisissez une ville")
    city = st.text_input(
        "Votre ville",
        value="Nancy, France"
    )

    buffer_km = st.slider(
        "Rayon autour de la ville, en km",
        min_value=0,
        max_value=30,
        value = 5,
        step=1
    )

    selected_pois_list = []
    st.subheader("Choisissez vos critères")

    for poi_name, poi_config in POI_TAGS.items():
        selected = st.checkbox(poi_name)
    
        if selected:
            selected_pois_list.append(poi_name)
            if poi_config["type"] == "osm":
                priority = st.slider(
                    f"Importance",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"priority_{poi_name}"
                )
                st.caption("Faible ← → Forte")
                POI_TAGS[poi_name]["weight"] = priority

            elif poi_config["type"] == "address":
                work_adress = st.text_input(
                    "Adresse du travail",
                    value="",
                    key="work_adress"
                )

                max_time = st.number_input(
                    "Temps max à vélo, en minutes",
                    min_value = 1,
                    max_value = 130,
                    value = poi_config["max_time_min"],
                    key = "work_max_time"
                )

                POI_TAGS[poi_name]["address"] = work_adress
                POI_TAGS[poi_name]["max_time_min"] = max_time
                POI_TAGS[poi_name]["max_distance"] = (max_time * poi_config["bike_speed_m_per_min"])
        
    if "loaded_city" not in st.session_state:
        st.session_state.loaded_city = None

    if st.button("Load city"):
        st.session_state.loaded_city = city

if st.session_state.loaded_city:
    try:
        city = st.session_state.loaded_city
        place = ox.geocode_to_gdf(city)
        study_area = create_study_area(place, buffer_km)
        center = study_area.to_crs(epsg=2154).geometry.centroid.to_crs(epsg=4326).iloc[0]

        st.success(f"City found: {city}")

        # Créer la carte Folium
        m = folium.Map(
            location=[center.y, center.x],
            zoom_start=12
        )
        # Contour zone élargie
        folium.GeoJson(
            study_area.__geo_interface__,
            style_function=lambda x: {
                "fillColor": "transparent",
                "color": "#FFFFFF",
                "weight": 2,
                "fillOpacity": 0,
            },
        ).add_to(m)
        
        # Ajouter le contour de la ville
        folium.GeoJson(
            place.__geo_interface__,
            style_function=lambda x: {
                "fillColor": "transparent",
                "color": "#000000",
                "weight": 3,
                "fillOpacity": 0,
            },
        ).add_to(m)
        
        # Récupérer les POI
        pois_by_criteria={}
        for poi_name in selected_pois_list:
            poi_config = POI_TAGS[poi_name]

            if poi_config["type"] == "osm":
                pois = get_pois(study_area, poi_config["tags"])
                pois_by_criteria[poi_name] = pois

                #st.write(f"{len(pois)} lieux trouvés pour : {poi_name}")

            elif poi_config["type"] == "address":
                if not poi_config.get("address"):
                    st.warning("Adresse du travail non renseignée.")
                    continue

                work_point = ox.geocode(poi_config["address"])

                pois = gpd.GeoDataFrame(
                    [{"name": "Travail", "geometry": Point(work_point[1], work_point[0])}],
                    crs="EPSG:4326"
                )

                pois_by_criteria[poi_name] = pois

                #st.write(f"Adresse travail prise en compte : {poi_config['address']}")
            
            for _, row in pois.iterrows():
                point = row.geometry.centroid
                name = row.get("name") or poi_name

                folium.Marker(
                    location=[point.y, point.x],
                    popup=f"{poi_name} - {name}",
                    tooltip=f"{poi_name} - {name}",
                    icon=folium.Icon(color=poi_config["color"], icon="info-sign")
                ).add_to(m)
                
        #Générer la grille et calculer les scores
        grid = create_h3_grid(study_area, resolution=9)

        grid["score"] = compute_global_score(
            grid,
            pois_by_criteria,
            POI_TAGS
        )
        grid["display_score"]=normalize_for_display(grid["score"])
        #st.write("score min/max", grid["score"].min(), grid["score"].max())
        #st.write("display_score min/max", grid["display_score"].min(), grid["display_score"].max())

        #st.dataframe(
        #    grid[["cell", "score", "display_score"]]
        #    .sort_values("display_score")
        #    .head(10)
        #)

        #st.dataframe(
        #    grid[["cell", "score", "display_score"]]
        #    .sort_values("display_score", ascending=False)
        #    .head(10)
        #)

        folium.GeoJson(
            grid.__geo_interface__,
            style_function=lambda feature: {
                "fillColor" : score_to_color(feature["properties"]["display_score"]),
                "color" : "#666666",
                "weight": 0.5,
                "fillOpacity": 0.5,
                },
            ).add_to(m)
        #st.write(f"{len(grid)} points dans la grille")
        
        #st.write(grid[["cell", "score"]].head())

        # Afficher la carte
        st_folium(m, width=2400, height=1200, key="city_map")

    except Exception as e:
        st.error(e)
