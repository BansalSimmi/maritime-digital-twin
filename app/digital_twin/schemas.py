"""
digital_twin/schemas.py
=======================
All Pydantic models for the digital twin module.

Version 4 adds:
VesselSummary → minimal info for maps, no routes.
AllVesselsResponse → paginated vessel list.

NEW (v4):
  VesselSummary      — lightweight vessel record for map display (no route data)
  AllVesselsResponse — paginated list of vessels for /state/all and /state/area
"""

# Logic: Pydantic ensures:
# Data validation.
# Clear typing.
# Automatic conversion to JSON for FastAPI responses.

from __future__ import annotations #Allows using newer Python type hints (like list[RouteWaypoint]) even in older Python versions.
from datetime import datetime 
from pydantic import BaseModel, Field

# datetime: For timestamps (last_update, simulation_time).
# BaseModel: All Pydantic models inherit from this.
# Field: Adds metadata, default values, validation, and description for each field.


# ─────────────────────────────────────────────
# REQUEST BODIES - These are used in POST endpoints to validate input
# ─────────────────────────────────────────────

class SimulationRequest(BaseModel):
    mmsi:          int = Field(..., description="Vessel MMSI identifier") #mmsi: Vessel identifier (required).
    scenario:      str = Field(..., description="e.g. 'AUTO', 'STORM', 'DETOUR', 'NORMAL'") #scenario: Type of simulation.
    minutes_ahead: int = Field(120, ge=1, le=1440)  #minutes_ahead: How far into the future to simulate (1–1440 min, default 120).
    step_minutes:  int = Field(20,  ge=1, le=60)  # step_minutes: Simulation step interval (1–60 min, default 20).

class SyncRequest(BaseModel):
    minutes_ahead: int = Field(120, ge=1, le=1440)
    step_minutes:  int = Field(20,  ge=1, le=60)
# Used in /sync endpoint for manual worker trigger.
# Same fields as SimulationRequest except MMSI and scenario.

class AreaRequest(BaseModel):
    """Bounding box for GET /state/area"""
    min_lat: float = Field(..., ge=-90,  le=90,  description="South boundary latitude")
    max_lat: float = Field(..., ge=-90,  le=90,  description="North boundary latitude")
    min_lon: float = Field(..., ge=-180, le=180, description="West boundary longitude")
    max_lon: float = Field(..., ge=-180, le=180, description="East boundary longitude")
    limit:   int   = Field(500, ge=1, le=5000,   description="Max vessels to return")
# Defines bounding box for /vessels/area.
# Validation ensures lat/lon are within valid ranges.

# ─────────────────────────────────────────────
# RESPONSE MODELS - These define the data structure returned by the API.
# ─────────────────────────────────────────────
# Represents one predicted point in a vessel’s route.
class RouteWaypoint(BaseModel):
    minute: int
    lat:    float
    lon:    float
    speed:  float


class TwinStateResponse(BaseModel):
    """
    GET /digital-twin/state/{mmsi}
    Full detail for one vessel including predicted route waypoints.

    - Full vessel state, real + simulated positions, predicted route.
    - Returned by /state/{mmsi}.
    - None indicates optional fields.
    """
    mmsi:                int
    latitude:            float
    longitude:           float
    current_speed:       float | None = None
    current_heading:     float | None = None
    last_update:         datetime | None = None
    simulated_latitude:  float | None = None
    simulated_longitude: float | None = None
    simulated_speed:     float | None = None
    predicted_route:     list[RouteWaypoint] = []
    simulation_scenario: str | None = None
    simulation_time:     datetime | None = None


class VesselSummary(BaseModel):
    """
    Lightweight vessel record for map display.
    Used in AllVesselsResponse — excludes predicted_route to keep
    payload small when returning thousands of vessels at once.
    If the frontend needs the full route for a vessel, it calls
    GET /state/{mmsi} which returns TwinStateResponse with route.


    - Lightweight version of TwinStateResponse.
    - No predicted route → ideal for map display.
    - used in AllVesselsResponse.
    """
    mmsi:                int
    latitude:            float
    longitude:           float
    current_speed:       float | None = None
    current_heading:     float | None = None
    last_update:         datetime | None = None
    simulated_latitude:  float | None = None
    simulated_longitude: float | None = None
    simulated_speed:     float | None = None
    simulation_scenario: str | None = None
    simulation_time:     datetime | None = None


class AllVesselsResponse(BaseModel):
    """
    GET /digital-twin/state/all
    GET /digital-twin/state/area
    Paginated list of vessels with their latest simulation state.
    predicted_route excluded — call /state/{mmsi} for full route.

    - Paginated response for /vessels and /vessels/area.
    - Includes metadata (total, limit, offset) and vessel list.
    """
    total:   int                  # total vessels matching the query
    limit:   int                  # page size used
    offset:  int                  # page offset used
    vessels: list[VesselSummary]  # this page of results


class SimulationResponse(BaseModel):
#  Response for /simulate.
# Shows current state, simulated state, and predicted route."
    mmsi:                int
    scenario:            str
    current_latitude:    float
    current_longitude:   float
    current_speed:       float
    current_heading:     float
    simulated_latitude:  float
    simulated_longitude: float
    simulated_speed:     float
    predicted_route:     list[RouteWaypoint]
    simulation_time:     datetime


class RefreshResponse(BaseModel):
    status:    str
    total:     int
    simulated: int = 0
    skipped:   int = 0
# Response for /sync.
# Reports how many vessels were simulated vs skipped.

class ErrorResponse(BaseModel):
    error: str #Standard error structure for 404/422 responses.


# ─────────────────────────────────────────────
# INTERNAL MODELS
# ─────────────────────────────────────────────

class VesselState(BaseModel):
    mmsi:        int
    lat:         float
    lon:         float
    speed:       float
    heading:     float
    last_update: datetime | None = None


class FullTwinRow(BaseModel):
    mmsi:                int
    latitude:            float
    longitude:           float
    speed:               float
    heading:             float
    last_update:         datetime
    simulated_latitude:  float
    simulated_longitude: float
    simulated_speed:     float
    predicted_route:     str
    simulation_scenario: str
    simulation_time:     datetime

"""
| Schema             | Purpose                            |
| ------------------ | ---------------------------------- |
| SimulationRequest  | POST input for `/simulate`         |
| SyncRequest        | POST input for `/sync`             |
| AreaRequest        | GET input for `/vessels/area`      |
| RouteWaypoint      | Single predicted waypoint          |
| TwinStateResponse  | Full vessel state with route       |
| VesselSummary      | Lightweight vessel for map display |
| AllVesselsResponse | Paginated list of vessels          |
| SimulationResponse | Response for a simulation scenario |
| RefreshResponse    | Response for worker sync           |
| ErrorResponse      | Standard error response            |
| VesselState        | Internal current state             |
| FullTwinRow        | Internal full record with route    |

"""