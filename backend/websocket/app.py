from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from backend.database.db import select_all_recommendations, clear_recommendations, db_worker, select_all_junctions, \
    select_audits_by_junction_id
from backend.simulation.sumo_worker import sumo_worker, pending_changes, \
    build_signal_program
from diagnostic.diagnostic_worker import diagnostic_worker
from optimisation.optimisation_worker import optimisation_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sumo_output_queue = asyncio.Queue(maxsize=500)
traffic_queue = asyncio.Queue(maxsize=500)
diagnostic_queue = asyncio.Queue(maxsize=500)
event_queue = asyncio.Queue(maxsize=500)
recommendation_queue = asyncio.Queue(maxsize=500)

accepted_queue = asyncio.Queue(maxsize=500)

db_queue = asyncio.Queue(maxsize=100)
shutdown_event = asyncio.Event()

async def put_latest(queue: asyncio.Queue, message: dict):
    if queue.full():
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(message)


async def fanout_traffic_messages():
    while True:
        message = await sumo_output_queue.get()

        await put_latest(traffic_queue, message)
        if message.get("type") == "junction_state":
            await put_latest(diagnostic_queue, message)

        sumo_output_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background workers...")
    sumo_task = asyncio.create_task(
        sumo_worker(
            traffic_queue=sumo_output_queue,
            shutdown_event=shutdown_event,
            db_queue=db_queue,
        )
    )

    fanout_task = asyncio.create_task(fanout_traffic_messages())

    diagnostic_task = asyncio.create_task(
        diagnostic_worker(
            traffic_queue=diagnostic_queue,
            event_queue=event_queue,
        )
    )

    optimisation_task = asyncio.create_task(
        optimisation_worker(
            event_queue=event_queue,
            recommendation_queue=recommendation_queue,
        )
    )

    db_task = asyncio.create_task(
        db_worker(
            db_queue=db_queue
        )
    )
    try:
        yield

    finally:
        logger.info("Stopping workers...")

        shutdown_event.set()

        tasks = [sumo_task, fanout_task, diagnostic_task, optimisation_task,db_task]

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

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

@app.get("/logs")
async def get_logs():
    data = select_all_recommendations()
    return {
        "type": "accepted_recommendations",
        "data": jsonable_encoder(data)
    }

@app.get("/junctions")
async def get_junctions():
    data = select_all_junctions()
    return {
        "type": "junctions",
        "data": jsonable_encoder(data)
    }

@app.delete("/del_logs")
async def delete_logs():
    clear_recommendations()

@app.get("/logs_junctions")
async def get_logs_junctions(junction_id: int):
    data = select_audits_by_junction_id(junction_id)
    return {
        "type": "accepted_recommendations_by_junction_id",
        "data": jsonable_encoder(data)
    }
