from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import clickhouse_connect
from functools import lru_cache
import os

DATABASE_URL = "postgresql://postgres:Simmi%40123@localhost:5432/maritime_digital_twin"

# engine = create_engine(DATABASE_URL) #connects FastAPI → PostgreSQL.
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
# Parameter	                Purpose
# pool_size=10       -  	keeps 10 connections ready
# max_overflow=20    -  	allows extra connections if traffic spikes
# pool_pre_ping=True -	    prevents broken connections
# This prevents "connection closed" errors.

#Every request gets its own DB connection.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base() #Used by models to create tables

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# ClickHouse Configuration
# -------------------------

# def get_clickhouse_client():
#     return clickhouse_connect.get_client(
#     host="localhost",
#     port=8123,
#     username="simmi",
#     password="Simmi@123",
#     database="maritime_digital_twin"
# )
def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host="localhost",
        port=8123,
        username="simmi",
        password="Simmi@123",
        database="maritime_digital_twin",
        connect_timeout=10,
        send_receive_timeout=60
    )