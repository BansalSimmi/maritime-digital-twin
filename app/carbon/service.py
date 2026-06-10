
# carbon/service.py
"""
Business logic for all Carbon Emissions API endpoints.

ais_data.vessel_type stores AIS codes as text: '37.0', '30.0', '0' etc.
vessel_profiles.vessel_type_code stores the EXACT same strings.
Lookup is a direct equality JOIN — no code stripping or transformation.
No geometry columns — positions as plain latitude/longitude floats.
"""

import json    #Used for: GeoJSON handling , Example: {"type":"Polygon","coordinates":[...]}
from sqlalchemy import text #text() allows raw SQL queries inside SQLAlchemy.Example: db.execute(text("SELECT * FROM emissions"))
from sqlalchemy.orm import Session #Represents the database connection session.
from fastapi import HTTPException #Used to return API errors.

# imports functions from utils.py. --> These are your physics model functions.
from .utils import (
    full_emission_row,
    full_emission_row_typed,
    normalize_vessel_type_code,
)


# ─────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────

def _require_rows(rows, detail: str): # Ensure query returned results.
    if not rows: # If result is empty.
        raise HTTPException(status_code=404, detail=detail)  # Throw API error.
    return rows  # Otherwise return rows.

# This function gets engine specs of a vessel type
# Inputs: db → database session , raw_type_code → vessel type from AIS
def _get_vessel_profile(db: Session, raw_type_code: str) -> dict:
    """
    Fetch engine profile from vessel_profiles using exact code match.
    '37.0' → looks up '37.0',  None → looks up '0'.
    Falls back to 'default' if code not found.
    Returns full row as dict including vessel_category.
    """
    code = normalize_vessel_type_code(raw_type_code) #Ensures vessel type is valid. Example:None → "0"

    #This query retrieves engine parameters.
    row = db.execute(
        text(""" 
            SELECT vessel_category, design_speed, mcr_kw, sfc,
                   co2_factor, nox_factor, sox_factor
            FROM vessel_profiles
            WHERE vessel_type_code = :code
            LIMIT 1
        """),
        {"code": code},
    ).fetchone()

    if not row: # If vessel type not found.
        # Code not found — use default
        #Use default engine profile.
        row = db.execute(
            text("""
                SELECT vessel_category, design_speed, mcr_kw, sfc,
                       co2_factor, nox_factor, sox_factor
                FROM vessel_profiles
                WHERE vessel_type_code = 'default'
                LIMIT 1
            """)
        ).fetchone()

    return dict(row._mapping) if row else {} 
"""
Convert SQL row to dictionary.
Example output:
{
 "vessel_category":"Cargo",
 "design_speed":22,
 "mcr_kw":12000
}
"""


