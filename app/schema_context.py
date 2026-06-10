SCHEMA_CONTEXT = """
================ POSTGRESQL DATABASE =================
Use for relational + structured vessel data, metadata, and history.

TABLE accounts
- account_id
- name
- email
- role
- created_at

TABLE ais_data
- mmsi
- base_date_time
- longitude
- latitude
- sog
- cog
- vessel_name
- vessel_type
- status

TABLE vessel_profiles
- vessel_type_code (Matches ais_data.vessel_type)
- vessel_category
- design_speed
- mcr_kw
- sfc
- co2_factor
- nox_factor
- sox_factor

TABLE emissions
- mmsi
- speed
- fuel_consumption
- co2_emission
- nox_emission
- sox_emission
- calculated_at

TABLE emission_predictions
- mmsi
- predicted_co2
- predicted_speed
- prediction_time

TABLE piracy_events
- piracy_id
- event_date
- attack_type
- attack_description
- risk_level
- latitude
- longitude
- nearest_country
- vessel_name

TABLE emergencies
- emergency_id
- mmsi
- emergency_type
- severity
- status
- latitude
- longitude
- reported_at

TABLE rescue_operations
- rescue_id
- emergency_id
- rescue_vessel
- eta_minutes
- response_status

TABLE anomaly_events
- mmsi
- vessel_name
- anomaly_type
- severity
- description
- latitude
- longitude
- sog
- extra_data
- detected_at
- is_resolved

TABLE analytics_summary
- metric_name
- metric_value
- region

================ CLICKHOUSE DATABASE =================
Use for real-time AIS telemetry + digital twin simulation history.

TABLE maritime_digital_twin.ais_data
- mmsi
- base_date_time
- latitude
- longitude
- sog
- cog
- heading
- vessel_name
- vessel_type
- status

TABLE maritime_digital_twin.digital_twin_state
- mmsi
- latitude
- longitude
- speed
- heading
- last_update
- simulated_latitude
- simulated_longitude
- simulated_speed
- predicted_route
- simulation_scenario
- simulation_time
"""

RELATIONSHIPS = """
================ RELATIONSHIPS =================

POSTGRESQL:
- ais_data.vessel_type = vessel_profiles.vessel_type_code (JOIN to get engine/design specs)
- ais_data.mmsi = emissions.mmsi
- ais_data.mmsi = emission_predictions.mmsi
- ais_data.mmsi = emergencies.mmsi
- emergencies.emergency_id = rescue_operations.emergency_id
- ais_data.mmsi = anomaly_events.mmsi

CLICKHOUSE:
- maritime_digital_twin.ais_data.mmsi = maritime_digital_twin.digital_twin_state.mmsi

IMPORTANT:
- vessel_profiles does NOT have mmsi. Always JOIN via vessel_type_code.
- NEVER JOIN PostgreSQL and ClickHouse tables in a single SQL query.
- Choose ONE database per query based on the question context.
"""

FULL_SCHEMA_CONTEXT = SCHEMA_CONTEXT + RELATIONSHIPS