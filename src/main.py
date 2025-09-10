from visualizer import run_visualizer
from utils import load_data

def main():
    # load_data returns (cities, name_to_latlon)
    cities, name_to_latlon = load_data("data/data.json")
    print("Data loaded successfully!")
    print("Cities available:", [c["name"] for c in cities])

if __name__ == "__main__":
    print("🚀 Launching AI Travel Assistant - Administrative Visualizer")
    run_visualizer()
    main()
