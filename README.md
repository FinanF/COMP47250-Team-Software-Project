
# Web-based Human-in-the-Loop (HITL) AI System for Traffic Signal Optimisation 

Traffic optimisation interface using Dublin city simulated traffic data.


## Deployment

To deploy this project run

```bash
  docker-compose up --build
```
To view the website connect to 
```bash
  http://localhost:5500
```

## WebSocket API Reference

This application exposes two WebSocket endpoints:

- **Traffic Simulation Stream** (`ws://localhost:8000/traffic`)
- **Optimisation Stream** (`ws://localhost:8000/opt`)

---

### Traffic Simulation Stream

Connect to receive real-time traffic simulation updates.

```http
ws://localhost:8000/traffic
```

The server automatically starts the traffic simulation worker when a client connects and streams junction and vehicle updates until the client disconnects.

### Junction State Update

The server periodically sends the current state of all simulated traffic junctions.

#### Message Type

```json
{
  "type": "junction_state"
}
```
#### Simulation Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | `string` | Message identifier (`junction_state`) |
| `schema_version` | `string` | Version of the message schema |
| `step` | `integer` | Current simulation step |
| `timestamp` | `float` | Simulation timestamp in seconds |
| `junction_count` | `integer` | Number of active junctions |
| `sim_status` | `string` | Current simulation status |
| `sim_time_remaining` | `float` | Remaining simulation time |

#### Junction Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique junction identifier |
| `lat` | `float` | Latitude coordinate |
| `lng` | `float` | Longitude coordinate |
| `current_phase` | `integer` | Current traffic light phase |
| `phase_duration_total` | `float` | Total phase duration |
| `phase_duration_remaining` | `float` | Remaining phase duration |
| `phase_duration_elapsed` | `float` | Elapsed phase duration |
| `signal_state` | `string` | Current signal state |

#### Approach Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `lane_id` | `string` | SUMO lane identifier |
| `queue_length` | `integer` | Number of queued vehicles |
| `waiting_time_avg` | `float` | Average waiting time |
| `vehicle_count` | `integer` | Number of vehicles |
| `green` | `boolean` | Lane currently has green |
| `seconds_since_green` | `float` | Seconds since last green |

---

### Vehicle State Update

Provides real-time vehicle position and movement data.

#### Message Type

```json
{
  "type": "vehicle_state"
}
```

#### Vehicle Object

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
| `id` | `string` | Vehicle identifier |
| `lat` | `float` | Latitude |
| `lng` | `float` | Longitude |
| `speed` | `float` | Speed |
| `angle` | `float` | Heading |
| `road_id` | `string` | Current road identifier |

---

### Optimisation Stream

Connect to receive AI-generated optimisation recommendations.

```http
ws://localhost:8000/opt
```

The optimisation worker analyses congestion events and streams recommendations to connected clients.

### Recommendation Message

#### Message Type

```json
{
  "type": "recommendation"
}
```

#### Recommendation Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `junction_id` | `string` | Junction requiring optimisation |
| `pattern_type` | `string` | Detected congestion pattern |
| `severity_score` | `float` | Confidence/severity score |
| `old_cycle_length` | `float` | Current cycle length |
| `new_cycle_length` | `float` | Proposed cycle length |
| `old_phase_splits` | `object` | Existing green allocations |
| `new_phase_splits` | `object` | Proposed green allocations |
| `new_phase_durations` | `array<float>` | Proposed phase durations |
| `before_max_queue` | `integer` | Current maximum queue |
| `after_est_queue` | `float` | Estimated queue after optimisation |
| `before_avg_wait` | `float` | Current average wait |
| `after_est_wait` | `float` | Estimated average wait |
| `improvement_pct` | `float` | Estimated improvement |
| `explanation` | `string` | Human-readable explanation |
| `created_at` | `string` | Recommendation timestamp |

### Operator Response

Clients respond by accepting or rejecting a recommendation.

#### Message

```json
{
  "action": "accept",
  "junction_id": "1396454306"
}
```

or

```json
{
  "action": "reject",
  "junction_id": "1396454306"
}
```

#### Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `action` | `string` | `accept` or `reject` |
| `junction_id` | `string` | Junction identifier |

## REST API

The backend exposes several REST endpoints for retrieving and managing optimisation audit data.

---

### Get Accepted Recommendations

Returns all accepted optimisation recommendations stored in the database.

```http
GET /logs
```

#### Response

```json
{
  "type": "accepted_recommendations",
  "data": [
    {
      "id": 1,
      "junction_id": "1396454306",
      "queue_reduction_pct": 30.5,
      "wait_reduction_pct": 27.8,
      "before_avg_queue": 8.2,
      "after_avg_queue": 5.7,
      "before_avg_wait": 18.3,
      "after_avg_wait": 13.2,
      "measured_at": 420.0,
      "accepted_at": "2026-07-18T17:01:55"
    }
  ]
}
```

---

### Get Junction Metadata

Returns all signalised junctions stored in the database.

```http
GET /junctions
```

#### Response

```json
{
  "type": "junctions",
  "data": [
    {
      "junction_id": "1396454306",
      "lat": 53.348751,
      "lng": -6.257620
    }
  ]
}
```

---

### Get Recommendations for a Junction

Returns all accepted optimisation recommendations associated with a specific junction.

```http
GET /logs_junctions?junction_id=1396454306
```

#### Query Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `junction_id` | `string` | Junction identifier |

#### Response

```json
{
  "type": "accepted_recommendations_by_junction_id",
  "data": [
    {
      "id": 3,
      "junction_id": "1396454306",
      "queue_reduction_pct": 31.2,
      "wait_reduction_pct": 28.9,
      "before_avg_queue": 9.1,
      "after_avg_queue": 6.2,
      "before_avg_wait": 19.5,
      "after_avg_wait": 14.1,
      "measured_at": 660.0,
      "accepted_at": "2026-07-18T17:12:30"
    }
  ]
}
```

---

### Clear Recommendation Log

Deletes all stored optimisation audit records and resets the table.

```http
DELETE /del_logs
```

#### Response

Returns HTTP `200 OK` after successfully clearing the recommendation log.
### Authors

- [Yang Ruhao](https://github.com/YangRuhao)
- [Princeton Jose](https://github.com/princetonjose17-dotcom)
- [Kiri Wang](https://github.com/KiriWang2002)
- [FinanF](https://github.com/FinanF)
