import numpy as np
from scipy.spatial import cKDTree

def get_centroids(gdf):
    """
    Convertit les géométries en points centraux projetés en mètres.
    EPSG:2154 = projection française en mètres.
    """
    projected = gdf.to_crs(epsg=2154)
    centroids = projected.geometry.centroid

    return np.array([[point.x, point.y] for point in centroids])


def distance_to_nearest_poi(grid_gdf, pois_gdf):
    """
    Pour chaque hexagone, calcule la distance au POI le plus proche.
    Retourne un tableau de distances en mètres.
    """
    if pois_gdf.empty:
        return np.full(len(grid_gdf), np.nan)

    grid_points = get_centroids(grid_gdf)
    poi_points = get_centroids(pois_gdf)

    tree = cKDTree(poi_points)
    distances, _ = tree.query(grid_points, k=1)

    return distances


def preference_layer(grid_gdf, pois_gdf, scale):
    """
    Layer de préférence type piscine/escalade.

    Plus l'hexagone est proche d'un POI, plus le score est haut.
    Décroissance douce, sans seuil brutal.

    score = exp(-distance / scale)
    """
    distances = distance_to_nearest_poi(grid_gdf, pois_gdf)

    if np.all(np.isnan(distances)):
        return np.zeros(len(grid_gdf))

    return np.exp(-distances / scale)


def constraint_layer(grid_gdf, pois_gdf, max_distance, falloff_scale):
    """
    Layer de contrainte type travail.

    - score = 1 dans la zone acceptable
    - puis le score diminue progressivement au-delà

    Exemple :
    travail à moins de 20 min vélo.
    """
    distances = distance_to_nearest_poi(grid_gdf, pois_gdf)

    if np.all(np.isnan(distances)):
        return np.zeros(len(grid_gdf))

    return np.where(
        distances <= max_distance,
        1.0,
        np.exp(-(distances - max_distance) / falloff_scale)
    )

def combine_preference_distances(weighted_distances, weights, scale):
    """
    Combine les préférences par coût total en distance.

    Une zone est bonne seulement si elle est globalement proche
    de tous les critères loisirs sélectionnés.
    """
    if not weighted_distances:
        return None

    distances = np.vstack(weighted_distances)
    weights = np.array(weights, dtype=float)

    weighted_cost = np.average(
        distances,
        axis=0,
        weights=weights
    )

    return np.exp(-weighted_cost / scale)

def combine_constraint_layers(constraint_layers):
    """
    Combine les contraintes.

    On multiplie les contraintes :
    - si une contrainte vaut 0, le score final tombe à 0
    - si toutes les contraintes valent 1, rien n'est pénalisé
    """
    if not constraint_layers:
        return None

    layers = np.vstack(constraint_layers)

    return np.prod(layers, axis=0)

def compute_global_score(grid_gdf, pois_by_criterion, poi_config):
    preference_distances = []
    preference_weights = []
    constraint_layers = []

    for criterion_name, pois_gdf in pois_by_criterion.items():
        config = poi_config[criterion_name]

        distances = distance_to_nearest_poi(grid_gdf, pois_gdf)

        if config["type"] == "osm":
            preference_distances.append(distances)
            preference_weights.append(config["weight"])

        elif config["type"] == "address":
            max_distance = (
                config["max_time_min"]
                * config["bike_speed_m_per_min"]
            )

            layer = constraint_layer(
                grid_gdf,
                pois_gdf,
                max_distance=max_distance,
                falloff_scale=config["scale"]
            )

            constraint_layers.append(layer)

    preference_score = combine_preference_distances(
        preference_distances,
        preference_weights,
        scale=1500
    )

    constraint_score = combine_constraint_layers(
        constraint_layers
    )

    if preference_score is None:
        preference_score = np.ones(len(grid_gdf))

    if constraint_score is None:
        constraint_score = np.ones(len(grid_gdf))

    return preference_score * constraint_score
