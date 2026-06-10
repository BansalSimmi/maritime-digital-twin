# """
# vessel_tracking/tracking.py
# --------------------
# Vessel Tracking — all endpoints in one file.

# Endpoints:
#   1. Live Positions      GET /api/tracking/live
#   2. Search & Filter     GET /api/tracking/search
#   3. Position History    GET /api/tracking/{mmsi}/history
#   4. Speed Profile       GET /api/tracking/{mmsi}/speed-profile
#   5. Day Summary         GET /api/tracking/{mmsi}/day-summary
# """

# # from fastapi import APIRouter, Depends, Query, HTTPException
# # # from sqlalchemy.ext.asyncio import AsyncSession
# # from sqlalchemy.orm import Session
# # from sqlalchemy import text
# # from typing import Optional
# # from datetime import timedelta
# # import math

# # from app.dependencies import get_db
# from fastapi import APIRouter, Depends, Query, HTTPException
# from sqlalchemy.orm import Session
# from sqlalchemy import text
# from typing import Optional
# from datetime import timedelta
# import math

# from app.vessel_tracking.database import get_db

# router = APIRouter()


# # ═══════════════════════════════════════════════════════════════════════════════
# # 1. LIVE POSITIONS — Latest AIS ping per vessel (for live map)
# # GET /api/tracking/live
# # ═══════════════════════════════════════════════════════════════════════════════
# @router.get("/live", summary="Live positions of all vessels for map rendering")
# def live_positions(db: Session = Depends(get_db)):
#     """
#     Returns the most recent AIS ping for every unique vessel.
#     Use this to render all vessel dots on the live fleet map.

#     Response: list of { mmsi, vessel_name, vessel_type, lat, lon, sog, cog, heading, last_seen }
#     """
#     result = db.execute(text("""
#         SELECT DISTINCT ON (mmsi)
#             mmsi,
#             vessel_name,
#             vessel_type,
#             latitude,
#             longitude,
#             sog,
#             cog,
#             heading,
#             base_date_time AS last_seen
#         FROM ais_data
#         WHERE mmsi        IS NOT NULL
#           AND latitude    IS NOT NULL
#           AND longitude   IS NOT NULL
#         ORDER BY mmsi, base_date_time DESC
#     """))
#     rows = result.mappings().all()
#     return {
#         "positions": [dict(r) for r in rows],
#         "total_vessels": len(rows)
#     }


# # ═══════════════════════════════════════════════════════════════════════════════
# # 2. SEARCH & FILTER VESSELS
# # GET /api/tracking/search
# # ═══════════════════════════════════════════════════════════════════════════════
# @router.get("/search", summary="Search and filter vessels by name, MMSI, type, speed")
# def search_vessels(
#     db:Session = Depends(get_db),
#     q:           Optional[str]   = Query(None,  description="Vessel name or MMSI keyword"),
#     vessel_type: Optional[str]   = Query(None,  description="Cargo | Tanker | Passenger | Fishing"),
#     min_speed:   float           = Query(0.0,   description="Min average speed (knots)"),
#     max_speed:   float           = Query(50.0,  description="Max average speed (knots)"),
#     limit:       int             = Query(50,    description="Max results"),
# ):
#     """
#     Search vessels by name or MMSI keyword.
#     Filter by vessel type and average speed range.

#     Examples:
#       /search?q=aurora
#       /search?vessel_type=Tanker&min_speed=10
#       /search?q=366&max_speed=15
#     """
#     filters = ["mmsi IS NOT NULL"]
#     params: dict = {"min_speed": min_speed, "max_speed": max_speed, "limit": limit}

#     if q:
#         filters.append(
#             "(LOWER(vessel_name) LIKE :q OR CAST(mmsi AS TEXT) LIKE :q)"
#         )
#         params["q"] = f"%{q.lower()}%"

#     if vessel_type:
#         filters.append("LOWER(vessel_type) LIKE :vtype")
#         params["vtype"] = f"%{vessel_type.lower()}%"

#     where = " AND ".join(filters)

