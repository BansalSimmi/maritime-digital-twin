"""
digital_twin/config.py
======================
Central config — constants and shared ClickHouse client.

Client: clickhouse_connect (HTTP, port 8123)
  Shared via lru_cache in app/database.py.
  100 requests → 1 connection (not 100).
  Do NOT use clickhouse_driver anywhere in this module.

Table: maritime_digital_twin.digital_twin_state
Engine: MergeTree ORDER BY (mmsi, simulation_time)
  - Append-only — every INSERT permanently adds rows
  - Full AIS history preserved (all rows imported, not just latest)
  - Latest state per vessel = ORDER BY simulation_time DESC LIMIT 1
  - Worker rows: simulation_time = NOW() — always newest
  - Seed rows:   simulation_time = base_date_time — always older

NO FINAL keyword in any query. FINAL is for ReplacingMergeTree only.
"""

import logging  #Sets up logging to capture info/warnings/errors.
from app.database import get_clickhouse_client    #Imports a cached ClickHouse client from app/database.py.
# This function gives the database connection.

# Logging = recording events or messages while your program runs.
# Example:
# When a function starts
# When data is inserted
# When an error occurs
# Instead of printing with print(), developers use logging.

# Example log output:
# 2026-03-12 10:45:22 [INFO] Worker started
# 2026-03-12 10:45:23 [ERROR] Database connection failed
# This helps developers debug problems and monitor the system.
logging.basicConfig( #Configures the global logging behavior for the module.
    level=logging.INFO, #This tells Python how logs should appear.
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__) #Create logger - This creates a logger object for this file.

# format="%(asctime)s [%(levelname)s] %(message)s": Defines how each log line looks.
# %(asctime)s: Timestamp when the log was written.
# %(levelname)s: The severity level (INFO, ERROR, etc.).
#%(message)s: The actual log text


# ─────────────────────────────────────────────
# SIMULATION CONSTANTS - These define default parameters for the physics simulation:
# fixed values used by the vessel simulation.
# ─────────────────────────────────────────────
SIMULATION_MINUTES  = 120    # prediction horizon (minutes) --> Predict vessel movement 2 hours into the future.
SIMULATION_STEP_MIN = 20     # waypoint interval  (minutes) --> Create a prediction point every 20 minutes.
#  Example route prediction: +20 -> +40 -> +60 -> +80 -> +100 -> +120
WORKER_INTERVAL_SEC = 300    # worker cycle (seconds = 5 min) -> Background worker runs every 300 seconds (5 minutes).

EARTH_RADIUS_KM     = 6371.0 #Needed for Haversine formula to calculate distance on Earth. --> Used when predicting vessel movement.
# Default values - AIS data sometimes has missing values. --> So fallback values are defined.
DEFAULT_SPEED_KNOTS = 10.0   # fallback when speed is NULL or 0 --> If speed is missing → assume 10 knots.
DEFAULT_HEADING_DEG = 0.0    # fallback when heading=0 while moving (bad COG) = If heading is missing → assume north direction.
MIN_MOVING_SPEED    = 0.5    # knots — below this = stationary vessel = If speed < 0.5 knots → vessel is considered stationary.

# How far ahead to predict (SIMULATION_MINUTES)
# How often to record waypoints (SIMULATION_STEP_MIN)
# How often the background worker runs (WORKER_INTERVAL_SEC)
# Earth radius → needed for Haversine formula.
# Default speed/heading if AIS data is missing.
# Minimum speed threshold to consider a vessel moving.

# ─────────────────────────────────────────────
# TABLE + COLUMNS  (single source of truth) - Every insert query can use this list instead of rewriting columns.
# ─────────────────────────────────────────────
DT_TABLE   = "maritime_digital_twin.digital_twin_state"
DT_COLUMNS = [
    "mmsi",
    "latitude",
    "longitude",
    "speed",
    "heading",
    "last_update",
    "simulated_latitude",
    "simulated_longitude",
    "simulated_speed",
    "predicted_route",
    "simulation_scenario",
    "simulation_time",
]

# ─────────────────────────────────────────────
# CLIENT FACTORY
# ─────────────────────────────────────────────
def get_client():
    """
    Return the shared clickhouse_connect client from app/database.py.
    lru_cache(maxsize=1) ensures one connection for the entire process.
    """
    return get_clickhouse_client()  #This simply returns the shared ClickHouse client.

"""
Why shared client?

Without caching:
100 API requests → 100 database connections

With caching:
100 API requests → 1 connection reused
This makes the system much faster and more efficient.

Seed rows vs worker rows

Seed rows: simulation_time = original AIS time
Worker rows: simulation_time = NOW()

Worker rows are always newest.
"""