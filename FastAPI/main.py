from fastapi import FastAPI, WebSocket

from simulation.sumo_worker import sumo_worker, _standalone_test

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    while True:
        vehicle_data = _standalone_test()
        await ws.send_json(vehicle_data)