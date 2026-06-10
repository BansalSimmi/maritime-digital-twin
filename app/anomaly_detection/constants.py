# app/anomaly_detection/constants.py


class AnomalyType:
    SPEED_VIOLATION   = "speed_violation"
    EMISSION_SPIKE    = "emission_spike"
    AIS_SIGNAL_GAP    = "ais_signal_gap"
    GEOFENCE_BREACH   = "geofence_breach"
    DARK_SHIP         = "dark_ship"
    COURSE_DEVIATION  = "course_deviation"
    DRAUGHT_CHANGE    = "draught_change"
    SUDDEN_SPEED_DROP = "sudden_speed_drop"


class Severity:
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


# ── Detection windows ────────────────────────────────────────────────────────
DETECTION_WINDOW_HOURS:    int   = 72    # default = 3 days (fast sync run)
AIS_GAP_THRESHOLD_MINUTES: int   = 30
DARK_SHIP_MINUTES:         int   = 120

# ── Thresholds ───────────────────────────────────────────────────────────────
SPEED_VIOLATION_FACTOR:   float = 1.2
SPEED_VIOLATION_MIN_SOG:  float = 1.0

EMISSION_SPIKE_FACTOR:    float = 1.5
EMISSION_SPIKE_MIN_CO2:   float = 100.0

COURSE_DEVIATION_DEGREES: float = 30.0
COURSE_DEVIATION_MIN_SOG: float = 2.0
COURSE_DEVIATION_WINDOW:  int   = 6

DRAUGHT_CHANGE_THRESHOLD: float = 1.0
DRAUGHT_MIN_VALUE:        float = 0.3

SPEED_DROP_THRESHOLD:     float = 5.0
SPEED_DROP_MIN_PREV_SOG:  float = 3.0

# ── Severity per type ────────────────────────────────────────────────────────
ANOMALY_SEVERITY: dict = {
    AnomalyType.SPEED_VIOLATION:   Severity.HIGH,
    AnomalyType.EMISSION_SPIKE:    Severity.CRITICAL,
    AnomalyType.AIS_SIGNAL_GAP:    Severity.MEDIUM,
    AnomalyType.GEOFENCE_BREACH:   Severity.HIGH,
    AnomalyType.DARK_SHIP:         Severity.CRITICAL,
    AnomalyType.COURSE_DEVIATION:  Severity.MEDIUM,
    AnomalyType.DRAUGHT_CHANGE:    Severity.MEDIUM,
    AnomalyType.SUDDEN_SPEED_DROP: Severity.HIGH,
}

# ── Pagination ───────────────────────────────────────────────────────────────
FLEET_DEFAULT_LIMIT: int = 100
FLEET_MAX_LIMIT:     int = 1000

# ── Parallel detection ───────────────────────────────────────────────────────
DETECTOR_MAX_WORKERS: int = 4   # threadpool size for concurrent detectors