#     result = db.execute(text(f"""
#         SELECT
#             mmsi,
#             MAX(vessel_name)                    AS vessel_name,
#             MAX(vessel_type)                    AS vessel_type,
#             MAX(imo)                            AS imo,
#             COUNT(*)                            AS total_pings,
#             ROUND(AVG(sog)::numeric, 2)         AS avg_speed,
#             MAX(base_date_time)                 AS last_seen
#         FROM ais_data
#         WHERE {where}
#         GROUP BY mmsi
#         HAVING AVG(sog) BETWEEN :min_speed AND :max_speed
#         ORDER BY last_seen DESC
#         LIMIT :limit
#     """), params)

#     rows = result.mappings().all()
#     return {
#         "results": [dict(r) for r in rows],
#         "count": len(rows),
#         "query": q,
#         "filters": {"vessel_type": vessel_type, "min_speed": min_speed, "max_speed": max_speed}
#     }


# # ═══════════════════════════════════════════════════════════════════════════════
# # 3. POSITION HISTORY — Full track with optional date range
# # GET /api/tracking/{mmsi}/history
# # ═══════════════════════════════════════════════════════════════════════════════
# @router.get("/{mmsi}/history", summary="Full position history for a vessel")
# def vessel_history(
#     mmsi: int,
#     db: Session = Depends(get_db),
#     start: Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-01T00:00:00"),
#     end:   Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-07T23:59:59"),
#     limit: int           = Query(5000, description="Max points (default 5000)"),
# ):
#     """
#     Returns time-ordered AIS positions for a single vessel.

#     Each point: { timestamp, latitude, longitude, sog, cog, heading }

#     Use start/end to narrow date window.
#     Use limit to cap response size.
#     Perfect for drawing track lines on a map.
#     """
#     filters = [
#         "mmsi      = :mmsi",
#         "latitude  IS NOT NULL",
#         "longitude IS NOT NULL"
#     ]
#     params: dict = {"mmsi": mmsi, "limit": limit}

#     if start:
#         filters.append("base_date_time >= :start")
#         params["start"] = start
#     if end:
#         filters.append("base_date_time <= :end")
#         params["end"] = end

#     where = " AND ".join(filters)

#     result =  db.execute(text(f"""
#         SELECT
#             base_date_time AS timestamp,
#             latitude, longitude,
#             sog, cog, heading
#         FROM ais_data
#         WHERE {where}
#         ORDER BY base_date_time ASC
#         LIMIT :limit
#     """), params)

#     rows = result.mappings().all()
#     if not rows:
#         raise HTTPException(status_code=404, detail=f"No data found for MMSI {mmsi}")

#     vessel_name = _get_vessel_name(db, mmsi)

#     return {
#         "mmsi":         mmsi,
#         "vessel_name":  vessel_name,
#         "total_points": len(rows),
#         "filter":       {"start": start, "end": end},
#         "points":       [dict(r) for r in rows],
#     }


# # ═══════════════════════════════════════════════════════════════════════════════
# # 5. SPEED PROFILE — Hourly average SOG
# # GET /api/tracking/{mmsi}/speed-profile
# # ═══════════════════════════════════════════════════════════════════════════════
# @router.get("/{mmsi}/speed-profile", summary="Hourly average speed over full tracking period")
# def speed_profile(
#     mmsi:  int,
#     db:   Session  = Depends(get_db),
#     start: Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-01T00:00:00"),
#     end:   Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-07T23:59:59"),
#     limit: int           = Query(5000, description="Max hourly buckets to return (default 5000)"),
# ):
#     """
#     Returns hourly bucketed average speed (SOG) for the vessel.
#     Use this to draw the speed-over-time graph on the dashboard.
#     Also useful for fuel consumption and emission calculations.

#     Use start/end to narrow date window (same as /history).
#     """
#     filters = ["mmsi = :mmsi", "sog IS NOT NULL"]
#     params: dict = {"mmsi": mmsi, "limit": limit}

#     if start:
#         filters.append("base_date_time >= :start")
#         params["start"] = start
#     if end:
#         filters.append("base_date_time <= :end")
#         params["end"] = end

