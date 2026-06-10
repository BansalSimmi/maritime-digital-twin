"""
app/anomaly_detection/detectors.py
===================================

Anomaly detectors refactored for ClickHouse (OLAP). 
Queries use ClickHouse argMax() for ultra-fast "latest state" aggregation 
over the 217M row ais_data table instead of PostgreSQL DISTINCT ON.

Any required relational metadata (like design_speed or geofence_zones) 
is looked up natively in PostgreSQL after fetching the minimal aggregated 
result set from ClickHouse.
"""

from __future__ import annotations

import logging
import math
from typing import List

from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session

from app.anomaly_detection.constants import (
    AIS_GAP_THRESHOLD_MINUTES,
    ANOMALY_SEVERITY,
    COURSE_DEVIATION_DEGREES,
    COURSE_DEVIATION_MIN_SOG,
    COURSE_DEVIATION_WINDOW,
    DARK_SHIP_MINUTES,
    DRAUGHT_CHANGE_THRESHOLD,
    DRAUGHT_MIN_VALUE,
    EMISSION_SPIKE_FACTOR,
    EMISSION_SPIKE_MIN_CO2,
    SPEED_DROP_MIN_PREV_SOG,
    SPEED_DROP_THRESHOLD,
    SPEED_VIOLATION_FACTOR,
    SPEED_VIOLATION_MIN_SOG,
    AnomalyType,
)
from app.anomaly_detection.utils import angular_diff, build_anomaly_record

logger = logging.getLogger("anomaly_detection.detectors")


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_ch_anchor(ch_client) -> str:
    """Return the MAX(base_date_time) formatted as stringent for ClickHouse."""
    res = ch_client.query("SELECT toString(max(base_date_time)) FROM ais_data")
    if not res.result_rows or not res.result_rows[0][0]:
        return "NOW()"
    val = res.result_rows[0][0]
    return f"'{val}'"

def _ch_window_filter(anchor: str, window_hours: int) -> str:
    """SQL fragment: restrict to the most recent N hours of AIS data in CH."""
    return f"base_date_time >= toDateTime({anchor}) - INTERVAL {int(window_hours)} HOUR"

def _dict_rows(ch_res) -> list[dict]:
    """Convert ClickHouse query result to a list of dicts."""
    cols = ch_res.column_names
    return [dict(zip(cols, row)) for row in ch_res.result_rows]


