from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.simulation.sumo_worker import sumo_worker
from diagnostic.diagnostic_worker import diagnostic_worker
from optimisation.optimisation_worker import optimisation_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

traffic_queue = asyncio.Queue(maxsize=500)
diagnostic_queue = asyncio.Queue(maxsize=500)
event_queue = asyncio.Queue(maxsize=500)
recommendation_queue = asyncio.Queue(maxsize=500)

db_queue = asyncio.Queue(maxsize=100)
shutdown_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background workers...")

    sumo_task = asyncio.create_task(
        sumo_worker(
            traffic_queue=traffic_queue,
            shutdown_event=shutdown_event,
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
            recommendation_queue=recommendation_queue
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

    try:
        while True:
            recommendation = await recommendation_queue.get()
            await websocket.send_json(recommendation)

    except WebSocketDisconnect:
        logger.info("Optimisation client disconnected.")