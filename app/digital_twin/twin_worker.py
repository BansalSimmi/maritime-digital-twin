"""
digital_twin/twin_worker.py
============================
Background daemon thread — appends fresh simulation rows every 5 minutes.

Every WORKER_INTERVAL_SEC (300s):
    1. refresh_and_simulate()
       → reads latest state per vessel (argMax GROUP BY mmsi)
       → runs Haversine physics on each moving vessel
       → appends one FullTwinRow per vessel (simulation_time = NOW())
    2. Log result
    3. Sleep

Client is created once and reused (shared from app/database.py via lru_cache).
No new connection per cycle — one connection for the entire worker lifetime.
"""

import time
import logging
import threading

from .config import get_client, WORKER_INTERVAL_SEC, SIMULATION_MINUTES, SIMULATION_STEP_MIN
from .service import refresh_and_simulate

log = logging.getLogger(__name__)


def _worker_loop() -> None:
    log.info("Digital Twin Worker started")
    log.info(f"  Cycle every : {WORKER_INTERVAL_SEC}s ({WORKER_INTERVAL_SEC // 60} min)")
    log.info(f"  Horizon     : {SIMULATION_MINUTES} min")
    log.info(f"  Route step  : {SIMULATION_STEP_MIN} min")

    # Single client reused across all cycles
    # lru_cache in app/database.py ensures this is the same shared connection
    client = get_client()

    while True:
        try:
            result = refresh_and_simulate(
                client,
                minutes=SIMULATION_MINUTES,
                step=SIMULATION_STEP_MIN
            )
            log.info(
                f"[Worker] OK — total={result.total} "
                f"simulated={result.simulated} skipped={result.skipped}"
            )
        except Exception as e:
            log.error(f"[Worker] cycle failed: {e}", exc_info=True)

        time.sleep(WORKER_INTERVAL_SEC)


def start_twin_worker() -> threading.Thread:
    """
    Launch the worker as a daemon thread.
    Stops automatically when the FastAPI process exits.
    """
    thread = threading.Thread(target=_worker_loop, name="DigitalTwinWorker", daemon=True)
    thread.start()
    log.info(f"Digital Twin Worker launched (thread id={thread.ident})")
    return thread