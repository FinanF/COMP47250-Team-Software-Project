import os
from dotenv import load_dotenv
from sqlalchemy.sql.schema import ForeignKey

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
junctions = Table(
    "junctions",
    metadata,
    Column("junction_id", String, nullable=False, primary_key=True),
    Column("lat", Float),
    Column("lng", Float)
)
accepted_recommendations = Table(
    "accepted_recommendations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("junction_id", String,nullable=False),
    Column("queue_reduction_pct", Float),
    Column("wait_reduction_pct", Float),
    Column("before_avg_queue", Float),
    Column("after_avg_queue", Float),
    Column("before_avg_wait", Float),
    Column("after_avg_wait", Float),
    Column("measured_at", Float),
    Column("accepted_at", DateTime, server_default=func.now())
)

metadata.create_all(engine)

def insert_junction(junction: dict):
    try:
        with engine.begin() as conn:
            conn.execute(
                junctions.insert().values(
                    junction_id=junction["junction_id"],
                    lat=junction["lat"],
                    lng=junction["lng"]
                )
            )
            print(f"[DB] Inserted junction {junction['junction_id']}")
    except Exception as e:
        print(f"[DB] Error inserting junction {junction['junction_id']} {e}")

def insert_audit(recommendation: dict, ):
    try:
        with engine.begin() as conn:
            conn.execute(
                accepted_recommendations.insert().values(
                    junction_id=recommendation["junction_id"],
                    queue_reduction_pct=recommendation["queue_reduction_pct"],
                    wait_reduction_pct=recommendation["wait_reduction_pct"],
                    before_avg_queue=recommendation["before_avg_queue"],
                    after_avg_queue=recommendation["after_avg_queue"],
                    before_avg_wait=recommendation["before_avg_wait"],
                    after_avg_wait=recommendation["after_avg_wait"],
                    measured_at=recommendation["measured_at"],
                )
            )
            print(f"[DB] Inserted recommendation for junction {recommendation['junction_id']}")
    except Exception as e:
        print(f"[DB] Error inserting recommendation for junction {recommendation['junction_id']}: {e}")

def select_all_recommendations():
    with engine.begin() as conn:
        result=conn.execute(select(accepted_recommendations))
        return [dict(row) for row in result.mappings()]

def select_all_junctions():
    with engine.begin() as conn:
        result=conn.execute(select(junctions))
        return [dict(row) for row in result.mappings()]

def select_audits_by_junction_id(junction_id):
    with engine.begin() as conn:
        result=conn.execute(
            select(accepted_recommendations).where(accepted_recommendations.c.junction_id == junction_id)
        )
        return [dict(row) for row in result.mappings()]

def clear_recommendations():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE accepted_recommendations RESTART IDENTITY;"
            )
        )
    print("[DB] Cleared all recommendations from the database.")

async def db_worker(db_queue):
    while True:
        message = await db_queue.get()
        print(f"[DB] Received message: {message}")
        if message.get("type") == "update_actual_improvement":
            insert_audit(message)
        elif message.get("type") == "seed_junctions":
            print(f"[DB] seed_junctions received — {len(message.get('junctions', []))} junctions")
            for junction in message["junctions"]:
                insert_junction(junction)
        else:
            print(f"[DB] Unknown message type: {message.get('type')}")

