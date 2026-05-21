import random
from dataclasses import dataclass, field
from collections import deque

# Tile types
GRASS = 0
ROAD_H = 1
ROAD_V = 2
BUILDING = 3
TREE = 4
WATER = 5
SIDEWALK = 6

TILE_NAMES = {
    GRASS: "grass", ROAD_H: "road_h", ROAD_V: "road_v",
    BUILDING: "building", TREE: "tree", WATER: "water", SIDEWALK: "sidewalk",
}

# 20x14 town map (0=grass, 1=road_h, 2=road_v, 3=building, 4=tree, 5=water, 6=sidewalk)
TOWN_MAP: list[list[int]] = [
    [4,4,4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4,4,4],
    [4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4],
    [0,0,3,3,3,0,0,0,3,3,3,0,0,0,3,3,3,0,0,0],
    [0,0,3,3,3,0,0,0,3,3,3,0,0,0,3,3,3,0,0,0],
    [6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,3,3,0,0,0,0,3,3,3,0,0,0,0,3,3,0,0,0],
    [0,0,3,3,0,0,0,0,3,3,3,0,0,0,0,3,3,0,0,0],
    [6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6],
    [0,0,0,4,0,0,0,0,0,5,5,0,0,0,0,4,0,0,0,0],
    [0,0,0,4,0,0,0,0,0,5,5,0,0,0,0,4,0,0,0,0],
    [6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6],
    [0,0,0,0,0,0,0,0,3,3,3,0,0,0,0,0,0,0,0,0],
    [0,4,4,0,0,4,0,0,3,3,3,0,0,4,0,0,4,4,0,0],
]


@dataclass
class Location:
    id: str
    name: str
    tile_x: int  # center tile x on map
    tile_y: int  # center tile y on map
    width: int = 3
    height: int = 3
    color: str = "#888"
    icon: str = "?"

    def contains(self, tx: int, ty: int) -> bool:
        hw = self.width // 2
        hh = self.height // 2
        return abs(tx - self.tile_x) <= hw and abs(ty - self.tile_y) <= hh

    @property
    def pixel_x(self) -> int:
        return self.tile_x * 32

    @property
    def pixel_y(self) -> int:
        return self.tile_y * 32


LOCATIONS: dict[str, Location] = {
    "home_ne": Location("home_ne", "Blue Roof House", 2, 2, 3, 2, "#6B8EB5", "🏠"),
    "home_nw": Location("home_nw", "Red Roof House", 9, 2, 3, 2, "#C47A6B", "🏠"),
    "home_se": Location("home_se", "Green Roof House", 14, 2, 3, 2, "#6BB57A", "🏠"),
    "home_sw": Location("home_sw", "Yellow Roof House", 2, 6, 3, 2, "#D4B86B", "🏠"),
    "cafe": Location("cafe", "Morning Brew Cafe", 9, 6, 3, 2, "#C4906B", "☕"),
    "market": Location("market", "Trading Floor", 2, 9, 1, 2, "#8B8BA0", "📊"),
    "library": Location("library", "Data Library", 15, 6, 3, 2, "#8BA0B5", "📚"),
    "square": Location("square", "Town Square", 9, 12, 3, 3, "#A0A090", "🌳"),
    "park": Location("park", "Willow Park", 9, 9, 2, 2, "#6BA06B", "🌿"),
    # Observer locations
    "observatory": Location("observatory", "Observatory", 17, 10, 2, 2, "#3A3A5A", "🔭"),
    "math_tower":  Location("math_tower", "Math Tower", 18, 2, 2, 2, "#4A4A6A", "📐"),
    "fortune_tent": Location("fortune_tent", "Fortune Tent", 1, 11, 2, 2, "#6A3A6A", "🔮"),
}

OBSERVER_HOMES: dict[str, str] = {
    "physicist": "observatory",
    "mathematician": "math_tower",
    "mystic": "fortune_tent",
}

HOME_ASSIGNMENTS: dict[str, str] = {
    "INTJ": "home_ne", "INTP": "home_ne", "ENTJ": "home_ne", "ENTP": "home_ne",
    "INFJ": "home_nw", "INFP": "home_nw", "ENFJ": "home_nw", "ENFP": "home_nw",
    "ISTJ": "home_se", "ISFJ": "home_se", "ESTJ": "home_se", "ESFJ": "home_se",
    "ISTP": "home_sw", "ISFP": "home_sw", "ESTP": "home_sw", "ESFP": "home_sw",
}


def bfs_path(start: tuple[int, int], end: tuple[int, int], max_steps: int = 40) -> list[tuple[int, int]]:
    """Simple BFS pathfinding on the town grid. Avoids WATER and BUILDING tiles."""
    if start == end:
        return [start]

    rows, cols = len(TOWN_MAP), len(TOWN_MAP[0])
    queue = deque([[start]])
    visited = {start}

    while queue:
        path = queue.popleft()
        if len(path) > max_steps:
            continue
        x, y = path[-1]
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in visited:
                tile = TOWN_MAP[ny][nx]
                if tile in (WATER, BUILDING):
                    visited.add((nx, ny))
                    continue
                new_path = path + [(nx, ny)]
                if (nx, ny) == end:
                    return new_path
                visited.add((nx, ny))
                queue.append(new_path)

    # If no path found, return direct interpolated path
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    if steps <= 1:
        return [start, end]
    path = []
    for i in range(steps + 1):
        t = i / steps
        px = round(start[0] + (end[0] - start[0]) * t)
        py = round(start[1] + (end[1] - start[1]) * t)
        path.append((px, py))
    return path


def get_adjacent_agents(
    agent_pos: tuple[int, int], agent_locations: dict[str, tuple[int, int]], self_id: str, radius: int = 3
) -> list[str]:
    """Find agents within conversation radius."""
    nearby: list[str] = []
    ax, ay = agent_pos
    for aid, (bx, by) in agent_locations.items():
        if aid == self_id:
            continue
        if abs(ax - bx) <= radius and abs(ay - by) <= radius:
            nearby.append(aid)
    return nearby


def random_nearby_tile(cx: int, cy: int, spread: int = 2) -> tuple[int, int]:
    """Get a random walkable tile near a given position."""
    cols, rows = len(TOWN_MAP[0]), len(TOWN_MAP)
    for _ in range(20):
        tx = cx + random.randint(-spread, spread)
        ty = cy + random.randint(-spread, spread)
        if 0 <= tx < cols and 0 <= ty < rows:
            tile = TOWN_MAP[ty][tx]
            if tile not in (WATER, BUILDING):
                return (tx, ty)
    return (cx, cy)
