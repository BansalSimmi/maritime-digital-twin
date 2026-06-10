# carbon/utils.py
"""
Physics-based engine load and emission helpers.

Your ais_data.vessel_type stores AIS codes as text with .0 suffix:
  '37.0', '30.0', '52.0' etc. Code zero is stored as just '0'.

vessel_profiles.vessel_type_code stores the SAME exact strings,
so the lookup is a direct equality — no transformation needed.

Two calculation paths:
  full_emission_row(speed)                → global default constants
  full_emission_row_typed(speed, profile) → vessel-type specific dict
"""

# ── Default constants (generic medium cargo, used as fallback) ────────────────
DESIGN_SPEED = 20.0  #Default maximum ship speed (knots). --> Used for engine load calculation. [ ship speed = 10 knots , design speed = 20 knots ]
MCR_KW       = 10_000  #MCR = Maximum Continuous Rating --> Maximum engine power , Unit: kilowatts
SFC          = 0.200  #SFC = Specific Fuel Consumption --> Fuel required per kWh , Unit: kg fuel / kWh , Example:0.2 kg fuel per kWh
MIN_LOAD     = 0.05  #Minimum engine load = 5% --> Why? Ships never run at 0% engine load, so we enforce a minimum threshold.

CO2_FACTOR   = 3.206   # IMO MEPC.281 HFO --> For 1 kg fuel burned, ship produces: 3.206 kg CO₂ --> This value comes from IMO emission standards.
NOX_FACTOR   = 0.087   # Tier II average --> 1 kg fuel → 0.087 kg NOx
SOX_FACTOR   = 0.054   # 3% sulphur HFO --> 1 kg fuel → 0.054 kg SOx --> Depends on sulphur content in fuel.


def normalize_vessel_type_code(raw: str) -> str: #Defines a function.
    """
    Input:raw vessel type from AIS
    Output: normalized vessel type

    Return the vessel_type value to use for a DB lookup. -> This function ensures we always get a valid vessel type.
    Raw NULL → '0' (Not Available). -> If vessel type is missing → return '0'.
    Everything else is returned as-is because vessel_profiles --> If value exists, return it unchanged.
    stores the exact same strings as ais_data.vessel_type.
    """
    return raw if raw else '0' 
"""
    if raw:
      return raw
   else:
      return '0'
"""

def estimate_engine_load(speed: float, design_speed: float = DESIGN_SPEED) -> float:
    """This function calculates engine load.

       Input: speed , design_speed
       Output: engine load (0 → 1)

Cubic-law engine load, floored at MIN_LOAD, capped at 1.0. 
                  ^
                  |
Ship engines follow cubic law: Load=(speed/design_speed) 3
"""
    if speed is None or speed < 0:
        return MIN_LOAD  # return minimum load
    ds  = design_speed if design_speed and design_speed > 0 else DESIGN_SPEED #This ensures design_speed is valid. If invalid: use default DESIGN_SPEED
    raw = (min(speed, ds) / ds) ** 3  #This is the cubic law formula.
    """
    raw = (min(speed, ds) / ds) ** 3  - This is the cubic law formula.
    Example:speed = 10 , design speed = 20
    Calculation:(10/20)^3 = 0.125
    Engine load = 12.5%
    """
    return max(raw, MIN_LOAD) #Ensures load never goes below 5%.


def calculate_fuel( #This calculates fuel consumption.
    engine_load: float,
    mcr_kw: float = MCR_KW,
    sfc: float = SFC,
) -> float:
    """Fuel consumption in kg/h. = engine_load * mcr_kw * sfc
     Fuel = EngineLoad × EnginePower × SFC """
    return engine_load * mcr_kw * sfc

 
def calculate_emissions(
    fuel: float,
    co2_factor: float = CO2_FACTOR,
    nox_factor: float = NOX_FACTOR,
    sox_factor: float = SOX_FACTOR,
) -> tuple[float, float, float]:
    """Return (co2, nox, sox) in kg/h."""
    return fuel * co2_factor, fuel * nox_factor, fuel * sox_factor

#Creates a complete emission record.
def full_emission_row(speed: float) -> dict:
    """Compute emissions using global DEFAULT constants. Fallback path."""
    el            = estimate_engine_load(speed) #Step 1: calculate engine load
    fuel          = calculate_fuel(el) #STEP 2:calculate fuel consumption
    co2, nox, sox = calculate_emissions(fuel) # STEP 3:calculate emissions
    return {
        "speed":            round(speed, 2), # Speed round off 2 decimal places
        "engine_load":      round(el,    4), # round off 4 decimal places
        "fuel_consumption": round(fuel,  3), #
        "co2_emission":     round(co2,   3),
        "nox_emission":     round(nox,   3),
        "sox_emission":     round(sox,   3),
    }

# advanced version. --> Uses ship-specific parameters.
def full_emission_row_typed(speed: float, profile: dict) -> dict:
    """
    Compute emissions using a VESSEL-TYPE SPECIFIC profile dict.
    profile must have: design_speed, mcr_kw, sfc,
                       co2_factor, nox_factor, sox_factor
    Any missing key falls back to global defaults.

    x =  profile.get("y", y)
    if profile contains y
       use it
   else
       use default
    """
    ds    = profile.get("design_speed", DESIGN_SPEED) or DESIGN_SPEED
    mcr   = profile.get("mcr_kw",       MCR_KW)       or MCR_KW
    sfc   = profile.get("sfc",          SFC)          or SFC
    co2_f = profile.get("co2_factor",   CO2_FACTOR)   or CO2_FACTOR
    nox_f = profile.get("nox_factor",   NOX_FACTOR)   or NOX_FACTOR
    sox_f = profile.get("sox_factor",   SOX_FACTOR)   or SOX_FACTOR

    el            = estimate_engine_load(speed, design_speed=ds)
    fuel          = calculate_fuel(el, mcr_kw=mcr, sfc=sfc)
    co2, nox, sox = calculate_emissions(fuel, co2_f, nox_f, sox_f)

    return {
        "speed":            round(speed, 2),
        "engine_load":      round(el,    4),
        "fuel_consumption": round(fuel,  3),
        "co2_emission":     round(co2,   3),
        "nox_emission":     round(nox,   3),
        "sox_emission":     round(sox,   3),
    }

"""  
Final Flow
Speed
   ↓
Engine Load (Cubic Law)
   ↓
Fuel Consumption
   ↓
Emission Factors
   ↓
CO2 / NOx / SOx
"""
