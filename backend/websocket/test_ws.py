import asyncio

from backend.simulation.sumo_worker import sumo_worker
from backend.websocket.app import db_queue
from diagnostic.diagnostic_worker import diagnostic_worker
from diagnostic.rules import RuleBasedDetector
from optimisation.optimisation_worker import optimisation_worker
from optimisation.optimiser import TrafficSignalOptimiser
traffic_queue = asyncio.Queue()
event_queue = asyncio.Queue()
recommendation_queue = asyncio.Queue()
diagnostic_queue = asyncio.Queue()
db_queue = asyncio.Queue()
shutdown_event = asyncio.Event()

sumo_task = asyncio.create_task(
        sumo_worker(
            traffic_queue=traffic_queue,
            db_queue=db_queue,
            shutdown_event=shutdown_event,
        )
)

diagnostic_task = asyncio.create_task(
        diagnostic_worker(
            traffic_queue=diagnostic_queue,
            event_queue=event_queue
        )
)

optimisation_task = asyncio.create_task(
        optimisation_worker(
            event_queue=event_queue,
            recommendation_queue=recommendation_queue
        )
)


print(recommendation_queue.get())