# ─────────────────────────────────────────────────────────────
# CALCULATE EMISSIONS
# ─────────────────────────────────────────────────────────────
# Main function that runs emission calculations.
def calculate_emissions_service(db: Session, mmsi: int = None): #Inputs: db → database , mmsi → optional vessel ID
    """
    AIS → exact vessel_type code lookup → physics model → UPSERT.
    One row per MMSI; re-runs safely update existing rows.
    """
    # Step1 :filter ais data
    where  = "WHERE sog IS NOT NULL AND latitude IS NOT NULL AND longitude IS NOT NULL" #Ensures valid vessel data.
    params = {}
    if mmsi: #If user wants specific vessel.
        where += " AND mmsi = :mmsi" #Filter by MMSI.
        params["mmsi"] = mmsi

    #Step 2: Get latest vessel positions - get latest record per vessel
    rows = db.execute(
        text(f"""
            SELECT DISTINCT ON (mmsi)    
                mmsi, sog, latitude, longitude, vessel_type
            FROM ais_data
            {where}
            ORDER BY mmsi, base_date_time DESC
        """), # Latest timestamp first.
        params,
    ).fetchall()

    _require_rows(rows, f"No AIS data found{' for MMSI ' + str(mmsi) if mmsi else ''}")

    results = []
    # Step 3: Process each vessel
    for r in rows:  # loop through these vessels
        speed      = float(r.sog) #SOG = Speed Over Ground.
        raw_code   = r.vessel_type #Get vessel type.
        code       = normalize_vessel_type_code(raw_code) 
        profile    = _get_vessel_profile(db, raw_code) #Fetch vessel engine parameters.
        vessel_cat = profile.pop("vessel_category", "Unknown") #Extract vessel category.
        #Step 4: Calculate emissions -> Fallback: full_emission_row(speed)
        em         = full_emission_row_typed(speed, profile) if profile else full_emission_row(speed) #Uses ship-specific physics model.

        #Step 5: Store results --> Stores emission record.
        db.execute(
            text("""
                INSERT INTO emissions (
                    mmsi, vessel_type_code, vessel_category,
                    speed, engine_load, fuel_consumption,
                    co2_emission, nox_emission, sox_emission,
                    latitude, longitude, calculation_source, calculated_at
                ) VALUES (
                    :mmsi, :code, :category,
                    :speed, :engine_load, :fuel,
                    :co2, :nox, :sox,
                    :lat, :lon, 'digital_twin_model', CURRENT_TIMESTAMP
                )
                ON CONFLICT (mmsi) DO UPDATE SET
                    vessel_type_code   = EXCLUDED.vessel_type_code,
                    vessel_category    = EXCLUDED.vessel_category,
                    speed              = EXCLUDED.speed,
                    engine_load        = EXCLUDED.engine_load,
                    fuel_consumption   = EXCLUDED.fuel_consumption,
                    co2_emission       = EXCLUDED.co2_emission,
                    nox_emission       = EXCLUDED.nox_emission,
                    sox_emission       = EXCLUDED.sox_emission,
                    latitude           = EXCLUDED.latitude,
                    longitude          = EXCLUDED.longitude,
                    calculation_source = EXCLUDED.calculation_source,
                    calculated_at      = EXCLUDED.calculated_at
            """),
            #   UPSERT logic --> ON CONFLICT (mmsi) DO UPDATE
            #    Meaning: If record exists → update it. Otherwise → insert new.
            
            {
                "mmsi":        r.mmsi,
                "code":        code,
                "category":    vessel_cat,
                "speed":       em["speed"],
                "engine_load": em["engine_load"],
                "fuel":        em["fuel_consumption"],
                "co2":         em["co2_emission"],
                "nox":         em["nox_emission"],
                "sox":         em["sox_emission"],
                "lat":         float(r.latitude),
                "lon":         float(r.longitude),
            },
        )
        results.append({
            "mmsi":             r.mmsi,
            "vessel_type_code": code,
            "vessel_category":  vessel_cat,
            **em,
        })

    db.commit()
    return {"vessels_processed": len(results), "results": results}


# ─────────────────────────────────────────────────────────────
# PREDICT EMISSIONS - Predicts emissions 30 minutes ahead.
# ─────────────────────────────────────────────────────────────

def predict_emissions_service(db: Session, mmsi: int = None):
    """
    Project 30-min forward: growth = 1 + clamp(speed/100, 0, 0.20)
    """
    where  = ""
    params = {}
    if mmsi:
        where  = "WHERE mmsi = :mmsi"
        params["mmsi"] = mmsi

    rows = db.execute(
        text(f"""
            SELECT DISTINCT ON (mmsi)
                mmsi, vessel_type_code, vessel_category, speed,
                co2_emission, nox_emission, sox_emission
            FROM emissions
            {where}
            ORDER BY mmsi, calculated_at DESC
        """),
        params,
    ).fetchall()

    _require_rows(rows, f"No emission records found{' for MMSI ' + str(mmsi) if mmsi else ''}")

    predictions = []
    for r in rows:
        speed    = float(r.speed or 0)
        growth   = 1.0 + min(speed / 100.0, 0.20)
        pred_co2 = round(float(r.co2_emission) * growth, 3)
        pred_nox = round(float(r.nox_emission) * growth, 3)
        pred_sox = round(float(r.sox_emission) * growth, 3)

        db.execute(
            text("""
                INSERT INTO emission_predictions (
                    mmsi, predicted_co2, predicted_speed,
                    prediction_horizon_minutes, model_used
                ) VALUES (:mmsi, :co2, :speed, 30, 'speed_adjusted_model')
            """),
            {"mmsi": r.mmsi, "co2": pred_co2, "speed": speed},
        )
        predictions.append({
            "mmsi":                r.mmsi,
            "vessel_type_code":    r.vessel_type_code,
            "vessel_category":     r.vessel_category,
            "current_speed_knots": round(speed, 2),
            "growth_factor":       round(growth, 3),
            "current_co2_kg_h":    round(float(r.co2_emission), 3),
            "predicted_co2_kg_h":  pred_co2,
            "predicted_nox_kg_h":  pred_nox,
            "predicted_sox_kg_h":  pred_sox,
            "horizon_minutes":     30,
        })

    db.commit()
    return {"predictions_generated": len(predictions), "predictions": predictions}