def _geofence_table_exists(db: Session) -> bool:
    """Return True if geofence_zones table is present in PostgreSQL."""
    result = db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name   = 'geofence_zones'
        )
    """)).scalar()
    return bool(result)


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: SPEED VIOLATION
# ─────────────────────────────────────────────────────────────────────────────

def detect_speed_violations(db: Session, ch_client, window_hours: int) -> List[dict]:
    try:
        anchor = _get_ch_anchor(ch_client)
        
        # 1. Ask ClickHouse for latest state of all vessels speeding > MIN_SOG
        sql_ch = f"""
            SELECT
                mmsi,
                argMax(vessel_name, base_date_time) AS vessel_name,
                argMax(sog, base_date_time) AS sog,
                argMax(latitude, base_date_time) AS latitude,
                argMax(longitude, base_date_time) AS longitude,
                argMax(vessel_type, base_date_time) AS vessel_type
            FROM ais_data
            WHERE {_ch_window_filter(anchor, window_hours)}
            GROUP BY mmsi
            HAVING argMax(sog, base_date_time) >= {SPEED_VIOLATION_MIN_SOG}
        """
        ch_res = ch_client.query(sql_ch)
        latest = _dict_rows(ch_res)
        if not latest:
            return []

        # 2. Look up Vessel Profiles in PostgreSQL
        mmsi_types = {r["mmsi"]: r["vessel_type"] for r in latest if r["vessel_type"]}
        type_codes = list(set([str(t) for t in mmsi_types.values()]))

        profiles = {}
        if type_codes:
            sql_vp = text("""
                SELECT vessel_type_code, design_speed, vessel_category
                FROM vessel_profiles
                WHERE vessel_type_code IN :codes
            """).bindparams(bindparam("codes", expanding=True))
            vp_rows = db.execute(sql_vp, {"codes": type_codes}).mappings().all()
            for vp in vp_rows:
                profiles[str(vp["vessel_type_code"])] = vp

        # 3. Calculate Speed Violations natively in Python
        results: List[dict] = []
        for r in latest:
            vtype        = str(r["vessel_type"]) if r["vessel_type"] else '0'
            vp           = profiles.get(vtype, {})
            design_speed = float(vp.get("design_speed") or 20.0)
            category     = vp.get("vessel_category") or "Unknown"
            sog          = float(r["sog"])

            if sog > design_speed * SPEED_VIOLATION_FACTOR:
                excess_pct = round(((sog / design_speed) - 1.0) * 100.0, 1) if design_speed > 0 else None
                results.append(build_anomaly_record(
                    mmsi=r["mmsi"],
                    vessel_name=r["vessel_name"],
                    anomaly_type=AnomalyType.SPEED_VIOLATION,
                    severity=ANOMALY_SEVERITY[AnomalyType.SPEED_VIOLATION],
                    description=(
                        f"SOG {round(sog, 2)} kn exceeds design speed "
                        f"{round(design_speed, 2)} kn"
                        + (f" by {excess_pct}%" if excess_pct is not None else "")
                        + f" ({category})"
                    ),
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    sog=sog,
                    extra={
                        "design_speed":    design_speed,
                        "excess_pct":      excess_pct,
                        "vessel_category": category,
                    },
                ))
                
        # Sort and limit 500
        results.sort(key=lambda x: x["sog"], reverse=True)
        results = results[:500]
        
        logger.info("Speed violations (CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("speed_violation failed: %s", exc, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: EMISSION SPIKE
# ─────────────────────────────────────────────────────────────────────────────

def detect_emission_spikes(db: Session, ch_client, window_hours: int) -> List[dict]:
    # Emissions table is already heavily aggregated in PG. We only need CH for fast vessel_name lookup.
    del window_hours  
    try:
        # 1. PostgreSQL calculates emission spikes
        sql = f"""
            WITH category_avg AS (
                SELECT vessel_category,
                       AVG(co2_emission) AS avg_co2
                FROM emissions
                WHERE co2_emission >= {EMISSION_SPIKE_MIN_CO2}
                GROUP BY vessel_category
            )
            SELECT
                e.mmsi,
                e.vessel_category,
                e.co2_emission,
                e.nox_emission,
                e.sox_emission,
                e.speed,
                e.latitude,
                e.longitude,
                ca.avg_co2
            FROM emissions e
            JOIN category_avg ca ON ca.vessel_category = e.vessel_category
            WHERE e.co2_emission > ca.avg_co2 * {EMISSION_SPIKE_FACTOR}
            ORDER BY e.co2_emission DESC
            LIMIT 500
        """
        rows = db.execute(text(sql)).mappings().all()
        if not rows:
            return []

        # 2. Ask ClickHouse for fast vessel_names for only these MMSIs
        mmsis = [int(r["mmsi"]) for r in rows]
        sql_ch = f"""
            SELECT mmsi, argMax(vessel_name, base_date_time) AS vessel_name
            FROM ais_data WHERE mmsi IN {tuple(mmsis)} GROUP BY mmsi
        """
        ch_res = ch_client.query(sql_ch)
        names = {int(r["mmsi"]): r["vessel_name"] for r in _dict_rows(ch_res)}

        # 3. Build records
        results = []
        for r in rows:
            mmsi = int(r["mmsi"])
            vname = names.get(mmsi) or str(mmsi)
            results.append(
                build_anomaly_record(
                    mmsi=mmsi,
                    vessel_name=vname,
                    anomaly_type=AnomalyType.EMISSION_SPIKE,
                    severity=ANOMALY_SEVERITY[AnomalyType.EMISSION_SPIKE],
                    description=(
                        f"CO\u2082 spike {round(float(r['co2_emission']), 3)} kg/h "
                        f"(avg {round(float(r['avg_co2']), 3)} kg/h, {r['vessel_category']})"
                    ),
                    latitude=r.get("latitude"),
                    longitude=r.get("longitude"),
                    sog=r.get("speed"),
                    extra={
                        "avg_category_co2": float(r["avg_co2"]),
                        "vessel_category":  r["vessel_category"],
                        "nox_kg_h": float(r["nox_emission"]) if r.get("nox_emission") is not None else None,
                        "sox_kg_h": float(r["sox_emission"]) if r.get("sox_emission") is not None else None,
                    },
                )
            )
        logger.info("Emission spikes (PG+CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("emission_spike failed: %s", exc, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: AIS GAP & DARK SHIPS (Shared query)
# ─────────────────────────────────────────────────────────────────────────────

def _latest_gap_rows_ch(ch_client, window_hours: int) -> list[dict]:
    anchor = _get_ch_anchor(ch_client)
    sql = f"""
        SELECT
            mmsi,
            argMax(vessel_name, base_date_time) AS vessel_name,
            argMax(latitude, base_date_time) AS latitude,
            argMax(longitude, base_date_time) AS longitude,
            argMax(sog, base_date_time) AS sog,
            dateDiff('minute', max(base_date_time), toDateTime({anchor})) AS gap_minutes
        FROM ais_data
        WHERE {_ch_window_filter(anchor, window_hours)}
        GROUP BY mmsi
        HAVING gap_minutes >= {AIS_GAP_THRESHOLD_MINUTES}
    """
    ch_res = ch_client.query(sql)
    return _dict_rows(ch_res)


def detect_ais_gaps(db: Session, ch_client, window_hours: int) -> List[dict]:
    try:
        rows    = _latest_gap_rows_ch(ch_client, window_hours)
        results = []
        for r in rows:
            gap = float(r["gap_minutes"] or 0.0)
            if AIS_GAP_THRESHOLD_MINUTES <= gap < DARK_SHIP_MINUTES:
                results.append(build_anomaly_record(
                    mmsi=r["mmsi"],
                    vessel_name=r["vessel_name"],
                    anomaly_type=AnomalyType.AIS_SIGNAL_GAP,
                    severity=ANOMALY_SEVERITY[AnomalyType.AIS_SIGNAL_GAP],
                    description=f"AIS signal gap {round(gap, 1)} min",
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    sog=r.get("sog"),
                    extra={"gap_minutes": gap},
                ))
        logger.info("AIS gaps (CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("ais_gap failed: %s", exc, exc_info=True)
        return []


def detect_dark_ships(db: Session, ch_client, window_hours: int) -> List[dict]:
    try:
        rows    = _latest_gap_rows_ch(ch_client, window_hours)
        results = [
            build_anomaly_record(
                mmsi=r["mmsi"],
                vessel_name=r["vessel_name"],
                anomaly_type=AnomalyType.DARK_SHIP,
                severity=ANOMALY_SEVERITY[AnomalyType.DARK_SHIP],
                description=f"Dark ship {round(float(r['gap_minutes']) / 60.0, 2)} hrs",
                latitude=r["latitude"],
                longitude=r["longitude"],
                sog=r.get("sog"),
                extra={"gap_minutes": float(r["gap_minutes"])},
            )
            for r in rows
            if float(r["gap_minutes"] or 0.0) >= DARK_SHIP_MINUTES
        ]
        logger.info("Dark ships (CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("dark_ship failed: %s", exc, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: COURSE DEVIATION
# ─────────────────────────────────────────────────────────────────────────────

def detect_course_deviations(db: Session, ch_client, window_hours: int) -> List[dict]:
    try:
        hours  = max(int(window_hours), int(COURSE_DEVIATION_WINDOW))
        anchor = _get_ch_anchor(ch_client)
        
        sql = f"""
            SELECT 
                mmsi,
                argMax(vessel_name, base_date_time) AS vessel_name,
                argMax(cog, base_date_time) AS current_cog,
                argMax(sog, base_date_time) AS sog,
                argMax(latitude, base_date_time) AS latitude,
                argMax(longitude, base_date_time) AS longitude,
                avg(cog) AS baseline_cog
            FROM ais_data
            WHERE {_ch_window_filter(anchor, hours)}
              AND cog IS NOT NULL
            GROUP BY mmsi
            HAVING argMax(sog, base_date_time) >= {COURSE_DEVIATION_MIN_SOG}
        """
        ch_res  = ch_client.query(sql)
        rows    = _dict_rows(ch_res)
        results = []
        
        for r in rows:
            if not r["current_cog"] or not r["baseline_cog"]:
                continue
            diff = angular_diff(float(r["current_cog"]), float(r["baseline_cog"]))
            if diff >= COURSE_DEVIATION_DEGREES:
                results.append(build_anomaly_record(
                    mmsi=r["mmsi"],
                    vessel_name=r["vessel_name"],
                    anomaly_type=AnomalyType.COURSE_DEVIATION,
                    severity=ANOMALY_SEVERITY[AnomalyType.COURSE_DEVIATION],
                    description=f"Course deviation {round(diff, 1)}° vs baseline",
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    sog=r["sog"],
                    extra={
                        "current_cog":  float(r["current_cog"]),
                        "baseline_cog": float(r["baseline_cog"]),
                        "diff_degrees": diff,
                    },
                ))
        logger.info("Course deviations (CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("course_deviation failed: %s", exc, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: DRAUGHT CHANGE
# ─────────────────────────────────────────────────────────────────────────────

def detect_draught_changes(db: Session, ch_client, window_hours: int) -> List[dict]:
    try:
        anchor = _get_ch_anchor(ch_client)
        sql = f"""
            SELECT
                mmsi,
                argMax(vessel_name, base_date_time) AS vessel_name,
                max(draft) - min(draft) AS change_m,
                avg(latitude) AS latitude,
                avg(longitude) AS longitude
            FROM ais_data
            WHERE {_ch_window_filter(anchor, window_hours)}
              AND draft >= {DRAUGHT_MIN_VALUE}
            GROUP BY mmsi
            HAVING change_m >= {DRAUGHT_CHANGE_THRESHOLD}
            ORDER BY change_m DESC
            LIMIT 500
        """
        ch_res  = ch_client.query(sql)
        rows    = _dict_rows(ch_res)
        results = [
            build_anomaly_record(
                mmsi=r["mmsi"],
                vessel_name=r["vessel_name"] or str(r["mmsi"]),
                anomaly_type=AnomalyType.DRAUGHT_CHANGE,
                severity=ANOMALY_SEVERITY[AnomalyType.DRAUGHT_CHANGE],
                description=f"Draught change {round(float(r['change_m']), 2)} m",
                latitude=r["latitude"],
                longitude=r["longitude"],
                extra={"change_m": float(r["change_m"])},
            )
            for r in rows
        ]
        logger.info("Draught changes (CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("draught_change failed: %s", exc, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: SUDDEN SPEED DROP
# ─────────────────────────────────────────────────────────────────────────────

def detect_sudden_speed_drops(db: Session, ch_client, window_hours: int) -> List[dict]:
    try:
        anchor = _get_ch_anchor(ch_client)
        sql = f"""
            SELECT
                mmsi,
                argMax(vessel_name, base_date_time) AS vessel_name,
                argMax(sog, base_date_time) AS current_sog,
                argMax(latitude, base_date_time) AS latitude,
                argMax(longitude, base_date_time) AS longitude,
                avg(sog) AS prev_avg_sog,
                avg(sog) - argMax(sog, base_date_time) AS drop_kn
            FROM ais_data
            WHERE {_ch_window_filter(anchor, window_hours)}
              AND sog IS NOT NULL
            GROUP BY mmsi
            HAVING prev_avg_sog >= {SPEED_DROP_MIN_PREV_SOG}
               AND drop_kn >= {SPEED_DROP_THRESHOLD}
            ORDER BY drop_kn DESC
            LIMIT 500
        """
        ch_res  = ch_client.query(sql)
        rows    = _dict_rows(ch_res)
        results = [
            build_anomaly_record(
                mmsi=r["mmsi"],
                vessel_name=r["vessel_name"],
                anomaly_type=AnomalyType.SUDDEN_SPEED_DROP,
                severity=ANOMALY_SEVERITY[AnomalyType.SUDDEN_SPEED_DROP],
                description=(
                    f"Speed drop {round(float(r['drop_kn']), 2)} kn "
                    f"(avg {round(float(r['prev_avg_sog']), 2)} → "
                    f"current {round(float(r['current_sog']), 2)})"
                ),
                latitude=r["latitude"],
                longitude=r["longitude"],
                sog=r["current_sog"],
                extra={
                    "current_sog":  float(r["current_sog"]),
                    "prev_avg_sog": float(r["prev_avg_sog"]),
                    "drop_kn":      float(r["drop_kn"]),
                },
            )
            for r in rows
        ]
        logger.info("Sudden speed drops (CH): %d", len(results))
        return results
    except Exception as exc:
        logger.error("sudden_speed_drop failed: %s", exc, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR: GEOFENCE BREACH
# ─────────────────────────────────────────────────────────────────────────────

def detect_geofence_breaches(db: Session, ch_client, window_hours: int) -> List[dict]:
    if not _geofence_table_exists(db):
        logger.warning("geofence_zones table not found — skipping geofence detector.")
        return []
        
    try:
        anchor = _get_ch_anchor(ch_client)
        # 1. Fetch latest coordinates for all ships natively in CH
        sql_ch = f"""
            SELECT 
                mmsi,
                argMax(vessel_name, base_date_time) AS vessel_name,
                argMax(latitude, base_date_time) AS latitude,
                argMax(longitude, base_date_time) AS longitude,
                argMax(sog, base_date_time) as sog
            FROM ais_data
            WHERE {_ch_window_filter(anchor, window_hours)}
            GROUP BY mmsi
            HAVING argMax(latitude, base_date_time) IS NOT NULL
               AND argMax(longitude, base_date_time) IS NOT NULL
        """
        ch_res = ch_client.query(sql_ch)
        latest_coords = _dict_rows(ch_res)
        if not latest_coords:
            return []

        # 2. Check intersections in PostgreSQL natively by passing a VALUES block
        # Batch inserting a temp list via CTE to verify intersections against geofences
        # Max rows = 50,000. For PG, parsing a 50k rows VALUES block is fast enough.
        # Format: (mmsi, lon, lat)
        
        # Split into batches of 5000 to prevent overwhelming memory or query size
        BATCH_SIZE = 5000
        breaches = []
        
        for i in range(0, len(latest_coords), BATCH_SIZE):
            batch = latest_coords[i : i+BATCH_SIZE]
            
            # Construct the VALUES clause dynamically and avoid SQL injection by parameterizing
            values_clause = []
            params = {}
            for idx, pt in enumerate(batch):
                p_lon = f"lon_{idx}"
                p_lat = f"lat_{idx}"
                p_mmsi = f"mmsi_{idx}"
                values_clause.append(f"(:{p_mmsi}::int, :{p_lon}::float, :{p_lat}::float)")
                params[p_lon] = pt["longitude"]
                params[p_lat] = pt["latitude"]
                params[p_mmsi] = pt["mmsi"]

            values_str = ", ".join(values_clause)
            
            sql_pg = f"""
                WITH pts AS (
                    SELECT mmsi, lon, lat
                    FROM (VALUES {values_str}) AS t(mmsi, lon, lat)
                )
                SELECT 
                    p.mmsi, 
                    gz.zone_name 
                FROM pts p
                JOIN geofence_zones gz 
                  ON ST_Contains(gz.polygon, ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326))
            """
            rows = db.execute(text(sql_pg), params).mappings().all()
            
            for check in rows:
                breaches.append(check)
                
        # 3. Compile final anomaly events
        breaches_map = {r["mmsi"]: r["zone_name"] for r in breaches}
        results = []
        
        for r in latest_coords:
            if r["mmsi"] in breaches_map:
                zone_name = breaches_map[r["mmsi"]]
                results.append(
                    build_anomaly_record(
                        mmsi=r["mmsi"],
                        vessel_name=r["vessel_name"],
                        anomaly_type=AnomalyType.GEOFENCE_BREACH,
                        severity=ANOMALY_SEVERITY[AnomalyType.GEOFENCE_BREACH],
                        description=f"Inside restricted zone: {zone_name}",
                        latitude=r["latitude"],
                        longitude=r["longitude"],
                        sog=r.get("sog"),
                        extra={"zone_name": zone_name},
                    )
                )
                
        logger.info("Geofence breaches (CH+PG): %d", len(results))
        return results
    except Exception as exc:
        logger.error("geofence_breach failed: %s", exc, exc_info=True)
        return []
