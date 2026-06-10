# app/vessel_tracking/utils.py
"""
Pure-function physics helpers for vessel tracking.
No database dependency — fully unit-testable in isolation.
"""

import math
from typing import Optional

from app.vessel_tracking.constants import (
    MIN_ENGINE_LOAD,
    CO2_FACTOR, NOX_FACTOR, SOX_FACTOR,
    ALERT_CRITICAL, ALERT_HIGH, ALERT_ELEVATED,
    DEFAULT_DESIGN_SPEED, DEFAULT_MCR_KW, DEFAULT_SFC,
)


# ── Distance ────────────────────────────────────────────────────────────────

def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance in nautical miles (Haversine formula).
    Accurate to ~0.3% for typical maritime distances.
    """
    R_NM = 3_440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return R_NM * 2 * math.asin(math.sqrt(a))


# ── Engine & Emissions ──────────────────────────────────────────────────────

def calc_engine_load(speed_kn: float, design_speed: float) -> float:
    """
    IMO cubic law engine load fraction.
    Floor at MIN_ENGINE_LOAD so anchored vessels still have hotel load.
    """
    if design_speed <= 0:
        return MIN_ENGINE_LOAD
    raw = (min(speed_kn, design_speed) / design_speed) ** 3
    return max(raw, MIN_ENGINE_LOAD)


def calc_emissions(
    speed_kn: float,
    mcr_kw: float,
    sfc: float,
    design_speed: float,
) -> dict:
    """
    Returns instantaneous emission rates at the given speed.

    Returns:
        engine_load   (fraction 0.05–1.0)
        fuel_kg_h     (kg/h fuel burn)
        co2_kg_h      (kg/h CO₂)
        nox_kg_h      (kg/h NOx)
        sox_kg_h      (kg/h SOx)
    """
    load = calc_engine_load(speed_kn, design_speed)
    fuel = load * mcr_kw * sfc
    return {
        "engine_load": round(load, 4),
        "fuel_kg_h":   round(fuel, 2),
        "co2_kg_h":    round(fuel * CO2_FACTOR, 2),
        "nox_kg_h":    round(fuel * NOX_FACTOR, 2),
        "sox_kg_h":    round(fuel * SOX_FACTOR, 2),
    }


def emission_alert_level(co2_kg_h: float) -> str:
    """Classify a CO₂ rate into a named alert level."""
    if co2_kg_h >= ALERT_CRITICAL:
        return "CRITICAL"
    if co2_kg_h >= ALERT_HIGH:
        return "HIGH"
    if co2_kg_h >= ALERT_ELEVATED:
        return "ELEVATED"
    return "NORMAL"


# ── Profile fallback ────────────────────────────────────────────────────────

def default_profile() -> dict:
    """
    Absolute fallback profile used when vessel_profiles has no matching row
    AND no 'default' row.  Should never be reached in a healthy DB.
    """
    return {
        "vessel_category": "Unknown",
        "design_speed":    DEFAULT_DESIGN_SPEED,
        "mcr_kw":          DEFAULT_MCR_KW,
        "sfc":             DEFAULT_SFC,
    }