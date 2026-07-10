
# Web-based Human-in-the-Loop (HITL) AI System for Traffic Signal Optimisation 

Traffic optimisation interface using Dublin city simulated traffic data.


## Deployment

To deploy this project run

```bash
  docker-compose up --build
```
To view the website connect to 
```bash
  http://localhost:3000
```

## WebSocket API Reference

### Traffic Simulation Stream

Connect to the WebSocket endpoint to receive real-time junction state updates from the traffic simulation.

```http
ws://localhost:8000/traffic
```

The server automatically starts the traffic simulation worker when a client connects and streams junction updates until the client disconnects.

---

## Server Messages

### Junction State Update

The server periodically sends the current state of all simulated traffic junctions.

#### Message Type

```json
{
  "type": "junction_state"
}
```

#### Example Response

```json
{
  "type": "junction_state",
  "schema_version": "1.2",
  "step": 180,
  "timestamp": 90.0,
  "junction_count": 28,
  "sim_status": "running",
  "sim_time_remaining": 3510.0,
  "junctions": [
    {
      "id": "1294004372",
      "lat": 53.34957,
      "lng": -6.253556,
      "current_phase": 2,
      "phase_duration_remaining": 0.0,
      "signal_state": "rr",
      "approaches": [
        {
          "lane_id": "4385842#0_0",
          "queue_length": 0,
          "waiting_time_avg": 0.0,
          "vehicle_count": 0,
          "green": false
        }
      ]
    }
  ]
}
```

---

## Junction State Schema

### Simulation Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | `string` | Message identifier (`junction_state`) |
| `schema_version` | `string` | Version of the message schema |
| `step` | `integer` | Current simulation step |
| `timestamp` | `float` | Simulation timestamp in seconds |
| `junction_count` | `integer` | Number of active junctions |
| `sim_status` | `string` | Current simulation status |
| `sim_time_remaining` | `float` | Remaining simulation time in seconds |

---

### Junction Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique junction identifier |
| `lat` | `float` | Latitude coordinate |
| `lng` | `float` | Longitude coordinate |
| `current_phase` | `integer` | Current traffic light phase |
| `phase_duration_total` | `float` | Total duration of current phase |
| `phase_duration_remaining` | `float` | Remaining phase duration |
| `phase_duration_elapsed` | `float` | Elapsed phase duration |
| `signal_state` | `string` | Current signal pattern |

---

### Approach Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `lane_id` | `string` | SUMO lane identifier |
| `queue_length` | `integer` | Number of queued vehicles |
| `waiting_time_avg` | `float` | Average waiting time of vehicles |
| `vehicle_count` | `integer` | Number of vehicles on approach |
| `green` | `boolean` | Whether the approach currently has green |
| `seconds_since_green` | `float` | Time since last green phase |

## Vehicle State Update

The server provides real-time vehicle position and movement data from the traffic simulation.

### Message Type

```json
{
  "type": "vehicle_state"
}
```

### Vehicle Object

```json
{
  "id": "vehicle_001",
  "lat": 53.34957,
  "lng": -6.253556,
  "speed": 13.45,
  "angle": 90.0,
  "road_id": "road_123"
}
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique vehicle identifier |
| `lat` | `float` | Vehicle latitude coordinate |
| `lng` | `float` | Vehicle longitude coordinate |
| `speed` | `float` | Current vehicle speed |
| `angle` | `float` | Vehicle heading angle in degrees |
| `road_id` | `string` | Current road/lane identifier |
### Authors

- [Yang Ruhao](https://github.com/YangRuhao)
- [Princeton Jose](https://github.com/princetonjose17-dotcom)
- [Kiri Wang](https://github.com/KiriWang2002)
- [FinanF](https://github.com/FinanF)