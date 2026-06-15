from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    while True:
        vehicle_data = get_vehicle_positions()
        await ws.send_json(vehicle_data)