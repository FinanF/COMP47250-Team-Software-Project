from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logging
import asyncio
import json

app = FastAPI()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@app.get("/")
def root():
    return {"status": "ok"}

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()

    # Lazy import so app starts even if SUMO/traci unavailable
    try:
        from backend.simulation.sumo_worker import sumo_worker
    except ImportError as e:
        logger.exception("Failed to import backend.simulation.sumo_worker")
        await websocket.send_json({"error": "import failed", "detail": str(e)})
        await websocket.close()
        return

    try:
        # Create queues for communication between SUMO worker and WebSocket
        traffic_queue = asyncio.Queue(maxsize=50)
        db_queue = asyncio.Queue(maxsize=50)
        shutdown_event = asyncio.Event()

        # Launch the SUMO worker as a background task
        worker_task = asyncio.create_task(
            sumo_worker(traffic_queue, db_queue, shutdown_event)
        )

        # Stream traffic data to the WebSocket client
        try:
            while not shutdown_event.is_set():
                try:
                    # Get data from the simulation queue with a timeout
                    state = await asyncio.wait_for(traffic_queue.get(), timeout=3.0)
                    # Send the state data to the WebSocket client
                    await websocket.send_json(state)
                except asyncio.TimeoutError:
                    # Queue is empty, check if worker is still running
                    if shutdown_event.is_set():
                        logger.info("Simulation ended")
                        break
                    continue

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        finally:
            # Shut down the worker when client disconnects
            shutdown_event.set()
            try:
                await asyncio.wait_for(worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Worker task did not shutdown gracefully")
                worker_task.cancel()

    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json({"error": "runtime error", "detail": str(e)})
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass

