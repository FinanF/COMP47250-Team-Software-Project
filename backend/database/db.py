import logging
import os
from dotenv import load_dotenv

load_dotenv()
POSTGRES_USER=os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB=os.getenv("POSTGRES_DB")

from sqlalchemy import (
    Table, Column, Integer, String, Float,
    DateTime, MetaData, create_engine, select, text
)
from sqlalchemy.sql import func

metadata = MetaData()
engine = create_engine(f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@database:5432/{POSTGRES_DB}")
accepted_recommendations = Table(
    "accepted_recommendations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("junction_id", String, nullable=False),
    Column("pattern_type", String),
    Column("severity_score", Float),
    Column("improvement_pct", Float),
    Column("accepted_at", DateTime, server_default=func.now())
)

metadata.create_all(engine)

def insert_audit(recommendation: dict):
    with engine.begin() as conn:
        conn.execute(
            accepted_recommendations.insert().values(
                junction_id=recommendation["junction_id"],
                pattern_type=recommendation["pattern_type"],
                severity_score=recommendation["severity_score"],
                improvement_pct=recommendation["improvement_pct"],
            )
        )

def select_all_recommendations():
    with engine.begin() as conn:
        result=conn.execute(select(accepted_recommendations))
        return [dict(row) for row in result.mappings()]

def clear_recommendations():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE accepted_recommendations RESTART IDENTITY;"
            )
        )