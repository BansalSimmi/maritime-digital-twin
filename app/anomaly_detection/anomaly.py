# app/anomaly_detection/anomaly.py

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.anomaly_detection import service as svc
from app.anomaly_detection.constants import (
    DETECTION_WINDOW_HOURS, FLEET_DEFAULT_LIMIT, FLEET_MAX_LIMIT, AnomalyType,
)

logger = logging.getLogger("anomaly_detection.routes")
router = APIRouter()

_ALL_TYPES = ", ".join([
    AnomalyType.SPEED_VIOLATION, AnomalyType.EMISSION_SPIKE,
    AnomalyType.AIS_SIGNAL_GAP,  AnomalyType.GEOFENCE_BREACH,
    AnomalyType.DARK_SHIP,       AnomalyType.COURSE_DEVIATION,
    AnomalyType.DRAUGHT_CHANGE,  AnomalyType.SUDDEN_SPEED_DROP,
])


@router.post("/detect", summary="Run anomaly detection — saves and returns results")
def run_detection(
    db:           Session       = Depends(get_db),
    window_hours: int           = Query(
        DETECTION_WINDOW_HOURS, ge=1, le=8760,   # up to 1 year
        description="Hours of AIS data to scan. Default 744 = 31 days. Max 8760 = 1 year."
    ),
    types:        Optional[str] = Query(
        None,
        description=f"Comma-separated types to run. Default = all. Options: {_ALL_TYPES}"
    ),
    persist:      bool          = Query(True, description="Save to anomaly_events table"),
):
    type_list = [t.strip() for t in types.split(",")] if types else None
    return svc.run_detection(db=db, window_hours=window_hours, types=type_list, persist=persist)


@router.get("/fleet", summary="All saved anomalies")
def fleet_anomalies(
    db:           Session       = Depends(get_db),
    severity:     Optional[str] = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW"),
    anomaly_type: Optional[str] = Query(None, description=f"One of: {_ALL_TYPES}"),
    resolved:     bool          = Query(False),
    limit:        int           = Query(FLEET_DEFAULT_LIMIT, ge=1, le=FLEET_MAX_LIMIT),
    offset:       int           = Query(0, ge=0),
):
    return svc.get_fleet_anomalies(
        db=db, severity=severity, anomaly_type=anomaly_type,
        resolved=resolved, limit=limit, offset=offset,
    )


@router.get("/summary", summary="KPI counts by severity and type")
def summary(db: Session = Depends(get_db)):
    return svc.get_summary(db)


@router.get("/map/overlay", summary="Anomaly markers with lat/lon for map rendering")
def map_overlay(db: Session = Depends(get_db)):
    return svc.get_map_overlay(db)


@router.get("/debug")
def debug(db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM ais_data) AS ais_count,
            (SELECT COUNT(*) FROM emissions) AS emissions_count,
            (SELECT MAX(base_date_time) FROM ais_data) AS last_time
    """)).mappings().first()

    return dict(result)

@router.get("/{mmsi}", summary="All anomalies for a single vessel")
def vessel_anomalies(mmsi: int, db: Session = Depends(get_db)):
    return svc.get_vessel_anomalies(db=db, mmsi=mmsi)


@router.put("/{anomaly_id}/resolve", summary="Mark anomaly as resolved")
def resolve_anomaly(anomaly_id: str, db: Session = Depends(get_db)):
    ok = svc.resolve_anomaly(db=db, anomaly_id=anomaly_id)
    if not ok:
        raise HTTPException(404, f"Anomaly {anomaly_id} not found or already resolved")
    return {"status": "resolved", "anomaly_id": anomaly_id}


@router.delete("/{anomaly_id}", summary="Delete a single anomaly record")
def delete_anomaly(anomaly_id: str, db: Session = Depends(get_db)):
    ok = svc.delete_anomaly(db=db, anomaly_id=anomaly_id)
    if not ok:
        raise HTTPException(404, f"Anomaly {anomaly_id} not found")
    return {"status": "deleted", "anomaly_id": anomaly_id}
