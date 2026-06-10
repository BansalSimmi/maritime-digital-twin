# chatbot.py
from groq import Groq
import difflib
import re
from sqlalchemy import create_engine, text
from app.schema_context import FULL_SCHEMA_CONTEXT
from app.schema_embeddings import get_relevant_tables
import os
import math

# Try to load environment variables from .env if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================
# DATABASE CONNECTIONS
# ==============================
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:Simmi%40123@localhost:5432/maritime_digital_twin")
pg_engine = create_engine(POSTGRES_URL)

import clickhouse_connect
ch_client = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
    username=os.getenv("CLICKHOUSE_USER", "simmi"),
    password=os.getenv("CLICKHOUSE_PASSWORD", "Simmi@123")
)

# ==============================
# LLM CONFIG
# ==============================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# ==============================
# VALID TABLES
# ==============================
POSTGRES_TABLES = ["accounts", "ais_data", "vessel_profiles", "emissions", "emission_predictions", "piracy_events", "emergencies", "rescue_operations", "anomaly_events", "analytics_summary"]
CLICKHOUSE_TABLES = ["maritime_digital_twin.ais_data", "maritime_digital_twin.digital_twin_state"]
ALL_TABLES = POSTGRES_TABLES + CLICKHOUSE_TABLES

# ==============================
# UTILS
# ==============================
def clean_sql(response: str) -> str:
    response = response.replace("```sql", "").replace("```", "")
    match = re.search(r"(SELECT .*?;)", response, re.IGNORECASE | re.DOTALL)
    if not match: 
        # Attempt to find SELECT if no semicolon
        match = re.search(r"(SELECT .*?)$", response, re.IGNORECASE | re.DOTALL)
        if not match: raise Exception("No valid SQL generated")
    
    sql = match.group(1).strip()
    if not sql.lower().startswith("select"): raise Exception("Only SELECT queries allowed")
    
    # Failsafe against common LLM hallucination
    sql = re.sub(r'(?i)\b(dts\.)?simulated_heading\b', r'\1heading', sql)
    return sql

def fix_table_names(sql: str):
    # Avoid aggressive fixing to prevent breaking valid SQL
    words = sql.replace("(", " ( ").replace(")", " ) ").split()
    for i, word in enumerate(words):
        clean_word = word.lower().strip(",;()")
        if not clean_word: continue
        match = difflib.get_close_matches(clean_word, ALL_TABLES, n=1, cutoff=0.85)
        if match: 
            words[i] = word.replace(clean_word, match[0])
    return " ".join(words)

def detect_db_from_sql(sql: str):
    # More robust detection
    sql_lower = sql.lower()
    if "maritime_digital_twin" in sql_lower:
        return "clickhouse"
    # Additional check for Postgres specific tables
    for t in POSTGRES_TABLES:
        if t in sql_lower: return "postgres"
    return "postgres"

def clean_result(data):
    cleaned = []
    for row in data:
        if isinstance(row, dict):
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): clean_row[k] = None
                else: clean_row[k] = v
            cleaned.append(clean_row)
        else:
            clean_row = []
            for v in row:
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): clean_row.append(None)
                else: clean_row.append(v)
            cleaned.append(clean_row)
    return cleaned

