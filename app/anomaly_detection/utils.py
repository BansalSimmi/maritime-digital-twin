# app/anomaly_detection/utils.py

import math
from datetime import datetime, timezone
from typing import Optional

from app.anomaly_detection.constants import (
    COURSE_DEVIATION_DEGREES, SPEED_VIOLATION_FACTOR,
    ANOMALY_SEVERITY, Severity,
)


def angular_diff(a: float, b: float) -> float:
    """Smallest angle between two compass bearings. Returns 0–180."""
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def is_speed_violation(sog: float, design_speed: float) -> bool:
    if design_speed <= 0:
        return False
    return sog > (design_speed * SPEED_VIOLATION_FACTOR)


def is_course_deviation(current_cog: float, baseline_cog: float) -> bool:
    return angular_diff(current_cog, baseline_cog) > COURSE_DEVIATION_DEGREES


def severity_score(severity: str) -> int:
    return {Severity.LOW: 1, Severity.MEDIUM: 2,
            Severity.HIGH: 3, Severity.CRITICAL: 4}.get(severity, 0)


def build_anomaly_record(
    mmsi: int,
    vessel_name: Optional[str],
    anomaly_type: str,
    severity: str,
    description: str,
    latitude: Optional[float],
    longitude: Optional[float],
    sog: Optional[float] = None,
    extra: Optional[dict] = None,
    detected_at: Optional[datetime] = None,
) -> dict:
    return {
        "mmsi":         mmsi,
        "vessel_name":  vessel_name or str(mmsi),
        "anomaly_type": anomaly_type,
        "severity":     severity,
        "description":  description,
        "latitude":     latitude,
        "longitude":    longitude,
        "sog":          sog,
        "extra":        extra or {},
        "detected_at":  (detected_at or datetime.now(timezone.utc)).isoformat(),
    }