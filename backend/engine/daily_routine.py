import random
from backend.engine.rules import get_rules
from backend.mbti.types import TraitProfile
from backend.models.town import (
    Location, LOCATIONS, HOME_ASSIGNMENTS, bfs_path,
    TOWN_MAP, GRASS, SIDEWALK, ROAD_H, ROAD_V, random_nearby_tile,
)


class DailyRoutine:
    def __init__(self, agent_id: str, traits: TraitProfile, rules=None):
        self.agent_id = agent_id
        self.traits = traits
        self.rules = rules or get_rules()
        self.home_id = HOME_ASSIGNMENTS.get(agent_id, "home_nw")
        self.home = LOCATIONS[self.home_id]
        self.schedule = self._build_schedule()
        self.step_index: int = 0
        self.ticks_at_current: int = 0
        # Movement
        self.path: list[tuple[int, int]] = []
        self.path_progress: int = 0
        self.current_tile: tuple[int, int] = (self.home.tile_x, self.home.tile_y)
        self.target_location: Location = self.home

    def _build_schedule(self) -> list[tuple[str, int]]:
        """Build a daily schedule from the user-editable routine rules.

        The JSON uses the literal ``home`` placeholder, which resolves to the
        agent's own house. Unknown locations are ignored so a typo in the rules
        cannot strand an agent outside the town.
        """
        is_extravert = self.traits.extraversion > 0.5
        is_thinking = self.traits.thinking > 0.5
        is_judging = self.traits.judging > 0.5
        key = "extravert" if is_extravert else "thinking" if is_thinking else "default"
        raw = self.rules.get(f"routines.{key}", []) or []
        schedule: list[tuple[str, int]] = []
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            loc_id, ticks = item
            if loc_id == "home":
                loc_id = self.home_id
            if loc_id not in LOCATIONS:
                continue
            try:
                duration = max(1, int(ticks))
            except (TypeError, ValueError):
                continue
            schedule.append((str(loc_id), duration))
        if not schedule:
            # Defensive fallback if a user empties every schedule.
            schedule = [(self.home_id, 3), ("cafe", 3), ("square", 3), (self.home_id, 2)]
        # Perceiving types wander more (shorter stays).
        if not is_judging:
            delta = int(self.rules.get("routines.perceiving_duration_delta", -1))
            schedule = [(loc, max(1, t + delta)) for loc, t in schedule]
        return schedule

    def current_location_id(self) -> str:
        if self.step_index < len(self.schedule):
            return self.schedule[self.step_index][0]
        return self.home_id

    def is_moving(self) -> bool:
        return len(self.path) > 0 and self.path_progress < len(self.path)

    def tick(self, tick: int):
        """Advance routine by one simulation tick. Returns (location_changed, new_location_id)."""
        self.ticks_at_current += 1
        loc_id = self.current_location_id()
        target_loc = LOCATIONS.get(loc_id, self.home)

        # If at destination, stay for scheduled duration
        if not self.is_moving():
            if self.step_index < len(self.schedule):
                _, duration = self.schedule[self.step_index]
                if self.ticks_at_current >= duration:
                    self.step_index = (self.step_index + 1) % len(self.schedule)
                    self.ticks_at_current = 0
                    new_loc_id = self.current_location_id()
                    new_target = LOCATIONS.get(new_loc_id, self.home)
                    self.target_location = new_target
                    self._start_moving(new_target)
                    return True, new_loc_id
            return False, loc_id

        # Continue moving along path
        self.path_progress += 1
        if self.path_progress < len(self.path):
            self.current_tile = self.path[self.path_progress]
        else:
            self.path = []
            self.path_progress = 0
        return False, loc_id

    def _start_moving(self, target: Location):
        start = self.current_tile
        end = (target.tile_x, target.tile_y)
        self.path = bfs_path(start, end)
        self.path_progress = 0
        # If we found a path, move one step
        if self.path:
            self.current_tile = self.path[0]
        else:
            self.current_tile = end
        self.target_location = target

    def wander(self):
        """Perceiving types occasionally wander to nearby tiles."""
        if self.traits.judging > 0.5:
            return
        chance = float(self.rules.get("routines.wander_chance", 0.10))
        if random.random() < chance:
            self.current_tile = random_nearby_tile(self.current_tile[0], self.current_tile[1], 2)
