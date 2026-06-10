"""
app/anomaly_detection/service.py
=================================

All business logic for the anomaly-detection feature.

Performance design:
  - Detectors run in parallel via ThreadPoolExecutor (each gets its own
    DB session from SessionLocal so there are no thread-safety issues).
  - get_fleet_anomalies returns a real COUNT(*) total for correct pagination.
  - get_summary returns full KPI fields expected by the frontend.
  - get_map_overlay has the required ORDER BY for DISTINCT ON.
  - resolve_anomaly / delete_anomaly use .fetchone() not rowcount
    (rowcount is -1 for DML+RETURNING in psycopg2).
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam

from app.database import SessionLocal
from app.anomaly_detection import detectors as det
from app.anomaly_detection.constants import (
    DETECTION_WINDOW_HOURS,
    DETECTOR_MAX_WORKERS,
    FLEET_DEFAULT_LIMIT,
    AnomalyType,
    Severity,
)
from app.anomaly_detection.utils import severity_score

logger = logging.getLogger("anomaly_detection.service")
DEBUG_LOG_PATH = Path(__file__).resolve().parents[2] / "debug-b9ce97.log"


# region agent log
def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "b9ce97",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass
# endregion

ALL_DETECTORS = [
    (AnomalyType.SPEED_VIOLATION,   det.detect_speed_violations),
    (AnomalyType.EMISSION_SPIKE,    det.detect_emission_spikes),
    (AnomalyType.AIS_SIGNAL_GAP,    det.detect_ais_gaps),
    (AnomalyType.DARK_SHIP,         det.detect_dark_ships),
    (AnomalyType.GEOFENCE_BREACH,   det.detect_geofence_breaches),
    (AnomalyType.COURSE_DEVIATION,  det.detect_course_deviations),
    (AnomalyType.DRAUGHT_CHANGE,    det.detect_draught_changes),
    (AnomalyType.SUDDEN_SPEED_DROP, det.detect_sudden_speed_drops),
]


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _run_detector_isolated(
    atype: str, fn, window_hours: int
) -> tuple:
    """
    Run one detector in its own DB session (thread-safe).
    Returns (atype, results_list, error_str_or_None).
    """
    from app.database import get_clickhouse_client
    db = SessionLocal()
    ch_client = get_clickhouse_client()
    try:
        found = fn(db, ch_client, window_hours)
        logger.info("Detector %s → %d anomalies", atype, len(found))
        return atype, found, None
    except Exception as exc:
        logger.error("Detector %s failed: %s", atype, exc, exc_info=True)
        return atype, [], str(exc)
    finally:
        db.close()


def _persist_anomalies(db: Session, anomalies: List[dict]) -> int:
    if not anomalies:
        logger.warning("No anomalies to persist")
        return 0

    upserted = 0
    for a in anomalies:
        try:
            db.execute(text("""
                INSERT INTO anomaly_events (
                    mmsi, vessel_name, anomaly_type, severity,
                    description, latitude, longitude, sog,
                    extra_data, detected_at, is_resolved
                ) VALUES (
                    :mmsi, :vessel_name, :anomaly_type, :severity,
                    :description, :latitude, :longitude, :sog,
                    CAST(:extra AS JSONB), :detected_at, false
                )
                ON CONFLICT (mmsi, anomaly_type)
                DO UPDATE SET
                    severity    = EXCLUDED.severity,
                    description = EXCLUDED.description,
                    latitude    = EXCLUDED.latitude,
                    longitude   = EXCLUDED.longitude,
                    sog         = EXCLUDED.sog,
                    extra_data  = EXCLUDED.extra_data,
                    detected_at = EXCLUDED.detected_at,
                    is_resolved = false
            """), {
                "mmsi":         a["mmsi"],
                "vessel_name":  a["vessel_name"],
                "anomaly_type": a["anomaly_type"],
                "severity":     a["severity"],
                "description":  a["description"],
                "latitude":     a.get("latitude"),
                "longitude":    a.get("longitude"),
                "sog":          a.get("sog"),
                "extra":        json.dumps(a.get("extra", {})),
                "detected_at":  a.get("detected_at"),
            })
            upserted += 1
        except Exception as exc:
            logger.error(
                "Persist failed | mmsi=%s type=%s error=%s",
                a.get("mmsi"), a.get("anomaly_type"), exc,
                exc_info=True,
            )
            db.rollback()

    db.commit()
    logger.info("Persisted %d anomalies", upserted)
    return upserted


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: DETECTION (PARALLEL)
# ─────────────────────────────────────────────────────────────────────────────

def run_detection(
    db:           Session,
    window_hours: int = DETECTION_WINDOW_HOURS,
    types:        Optional[List[str]] = None,
    persist:      bool = True,
) -> dict:
    # region agent log
    _debug_log("pre-fix", "H2", "app/anomaly_detection/service.py:run_detection", "Run detection entered", {
        "window_hours": window_hours,
        "persist": persist,
        "types": types or [],
    })
    # endregion
    logger.info(
        "Starting anomaly detection | window=%sh | types=%s | persist=%s",
        window_hours, types, persist,
    )

    detectors_to_run = [
        (atype, fn)
        for atype, fn in ALL_DETECTORS
        if not types or atype in types
    ]

    all_anomalies: List[dict] = []
    type_counts:   dict       = {}
    errors:        List[str]  = []

    # ── Parallel execution ────────────────────────────────────────────────
    with ThreadPoolExecutor(max_workers=DETECTOR_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_run_detector_isolated, atype, fn, window_hours): atype
            for atype, fn in detectors_to_run
        }
        for future in as_completed(futures):
            atype, found, error = future.result()
            if error:
                errors.append(f"{atype}: {error}")
            all_anomalies.extend(found)
            type_counts[atype] = len(found)
            # region agent log
            _debug_log("pre-fix", "H2", "app/anomaly_detection/service.py:run_detection", "Detector finished", {
                "anomaly_type": atype,
                "count": len(found),
                "error": error,
            })
            # endregion

    # ── Sort by severity ──────────────────────────────────────────────────
    all_anomalies.sort(
        key=lambda x: severity_score(x["severity"]),
        reverse=True,
    )

    total = len(all_anomalies)
    # region agent log
    _debug_log("pre-fix", "H4", "app/anomaly_detection/service.py:run_detection", "Run detection completed", {
        "total": total,
        "persisted_expected": persist,
        "errors_count": len(errors),
    })
    # endregion
    logger.info("Total anomalies detected: %d", total)
    if total == 0:
        logger.warning("No anomalies detected — check thresholds or data window")

    # ── Auto-Resolution ───────────────────────────────────────────────────
    # If we are persisting, we should resolve "stale" anomalies for the 
    # specific types we just scanned. If a vessel was flagged before but 
    # isn't in 'all_anomalies' now, it's no longer an active situation.
    if persist and detectors_to_run:
        scanned_types = [atype for atype, _ in detectors_to_run]
        for stype in scanned_types:
            found_mmsis = [a["mmsi"] for a in all_anomalies if a["anomaly_type"] == stype]
            
            if found_mmsis:
                db.execute(text("""
                    UPDATE anomaly_events
                    SET is_resolved = true, resolved_at = NOW()
                    WHERE anomaly_type = :stype
                      AND is_resolved = false
                      AND mmsi NOT IN :mmsis
                """).bindparams(bindparam("mmsis", expanding=True)), {
                    "stype": stype,
                    "mmsis": found_mmsis,
                })
            else:
                # No anomalies found for this type? Resolve all active ones.
                db.execute(text("""
                    UPDATE anomaly_events
                    SET is_resolved = true, resolved_at = NOW()
                    WHERE anomaly_type = :stype
                      AND is_resolved = false
                """), {"stype": stype})
        db.commit()

    # ── Persist ───────────────────────────────────────────────────────────
    persisted = _persist_anomalies(db, all_anomalies) if persist else 0

    # ── Severity counts ───────────────────────────────────────────────────
    severity_counts: dict = {}
    for a in all_anomalies:
        s = a["severity"]
        severity_counts[s] = severity_counts.get(s, 0) + 1

    return {
        "window_hours":  window_hours,
        "total":         total,
        "persisted":     persisted,
        "by_type":       type_counts,
        "by_severity":   severity_counts,
        "errors":        errors,
        "anomalies":     all_anomalies,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: FLEET LIST  (pagination with real total)
# ─────────────────────────────────────────────────────────────────────────────

def get_fleet_anomalies(
    db:           Session,
    severity:     Optional[str] = None,
    anomaly_type: Optional[str] = None,
    resolved:     bool = False,
    limit:        int = FLEET_DEFAULT_LIMIT,
    offset:       int = 0,
) -> dict:

    filters = ["is_resolved = :resolved"]
    params: dict = {"resolved": resolved, "limit": limit, "offset": offset}

    if severity:
        filters.append("severity = :severity")
        params["severity"] = severity.upper()
    if anomaly_type:
        filters.append("anomaly_type = :atype")
        params["atype"] = anomaly_type

    where = " AND ".join(filters)

    # ── Real total (not page len) ─────────────────────────────────────────
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total: int = db.execute(
        text(f"SELECT COUNT(*) FROM anomaly_events WHERE {where}"),
        count_params,
    ).scalar() or 0

    rows = db.execute(text(f"""
        SELECT *
        FROM anomaly_events
        WHERE {where}
        ORDER BY
            CASE severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH'     THEN 2
                WHEN 'MEDIUM'   THEN 3
                WHEN 'LOW'      THEN 4
                ELSE 5
            END,
            detected_at DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    return {
        "total":     total,
        "limit":     limit,
        "offset":    offset,
        "filters":   {
            "severity":     severity,
            "anomaly_type": anomaly_type,
            "resolved":     resolved,
        },
        "anomalies": [dict(r) for r in rows],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: SUMMARY KPIs
# ─────────────────────────────────────────────────────────────────────────────

def get_summary(db: Session) -> dict:
    rows = db.execute(text("""
        SELECT
            anomaly_type,
            severity,
            COUNT(*) FILTER (WHERE NOT is_resolved) AS active,
            COUNT(*) FILTER (WHERE     is_resolved) AS resolved,
            COUNT(*)                                 AS total
        FROM anomaly_events
        GROUP BY anomaly_type, severity
        ORDER BY
            CASE severity
                WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM'   THEN 3 WHEN 'LOW'  THEN 4 ELSE 5
            END
    """)).mappings().all()

    rows = [dict(r) for r in rows]

    total_active    = sum(r["active"]   for r in rows)
    total_resolved  = sum(r["resolved"] for r in rows)
    critical_active = sum(r["active"]   for r in rows if r["severity"] == Severity.CRITICAL)
    high_active     = sum(r["active"]   for r in rows if r["severity"] == Severity.HIGH)
    medium_active   = sum(r["active"]   for r in rows if r["severity"] == Severity.MEDIUM)
    low_active      = sum(r["active"]   for r in rows if r["severity"] == Severity.LOW)

    return {
        "total_active":    total_active,
        "total_resolved":  total_resolved,
        "critical_active": critical_active,
        "high_active":     high_active,
        "medium_active":   medium_active,
        "low_active":      low_active,
        "breakdown":       rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: MAP OVERLAY (fix: ORDER BY required for DISTINCT ON)
# ─────────────────────────────────────────────────────────────────────────────

def get_map_overlay(db: Session) -> dict:
    rows = db.execute(text("""
        SELECT DISTINCT ON (mmsi)
            mmsi, vessel_name, anomaly_type, severity,
            latitude, longitude, description, detected_at
        FROM anomaly_events
        WHERE is_resolved = false
          AND latitude  IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY
            mmsi,
            CASE severity
                WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM'   THEN 3 WHEN 'LOW'  THEN 4 ELSE 5
            END
    """)).mappings().all()

    return {
        "total":   len(rows),
        "markers": [dict(r) for r in rows],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: VESSEL ANOMALIES
# ─────────────────────────────────────────────────────────────────────────────

def get_vessel_anomalies(db: Session, mmsi: int) -> dict:
    rows = db.execute(text("""
        SELECT *
        FROM anomaly_events
        WHERE mmsi = :mmsi
        ORDER BY detected_at DESC
    """), {"mmsi": mmsi}).mappings().all()

    return {
        "mmsi":      mmsi,
        "total":     len(rows),
        "anomalies": [dict(r) for r in rows],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: RESOLVE / DELETE  (fix: use fetchone(), not rowcount)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_anomaly(db: Session, anomaly_id: str) -> bool:
    row = db.execute(text("""
        UPDATE anomaly_events
        SET is_resolved = true, resolved_at = NOW()
        WHERE anomaly_id = :id AND is_resolved = false
        RETURNING anomaly_id
    """), {"id": anomaly_id}).fetchone()
    db.commit()
    return row is not None


def delete_anomaly(db: Session, anomaly_id: str) -> bool:
    row = db.execute(text("""
        DELETE FROM anomaly_events
        WHERE anomaly_id = :id
        RETURNING anomaly_id
    """), {"id": anomaly_id}).fetchone()
    db.commit()
    return row is not None