# ==============================
# CORE LOGIC
# ==============================
def generate_sql(question: str, history: list = None):
    relevant_schema = get_relevant_tables(question, top_k=5)
    
    # Simple history context for SQL generation
    history_context = ""
    if history:
        last_exchange = history[-2:] if len(history) >= 2 else history
        history_context = "\n".join([f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}" for m in last_exchange])

    prompt = f"""
You are an EXPERT SQL engineer for a Maritime Digital Twin system.

================ DATABASE SCHEMA ================
{FULL_SCHEMA_CONTEXT}

================ RELEVANT TABLES ================
{relevant_schema}

================ CONVERSATION CONTEXT ================
{history_context}

================ CRITICAL RULES =================
- ONLY USE columns that exist in the TABLE definitions provided above.
- vessel_name is ONLY in: ais_data, piracy_events, and anomaly_events.
- emissions table does NOT have vessel_name. You MUST JOIN with ais_data on mmsi to get the name.
- ALWAYS use `(SELECT MAX(vessel_name) FROM ais_data a WHERE a.mmsi = e.mmsi)` as vessel_name when joining emissions and ais_data to ensure you get a name if one exists.
- ALL vessel-related tables MUST be joined using mmsi (except vessel_profiles).
- vessel_profiles MUST be joined using:
  vessel_profiles.vessel_type_code = ais_data.vessel_type
- NEVER join using vessel_type in other tables.
- NEVER hallucinate columns. For digital_twin_state, ONLY use exactly: mmsi, latitude, longitude, speed, heading, last_update, simulated_latitude, simulated_longitude, simulated_speed, predicted_route, simulation_scenario, simulation_time.
- CRITICAL: There is NO column named simulated_heading. Use heading instead. Do NOT SELECT simulated_heading.

================ DATABASE SELECTION =================
- If query involves real-time tracking, simulation → use CLICKHOUSE
- If query involves emissions, anomaly, history → use POSTGRESQL
- ClickHouse tables MUST start with maritime_digital_twin.

================ JOIN LOGIC =================
- To get vessel names for emissions (Avoid duplicates!):
  SELECT e.mmsi, (SELECT MAX(vessel_name) FROM ais_data a WHERE a.mmsi = e.mmsi) as vessel_name, e.co2_emission
  FROM emissions e

================ COMMON QUERY EXAMPLES =================
- "highest CO2 emitter" or "top polluter" (single vessel):
  SELECT e.mmsi,
         COALESCE((SELECT MAX(vessel_name) FROM ais_data a WHERE a.mmsi = e.mmsi), 'Unknown') AS vessel_name,
         e.co2_emission
  FROM emissions e
  ORDER BY e.co2_emission DESC
  LIMIT 1;

- "top polluters" or "top N CO2 emitters" (multiple vessels):
  SELECT e.mmsi,
         COALESCE((SELECT MAX(vessel_name) FROM ais_data a WHERE a.mmsi = e.mmsi), 'Unknown') AS vessel_name,
         ROUND(CAST(e.co2_emission AS numeric), 2) AS co2_emission
  FROM emissions e
  ORDER BY e.co2_emission DESC
  LIMIT 10;

- "scenario in digital twin simulation" (or similar):
  SELECT DISTINCT simulation_scenario
  FROM maritime_digital_twin.digital_twin_state
  WHERE simulation_scenario IS NOT NULL;

================ FORMATTING =================
- Return SQL ONLY. No explanation.
- End with semicolon (;).

================ USER QUESTION =================
{question}
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": "You are a SQL expert."}, {"role": "user", "content": prompt}],
        temperature=0
    )
    sql_text = response.choices[0].message.content
    return fix_table_names(clean_sql(sql_text))

def generate_summary(question: str, data: list, history: list = None):
    if not data: return "I found no results in the database that match your question."
    
    # Process history for the prompt
    history_prompt = ""
    if history:
        history_prompt = "\n".join([f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}" for m in history])

    prompt = f"""
You are a Maritime AI Assistant. Summarize the following data into a clear, natural language answer for the user.
Consider the conversation context provided below.

================ CONVERSATION HISTORY ================
{history_prompt}

================ DATA FOUND ================
{data[:15]}

================ RULES ================
- Be concise and professional.
- Use **Markdown** for formatting (bold, italics).
- If there are multiple records, use a **Markdown table** to display them clearly.
- If the data contains coordinates (latitude, longitude), mention them if relevant.
- Do NOT mention SQL or technical jargon.
- Format as **Markdown** with clean line breaks.
- If the user asks about the best feature in MarineOS, ALWAYS reply that the "digital twin simulation feature is one of the best features in MarineOS." and briefly explain its benefits instead of mentioning anomaly detection.

Question: {question}
Answer:
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summary Error: {e}")
        return f"I found {len(data)} matching records."

def ask_database(question: str, history: list = None):
    question_lower = question.lower()
    if "best feature" in question_lower:
        reply = """Based on the data and information provided, I would say that the **Digital Twin simulation feature** is one of the best features in MarineOS. This feature allows for creating complete virtual replicas of your fleet, which can help optimize routes, simulate operational conditions, and predict performance proactively.

Here's a brief explanation of how this feature works:

- **Virtual Replicas**: MarineOS creates continuous running digital models of the vessels based on their physical parameters and engine profiles.
- **Scenario Testing**: The system allows operators to simulate various weather conditions, routing choices, and speed impacts entirely virtually.
- **Predictive Optimization**: By simulating future states, stakeholders can optimize fuel consumption, reduce emissions, and increase safety without risking physical assets.

This feature is particularly useful in preventing costly inefficiencies and reducing the risk of environmental damage. By predicting performance and bottlenecks in real-time, MarineOS can help completely optimize vessel operations and improve overall safety and fuel efficiency."""
        return {
            "database": "none",
            "sql": "N/A",
            "rows_returned": 0,
            "result": [],
            "summary": reply
        }

    try:
        sql_query = generate_sql(question, history)
        db_type = detect_db_from_sql(sql_query)
        
        if db_type == "postgres":
            with pg_engine.connect() as conn:
                result = conn.execute(text(sql_query))
                data = [dict(row._mapping) for row in result.fetchall()]
        else:
            result = ch_client.query(sql_query)
            data = [dict(zip(result.column_names, row)) for row in result.result_rows]

        data = clean_result(data)
        summary = generate_summary(question, data, history)

        return {
            "database": db_type,
            "sql": sql_query,
            "rows_returned": len(data),
            "result": data,
            "summary": summary
        }
    except Exception as e:
        print(f"❌ Chatbot Error: {str(e)}")
        return {"error": str(e), "message": "Query failed", "sql": locals().get("sql_query", "None")}