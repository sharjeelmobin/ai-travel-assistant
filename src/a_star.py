import heapq
import math


def heuristic(coord1, coord2):
    """Euclidean distance heuristic using lat/lon"""
    return math.sqrt((coord1[0] - coord2[0])**2 + (coord1[1] - coord2[1])**2)


def a_star_search(graph, cities, start, goal):
    """
    Perform A* search on the given graph.
    graph: dict {node: [(neighbor, cost), ...]}
    cities: dict {city_name: (lat, lon)} for heuristic
    start: starting node (city name)
    goal: goal node (city name)
    """

    frontier = []
    heapq.heappush(frontier, (0, start))  # (priority, node)
    came_from = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)

        if current == goal:
            break

        for neighbor, cost in graph.get(current, []):
            new_cost = cost_so_far[current] + cost
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                # ✅ Proper heuristic using city coordinates
                h = heuristic(cities[neighbor], cities[goal])
                priority = new_cost + h
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

    # Reconstruct path
    path = []
    current = goal
    while current is not None:
        path.append(current)
        current = came_from.get(current)
    path.reverse()

    return path, cost_so_far.get(goal, float("inf"))
