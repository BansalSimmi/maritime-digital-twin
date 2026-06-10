"""
digital_twin/service.py
=======================
All ClickHouse queries and business logic.

NEW ENDPOINTS (v4):
  get_all_vessels()      → latest state for ALL vessels (for map display)
  get_vessels_in_area()  → latest state for vessels within a bounding box

Both read only worker rows (simulation_scenario != '') so they never
return seed row zeros. They use argMax per mmsi to get the single
latest simulation row per vessel.

Your digital_twin/service.py is the core business logic layer of the Digital Twin module.
It sits between the API routes and the ClickHouse database and handles:

Querying vessel data from ClickHouse
Running simulations
Converting database rows → API response models
Inserting new simulation results

Think of the architecture like this:
FastAPI Routes
      ↓
service.py  (business logic + ClickHouse queries)
      ↓
ClickHouse DB
"""

import json
import logging
from datetime import datetime, timezone
"""
| Module   | Purpose                                 |
| -------- | --------------------------------------- |
| json     | Convert predicted routes stored as JSON |
| logging  | Log system activity                     |
| datetime | Track simulation timestamps             |

"""
# These are constants used by the simulation:
from .config import (
    DT_TABLE,
    DT_COLUMNS,
    SIMULATION_MINUTES,
    SIMULATION_STEP_MIN,
    MIN_MOVING_SPEED,
    DEFAULT_SPEED_KNOTS,
    DEFAULT_HEADING_DEG,
)
"""
| Constant              | Meaning                          |
| --------------------- | -------------------------------- |
| `SIMULATION_MINUTES`  | how far ahead simulation runs    |
| `SIMULATION_STEP_MIN` | simulation step interval         |
| `MIN_MOVING_SPEED`    | threshold for stationary vessels |
| `DEFAULT_SPEED_KNOTS` | fallback speed                   |
| `DEFAULT_HEADING_DEG` | fallback direction               |

"""

# These are Pydantic models used for validation and API responses.
"""
| Model                | Purpose                |
| -------------------- | ---------------------- |
| `VesselState`        | internal vessel state  |
| `FullTwinRow`        | full simulation row    |
| `TwinStateResponse`  | API response           |
| `VesselSummary`      | lightweight map vessel |
| `AllVesselsResponse` | paginated vessel list  |
"""
from .schemas import (
    VesselState,
    FullTwinRow,
    TwinStateResponse,
    SimulationResponse,
    RefreshResponse,
    RouteWaypoint,
    AllVesselsResponse,
    VesselSummary,
)
from .simulation_engine import build_full_row  #This function runs the vessel movement simulation and returns a new FullTwinRow.

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# SHARED HELPER — build TwinStateResponse from a DB row tuple
# ─────────────────────────────────────────────
# Convert database row → API response object
def _row_to_twin_state(r: tuple) -> TwinStateResponse: 
    """
    Convert a 12-column DB row → TwinStateResponse.
    r = (mmsi, lat, lon, speed, heading, last_update,
         sim_lat, sim_lon, sim_speed, predicted_route,
         simulation_scenario, simulation_time)
    """
    # Step 1 — detect seed rows
    is_seeded_only = (r[10] == "" or r[10] is None) 
   #Seed rows = initial data before simulation. --> So simulated values should be hidden. 
#     Step 2 — parse predicted route JSON --> Database stores route as JSON string: "[{minute:0,lat:..,lon:..}, ...]"
      # Convert to Python objects: route = [RouteWaypoint(**wp) for wp in route_data]
    try:
        route_data = json.loads(r[9]) if r[9] else []
        route      = [RouteWaypoint(**wp) for wp in route_data]
    except (json.JSONDecodeError, TypeError, KeyError):
        route = []

    def _real_float(val):
        return float(val) if val is not None else None  #Convert DB values safely.

    def _sim_float(val):
        if is_seeded_only:
            return None
        return float(val) if val is not None else None  #Return simulated value only if not seed row.


# Step 4 — build response
# Returns:TwinStateResponse
# Used by API endpoint:GET /digital-twin/state/{mmsi}
    return TwinStateResponse(
        mmsi                = r[0],
        latitude            = r[1],
        longitude           = r[2],
        current_speed       = _real_float(r[3]),
        current_heading     = _real_float(r[4]),
        last_update         = r[5] if r[5] else None,
        simulated_latitude  = _sim_float(r[6]),
        simulated_longitude = _sim_float(r[7]),
        simulated_speed     = _sim_float(r[8]),
        predicted_route     = route if not is_seeded_only else [],
        simulation_scenario = r[10] if r[10] else None,
        simulation_time     = r[11] if r[11] else None,
    )


