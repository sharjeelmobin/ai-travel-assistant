# src/osrm_client.py
import requests
import os
import json
import time

OSRM_BASE = "https://router.project-osrm.org"  # public demo server
CACHE_FILE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "data", "osrm_cache.json")

def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass

def get_osrm_route(start_lat, start_lon, end_lat, end_lon, profile="driving"):
    """
    Query OSRM public server for route between start and end.
    Returns: (distance_km: float, coords: list of [lon, lat]).
    Uses simple disk cache to reduce repeated calls.
    """
    key = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    cache = _load_cache()
    if key in cache:
        entry = cache[key]
        return entry["distance_km"], entry["coords"]

    url = (
        f"{OSRM_BASE}/route/v1/{profile}/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        "?overview=full&geometries=geojson"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(data.get("message", "No route found"))

    route = data["routes"][0]
    distance_km = route["distance"] / 1000.0
    coords = route["geometry"]["coordinates"]  # [[lon, lat], ...]
    cache[key] = {"distance_km": distance_km, "coords": coords, "ts": time.time()}
    _save_cache(cache)
    return distance_km, coords
