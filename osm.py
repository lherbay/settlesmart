import osmnx as ox

def get_pois(city, tags):
    return ox.features_from_polygon(city.geometry.iloc[0], tags)
