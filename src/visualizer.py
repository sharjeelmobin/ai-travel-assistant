import os
import sys
import json
import threading
import tempfile
import webbrowser
import requests
import folium
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

# ---------------------------
# Resource helper (works in source and in PyInstaller bundle)
# ---------------------------
def resource_path(relative_path: str) -> str:
    """
    Return absolute path to resource, working in dev and in PyInstaller-built exe.
    Example relative_path: "data/data.json"
    """
    if getattr(sys, "_MEIPASS", None):
        base = sys._MEIPASS
    else:
        # project root assumed one level above this file (adjust if your layout differs)
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, relative_path)

# Use resource_path to locate the JSON file (works in exe when using --add-data "data;data")
DATA_PATH = resource_path("data/data.json")

# ---------------------------
# Helpers
# ---------------------------

def get_route_from_osrm(start_coords, end_coords, timeout=25):
    """
    start_coords and end_coords are (lat, lon)
    Returns: (list_of_[lon,lat], distance_km, duration_hr)
    """
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
        f"?overview=full&geometries=geojson&steps=false"
    )
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not data.get("routes"):
        return None, None, None
    route = data["routes"][0]["geometry"]["coordinates"]
    dist_km = data["routes"][0]["distance"] / 1000.0
    dur_hr = data["routes"][0]["duration"] / 3600.0
    return route, dist_km, dur_hr

def save_map_html(m, title="map"):
    """
    Save folium Map to a temporary, writeable directory and return file path.
    Uses the system temp directory so PyInstaller users can write here.
    """
    tmpdir = os.path.join(tempfile.gettempdir(), "ai_travel_maps")
    os.makedirs(tmpdir, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=title + "_", suffix=".html", dir=tmpdir)
    os.close(fd)
    m.save(path)
    return path