# ─────────────────────────────────────────────
# GET TWIN STATE  (one vessel — latest row)
# ─────────────────────────────────────────────

def get_twin_state(client, mmsi: int) -> TwinStateResponse | dict:
    """
    Return the latest simulation row for one vessel.
    scenario='' → seed row → sim cols returned as None.
    scenario!='' → worker row → sim cols returned as real floats.
    """
    result = client.query(
        """
        SELECT
            mmsi, latitude, longitude, speed, heading, last_update,
            simulated_latitude, simulated_longitude, simulated_speed,
            predicted_route, simulation_scenario, simulation_time
        FROM digital_twin_state
        WHERE mmsi = {mmsi:Int64}
        ORDER BY simulation_time DESC
        LIMIT 1
        """,
        parameters={"mmsi": mmsi}
    )

    rows = result.result_rows
    if not rows:
        return {"error": f"Vessel {mmsi} not found"}

    return _row_to_twin_state(rows[0])


# ─────────────────────────────────────────────
# GET ALL VESSELS  (latest state for every vessel)
# ─────────────────────────────────────────────
# Purpose: Return latest simulation row for a vessel.
def get_all_vessels(
    client,
    limit:  int = 1000,
    offset: int = 0
) -> AllVesselsResponse:
    """
    Return the latest simulation row for ALL vessels.

    Used by the map frontend to display all ship positions at once.

    Only returns worker rows (simulation_scenario != '') — never seed zeros.
    Uses argMax(field, simulation_time) GROUP BY mmsi to get one row per vessel.

    Pagination via limit/offset to avoid returning 39,000 rows at once.
    Default: first 1000 vessels ordered by latest simulation_time.
    """
    # Total count of vessels with worker rows
    count_result = client.query("""
        SELECT count(DISTINCT mmsi)
        FROM digital_twin_state
        WHERE simulation_scenario != ''
    """)
    total = count_result.result_rows[0][0]

    result = client.query(f"""
        SELECT
            d.mmsi,
            d.latitude,
            d.longitude,
            d.speed,
            d.heading,
            d.last_update,
            d.simulated_latitude,
            d.simulated_longitude,
            d.simulated_speed,
            d.predicted_route,
            d.simulation_scenario,
            d.simulation_time
        FROM digital_twin_state d
        INNER JOIN (
            SELECT mmsi, max(simulation_time) AS max_st
            FROM digital_twin_state
            WHERE simulation_scenario != ''
            GROUP BY mmsi
        ) latest ON d.mmsi = latest.mmsi
                 AND d.simulation_time = latest.max_st
        WHERE d.simulation_scenario != ''
        ORDER BY d.simulation_time DESC
        LIMIT {limit}
        OFFSET {offset}
    """)

    vessels = []
    for r in result.result_rows:
        # Lightweight summary for map pins (no full route data)
        vessels.append(VesselSummary(
            mmsi                = r[0],
            latitude            = float(r[1]),
            longitude           = float(r[2]),
            current_speed       = float(r[3]) if r[3] is not None else None,
            current_heading     = float(r[4]) if r[4] is not None else None,
            last_update         = r[5] if r[5] else None,
            simulated_latitude  = float(r[6]) if r[6] is not None else None,
            simulated_longitude = float(r[7]) if r[7] is not None else None,
            simulated_speed     = float(r[8]) if r[8] is not None else None,
            simulation_scenario = r[10] if r[10] else None,
            simulation_time     = r[11] if r[11] else None,
        ))

    log.info(f"get_all_vessels: returned {len(vessels)} / {total} vessels")

    return AllVesselsResponse(
        total   = total,
        limit   = limit,
        offset  = offset,
        vessels = vessels,
    )


# ─────────────────────────────────────────────
# GET VESSELS IN AREA  (bounding box filter)
# ─────────────────────────────────────────────

