
# carbon/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class VesselProfile(BaseModel):
    vessel_type_code: str
    vessel_category:  str
    design_speed:     float
    mcr_kw:           float
    sfc:              float
    co2_factor:       float
    nox_factor:       float
    sox_factor:       float


class EmissionRecord(BaseModel):
    mmsi:             int
    vessel_type_code: Optional[str]   = None
    vessel_category:  Optional[str]   = None
    speed:            float
    engine_load:      float
    fuel_consumption: float
    co2_emission:     float
    nox_emission:     float
    sox_emission:     float
    latitude:         Optional[float] = None
    longitude:        Optional[float] = None


class EmissionPrediction(BaseModel):
    mmsi:                int
    vessel_type_code:    Optional[str] = None
    vessel_category:     Optional[str] = None
    current_speed_knots: float
    growth_factor:       float
    current_co2_kg_h:    float
    predicted_co2_kg_h:  float
    predicted_nox_kg_h:  float
    predicted_sox_kg_h:  float
    horizon_minutes:     int = 30


class PollutorEntry(BaseModel):
    rank:             int
    mmsi:             int
    vessel_type_code: Optional[str] = None
    vessel_category:  Optional[str] = None
    records:          int
    total_co2_kg:     float
    avg_co2_kg_h:     float
    peak_co2_kg_h:    float
    avg_speed_knots:  float


class EmissionAlert(BaseModel):
    mmsi:              int
    vessel_type_code:  Optional[str]      = None
    vessel_category:   Optional[str]      = None
    speed_knots:       float
    co2_emission_kg_h: float
    nox_emission_kg_h: float
    sox_emission_kg_h: float
    latitude:          Optional[float]    = None
    longitude:         Optional[float]    = None
    alert_level:       str
    time:              Optional[datetime] = None


class VesselTypeBreakdown(BaseModel):
    vessel_type_code: str
    vessel_category:  str
    vessels:          int
    avg_co2_kg_h:     float
    total_co2_kg:     float


class FleetSummary(BaseModel):
    total_vessels:        int
    total_records:        int
    distinct_type_codes:  int
    total_co2_kg:         float
    average_co2_kg_h:     float
    peak_co2_kg_h:        float
    total_nox_kg:         float
    total_sox_kg:         float
    average_speed_knots:  float
    average_engine_load:  float
    by_vessel_type:       List[VesselTypeBreakdown]


class ZoneCreate(BaseModel):
    zone_name:   str
    description: Optional[str]  = None
    geojson:     Dict[str, Any] = Field(description="GeoJSON Polygon geometry")


class ZoneEmissions(BaseModel):
    zone_name:     str
    records:       int
    vessels:       int
    total_co2_kg:  float
    avg_co2_kg_h:  float
    peak_co2_kg_h: float
    total_nox_kg:  float
    total_sox_kg:  float