#     where = " AND ".join(filters)

#     result = db.execute(text(f"""
#         SELECT
#             DATE_TRUNC('hour', base_date_time)  AS hour,
#             ROUND(AVG(sog)::numeric, 2)          AS avg_sog,
#             COUNT(*)                             AS pings
#         FROM ais_data
#         WHERE {where}
#         GROUP BY 1
#         ORDER BY 1 ASC
#         LIMIT :limit
#     """), params)

#     rows = result.mappings().all()
#     if not rows:
#         raise HTTPException(status_code=404, detail=f"No speed data for MMSI {mmsi}")

#     vessel_name = _get_vessel_name(db, mmsi)
#     avg_overall = round(sum(r["avg_sog"] for r in rows) / len(rows), 2)
#     max_speed   = max(r["avg_sog"] for r in rows)

#     return {
#         "mmsi":          mmsi,
#         "vessel_name":   vessel_name,
#         "filter":        {"start": start, "end": end},
#         "avg_speed_kn":  avg_overall,
#         "max_speed_kn":  round(max_speed, 2),
#         "total_hours":   len(rows),
#         "profile":       [dict(r) for r in rows],
#     }


# # ═══════════════════════════════════════════════════════════════════════════════
# # 6. DAY SUMMARY — Per-day activity stats
# # GET /api/tracking/{mmsi}/day-summary
# # ═══════════════════════════════════════════════════════════════════════════════
# @router.get("/{mmsi}/day-summary", summary="Day-by-day activity summary with distance estimate")
# def day_summary(
#     mmsi:  int,
#     db:    Session  = Depends(get_db),
#     start: Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-01T00:00:00"),
#     end:   Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-07T23:59:59"),
#     limit: int           = Query(5000, description="Max daily rows to return (default 5000)"),
# ):
#     """
#     Returns daily statistics for a vessel over the full tracking window.

#     Each day includes:
#       - ping count
#       - average & max speed
#       - estimated distance in nautical miles
#       - bounding box (min/max lat/lon) for map zoom

#     Use start/end to narrow date window (same as /history).
#     """
#     filters = ["mmsi = :mmsi"]
#     params: dict = {"mmsi": mmsi, "limit": limit}

#     if start:
#         filters.append("base_date_time >= :start")
#         params["start"] = start
#     if end:
#         filters.append("base_date_time <= :end")
#         params["end"] = end

#     where = " AND ".join(filters)

#     result = db.execute(text(f"""
#         SELECT
#             base_date_time::date                  AS date,
#             COUNT(*)                              AS pings,
#             ROUND(AVG(sog)::numeric, 2)           AS avg_sog,
#             ROUND(MAX(sog)::numeric, 2)           AS max_sog,
#             ROUND(MIN(latitude)::numeric,  4)     AS min_lat,
#             ROUND(MAX(latitude)::numeric,  4)     AS max_lat,
#             ROUND(MIN(longitude)::numeric, 4)     AS min_lon,
#             ROUND(MAX(longitude)::numeric, 4)     AS max_lon
#         FROM ais_data
#         WHERE {where}
#         GROUP BY 1
#         ORDER BY 1 ASC
#         LIMIT :limit
#     """), params)

#     rows = result.mappings().all()
#     if not rows:
#         raise HTTPException(status_code=404, detail=f"No data for MMSI {mmsi}")

#     # Estimate daily distance using avg_speed × active hours (pings × 10min intervals)
#     days = []
#     for r in rows:
#         r = dict(r)
#         hours_active  = r["pings"] / 6
#         distance_nm   = round(float(r["avg_sog"]) * hours_active, 1)
#         r["distance_nm"] = distance_nm
#         days.append(r)

#     vessel_name   = _get_vessel_name(db, mmsi)
#     total_dist    = round(sum(d["distance_nm"] for d in days), 1)
#     total_pings   = sum(d["pings"] for d in days)

#     return {
#         "mmsi":              mmsi,
#         "vessel_name":       vessel_name,
#         "filter":            {"start": start, "end": end},
#         "total_days":        len(days),
#         "total_pings":       total_pings,
#         "total_distance_nm": total_dist,
#         "days":              days,
#     }


