from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

# 🔥 MATCH THESE TO YOUR REAL POSTGRES + CLICKHOUSE COLUMNS
TABLE_DESCRIPTIONS = [
    # ================= POSTGRESQL =================
    "accounts: user login details, name, email, role, created_at",
    "ais_data postgres: ship tracking positions, latitude, longitude, speed, vessel_name, vessel_type",
    "vessel_profiles: engine specs, vessel_category, design_speed, mcr_kw, sfc, co2_factor, nox_factor, sox_factor",
    "emissions: fuel consumption and CO2, NOx, SOx emissions data",
    "emission_predictions: projected future emissions and speed",
    "piracy_events: maritime piracy attacks, risk levels, and locations",
    "emergencies: active maritime emergency alerts, type, severity, and position",
    "rescue_operations: search and rescue missions responding to emergencies",
    "anomaly_events: detected speed violations, gaps, and suspicious activities",
    "analytics_summary: pre-calculated maritime KPIs and metrics",

    # ================= CLICKHOUSE =================
    "maritime_digital_twin.ais_data: high-volume real-time ship positions for tracking",
    "maritime_digital_twin.digital_twin_state: simulated vessel positions, predicted routes, and scenarios"
]

embeddings = OllamaEmbeddings(model="nomic-embed-text")

vector_db = FAISS.from_texts(
    TABLE_DESCRIPTIONS,
    embedding=embeddings
)

def get_relevant_tables(question: str, top_k: int = 5):
    """
    Returns most relevant tables for the question.
    """
    docs = vector_db.similarity_search(question, k=top_k)
    return "\n".join([doc.page_content for doc in docs])