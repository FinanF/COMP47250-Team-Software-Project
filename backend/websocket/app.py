import os
from contextlib import asynccontextmanager
import asyncio
import logging
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.simulation.sumo_worker import sumo_worker, pending_changes, \
    build_signal_program
from diagnostic.diagnostic_worker import diagnostic_worker
from optimisation.optimisation_worker import optimisation_worker

from sqlalchemy import create_engine,select

load_dotenv()
POSTGRES_USER=os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB=os.getenv("POSTGRES_DB")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

traffic_queue = asyncio.Queue(maxsize=500)
diagnostic_queue = asyncio.Queue(maxsize=500)
event_queue = asyncio.Queue(maxsize=500)
recommendation_queue = asyncio.Queue(maxsize=500)

accepted_queue = asyncio.Queue(maxsize=500)

db_queue = asyncio.Queue(maxsize=100)
shutdown_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background workers...")
    sumo_task = asyncio.create_task(
        sumo_worker(
            traffic_queue=traffic_queue,
            shutdown_event=shutdown_event,
            db_queue=db_queue,
        )
    )

    diagnostic_task = asyncio.create_task(
        diagnostic_worker(
            traffic_queue=traffic_queue,
            event_queue=event_queue,
        )
    )

    optimisation_task = asyncio.create_task(
        optimisation_worker(
            event_queue=event_queue,
            recommendation_queue=recommendation_queue,
        )
    )
    try:
        yield

    finally:
        logger.info("Stopping workers...")

        shutdown_event.set()

        tasks = [sumo_task, diagnostic_task, optimisation_task]

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)

try:
    from sqlalchemy import (
        Table, Column, Integer, String, Float,
        DateTime, MetaData
    )
    from sqlalchemy.dialects.postgresql import JSONB
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
except Exception as e:
    logger.exception(e)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.websocket("/traffic")
async def traffic_ws(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            state = await traffic_queue.get()
            await websocket.send_json(state)

    except WebSocketDisconnect:
        logger.info("Traffic client disconnected.")


@app.websocket("/opt")
async def optimisation_ws(websocket: WebSocket):
    await websocket.accept()

    pending_recommendations = {}

    async def send_recommendations():
        while True:
            recommendation = await recommendation_queue.get()

            junction_id = recommendation["junction_id"]

            pending_recommendations[junction_id] = recommendation
            await websocket.send_json({
                "type": "recommendation",
                "data": recommendation
            })

    async def receive_decisions():
        while True:
            message = await websocket.receive_json()

            action = message.get("action")
            junction_id = message.get("junction_id")

            if action == "accept":
                recommendation = pending_recommendations.get(junction_id)

                if recommendation is None:
                    logger.warning(
                        f"No recommendation found for {junction_id}"
                    )
                    continue

                try:
                    with engine.begin() as conn:
                        conn.execute(
                            accepted_recommendations.insert().values(
                                junction_id=recommendation["junction_id"],
                                pattern_type=recommendation["pattern_type"],
                                severity_score=recommendation["severity_score"],
                                improvement_pct=recommendation["improvement_pct"],
                            )
                        )

                    new_program = build_signal_program(
                        recommendation["junction_id"],
                        recommendation["new_phase_durations"]
                    )

                    pending_changes[junction_id] = new_program

                    logger.info(
                        f"Accepted recommendation for {junction_id}"
                    )

                    # Remove after applying
                    del pending_recommendations[junction_id]

                except Exception as e:
                    logger.exception(
                        f"Failed creating signal program: {e}"
                    )

            elif action == "reject":
                pending_recommendations.pop(junction_id, None)

                logger.info(
                    f"Rejected recommendation for {junction_id}"
                )


    sender = asyncio.create_task(send_recommendations())
    receiver = asyncio.create_task(receive_decisions())

    try:
        await asyncio.gather(sender, receiver)

    except WebSocketDisconnect:
        logger.info("Optimisation client disconnected.")

    finally:
        sender.cancel()
        receiver.cancel()

@app.websocket("/logs")
async def logs_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            with engine.begin() as conn:
                result=conn.execute(select(accepted_recommendations))
                rows=result.fetchall()
                data=[dict(row) for row in rows]
                await websocket.send_json({"type": "accepted_recommendations", "data": data})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        logger.info("Logs client disconnected.")
