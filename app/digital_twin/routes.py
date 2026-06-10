"""
digital_twin/routes.py
======================
FastAPI router — HTTP layer only. No SQL, no physics.

Endpoints:
    GET  /digital-twin/state/{mmsi}   — full detail for one vessel
    GET  /digital-twin/state/all      — latest state for ALL vessels (paginated)
    GET  /digital-twin/state/area     — vessels within a bounding box
    POST /digital-twin/sync           — refresh predictions for all vessels
    POST /digital-twin/simulate       — named scenario for one vessel
"""

#Imports FastAPI tools, the database client, Pydantic schemas, and service functions.
from fastapi import APIRouter, HTTPException, Query
"""
Tool	      | Purpose
APIRouter	  | creates API routes
HTTPException | returns errors
Query	      | validates query parameters
"""

from .config import get_client # This gets the shared ClickHouse connection. -> Instead of creating many connections, it reuses one client.
# These are Pydantic models used to validate requests and responses.
# For example, SimulationRequest validates input data for /simulate, TwinStateResponse structures the response for a vessel.
from .schemas import ( #schemas are the data models.
    SimulationRequest, 
    SyncRequest,
    AreaRequest,
    TwinStateResponse,
    SimulationResponse,
    RefreshResponse,
    AllVesselsResponse,
    ErrorResponse,
)
# These are business logic functions that interact with ClickHouse and the simulation engine.
from .service import (
    get_twin_state,
    get_all_vessels,
    get_vessels_in_area,
    refresh_and_simulate,
    run_simulation,
)

# Defines a router with prefix /digital-twin.
# Tags are used in API docs for grouping.
router = APIRouter( #A router groups related API endpoints.
    prefix="/digital-twin",
    tags=["Digital Twin"]
)


# ─────────────────────────────────────────────
# GET ALL VESSELS  (paginated)
# ─────────────────────────────────────────────

@router.get(
    "/vessels",
    response_model=AllVesselsResponse,  #Response is validated against AllVesselsResponse.
    summary="Get latest simulation state for ALL vessels (paginated)"
)
# limit: How many vessels per page (1–5000). Default is 1000.
# offset: How many vessels to skip for pagination. Default 0.
# Query(...) ensures validation and auto-doc generation.
def all_vessels( #default=1000: By default, returns 1000 vessels.
    limit:  int = Query(default=1000, ge=1, le=5000, description="Vessels per page"),
    offset: int = Query(default=0,    ge=0,           description="Page offset"),
):
# ge = “greater than or equal to”
# le = “less than or equal to”
    """
    Returns the latest simulation state for every vessel that has been
    processed by the worker. Excludes seed-only rows (zeros).

    Use this endpoint to populate a world map with all ship positions.

    Pagination: use limit + offset to page through results.
    - Page 1: limit=1000, offset=0
    - Page 2: limit=1000, offset=1000
    - etc.

    predicted_route is excluded to keep payload small.
    Call GET /state/{mmsi} for the full route of a specific vessel.
    """
    client = get_client()
    return get_all_vessels(client, limit=limit, offset=offset)


# ─────────────────────────────────────────────
# GET VESSELS IN BOUNDING BOX
# ─────────────────────────────────────────────
# Return vessels inside a map region. --> This is used when a user zooms on a map.
@router.get(
    "/vessels/area",
    response_model=AllVesselsResponse,
    summary="Get vessels within a geographic bounding box"
)
# Endpoint for fetching vessels within latitude/longitude bounds.
def vessels_in_area(
    min_lat: float = Query(..., ge=-90,  le=90,  description="South boundary latitude"),
    max_lat: float = Query(..., ge=-90,  le=90,  description="North boundary latitude"),
    min_lon: float = Query(..., ge=-180, le=180, description="West boundary longitude"),
    max_lon: float = Query(..., ge=-180, le=180, description="East boundary longitude"),
    limit:   int   = Query(default=500, ge=1, le=5000, description="Max vessels to return"),
):
#min_lat / max_lat: Latitude range (-90° to 90°).
# min_lon / max_lon: Longitude range (-180° to 180°).
# limit: Max number of vessels to return (default 500).
    """
    Returns vessels currently located within the given bounding box.

    Use this for map viewport filtering — only load vessels visible
    in the current zoom level instead of all 39,000 at once.

    Example — vessels in the Gulf of Mexico:
        min_lat=18.0&max_lat=31.0&min_lon=-98.0&max_lon=-80.0

    Example — vessels near New York:
        min_lat=40.0&max_lat=41.5&min_lon=-74.5&max_lon=-72.5

    predicted_route is excluded. Call GET /state/{mmsi} for full route.
    """
    if min_lat >= max_lat:
        raise HTTPException(status_code=422, detail="min_lat must be less than max_lat")
    if min_lon >= max_lon:
        raise HTTPException(status_code=422, detail="min_lon must be less than max_lon")