def get_vessels_in_area(
    client,
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    limit:   int = 500,
) -> AllVesselsResponse:
    """
    Return latest simulation rows for vessels within a bounding box.

    Used by the map frontend to load only vessels visible in the current
    viewport — avoids sending all 39,000 vessels when zoomed in.

    Bounding box: (min_lat, min_lon) → (max_lat, max_lon)
    Filter applies to REAL latitude/longitude (current position),
    not simulated position.

    Example — vessels in the Gulf of Mexico:
        min_lat=18.0, max_lat=31.0, min_lon=-98.0, max_lon=-80.0
    """
    result = client.query(
        f"""
        SELECT
            d.mmsi,
            d.latitude,
            d.longitude,
            d.speed,
            d.heading,
            d.last_update,
            d.simulated_latitude,
            d.simulated_longitude,
            d.simulated_speed,
            d.predicted_route,
            d.simulation_scenario,
            d.simulation_time
        FROM digital_twin_state d
        INNER JOIN (
            SELECT mmsi, max(simulation_time) AS max_st
            FROM digital_twin_state
            WHERE simulation_scenario != ''
              AND latitude  BETWEEN {{min_lat:Float64}} AND {{max_lat:Float64}}
              AND longitude BETWEEN {{min_lon:Float64}} AND {{max_lon:Float64}}
            GROUP BY mmsi
        ) latest ON d.mmsi = latest.mmsi
                 AND d.simulation_time = latest.max_st
        WHERE d.simulation_scenario != ''
          AND d.latitude  BETWEEN {{min_lat:Float64}} AND {{max_lat:Float64}}
          AND d.longitude BETWEEN {{min_lon:Float64}} AND {{max_lon:Float64}}
        ORDER BY d.simulation_time DESC
        LIMIT {limit}
        """,
        parameters={
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon,
        }
    )

    # Count vessels in area
    count_result = client.query(
        """
        SELECT count(DISTINCT mmsi)
        FROM digital_twin_state
        WHERE simulation_scenario != ''
          AND latitude  BETWEEN {min_lat:Float64} AND {max_lat:Float64}
          AND longitude BETWEEN {min_lon:Float64} AND {max_lon:Float64}
        """,
        parameters={
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon,
        }
    )
    total = count_result.result_rows[0][0]

    vessels = []
    for r in result.result_rows:
        try:
            route_data = json.loads(r[9]) if r[9] else []
            route      = [RouteWaypoint(**wp) for wp in route_data]
        except (json.JSONDecodeError, TypeError, KeyError):
            route = []

        vessels.append(VesselSummary(
            mmsi                = r[0],
            latitude            = float(r[1]),
            longitude           = float(r[2]),
            current_speed       = float(r[3]) if r[3] is not None else None,
            current_heading     = float(r[4]) if r[4] is not None else None,
            last_update         = r[5] if r[5] else None,
            simulated_latitude  = float(r[6]) if r[6] is not None else None,
            simulated_longitude = float(r[7]) if r[7] is not None else None,
            simulated_speed     = float(r[8]) if r[8] is not None else None,
            simulation_scenario = r[10] if r[10] else None,
            simulation_time     = r[11] if r[11] else None,
        ))

    log.info(
        f"get_vessels_in_area: bbox=({min_lat},{min_lon})→({max_lat},{max_lon}) "
        f"returned {len(vessels)} / {total} vessels"
    )

    return AllVesselsResponse(
        total   = total,
        limit   = limit,
        offset  = 0,
        vessels = vessels,
    )


# ─────────────────────────────────────────────
# REFRESH AND SIMULATE  (worker cycle)
# ─────────────────────────────────────────────

