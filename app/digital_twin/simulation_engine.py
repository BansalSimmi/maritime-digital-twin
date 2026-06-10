"""
digital_twin/simulation_engine.py
==================================
Pure physics engine — zero database dependencies.

    predict_position()  — Haversine: position after N minutes
    predict_route()     — incremental waypoint trail
    build_full_row()    — VesselState → FullTwinRow (sole INSERT entry point)
"""

import math
import json
import random
from datetime import datetime, timezone

from .config import (
    EARTH_RADIUS_KM,
    DEFAULT_SPEED_KNOTS,
    DEFAULT_HEADING_DEG,
    SIMULATION_MINUTES,
    SIMULATION_STEP_MIN,
)
from .schemas import VesselState, FullTwinRow


def predict_position(
    lat: float, lon: float,
    speed_knots: float, heading_deg: float,
    minutes: float
) -> tuple[float, float]:
    """
    Haversine formula — predict position after `minutes`.

    More accurate than flat-earth (delta/111):
      Flat-earth error: ~2% at 60°N, breaks near poles.
      Haversine error:  < 0.3% anywhere on Earth.
    """
    if lat is None or lon is None:
        return lat, lon

    speed_kmh   = speed_knots * 1.852
    distance_km = speed_kmh * (minutes / 60.0)
    bearing     = math.radians(heading_deg)
    lat1        = math.radians(lat)
    lon1        = math.radians(lon)
    ang_dist    = distance_km / EARTH_RADIUS_KM

    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang_dist)
        + math.cos(lat1) * math.sin(ang_dist) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(ang_dist) * math.cos(lat1),
        math.cos(ang_dist) - math.sin(lat1) * math.sin(lat2)
    )
    return math.degrees(lat2), math.degrees(lon2)


def predict_route(
    lat: float, lon: float,
    speed_knots: float, heading_deg: float,
    minutes: int = SIMULATION_MINUTES,
    step: int = SIMULATION_STEP_MIN
) -> list[dict]:
    """
    Incremental waypoint trail.
    Each step advances from the previous position (not from origin).
    Speed varies ±10% per step to simulate real sea conditions.
    """
    route     = []
    cur_lat   = lat
    cur_lon   = lon
    cur_speed = speed_knots

    for t in range(step, minutes + 1, step):
        variation = cur_speed * 0.1 * (0.5 - random.random())
        cur_speed = max(0.0, cur_speed + variation)
        cur_lat, cur_lon = predict_position(
            cur_lat, cur_lon, cur_speed, heading_deg, step
        )
        route.append({
            "minute": t,
            "lat":    round(cur_lat,  6),
            "lon":    round(cur_lon,  6),
            "speed":  round(cur_speed, 2)
        })
    return route


def build_full_row(
    vessel: VesselState,
    scenario: str,
    minutes: int = SIMULATION_MINUTES,
    step: int = SIMULATION_STEP_MIN
) -> FullTwinRow:
    """
    Run simulation for one vessel → FullTwinRow ready for INSERT.

    simulation_time = NOW() — this row becomes the "latest" for the vessel
    in ORDER BY simulation_time DESC queries.
    """
    speed   = vessel.speed   if vessel.speed   > 0  else DEFAULT_SPEED_KNOTS
    heading = vessel.heading if vessel.heading >= 0  else DEFAULT_HEADING_DEG

    new_lat, new_lon = predict_position(
        vessel.lat, vessel.lon, speed, heading, minutes
    )
    route     = predict_route(vessel.lat, vessel.lon, speed, heading, minutes, step)
    sim_speed = route[-1]["speed"] if route else speed

    return FullTwinRow(
        mmsi                = vessel.mmsi,
        latitude            = vessel.lat,
        longitude           = vessel.lon,
        speed               = vessel.speed,
        heading             = vessel.heading,
        last_update         = vessel.last_update or datetime.now(timezone.utc),
        simulated_latitude  = round(new_lat,  6),
        simulated_longitude = round(new_lon,  6),
        simulated_speed     = round(sim_speed, 2),
        predicted_route     = json.dumps(route),
        simulation_scenario = scenario,
        simulation_time     = datetime.now(timezone.utc)   # ORDER BY key
    )