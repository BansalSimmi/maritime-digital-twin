from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import SessionLocal

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/ships")
def get_ships(db: Session = Depends(get_db)):

    vessels = db.execute(text("""
        SELECT DISTINCT ON (mmsi)
            mmsi,
            latitude,
            longitude,
            sog,
            cog
        FROM ais_data
        WHERE latitude IS NOT NULL
        AND longitude IS NOT NULL
        ORDER BY mmsi, base_date_time DESC
        LIMIT 500;
    """)).fetchall()

    return [dict(v._mapping) for v in vessels]