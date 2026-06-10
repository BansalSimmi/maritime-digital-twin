# app/vessel_tracking/constants.py
"""
Physics and emission constants for vessel tracking.
Single source of truth — imported by utils.py and tracking.py.
All values are IMO-standard; change here to affect every endpoint.
"""

# ── IMO Cubic Law ───────────────────────────────────────────────────────────
MIN_ENGINE_LOAD: float = 0.05      # 5% floor — hotel / auxiliary power load

# ── IMO MEPC.281(70) Emission Factors (kg pollutant per kg HFO fuel) ────────
CO2_FACTOR: float = 3.206          # Heavy Fuel Oil
NOX_FACTOR: float = 0.087          # Tier II average
SOX_FACTOR: float = 0.054          # 3% sulphur HFO

# ── Fallback engine profile (used when vessel_profiles has no matching row) ─
DEFAULT_DESIGN_SPEED: float = 20.0   # knots
DEFAULT_MCR_KW:       float = 10_000.0  # kW
DEFAULT_SFC:          float = 0.200  # kg/kWh specific fuel consumption

# ── Alert thresholds (kg CO₂ per hour) ─────────────────────────────────────
ALERT_ELEVATED: float = 2_000.0
ALERT_HIGH:     float = 3_000.0
ALERT_CRITICAL: float = 4_000.0

# ── Pagination hard caps ────────────────────────────────────────────────────
LIVE_DEFAULT_LIMIT:    int = 500
LIVE_MAX_LIMIT:        int = 5_000
HISTORY_DEFAULT_LIMIT: int = 5_000
HISTORY_MAX_LIMIT:     int = 50_000
SEARCH_DEFAULT_LIMIT:  int = 50
SEARCH_MAX_LIMIT:      int = 200