def fetch_pois_along_route(route_coords, tags=("fuel", "hotel"), radius=5000):
    """
    Fetch POIs along the route using Overpass API.
    tags: tuple containing "fuel" and/or "hotel"
    radius: meters around each sampled point to query
    Returns list of Overpass 'elements' (nodes) or [] on error.
    """
    # using a reliable Overpass endpoint (kumi); you can change if needed
    overpass_url = "https://overpass.kumi.systems/api/interpreter"

    query_parts = []
    # sample the route to avoid excessively large queries
    sample_step = max(1, len(route_coords)//30)
    for (lon, lat) in route_coords[::sample_step]:
        for tag in tags:
            if tag == "hotel":
                query_parts.append(f'node(around:{radius},{lat},{lon})[tourism=hotel];')
            else:
                query_parts.append(f'node(around:{radius},{lat},{lon})[amenity={tag}];')

    query = f"""
    [out:json][timeout:25];
    (
      {"".join(query_parts)}
    );
    out center;
    """

    try:
        r = requests.post(overpass_url, data={"data": query}, timeout=30)
        r.raise_for_status()
        return r.json().get("elements", [])
    except Exception as e:
        print("Overpass API error:", e)
        return []

# ---------------------------
# UI
# ---------------------------

def run_visualizer():
    # Load data.json (safe path)
    if not os.path.exists(DATA_PATH):
        messagebox.showerror("Missing data", f"Cannot find data.json at:\n{DATA_PATH}")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # build mapping name -> (lat, lon)
    name_to_latlon = {c["name"]: (c["lat"], c["lon"]) for c in data.get("cities", [])}
    city_names = sorted(name_to_latlon.keys())

    root = tk.Tk()
    root.title("AI Travel Assistant — Pakistan Routes")
    root.geometry("400x700")
    root.resizable(False, False)

    # LEFT PANEL ONLY
    left = tk.Frame(root, width=400, bg="#0f172a")
    left.pack(side="left", fill="both", expand=True)
    left.pack_propagate(False)

    tk.Label(left, text="AI Travel Assistant", bg="#0f172a", fg="white",
             font=("Segoe UI", 16, "bold")).pack(pady=(16, 10))

    form = tk.Frame(left, bg="#0f172a")
    form.pack(fill="x", padx=12)

    tk.Label(form, text="Start City", bg="#0f172a", fg="#cbd5e1").pack(anchor="w")
    cb_start = ttk.Combobox(form, values=city_names)  # allow typing (searchable)
    cb_start.pack(fill="x", pady=(2, 10))

    tk.Label(form, text="Destination City", bg="#0f172a", fg="#cbd5e1").pack(anchor="w")
    cb_end = ttk.Combobox(form, values=city_names)
    cb_end.pack(fill="x", pady=(2, 12))

    # Make comboboxes searchable (prefix match, case-insensitive)
    def make_searchable_combobox(cb, values):
        """
        Filters combobox values while user types; opens dropdown automatically.
        Only prefix matches (as requested). Non case-sensitive.
        """
        def on_keyrelease(event):
            typed = cb.get().strip().lower()
            if typed == "":
                filtered = values
            else:
                filtered = [item for item in values if item.lower().startswith(typed)]
            # update dropdown list
            cb["values"] = filtered
            if filtered:
                # show dropdown (works reliably on Windows/Tk)
                try:
                    cb.event_generate("<Down>")
                except Exception:
                    pass
        cb.bind("<KeyRelease>", on_keyrelease)

    make_searchable_combobox(cb_start, city_names)
    make_searchable_combobox(cb_end, city_names)

    # Checkboxes
    chk_fuel = tk.IntVar(value=1)
    chk_hotel = tk.IntVar(value=1)
    tk.Checkbutton(form, text="Include Petrol Stations", variable=chk_fuel,
                   bg="#0f172a", fg="white", selectcolor="#0f172a").pack(anchor="w", pady=2)
    tk.Checkbutton(form, text="Include Hotels", variable=chk_hotel,
                   bg="#0f172a", fg="white", selectcolor="#0f172a").pack(anchor="w", pady=2)

    find_btn = tk.Button(form, text="Find Route", bg="#2563eb", fg="white",
                         relief="flat", font=("Segoe UI", 11, "bold"))
    find_btn.pack(fill="x", pady=(10, 12))

    info_chip = tk.Label(left, text="", bg="#0f172a", fg="#e2e8f0",
                         font=("Segoe UI", 10))
    info_chip.pack(padx=12, pady=(6, 6), anchor="w")

    # Separate POI lists
    tk.Label(left, text="Petrol Stations", bg="#0f172a", fg="#38bdf8",
             font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
    fuel_box = ScrolledText(left, height=8, bg="#0b1220", fg="#e2e8f0",
                            insertbackground="white", relief="flat", wrap="word")
    fuel_box.pack(fill="x", padx=12, pady=(0, 10))

    tk.Label(left, text="Hotels", bg="#0f172a", fg="#f472b6",
             font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
    hotel_box = ScrolledText(left, height=8, bg="#0b1220", fg="#e2e8f0",
                             insertbackground="white", relief="flat", wrap="word")
    hotel_box.pack(fill="x", padx=12, pady=(0, 10))

    def set_status(text):
        info_chip.config(text=text)
        info_chip.update_idletasks()

    def render_map(route_lonlat, start, end, start_ll, end_ll, dist_km, dur_hr, pois):
        """
        Build and save folium map: returns local path to HTML file.
        route_lonlat is list of [lon, lat] pairs (OSRM output).
        """
        # Convert to lists for bounds (lat, lon)
        lats = [lat for (_, lat) in route_lonlat]
        lons = [lon for (lon, _) in route_lonlat]
        bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
        center = [(min(lats)+max(lats))/2.0, (min(lons)+max(lons))/2.0]

        m = folium.Map(location=center, zoom_start=6, tiles="OpenStreetMap", control_scale=True)

        # add route
        folium.PolyLine([(lat, lon) for (lon, lat) in route_lonlat],
                        color="red", weight=5, opacity=0.9).add_to(m)

        # start & end markers (lat, lon)
        folium.Marker(location=start_ll, popup=f"Start: {start}",
                      tooltip="Start", icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(location=end_ll, popup=f"End: {end}",
                      tooltip="End", icon=folium.Icon(color="orange", icon="flag")).add_to(m)

        # add POIs (optional; you had requested lists shown on left so this is non-invasive)
        for poi in pois:
            try:
                lat, lon = poi["lat"], poi["lon"]
                name = poi.get("tags", {}).get("name", "Unnamed")
                amenity = poi.get("tags", {}).get("amenity") or poi.get("tags", {}).get("tourism", "poi")
                color = "blue" if amenity == "fuel" else "purple"
                folium.Marker(
                    location=(lat, lon),
                    popup=f"{amenity.title()}: {name}",
                    tooltip=name,
                    icon=folium.Icon(color=color, icon="info-sign")
                ).add_to(m)
            except Exception:
                # keep map rendering even if some POI is malformed
                continue

        m.fit_bounds(bounds)
        return save_map_html(m, "route_map")

    def do_search():
        start = cb_start.get().strip()
        end = cb_end.get().strip()
        if not start or not end:
            messagebox.showwarning("Missing selection", "Select both start and destination cities.")
            return
        if start == end:
            messagebox.showinfo("Same city", "Start and destination are the same.")
            return
        if start not in name_to_latlon or end not in name_to_latlon:
            messagebox.showerror("Unknown city", "One of the selected cities is not in the dataset.")
            return

        # disable button to prevent double clicks
        find_btn.config(state="disabled")
        set_status("Starting...")

        def worker():
            try:
                set_status("Fetching route…")
                start_ll = name_to_latlon[start]  # (lat, lon)
                end_ll = name_to_latlon[end]
                route_lonlat, dist_km, dur_hr = get_route_from_osrm(start_ll, end_ll)
                if not route_lonlat:
                    raise RuntimeError("No route found from OSRM.")

                # Determine requested POI types
                tags = []
                if chk_fuel.get():
                    tags.append("fuel")
                if chk_hotel.get():
                    tags.append("hotel")

                pois = []
                if tags:
                    set_status("Fetching nearby POIs…")
                    pois = fetch_pois_along_route(route_lonlat, tags=tuple(tags))

                # Update POI lists on main thread
                def update_poi_boxes():
                    fuel_box.delete(1.0, tk.END)
                    hotel_box.delete(1.0, tk.END)
                    fuel_list = []
                    hotel_list = []
                    for poi in pois:
                        name = poi.get("tags", {}).get("name", "Unnamed")
                        amenity = poi.get("tags", {}).get("amenity") or poi.get("tags", {}).get("tourism", "poi")
                        if amenity == "fuel":
                            fuel_list.append(name)
                        elif amenity == "hotel":
                            hotel_list.append(name)
                    fuel_box.insert(tk.END, "\n".join(fuel_list) if fuel_list else "No Petrol Stations found.")
                    hotel_box.insert(tk.END, "\n".join(hotel_list) if hotel_list else "No Hotels found.")

                root.after(0, update_poi_boxes)

                set_status("Rendering map…")
                html_path = render_map(route_lonlat, start, end, start_ll, end_ll, dist_km, dur_hr, pois)

                # finish UI updates on main thread
                def finish():
                    set_status(f"{start} → {end} · {dist_km:.1f} km, {dur_hr:.1f} hrs")
                    # open the saved map in browser (use a proper file URI)
                    try:
                        uri = Path(html_path).as_uri()
                        webbrowser.open_new_tab(uri)
                    except Exception:
                        # fallback: try the simple file URL
                        webbrowser.open_new_tab(f"file:///{html_path}")
                    find_btn.config(state="normal")

                root.after(0, finish)

            except Exception as e:
                # show error on main thread and re-enable button
                def show_err():
                    messagebox.showerror("Error", f"{e}")
                    set_status("")
                    find_btn.config(state="normal")
                root.after(0, show_err)

        threading.Thread(target=worker, daemon=True).start()

    find_btn.config(command=do_search)
    root.mainloop()


if __name__ == "__main__":
    run_visualizer()
