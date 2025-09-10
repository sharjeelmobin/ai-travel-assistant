# src/utils.py
import json
import os

def get_project_root():
    """Absolute path to project root (one level above src)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_data(rel_path="data/data.json"):
    """
    Load data.json (keeps your filename).
    Returns (cities_list, name_to_latlon_dict).
    """
    project_root = get_project_root()
    path = os.path.join(project_root, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cities = data.get("cities", [])
    name_to_latlon = {c["name"]: (c["lat"], c["lon"]) for c in cities}
    return cities, name_to_latlon