# Validates bounding box correctness.
# If invalid, raises 422 Unprocessable Entity.

    client = get_client()
    return get_vessels_in_area(
        client,
        min_lat=min_lat, max_lat=max_lat,
        min_lon=min_lon, max_lon=max_lon,
        limit=limit,
    )
# Calls the service function that fetches the latest vessel state in the bounding box.


# ─────────────────────────────────────────────
# GET ONE VESSEL
# ─────────────────────────────────────────────
# Endpoint for one vessel by MMSI.
# TwinStateResponse is the response model.
# If vessel not found, returns 404 with ErrorResponse.
@router.get(
    "/state/{mmsi}",
    response_model=TwinStateResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get latest real + simulated state for one vessel"
)
def twin_state(mmsi: int):
    """
    Returns full detail for one vessel: real position + simulated position + full predicted route waypoints.
    """
    client = get_client()
    result = get_twin_state(client, mmsi)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ─────────────────────────────────────────────
# SYNC  (manual worker trigger)
# ─────────────────────────────────────────────
# POST endpoint to manually trigger a worker cycle.
@router.post(
    "/sync",
    response_model=RefreshResponse,
    summary="Append fresh simulation rows for all vessels"
)
def sync_twin(req: SyncRequest = SyncRequest()):
    """
    Manually trigger a worker cycle.
    Worker also runs automatically every 5 minutes.
    """
    client = get_client()
    return refresh_and_simulate(client, minutes=req.minutes_ahead, step=req.step_minutes)

"""
Purpose:Manually trigger prediction worker.
Normally the worker runs every 5 minutes automatically.
But this endpoint allows manual refresh.

API call
 ↓
sync_twin()
 ↓
refresh_and_simulate()
 ↓
simulate vessels
 ↓
insert rows in ClickHouse
"""


# ─────────────────────────────────────────────
# SIMULATE  (manual scenario)
# ─────────────────────────────────────────────
# POST endpoint to simulate a specific scenario for a single vessel.
# Response: SimulationResponse.
# 404 returned if MMSI not found.

"""
API call
 ↓
simulate()
 ↓
run_simulation()
 ↓
calculate predicted route
 ↓
insert result in ClickHouse
"""
@router.post(
    "/simulate",
    response_model=SimulationResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Run a named scenario for one vessel"
)
#Input: minutes_ahead and step_minutes from SyncRequest.
def simulate(req: SimulationRequest):
    """
    Run a named scenario for one vessel and append the result.
    Scenarios: AUTO, STORM, DETOUR, NORMAL (any string accepted).
    """
# Calls the simulation engine to predict positions for this vesse
    client = get_client()
    result = run_simulation(
        client,
        mmsi=req.mmsi, scenario=req.scenario,
        minutes=req.minutes_ahead, step=req.step_minutes 
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


"""
all_vessels() → Returns all vessels (paginated) without full routes.

vessels_in_area() → Returns vessels in a bounding box (map viewport filter).

twin_state() → Returns full state for one vessel, including predicted route.

sync_twin() → Triggers full simulation for all vessels (manual worker trigger).

simulate() → Triggers simulation for one vessel under a named scenario.

All endpoints reuse the same ClickHouse client.

Errors are handled using HTTPException.

Pagination and bounding box filtering ensure performance for thousands of vessels.


| Endpoint        | Purpose                      |
| --------------- | ---------------------------- |
| `/vessels`      | get all vessels              |
| `/vessels/area` | vessels in map region        |
| `/state/{mmsi}` | full vessel details          |
| `/sync`         | trigger worker simulation    |
| `/simulate`     | simulate one vessel scenario |

"""