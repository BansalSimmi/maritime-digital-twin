# Maritime Digital Twin

A comprehensive, AI-powered Maritime Digital Twin platform for real-time vessel tracking, anomaly detection, carbon emissions monitoring, and predictive simulation. This project provides a holistic view of maritime operations by combining spatial data, time-series analytics, and advanced Large Language Model (LLM) workflows.

## Key Features

* ** Real-Time Vessel Tracking:** Interactive map analytics utilizing Leaflet and geospatial processing to track and monitor fleet movements.
* ** Anomaly Detection:** Automated detection of unusual vessel behaviors, route deviations, and operational anomalies.
* ** Carbon Emissions Monitoring:** Track and analyze environmental impact and emissions data across the fleet.
* ** Digital Twin Simulation:** Predictive simulation engine to model maritime scenarios and optimize operations.
* ** AI-Powered Chatbot:** Advanced RAG (Retrieval-Augmented Generation) chatbot powered by Langchain, Langgraph, and Groq to answer complex questions about vessel data, operations, and anomalies.

##  Tech Stack

### Backend (Python/FastAPI)
* **Framework:** FastAPI
* **Databases:** 
  * PostgreSQL (Relational data & spatial queries via GeoAlchemy2)
  * ClickHouse (High-performance time-series data)
* **AI & Machine Learning:**
  * Langchain & Langgraph for agentic AI workflows
  * Groq API for fast LLM inference
  * FAISS for vector search / RAG capabilities
* **Geospatial:** Shapely, GeoAlchemy2

### Frontend (React/Vite)
* **Framework:** React 18 with TypeScript
* **Build Tool:** Vite
* **Routing:** React Router v7
* **Mapping:** Leaflet & React-Leaflet
* **UI/Icons:** Lucide React, React-Markdown

##  Project Structure

```text
maritime-digital-twin/
├── app/                      # FastAPI Backend
│   ├── anomaly_detection/    # Anomaly detection logic and rules
│   ├── carbon/               # Carbon emission tracking modules
│   ├── digital_twin/         # Simulation engine and workers
│   ├── vessel_tracking/      # Core tracking and spatial processing
│   ├── routes/               # API endpoint definitions
│   └── main.py               # FastAPI application entry point
├── frontend/                 # React UI Application
│   ├── src/
│   │   ├── components/       # Reusable UI components (MapBox, Sidebar, etc.)
│   │   ├── pages/            # View pages (Tracking, Anomaly, DigitalTwin, Chat)
│   │   └── context/          # React context (Auth)
│   └── package.json          # Frontend dependencies
├── requirements.txt          # Python backend dependencies
├── .env.example              # Example environment variables
└── swagger.json              # API Schema documentation
```

##  Getting Started

### Prerequisites
* Python 3.9+
* Node.js 18+
* PostgreSQL with PostGIS extension
* ClickHouse server

### 1. Backend Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy the environment variables template and configure your credentials:
   ```bash
   cp .env.example .env
   ```
3. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be available at `http://localhost:8000`.

### 2. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The UI will be accessible at `http://localhost:5173`.

##  Contributing 
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