def refresh_and_simulate(
    client,
    minutes: int = SIMULATION_MINUTES,
    step:    int = SIMULATION_STEP_MIN
) -> RefreshResponse:
    """
    Read latest real state for all vessels → simulate → append rows.
    Reads from ais_data (source of truth) not digital_twin_state.
    """
    result = client.query("""
        SELECT
            mmsi,
            argMax(latitude,  base_date_time) AS lat,
            argMax(longitude, base_date_time) AS lon,
            argMax(sog,       base_date_time) AS spd,
            argMax(cog,       base_date_time) AS hdg,
            max(base_date_time)               AS lu
        FROM (
            SELECT *
            FROM maritime_digital_twin.ais_data
            WHERE latitude  IS NOT NULL
              AND longitude  IS NOT NULL
              AND latitude  != 0
              AND longitude != 0
        )
        GROUP BY mmsi
    """)

    rows = result.result_rows
    if not rows:
        log.warning("refresh_and_simulate: no vessels found")
        return RefreshResponse(status="No vessels found", total=0)

    full_rows  = []
    skipped    = 0
    simulated  = 0

    for row in rows:
        mmsi, lat, lon, speed, heading, last_update = row
        speed = float(speed) if speed is not None else DEFAULT_SPEED_KNOTS

        if heading is None or (float(heading) == 0.0 and speed > MIN_MOVING_SPEED):
            heading = DEFAULT_HEADING_DEG
        else:
            heading = float(heading)

        vessel = VesselState(
            mmsi=int(mmsi), lat=float(lat), lon=float(lon),
            speed=speed, heading=heading, last_update=last_update
        )

        if speed < MIN_MOVING_SPEED:
            skipped += 1
            full_rows.append(FullTwinRow(
                mmsi=vessel.mmsi, latitude=vessel.lat, longitude=vessel.lon,
                speed=vessel.speed, heading=vessel.heading,
                last_update=vessel.last_update or datetime.now(timezone.utc),
                simulated_latitude=vessel.lat, simulated_longitude=vessel.lon,
                simulated_speed=0.0, predicted_route="[]",
                simulation_scenario="STATIONARY",
                simulation_time=datetime.now(timezone.utc)
            ))
        else:
            simulated += 1
            full_rows.append(build_full_row(vessel, "AUTO", minutes, step))

    _batch_insert(client, full_rows)
    log.info(f"refresh_and_simulate: total={len(rows)} simulated={simulated} stationary={skipped}")

    return RefreshResponse(
        status="OK", total=len(rows), simulated=simulated, skipped=skipped
    )


# ─────────────────────────────────────────────
# MANUAL SIMULATION  (one vessel, API-triggered)
# ─────────────────────────────────────────────

def run_simulation(
    client, mmsi: int, scenario: str,
    minutes: int = SIMULATION_MINUTES,
    step:    int = SIMULATION_STEP_MIN
) -> SimulationResponse | dict:
    result = client.query(
        """
        SELECT mmsi, latitude, longitude, speed, heading, last_update
        FROM digital_twin_state
        WHERE mmsi = {mmsi:Int64}
        ORDER BY simulation_time DESC
        LIMIT 1
        """,
        parameters={"mmsi": mmsi}
    )

    rows = result.result_rows
    if not rows:
        return {"error": f"Vessel {mmsi} not found"}

    r = rows[0]
    speed   = float(r[3]) if r[3] is not None else DEFAULT_SPEED_KNOTS
    heading = float(r[4]) if r[4] is not None else DEFAULT_HEADING_DEG
    if heading == 0.0 and speed > MIN_MOVING_SPEED:
        heading = DEFAULT_HEADING_DEG

    vessel = VesselState(
        mmsi=int(r[0]), lat=float(r[1]), lon=float(r[2]),
        speed=speed, heading=heading, last_update=r[5]
    )

    full_row = build_full_row(vessel, scenario, minutes, step)
    _batch_insert(client, [full_row])
    route = [RouteWaypoint(**wp) for wp in json.loads(full_row.predicted_route)]

    return SimulationResponse(
        mmsi=vessel.mmsi, scenario=scenario,
        current_latitude=vessel.lat, current_longitude=vessel.lon,
        current_speed=vessel.speed, current_heading=vessel.heading,
        simulated_latitude=full_row.simulated_latitude,
        simulated_longitude=full_row.simulated_longitude,
        simulated_speed=full_row.simulated_speed,
        predicted_route=route, simulation_time=full_row.simulation_time,
    )


# ─────────────────────────────────────────────
# BATCH INSERT
# ─────────────────────────────────────────────

def _batch_insert(client, rows: list[FullTwinRow]) -> None:
    if not rows:
        log.warning("_batch_insert: empty list, nothing to write")
        return

    data = [[
        r.mmsi, r.latitude, r.longitude, r.speed, r.heading,
        r.last_update, r.simulated_latitude, r.simulated_longitude,
        r.simulated_speed, r.predicted_route,
        r.simulation_scenario, r.simulation_time,
    ] for r in rows]

    client.insert(DT_TABLE, data, column_names=DT_COLUMNS)
    log.info(f"_batch_insert: appended {len(rows)} rows to {DT_TABLE}")