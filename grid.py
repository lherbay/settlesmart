#import numpy as np
#import geopandas as gpd
#from shapely.geometry import Point

# Deprecated à enlever

def create_point_grid(place_gdf, spacing=0.005):
    polygon = place_gdf.geometry.iloc[0]
    minx, miny, maxx, maxy = polygon.bounds

    xs = np.arange(minx, maxx, spacing)
    ys = np.arange(miny, maxy, spacing)

    points = []

    for x in xs:
        for y in ys:
            point = Point(x, y)
            if polygon.contains(point):
                points.append(point)

    return gpd.GeoDataFrame(geometry=points, crs=place_gdf.crs)


# Switch to H3 for the grid : to keep

import h3
import geopandas as gpd
from shapely.geometry import Polygon

def create_h3_grid(place_gdf, resolution=9):
    polygon = place_gdf.geometry.iloc[0]

    cells = h3.geo_to_cells(
        polygon.__geo_interface__,
        resolution
        )

    hexagons = []

    for cell in cells:
        boundary = h3.cell_to_boundary(cell)

        poly = Polygon(
            [(lon, lat) for lat, lon in boundary]
        )

        hexagons.append(
            {
                "cell": cell,
                "geometry" : poly
            }
        )

    return gpd.GeoDataFrame(
        hexagons,
        crs="EPSG:4326"
    )