# ─────────────────────────────────────────────────────────────
# VESSEL EMISSION HISTORY
# ─────────────────────────────────────────────────────────────

def get_vessel_emissions_service(db: Session, mmsi: int):
    rows = db.execute(
        text("""
            SELECT emission_id, vessel_type_code, vessel_category,
                   speed, engine_load, fuel_consumption,
                   co2_emission, nox_emission, sox_emission,
                   latitude, longitude, calculated_at
            FROM emissions
            WHERE mmsi = :mmsi
            ORDER BY calculated_at DESC
        """),
        {"mmsi": mmsi},
    ).fetchall()

    _require_rows(rows, f"No emission records for MMSI {mmsi}")
    data      = [dict(r._mapping) for r in rows]
    total_co2 = sum(float(r["co2_emission"] or 0) for r in data)

    return {
        "mmsi":             mmsi,
        "vessel_type_code": data[0]["vessel_type_code"] if data else None,
        "vessel_category":  data[0]["vessel_category"]  if data else None,
        "records":          len(data),
        "total_co2_kg":     round(total_co2, 2),
        "data":             data,
    }


# ─────────────────────────────────────────────────────────────
# TOP POLLUTERS
# ─────────────────────────────────────────────────────────────

def get_top_polluters_service(db: Session, limit: int = 10):
    rows = db.execute(
        text("""
            SELECT
                mmsi,
                vessel_type_code,
                vessel_category,
                COUNT(*)                                     AS records,
                ROUND(SUM(co2_emission)::numeric, 2)         AS total_co2,
                ROUND(AVG(co2_emission)::numeric, 2)         AS avg_co2,
                ROUND(MAX(co2_emission)::numeric, 2)         AS peak_co2,
                ROUND(AVG(speed)::numeric,        2)         AS avg_speed
            FROM emissions
            GROUP BY mmsi, vessel_type_code, vessel_category
            ORDER BY total_co2 DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()

    return {
        "top_polluters": [
            {
                "rank":             idx + 1,
                "mmsi":             r.mmsi,
                "vessel_type_code": r.vessel_type_code,
                "vessel_category":  r.vessel_category,
                "records":          r.records,
                "total_co2_kg":     float(r.total_co2),
                "avg_co2_kg_h":     float(r.avg_co2),
                "peak_co2_kg_h":    float(r.peak_co2),
                "avg_speed_knots":  float(r.avg_speed),
            }
            for idx, r in enumerate(rows)
        ]
    }


# ─────────────────────────────────────────────────────────────
# HIGH EMISSION ALERTS
# ─────────────────────────────────────────────────────────────

def high_emission_alerts_service(db: Session, threshold: float = 2000.0):
    rows = db.execute(
        text("""
            SELECT mmsi, vessel_type_code, vessel_category,
                   speed, co2_emission, nox_emission, sox_emission,
                   latitude, longitude, calculated_at
            FROM emissions
            WHERE co2_emission > :threshold
            ORDER BY co2_emission DESC
            LIMIT 100
        """),
        {"threshold": threshold},
    ).fetchall()

    alerts = []
    for r in rows:
        co2   = float(r.co2_emission)
        level = (
            "CRITICAL" if co2 > threshold * 2.0 else
            "HIGH"     if co2 > threshold * 1.5 else
            "ELEVATED"
        )
        alerts.append({
            "mmsi":              r.mmsi,
            "vessel_type_code":  r.vessel_type_code,
            "vessel_category":   r.vessel_category,
            "speed_knots":       round(float(r.speed), 2),
            "co2_emission_kg_h": round(co2, 2),
            "nox_emission_kg_h": round(float(r.nox_emission or 0), 2),
            "sox_emission_kg_h": round(float(r.sox_emission or 0), 2),
            "latitude":          r.latitude,
            "longitude":         r.longitude,
            "alert_level":       level,
            "time":              r.calculated_at,
        })

    return {"threshold_kg_h": threshold, "total_alerts": len(alerts), "alerts": alerts}


# ─────────────────────────────────────────────────────────────
# FLEET SUMMARY
# ─────────────────────────────────────────────────────────────

def fleet_summary_service(db: Session):
    row = db.execute(
        text("""
            SELECT
                COUNT(DISTINCT mmsi)                         AS vessels,
                COUNT(*)                                     AS total_records,
                COUNT(DISTINCT vessel_type_code)             AS type_codes,
                ROUND(SUM(co2_emission)::numeric, 2)         AS total_co2,
                ROUND(AVG(co2_emission)::numeric, 2)         AS avg_co2,
                ROUND(MAX(co2_emission)::numeric, 2)         AS max_co2,
                ROUND(SUM(nox_emission)::numeric, 2)         AS total_nox,
                ROUND(SUM(sox_emission)::numeric, 2)         AS total_sox,
                ROUND(AVG(speed)::numeric,        2)         AS avg_speed,
                ROUND(AVG(engine_load)::numeric,  4)         AS avg_load
            FROM emissions
        """)
    ).fetchone()

    type_rows = db.execute(
        text("""
            SELECT
                vessel_type_code,
                vessel_category,
                COUNT(*)                                     AS vessels,
                ROUND(AVG(co2_emission)::numeric, 2)         AS avg_co2,
                ROUND(SUM(co2_emission)::numeric, 2)         AS total_co2
            FROM emissions
            GROUP BY vessel_type_code, vessel_category
            ORDER BY total_co2 DESC
        """)
    ).fetchall()

    return {
        "total_vessels":        row.vessels,
        "total_records":        row.total_records,
        "distinct_type_codes":  row.type_codes,
        "total_co2_kg":         float(row.total_co2 or 0),
        "average_co2_kg_h":     float(row.avg_co2   or 0),
        "peak_co2_kg_h":        float(row.max_co2   or 0),
        "total_nox_kg":         float(row.total_nox or 0),
        "total_sox_kg":         float(row.total_sox or 0),
        "average_speed_knots":  float(row.avg_speed or 0),
        "average_engine_load":  float(row.avg_load  or 0),
        "by_vessel_type": [
            {
                "vessel_type_code": r.vessel_type_code,
                "vessel_category":  r.vessel_category,
                "vessels":          r.vessels,
                "avg_co2_kg_h":     float(r.avg_co2),
                "total_co2_kg":     float(r.total_co2),
            }
            for r in type_rows
        ],
    }


# ─────────────────────────────────────────────────────────────
# ZONE MANAGEMENT
# ─────────────────────────────────────────────────────────────

def create_zone_service(db: Session, zone_name: str, geojson: dict, description: str = None):
    result = db.execute(
        text("""
            INSERT INTO geofence_zones (zone_name, description, polygon)
            VALUES (:zone_name, :description,
                    ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
            RETURNING zone_id
        """),
        {"zone_name": zone_name, "description": description, "geojson": json.dumps(geojson)},
    ).fetchone()
    db.commit()
    return {"status": "zone_created", "zone_id": str(result.zone_id), "zone_name": zone_name}


def get_zones_service(db: Session):
    rows = db.execute(
        text("""
            SELECT zone_id, zone_name, description, ST_AsGeoJSON(polygon) AS geojson
            FROM geofence_zones ORDER BY created_at DESC
        """)
    ).fetchall()
    return {
        "zones": [
            {
                "zone_id":     str(r.zone_id),
                "zone_name":   r.zone_name,
                "description": r.description,
                "geojson":     json.loads(r.geojson),
            }
            for r in rows
        ]
    }


# ─────────────────────────────────────────────────────────────
# ZONE EMISSIONS
# ─────────────────────────────────────────────────────────────

def get_emissions_by_zone(db: Session, zone_name: str):
    zone = db.execute(
        text("SELECT zone_id FROM geofence_zones WHERE LOWER(zone_name) = LOWER(:z)"),
        {"z": zone_name},
    ).fetchone()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_name}' not found")

    result = db.execute(
        text("""
            SELECT
                g.zone_name,
                COUNT(*)                                             AS records,
                COUNT(DISTINCT e.mmsi)                               AS vessels,
                COALESCE(ROUND(SUM(e.co2_emission)::numeric, 2), 0) AS total_co2,
                COALESCE(ROUND(AVG(e.co2_emission)::numeric, 2), 0) AS avg_co2,
                COALESCE(ROUND(MAX(e.co2_emission)::numeric, 2), 0) AS peak_co2,
                COALESCE(ROUND(SUM(e.nox_emission)::numeric, 2), 0) AS total_nox,
                COALESCE(ROUND(SUM(e.sox_emission)::numeric, 2), 0) AS total_sox
            FROM emissions e
            JOIN geofence_zones g
              ON ST_Contains(g.polygon,
                             ST_SetSRID(ST_MakePoint(e.longitude, e.latitude), 4326))
            WHERE LOWER(g.zone_name) = LOWER(:z)
            GROUP BY g.zone_name
        """),
        {"z": zone_name},
    ).fetchone()

    if not result:
        return {"zone_name": zone_name, "records": 0, "vessels": 0,
                "total_co2_kg": 0, "avg_co2_kg_h": 0, "peak_co2_kg_h": 0,
                "total_nox_kg": 0, "total_sox_kg": 0}

    return {
        "zone_name":     result.zone_name,
        "records":       result.records,
        "vessels":       result.vessels,
        "total_co2_kg":  float(result.total_co2),
        "avg_co2_kg_h":  float(result.avg_co2),
        "peak_co2_kg_h": float(result.peak_co2),
        "total_nox_kg":  float(result.total_nox),
        "total_sox_kg":  float(result.total_sox),
    }


# ─────────────────────────────────────────────────────────────
# ZONE PREDICTION
# ─────────────────────────────────────────────────────────────

def predict_zone_emissions_service(db: Session, zone_name: str):
    zone = db.execute(
        text("SELECT zone_id FROM geofence_zones WHERE LOWER(zone_name) = LOWER(:z)"),
        {"z": zone_name},
    ).fetchone()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_name}' not found")

    rows = db.execute(
        text("""
            SELECT DISTINCT ON (e.mmsi)
                e.mmsi, e.vessel_type_code, e.vessel_category,
                e.speed, e.co2_emission
            FROM emissions e
            JOIN geofence_zones g
              ON ST_Contains(g.polygon,
                             ST_SetSRID(ST_MakePoint(e.longitude, e.latitude), 4326))
            WHERE LOWER(g.zone_name) = LOWER(:z)
            ORDER BY e.mmsi, e.calculated_at DESC
        """),
        {"z": zone_name},
    ).fetchall()

    if not rows:
        return {"zone": zone_name, "predictions_generated": 0, "predictions": [],
                "message": "No emission records found inside this zone"}

    predictions = []
    for r in rows:
        speed    = float(r.speed or 0)
        growth   = 1.0 + min(speed / 100.0, 0.20)
        pred_co2 = round(float(r.co2_emission) * growth, 3)

        db.execute(
            text("""
                INSERT INTO emission_predictions (
                    mmsi, predicted_co2, predicted_speed,
                    prediction_horizon_minutes, model_used
                ) VALUES (:mmsi, :co2, :speed, 30, 'zone_speed_model')
            """),
            {"mmsi": r.mmsi, "co2": pred_co2, "speed": speed},
        )
        predictions.append({
            "mmsi":               r.mmsi,
            "vessel_type_code":   r.vessel_type_code,
            "vessel_category":    r.vessel_category,
            "current_co2_kg_h":   round(float(r.co2_emission), 3),
            "predicted_co2_kg_h": pred_co2,
            "growth_factor":      round(growth, 3),
        })

    db.commit()
    return {
        "zone":                  zone_name,
        "predictions_generated": len(predictions),
        "predictions":           predictions,
    }
