# carbon/routes.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import get_db
from app.carbon.service import (
    calculate_emissions_service,
    predict_emissions_service,
    get_vessel_emissions_service,
    get_top_polluters_service,
    high_emission_alerts_service,
    fleet_summary_service,
    create_zone_service,
    get_zones_service,
    get_emissions_by_zone,
    predict_zone_emissions_service,
)

router = APIRouter(prefix="/carbon", tags=["Carbon Emissions"])


# ── Vessel profiles ───────────────────────────────────────────────────────────

@router.get("/vessel_profiles",
            summary="List all AIS vessel type code profiles")
def list_vessel_profiles(db: Session = Depends(get_db)):
    """
    Returns all rows from vessel_profiles.
    vessel_type_code values match exactly what is stored in ais_data.vessel_type.
    """
    rows = db.execute(
        text("""
            SELECT vessel_type_code, vessel_category, design_speed, mcr_kw, sfc,
                   co2_factor, nox_factor, sox_factor
            FROM vessel_profiles
            ORDER BY
                CASE WHEN vessel_type_code = 'default' THEN 9999
                     WHEN vessel_type_code = '0'       THEN 0
                     ELSE CAST(SPLIT_PART(vessel_type_code, '.', 1) AS INTEGER)
                END
        """)
    ).fetchall()
    return {"total": len(rows), "profiles": [dict(r._mapping) for r in rows]}


# ── Calculate ─────────────────────────────────────────────────────────────────

@router.post("/calculate",
             summary="Calculate emissions for ALL vessels")
def calculate_all(db: Session = Depends(get_db)):
    return calculate_emissions_service(db)


@router.post("/calculate/{mmsi}",
             summary="Calculate emissions for one vessel")
def calculate_for_vessel(mmsi: int, db: Session = Depends(get_db)):
    return calculate_emissions_service(db, mmsi=mmsi)


# ── Predict ───────────────────────────────────────────────────────────────────

@router.post("/predict",
             summary="Predict future emissions for ALL vessels")
def predict_all(db: Session = Depends(get_db)):
    return predict_emissions_service(db)


@router.post("/predict/{mmsi}",
             summary="Predict future emissions for one vessel")
def predict_for_vessel(mmsi: int, db: Session = Depends(get_db)):
    return predict_emissions_service(db, mmsi=mmsi)


# ── Vessel history ────────────────────────────────────────────────────────────

@router.get("/vessel/{mmsi}",
            summary="Full emission history for a vessel")
def get_vessel_emissions(mmsi: int, db: Session = Depends(get_db)):
    return get_vessel_emissions_service(db, mmsi)


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/top_polluters",
            summary="Rank vessels by cumulative CO2")
def top_polluters(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return get_top_polluters_service(db, limit=limit)


@router.get("/high_emission_alerts",
            summary="Vessels exceeding CO2 threshold")
def high_emission_alerts(
    threshold: float = Query(default=2000.0, description="CO2 threshold kg/h"),
    db: Session = Depends(get_db),
):
    return high_emission_alerts_service(db, threshold=threshold)


@router.get("/fleet_summary",
            summary="Fleet-wide emission stats with per-type breakdown")
def fleet_summary(db: Session = Depends(get_db)):
    return fleet_summary_service(db)


# ── Zone management ───────────────────────────────────────────────────────────

@router.get("/zones",
            summary="List all geofence zones")
def list_zones(db: Session = Depends(get_db)):
    return get_zones_service(db)


@router.post("/zones",
             summary="Create a new geofence zone")
def create_zone(
    zone_name:   str,
    geojson:     dict,
    description: str = None,
    db: Session = Depends(get_db),
):
    return create_zone_service(db, zone_name, geojson, description)


@router.get("/zones/{zone_name}/emissions",
            summary="Aggregate emissions inside a zone")
def emissions_by_zone(zone_name: str, db: Session = Depends(get_db)):
    return get_emissions_by_zone(db, zone_name)


@router.post("/zones/{zone_name}/predict",
             summary="Predict emissions for vessels inside a zone")
def predict_zone(zone_name: str, db: Session = Depends(get_db)):
    return predict_zone_emissions_service(db, zone_name)