# # ── Helper ────────────────────────────────────────────────────────────────────
# def _get_vessel_name(db: Session, mmsi: int) -> str:
#     """Fetch vessel name for a given MMSI."""
#     result = db.execute(text(
#         "SELECT MAX(vessel_name) AS n FROM ais_data WHERE mmsi = :mmsi"
#     ), {"mmsi": mmsi})
#     row = result.mappings().one_or_none()
#     return (row["n"] or str(mmsi)) if row else str(mmsi)


# app/vessel_tracking/tracking.py
"""
Vessel Tracking router — thin layer.

Each route does exactly three things:
  1. Validate / coerce inputs (FastAPI handles this via Query params)
  2. Call the corresponding service function
  3. Return the result or raise HTTPException

Zero business logic here — all of that lives in service.py.
Reuses the shared app/database.py engine via get_db dependency.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db                     # ← shared connection pool
from app.vessel_tracking import service as svc
from app.vessel_tracking.constants import (
    LIVE_DEFAULT_LIMIT, LIVE_MAX_LIMIT,
    HISTORY_DEFAULT_LIMIT, HISTORY_MAX_LIMIT,
    SEARCH_DEFAULT_LIMIT, SEARCH_MAX_LIMIT,
)

logger = logging.getLogger("vessel_tracking.routes")
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# 1. LIVE POSITIONS
# GET /api/tracking/live
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/live", summary="Live positions of all vessels for map rendering")
def live_positions(
    db:          Session        = Depends(get_db),
    limit:       int            = Query(LIVE_DEFAULT_LIMIT, ge=1, le=LIVE_MAX_LIMIT,
                                        description=f"Page size (default {LIVE_DEFAULT_LIMIT}, max {LIVE_MAX_LIMIT})"),
    offset:      int            = Query(0, ge=0, description="Pagination offset"),
    zone_name:   Optional[str]  = Query(None, description="Filter to vessels inside a named geofence zone"),
    min_speed:   Optional[float]= Query(None, ge=0, description="Min SOG filter (knots)"),
    max_speed:   Optional[float]= Query(None, ge=0, description="Max SOG filter (knots)"),
    vessel_type: Optional[str]  = Query(None, description="AIS vessel_type code e.g. '37.0'"),
    q:           Optional[str]  = Query(None, description="Vessel name or MMSI search keyword"),
):
    """
    Most recent AIS ping per vessel, enriched with:
    - vessel_category, design_speed from vessel_profiles
    - live engine_load, co2_kg_h, nox_kg_h, sox_kg_h from current SOG
    - alert_level: NORMAL / ELEVATED / HIGH / CRITICAL

    Paginate with limit/offset. Filter by zone, speed, or vessel type.
    """
    return svc.get_live_positions(
        db=db,
        limit=limit,
        offset=offset,
        zone_name=zone_name,
        min_speed=min_speed,
        max_speed=max_speed,
        vessel_type=vessel_type,
        q=q,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. SEARCH & FILTER
# GET /api/tracking/search
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/search", summary="Search and filter vessels by name, MMSI, type, speed")
def search_vessels(
    db:          Session       = Depends(get_db),
    q:           Optional[str] = Query(None, description="Vessel name or MMSI keyword"),
    vessel_type: Optional[str] = Query(None, description="Type e.g. Tanker, Cargo, Fishing"),
    min_speed:   float         = Query(0.0,  ge=0, description="Min average speed (knots)"),
    max_speed:   float         = Query(50.0, ge=0, description="Max average speed (knots)"),
    limit:       int           = Query(SEARCH_DEFAULT_LIMIT, ge=1, le=SEARCH_MAX_LIMIT),
):
    """
    Search by name or MMSI, filter by type and speed range.
    Results enriched with vessel_category and latest stored emissions.
    """
    return svc.search_vessels(
        db=db,
        q=q,
        vessel_type=vessel_type,
        min_speed=min_speed,
        max_speed=max_speed,
        limit=limit,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 3. POSITION HISTORY
# GET /api/tracking/{mmsi}/history
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/{mmsi}/history", summary="Full position history with Haversine distance + emissions")
def vessel_history(
    mmsi:  int,
    db:    Session       = Depends(get_db),
    start: Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-01T00:00:00"),
    end:   Optional[str] = Query(None, description="ISO8601 e.g. 2024-01-07T23:59:59"),
    limit: int           = Query(HISTORY_DEFAULT_LIMIT, ge=1, le=HISTORY_MAX_LIMIT),
):
    """
    Time-ordered track points with per-point:
    - segment_nm and cumulative_nm (Haversine)
    - co2_kg_h, nox_kg_h, sox_kg_h, engine_load
    """
    result = svc.get_vessel_history(db=db, mmsi=mmsi, start=start, end=end, limit=limit)
    if result is None:
        raise HTTPException(404, f"No AIS data found for MMSI {mmsi}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 4. SPEED PROFILE
# GET /api/tracking/{mmsi}/speed-profile
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/{mmsi}/speed-profile", summary="Hourly average speed with percentile stats")
def speed_profile(
    mmsi:  int,
    db:    Session       = Depends(get_db),
    start: Optional[str] = Query(None, description="ISO8601 start"),
    end:   Optional[str] = Query(None, description="ISO8601 end"),
    limit: int           = Query(5000, ge=1, le=50000),
):
    """
    Hourly SOG buckets with avg, max, p50, p90, idle%, vs design speed, CO₂.
    """
    result = svc.get_speed_profile(db=db, mmsi=mmsi, start=start, end=end, limit=limit)
    if result is None:
        raise HTTPException(404, f"No speed data for MMSI {mmsi}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 5. DAY SUMMARY
# GET /api/tracking/{mmsi}/day-summary
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/{mmsi}/day-summary", summary="Day-by-day activity summary with distance and emissions")
def day_summary(
    mmsi:  int,
    db:    Session       = Depends(get_db),
    start: Optional[str] = Query(None, description="ISO8601 start"),
    end:   Optional[str] = Query(None, description="ISO8601 end"),
    limit: int           = Query(365, ge=1, le=1825, description="Max days (default 365 = 1 year)"),
):
    """
    Per-day: active/idle hours, Haversine distance, CO₂/NOx/SOx totals, bounding box.
    """
    result = svc.get_day_summary(db=db, mmsi=mmsi, start=start, end=end, limit=limit)
    if result is None:
        raise HTTPException(404, f"No data for MMSI {mmsi}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. VESSEL SNAPSHOT  (new)
# GET /api/tracking/{mmsi}/profile
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/{mmsi}/profile", summary="Full vessel snapshot — AIS + engine profile + live emissions")
def vessel_snapshot(
    mmsi: int,
    db:   Session = Depends(get_db),
):
    """
    Single-call panel data combining:
    - Latest AIS identity + position
    - Engine profile from vessel_profiles
    - Live computed emissions from current SOG
    - Latest stored emissions from emissions table
    - Alert level

    Ideal for vessel detail panel / map popup.
    """
    result = svc.get_vessel_snapshot(db=db, mmsi=mmsi)
    if result is None:
        raise HTTPException(404, f"No AIS data found for MMSI {mmsi}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 7. EMISSION TRACK  (new)
# GET /api/tracking/{mmsi}/emission-track
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/{mmsi}/emission-track",
            summary="Per-point CO₂/NOx/SOx along the vessel track for map colour-coding")
def emission_track(
    mmsi:  int,
    db:    Session       = Depends(get_db),
    start: Optional[str] = Query(None, description="ISO8601 start"),
    end:   Optional[str] = Query(None, description="ISO8601 end"),
    limit: int           = Query(2000, ge=1, le=10000),
):
    """
    Every track point with instantaneous CO₂/NOx/SOx + cumulative_co2_kg.
    Use to colour-code the map track line by emission intensity.
    """
    result = svc.get_emission_track(db=db, mmsi=mmsi, start=start, end=end, limit=limit)
    if result is None:
        raise HTTPException(404, f"No track data for MMSI {mmsi}")
    return result