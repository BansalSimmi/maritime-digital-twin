# app/vessel_tracking/service.py
"""
All database queries for vessel tracking live here.
No FastAPI types (Request, Query, HTTPException) — pure SQLAlchemy.
Routes call these functions; functions are independently testable.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.vessel_tracking.utils import (
    calc_emissions,
    emission_alert_level,
    haversine_nm,
    default_profile,
)
from app.vessel_tracking.constants import (
    DEFAULT_DESIGN_SPEED, DEFAULT_MCR_KW, DEFAULT_SFC,
)

logger = logging.getLogger("vessel_tracking.service")

# ── Profile helper ──────────────────────────────────────────────────────────

def get_vessel_profile(db: Session, vessel_type_code: Optional[str]) -> dict:
    """
    Look up engine profile from vessel_profiles by AIS type code.
    Falls back to 'default' row, then to hard-coded constants.

    vessel_profiles.vessel_type_code stores values WITH .0 suffix
    (e.g. '37.0', '70.0') matching ais_data.vessel_type exactly.
    """
    code = vessel_type_code or "0"

    row = db.execute(
        text("""
            SELECT vessel_category, design_speed, mcr_kw, sfc
            FROM   vessel_profiles
            WHERE  vessel_type_code = :code
        """),
        {"code": code},
    ).mappings().one_or_none()

    if not row:
        row = db.execute(
            text("""
                SELECT vessel_category, design_speed, mcr_kw, sfc
                FROM   vessel_profiles
                WHERE  vessel_type_code = 'default'
            """)
        ).mappings().one_or_none()

    return dict(row) if row else default_profile()


def get_vessel_name(db: Session, mmsi: int) -> str:
    row = db.execute(
        text("SELECT MAX(vessel_name) AS n FROM ais_data WHERE mmsi = :m"),
        {"m": mmsi},
    ).mappings().one_or_none()
    return (row["n"] or str(mmsi)) if row else str(mmsi)


# ── 1. LIVE POSITIONS ───────────────────────────────────────────────────────

def get_live_positions(
    db:          Session,
    limit:       int,
    offset:      int,
    zone_name:   Optional[str],
    min_speed:   Optional[float],
    max_speed:   Optional[float],
    vessel_type: Optional[str],
    q:           Optional[str] = None,
) -> dict:
    """
    Latest AIS fix per vessel, enriched with vessel_profiles data
    and live emission estimate from current SOG.
    Optionally filters to vessels inside a PostGIS geofence zone.
    """
    # Build WHERE clauses dynamically
    speed_where = ""
    type_where  = ""
    params: dict = {
        "limit":  limit,
        "offset": offset,
        "ds":     DEFAULT_DESIGN_SPEED,
        "mcr":    DEFAULT_MCR_KW,
        "sfc":    DEFAULT_SFC,
    }

    if min_speed is not None:
        speed_where += " AND a.sog >= :min_speed"
        params["min_speed"] = min_speed
    if max_speed is not None:
        speed_where += " AND a.sog <= :max_speed"
        params["max_speed"] = max_speed
    if vessel_type:
        type_where = " AND a.vessel_type = :vessel_type"
        params["vessel_type"] = vessel_type

    # Search filter (name or mmsi)
    search_where = ""
    if q:
        search_where = " AND (LOWER(a.vessel_name) LIKE :q OR CAST(a.mmsi AS TEXT) LIKE :q)"
        params["q"] = f"%{q.lower()}%"

    # PostGIS zone join (only when zone_name is provided)
    zone_join = ""
    if zone_name:
        zone_join = """
            JOIN geofence_zones gz
              ON LOWER(gz.zone_name) = LOWER(:zone_name)
             AND ST_Contains(
                     gz.polygon,
                     ST_SetSRID(ST_MakePoint(a.longitude, a.latitude), 4326)
                 )
        """
        params["zone_name"] = zone_name

    rows = db.execute(text(f"""
        SELECT
            a.mmsi,
            a.vessel_name,
            a.vessel_type,
            COALESCE(vp.vessel_category, 'Unknown')    AS vessel_category,
            a.latitude,
            a.longitude,
            a.sog,
            a.cog,
            a.heading,
            a.base_date_time                           AS last_seen,
            COALESCE(vp.design_speed, :ds)             AS design_speed,
            COALESCE(vp.mcr_kw,       :mcr)            AS mcr_kw,
            COALESCE(vp.sfc,          :sfc)             AS sfc,
            e.co2_emission                             AS stored_co2_kg_h,
            e.engine_load                              AS stored_engine_load
        FROM latest_vessel_positions a
        {zone_join}
        LEFT JOIN vessel_profiles vp
               ON vp.vessel_type_code = COALESCE(a.vessel_type, '0')
        LEFT JOIN emissions e
               ON e.mmsi = a.mmsi
        WHERE 1 = 1
          {speed_where}
          {type_where}
          {search_where}
        ORDER BY a.mmsi
        LIMIT  :limit
        OFFSET :offset
    """), params).mappings().all()

    # ── Count total matching vessels (ignoring LIMIT/OFFSET) ──────────────────
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total_count = db.execute(text(f"""
        SELECT COUNT(*) AS cnt
        FROM latest_vessel_positions a
        WHERE 1 = 1
          {speed_where}
          {type_where}
          {search_where}
    """), count_params).scalar() or 0

    positions = []
    for r in rows:
        d   = dict(r)
        sog = float(d.get("sog") or 0)
        em  = calc_emissions(sog, float(d["mcr_kw"]), float(d["sfc"]), float(d["design_speed"]))
        d.update(em)
        d["alert_level"] = emission_alert_level(em["co2_kg_h"])
        # Remove internal profile fields from response — keep it clean
        for k in ("design_speed", "mcr_kw", "sfc"):
            d.pop(k, None)
        positions.append(d)

    return {
        "total_vessels": int(total_count),
        "limit":         limit,
        "offset":        offset,
        "zone_filter":   zone_name,
        "positions":     positions,
    }


# ── 2. SEARCH ───────────────────────────────────────────────────────────────

def search_vessels(
    db:          Session,
    q:           Optional[str],
    vessel_type: Optional[str],
    min_speed:   float,
    max_speed:   float,
    limit:       int,
) -> dict:
    filters = ["a.mmsi IS NOT NULL"]
    params: dict = {"min_speed": min_speed, "max_speed": max_speed, "limit": limit}

    if q:
        filters.append("(LOWER(a.vessel_name) LIKE :q OR CAST(a.mmsi AS TEXT) LIKE :q)")
        params["q"] = f"%{q.lower()}%"

    if vessel_type:
        filters.append("LOWER(COALESCE(vp.vessel_category, a.vessel_type)) LIKE :vtype")
        params["vtype"] = f"%{vessel_type.lower()}%"

    where = " AND ".join(filters)

    rows = db.execute(text(f"""
        SELECT
            a.mmsi,
            MAX(a.vessel_name)                          AS vessel_name,
            MAX(a.vessel_type)                          AS vessel_type,
            MAX(vp.vessel_category)                     AS vessel_category,
            MAX(a.imo)                                  AS imo,
            COUNT(*)                                    AS total_pings,
            ROUND(AVG(a.sog)::numeric, 2)               AS avg_speed_kn,
            ROUND(MAX(a.sog)::numeric, 2)               AS max_speed_kn,
            MAX(a.base_date_time)                       AS last_seen,
            -- latest stored emission values
            MAX(e.co2_emission)                         AS co2_kg_h,
            MAX(e.nox_emission)                         AS nox_kg_h,
            MAX(e.sox_emission)                         AS sox_kg_h,
            MAX(e.engine_load)                          AS engine_load,
            MAX(vp.design_speed)                        AS design_speed
        FROM  ais_data a
        LEFT JOIN vessel_profiles vp
               ON vp.vessel_type_code = COALESCE(a.vessel_type, '0')
        LEFT JOIN emissions e
               ON e.mmsi = a.mmsi
        WHERE {where}
        GROUP BY a.mmsi
        HAVING AVG(a.sog) BETWEEN :min_speed AND :max_speed
        ORDER BY last_seen DESC
        LIMIT :limit
    """), params).mappings().all()

    return {
        "count":   len(rows),
        "query":   q,
        "filters": {"vessel_type": vessel_type, "min_speed": min_speed, "max_speed": max_speed},
        "results": [dict(r) for r in rows],
    }


# ── 3. HISTORY ──────────────────────────────────────────────────────────────

def get_vessel_history(
    db:    Session,
    mmsi:  int,
    start: Optional[str],
    end:   Optional[str],
    limit: int,
) -> dict:
    filters = [
        "a.mmsi      = :mmsi",
        "a.latitude  IS NOT NULL",
        "a.longitude IS NOT NULL",
    ]
    params: dict = {
        "mmsi":  mmsi,
        "limit": limit,
        "ds":    DEFAULT_DESIGN_SPEED,
        "mcr":   DEFAULT_MCR_KW,
        "sfc":   DEFAULT_SFC,
    }
    if start:
        filters.append("a.base_date_time >= :start")
        params["start"] = start
    if end:
        filters.append("a.base_date_time <= :end")
        params["end"] = end

    where = " AND ".join(filters)

    rows = db.execute(text(f"""
        SELECT
            a.base_date_time                           AS timestamp,
            a.latitude,
            a.longitude,
            a.sog,
            a.cog,
            a.heading,
            COALESCE(vp.design_speed, :ds)             AS design_speed,
            COALESCE(vp.mcr_kw,       :mcr)            AS mcr_kw,
            COALESCE(vp.sfc,          :sfc)             AS sfc
        FROM  ais_data a
        LEFT JOIN vessel_profiles vp
               ON vp.vessel_type_code = COALESCE(a.vessel_type, '0')
        WHERE {where}
        ORDER BY a.base_date_time ASC
        LIMIT :limit
    """), params).mappings().all()

    if not rows:
        return None  # caller raises 404

    vessel_name   = get_vessel_name(db, mmsi)
    points        = []
    cumulative_nm = 0.0
    total_co2     = total_nox = total_sox = 0.0
    prev_lat = prev_lon = None

    for r in rows:
        d   = dict(r)
        sog = float(d.get("sog") or 0)
        lat = float(d["latitude"])
        lon = float(d["longitude"])

        seg_nm = haversine_nm(prev_lat, prev_lon, lat, lon) if prev_lat is not None else 0.0
        cumulative_nm += seg_nm

        em = calc_emissions(sog, float(d["mcr_kw"]), float(d["sfc"]), float(d["design_speed"]))
        total_co2 += em["co2_kg_h"]
        total_nox += em["nox_kg_h"]
        total_sox += em["sox_kg_h"]

        points.append({
            "timestamp":     d["timestamp"],
            "latitude":      lat,
            "longitude":     lon,
            "sog":           sog,
            "cog":           d.get("cog"),
            "heading":       d.get("heading"),
            "segment_nm":    round(seg_nm, 3),
            "cumulative_nm": round(cumulative_nm, 3),
            **em,
        })
        prev_lat, prev_lon = lat, lon

    return {
        "mmsi":              mmsi,
        "vessel_name":       vessel_name,
        "total_points":      len(points),
        "total_distance_nm": round(cumulative_nm, 2),
        "total_co2_kg":      round(total_co2, 2),
        "total_nox_kg":      round(total_nox, 2),
        "total_sox_kg":      round(total_sox, 2),
        "filter":            {"start": start, "end": end},
        "points":            points,
    }


# ── 4. SPEED PROFILE ────────────────────────────────────────────────────────

def get_speed_profile(
    db:    Session,
    mmsi:  int,
    start: Optional[str],
    end:   Optional[str],
    limit: int,
) -> dict:
    filters = ["a.mmsi = :mmsi", "a.sog IS NOT NULL"]
    params: dict = {
        "mmsi":  mmsi,
        "limit": limit,
        "ds":    DEFAULT_DESIGN_SPEED,
        "mcr":   DEFAULT_MCR_KW,
        "sfc":   DEFAULT_SFC,
    }
    if start:
        filters.append("a.base_date_time >= :start")
        params["start"] = start
    if end:
        filters.append("a.base_date_time <= :end")
        params["end"] = end

    where = " AND ".join(filters)

    rows = db.execute(text(f"""
        SELECT
            DATE_TRUNC('hour', a.base_date_time)         AS hour,
            ROUND(AVG(a.sog)::numeric, 2)                AS avg_sog,
            ROUND(MAX(a.sog)::numeric, 2)                AS max_sog,
            ROUND(PERCENTILE_CONT(0.5)
                  WITHIN GROUP (ORDER BY a.sog)::numeric, 2)  AS p50_sog,
            ROUND(PERCENTILE_CONT(0.9)
                  WITHIN GROUP (ORDER BY a.sog)::numeric, 2)  AS p90_sog,
            COUNT(*)                                      AS pings,
            COUNT(*) FILTER (WHERE a.sog < 1.0)           AS idle_pings,
            MAX(COALESCE(vp.design_speed, :ds))           AS design_speed,
            MAX(COALESCE(vp.mcr_kw,       :mcr))          AS mcr_kw,
            MAX(COALESCE(vp.sfc,          :sfc))           AS sfc
        FROM  ais_data a
        LEFT JOIN vessel_profiles vp
               ON vp.vessel_type_code = COALESCE(a.vessel_type, '0')
        WHERE {where}
        GROUP BY 1
        ORDER BY 1 ASC
        LIMIT :limit
    """), params).mappings().all()

    if not rows:
        return None

    vessel_name = get_vessel_name(db, mmsi)
    profile     = []

    for r in rows:
        d          = dict(r)
        avg_sog    = float(d["avg_sog"])
        design_spd = float(d["design_speed"])
        pings      = int(d["pings"])
        idle       = int(d["idle_pings"])
        em         = calc_emissions(avg_sog, float(d["mcr_kw"]), float(d["sfc"]), design_spd)

        profile.append({
            "hour":             d["hour"],
            "avg_sog":          avg_sog,
            "max_sog":          float(d["max_sog"]),
            "p50_sog":          float(d["p50_sog"]),
            "p90_sog":          float(d["p90_sog"]),
            "pings":            pings,
            "idle_pct":         round(idle / pings * 100, 1) if pings else 0,
            "vs_design_speed_pct": round(avg_sog / design_spd * 100, 1) if design_spd else None,
            "co2_kg_h":         em["co2_kg_h"],
            "engine_load":      em["engine_load"],
        })

    all_avgs = [p["avg_sog"] for p in profile]
    return {
        "mmsi":         mmsi,
        "vessel_name":  vessel_name,
        "total_hours":  len(profile),
        "avg_speed_kn": round(sum(all_avgs) / len(all_avgs), 2),
        "max_speed_kn": round(max(all_avgs), 2),
        "idle_hours":   sum(1 for p in profile if p["idle_pct"] > 50),
        "filter":       {"start": start, "end": end},
        "profile":      profile,
    }


# ── 5. DAY SUMMARY ──────────────────────────────────────────────────────────

def get_day_summary(
    db:    Session,
    mmsi:  int,
    start: Optional[str],
    end:   Optional[str],
    limit: int,
) -> dict:
    filters = ["a.mmsi = :mmsi"]
    params: dict = {
        "mmsi":  mmsi,
        "limit": limit,
        "ds":    DEFAULT_DESIGN_SPEED,
        "mcr":   DEFAULT_MCR_KW,
        "sfc":   DEFAULT_SFC,
    }
    if start:
        filters.append("a.base_date_time >= :start")
        params["start"] = start
    if end:
        filters.append("a.base_date_time <= :end")
        params["end"] = end

    where = " AND ".join(filters)

    rows = db.execute(text(f"""
        SELECT
            a.base_date_time::date                        AS date,
            COUNT(*)                                      AS pings,
            ROUND(AVG(a.sog)::numeric, 2)                 AS avg_sog,
            ROUND(MAX(a.sog)::numeric, 2)                 AS max_sog,
            COUNT(*) FILTER (WHERE a.sog >= 1.0)          AS active_pings,
            COUNT(*) FILTER (WHERE a.sog < 1.0)           AS idle_pings,
            ROUND(MIN(a.latitude)::numeric,  4)           AS min_lat,
            ROUND(MAX(a.latitude)::numeric,  4)           AS max_lat,
            ROUND(MIN(a.longitude)::numeric, 4)           AS min_lon,
            ROUND(MAX(a.longitude)::numeric, 4)           AS max_lon,
            MAX(COALESCE(vp.design_speed, :ds))           AS design_speed,
            MAX(COALESCE(vp.mcr_kw,       :mcr))          AS mcr_kw,
            MAX(COALESCE(vp.sfc,          :sfc))           AS sfc,
            MAX(COALESCE(vp.vessel_category, 'Unknown'))  AS vessel_category
        FROM  ais_data a
        LEFT JOIN vessel_profiles vp
               ON vp.vessel_type_code = COALESCE(a.vessel_type, '0')
        WHERE {where}
        GROUP BY 1
        ORDER BY 1 ASC
        LIMIT :limit
    """), params).mappings().all()

    if not rows:
        return None

    vessel_name = get_vessel_name(db, mmsi)
    days        = []
    total_dist = total_co2 = total_nox = total_sox = 0.0

    for r in rows:
        d            = dict(r)
        avg_sog      = float(d["avg_sog"])
        active_pings = int(d["active_pings"])
        idle_pings   = int(d["idle_pings"])
        # Each AIS ping ≈ 10-min interval → hours
        active_hours = round(active_pings / 6, 2)
        idle_hours   = round(idle_pings   / 6, 2)

        distance_nm  = round(avg_sog * active_hours, 1)
        total_dist  += distance_nm

        em          = calc_emissions(avg_sog, float(d["mcr_kw"]), float(d["sfc"]), float(d["design_speed"]))
        co2_day     = round(em["co2_kg_h"] * active_hours, 2)
        nox_day     = round(em["nox_kg_h"] * active_hours, 2)
        sox_day     = round(em["sox_kg_h"] * active_hours, 2)
        total_co2  += co2_day
        total_nox  += nox_day
        total_sox  += sox_day

        days.append({
            "date":             str(d["date"]),
            "pings":            int(d["pings"]),
            "avg_sog":          avg_sog,
            "max_sog":          float(d["max_sog"]),
            "active_hours":     active_hours,
            "idle_hours":       idle_hours,
            "distance_nm":      distance_nm,
            "co2_kg":           co2_day,
            "nox_kg":           nox_day,
            "sox_kg":           sox_day,
            "engine_load":      em["engine_load"],
            "vessel_category":  d["vessel_category"],
            "bounding_box": {
                "min_lat": d["min_lat"], "max_lat": d["max_lat"],
                "min_lon": d["min_lon"], "max_lon": d["max_lon"],
            },
        })

    return {
        "mmsi":               mmsi,
        "vessel_name":        vessel_name,
        "total_days":         len(days),
        "total_distance_nm":  round(total_dist, 2),
        "total_co2_kg":       round(total_co2, 2),
        "total_nox_kg":       round(total_nox, 2),
        "total_sox_kg":       round(total_sox, 2),
        "filter":             {"start": start, "end": end},
        "days":               days,
    }


# ── 6. VESSEL PROFILE SNAPSHOT ──────────────────────────────────────────────

def get_vessel_snapshot(db: Session, mmsi: int) -> dict:
    ais = db.execute(text("""
        SELECT DISTINCT ON (mmsi)
            mmsi, vessel_name, imo, call_sign,
            vessel_type, status,
            length, width, draft,
            latitude, longitude,
            sog, cog, heading,
            base_date_time AS last_seen
        FROM  ais_data
        WHERE mmsi = :mmsi
        ORDER BY mmsi, base_date_time DESC
    """), {"mmsi": mmsi}).mappings().one_or_none()

    if not ais:
        return None

    ais     = dict(ais)
    profile = get_vessel_profile(db, ais.get("vessel_type"))

    stored_em = db.execute(text("""
        SELECT co2_emission, nox_emission, sox_emission,
               fuel_consumption, engine_load, calculated_at
        FROM   emissions
        WHERE  mmsi = :mmsi
    """), {"mmsi": mmsi}).mappings().one_or_none()

    live_em = calc_emissions(
        float(ais.get("sog") or 0),
        profile["mcr_kw"],
        profile["sfc"],
        profile["design_speed"],
    )

    return {
        "mmsi": mmsi,
        "ais": {
            "vessel_name": ais.get("vessel_name"),
            "imo":         ais.get("imo"),
            "call_sign":   ais.get("call_sign"),
            "vessel_type": ais.get("vessel_type"),
            "status":      ais.get("status"),
            "dimensions":  {
                "length": ais.get("length"),
                "width":  ais.get("width"),
                "draft":  ais.get("draft"),
            },
            "position": {
                "latitude":  ais.get("latitude"),
                "longitude": ais.get("longitude"),
                "sog":       ais.get("sog"),
                "cog":       ais.get("cog"),
                "heading":   ais.get("heading"),
            },
            "last_seen": ais.get("last_seen"),
        },
        "engine_profile": {
            "vessel_category": profile["vessel_category"],
            "design_speed_kn": profile["design_speed"],
            "mcr_kw":          profile["mcr_kw"],
            "sfc_kg_kwh":      profile["sfc"],
        },
        "live_emissions":   live_em,
        "alert_level":      emission_alert_level(live_em["co2_kg_h"]),
        "stored_emissions": dict(stored_em) if stored_em else None,
    }


# ── 7. EMISSION TRACK ───────────────────────────────────────────────────────

def get_emission_track(
    db:    Session,
    mmsi:  int,
    start: Optional[str],
    end:   Optional[str],
    limit: int,
) -> dict:
    filters = [
        "a.mmsi      = :mmsi",
        "a.latitude  IS NOT NULL",
        "a.longitude IS NOT NULL",
    ]
    params: dict = {
        "mmsi":  mmsi,
        "limit": limit,
        "ds":    DEFAULT_DESIGN_SPEED,
        "mcr":   DEFAULT_MCR_KW,
        "sfc":   DEFAULT_SFC,
    }
    if start:
        filters.append("a.base_date_time >= :start")
        params["start"] = start
    if end:
        filters.append("a.base_date_time <= :end")
        params["end"] = end

    where = " AND ".join(filters)

    rows = db.execute(text(f"""
        SELECT
            a.base_date_time                           AS timestamp,
            a.latitude,
            a.longitude,
            a.sog,
            COALESCE(vp.design_speed, :ds)             AS design_speed,
            COALESCE(vp.mcr_kw,       :mcr)            AS mcr_kw,
            COALESCE(vp.sfc,          :sfc)             AS sfc
        FROM  ais_data a
        LEFT JOIN vessel_profiles vp
               ON vp.vessel_type_code = COALESCE(a.vessel_type, '0')
        WHERE {where}
        ORDER BY a.base_date_time ASC
        LIMIT :limit
    """), params).mappings().all()

    if not rows:
        return None

    vessel_name    = get_vessel_name(db, mmsi)
    track          = []
    cumulative_co2 = 0.0

    for r in rows:
        d   = dict(r)
        sog = float(d.get("sog") or 0)
        em  = calc_emissions(sog, float(d["mcr_kw"]), float(d["sfc"]), float(d["design_speed"]))
        cumulative_co2 += em["co2_kg_h"]

        track.append({
            "timestamp":         d["timestamp"],
            "latitude":          float(d["latitude"]),
            "longitude":         float(d["longitude"]),
            "sog":               sog,
            "co2_kg_h":          em["co2_kg_h"],
            "nox_kg_h":          em["nox_kg_h"],
            "sox_kg_h":          em["sox_kg_h"],
            "engine_load":       em["engine_load"],
            "cumulative_co2_kg": round(cumulative_co2, 2),
        })

    return {
        "mmsi":         mmsi,
        "vessel_name":  vessel_name,
        "total_points": len(track),
        "total_co2_kg": round(cumulative_co2, 2),
        "filter":       {"start": start, "end": end},
        "track":        track,
    }