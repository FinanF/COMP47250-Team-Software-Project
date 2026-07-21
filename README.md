# <img height="30" width="30" src="https://raw.githubusercontent.com/FinanF/COMP47250-Team-Software-Project/main/crest-ucd.svg" /> Web-based Human-in-the-Loop (HITL) AI System for Traffic Signal Optimisation 

Traffic optimisation interface using Dublin city simulated traffic data.

## Contents

- [Deployment](#deployment)
- [WebSocket API Reference](#websocket-api-reference)
  - [Traffic Simulation Stream](#traffic-simulation-stream)
  - [Optimisation Stream](#optimisation-stream)
- [REST API](#rest-api)
- [Database Schema](#database-schema)
- [Authors](#authors)

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

The traffic simulation runs in a background worker, and this endpoint streams junction and vehicle updates over the WebSocket while the simulation is active.
#### Junction State Update

The server periodically sends the current state of all simulated traffic junctions.

##### Message Type

```json
{
  "type": "junction_state"
}
```

##### Simulation Fields

| Field                | Type      | Description                           |
|:---------------------|:----------|:--------------------------------------|
| `type`               | `string`  | Message identifier (`junction_state`) |
| `schema_version`     | `string`  | Version of the message schema         |
| `step`               | `integer` | Current simulation step               |
| `timestamp`          | `float`   | Simulation timestamp in seconds       |
| `junction_count`     | `integer` | Number of active junctions            |
| `sim_status`         | `string`  | Current simulation status             |
| `sim_time_remaining` | `float`   | Remaining simulation time             |

##### Junction Object

| Field                      | Type      | Description                 |
|:---------------------------|:----------|:----------------------------|
| `id`                       | `string`  | Unique junction identifier  |
| `lat`                      | `float`   | Latitude coordinate         |
| `lng`                      | `float`   | Longitude coordinate        |
| `current_phase`            | `integer` | Current traffic light phase |
| `phase_duration_total`     | `float`   | Total phase duration        |
| `phase_duration_remaining` | `float`   | Remaining phase duration    |
| `phase_duration_elapsed`   | `float`   | Elapsed phase duration      |
| `signal_state`             | `string`  | Current signal state        |

##### Approach Object

| Field                 | Type      | Description               |
|:----------------------|:----------|:--------------------------|
| `lane_id`             | `string`  | SUMO lane identifier      |
| `queue_length`        | `integer` | Number of queued vehicles |
| `waiting_time_avg`    | `float`   | Average waiting time      |
| `vehicle_count`       | `integer` | Number of vehicles        |
| `green`               | `boolean` | Lane currently has green  |
| `seconds_since_green` | `float`   | Seconds since last green  |

---

#### Vehicle State Update

Provides real-time vehicle position and movement data.

##### Message Type

```json
{
  "type": "vehicle_state"
}
```

##### Vehicle Object

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

| Field     | Type     | Description             |
|:----------|:---------|:------------------------|
| `id`      | `string` | Vehicle identifier      |
| `lat`     | `float`  | Latitude                |
| `lng`     | `float`  | Longitude               |
| `speed`   | `float`  | Speed                   |
| `angle`   | `float`  | Heading                 |
| `road_id` | `string` | Current road identifier |

---

### Optimisation Stream

Connect to receive AI-generated optimisation recommendations.

```http
ws://localhost:8000/opt
```

The optimisation worker analyses congestion events and streams recommendations to connected clients.

#### Recommendation Message

##### Message Type

```json
{
  "type": "recommendation",
  "data": {
    "recommendation_id": "eab8f9c2-4d3e-4a1b-9f5e-2c3d4e5f6a7b",
    "junction_id": "1396454306",
    "pattern_type": "congestion",
    "severity_score": 0.85,
    "old_cycle_length": 90.0,
    "new_cycle_length": 75.0,
    "old_phase_splits": {
      "phase_1": 30.0,
      "phase_2": 30.0,
      "phase_3": 30.0
    },
    "new_phase_splits": {
      "phase_1": 25.0,
      "phase_2": 25.0,
      "phase_3": 25.0
    },
    "new_phase_durations": [25.0, 25.0, 25.0],
    "before_max_queue": 15,
    "after_est_queue": 10.5,
    "before_avg_wait": 20.0,
    "after_est_wait": 15.0,
    "improvement_pct": 25.0,
    "explanation": "Reducing cycle length and adjusting phase splits to alleviate congestion.",
    "created_at": "2026-07-18T17:01:55"
  }
}
```

##### Recommendation Fields

| Field                 | Type           | Description                        |
|:----------------------|:---------------|:-----------------------------------|
| `recommendation_id`   | `string`       | Recommendation identifier          |
| `junction_id`         | `string`       | Junction requiring optimisation    |
| `pattern_type`        | `string`       | Detected congestion pattern        |
| `severity_score`      | `float`        | Confidence/severity score          |
| `old_cycle_length`    | `float`        | Current cycle length               |
| `new_cycle_length`    | `float`        | Proposed cycle length              |
| `old_phase_splits`    | `object`       | Existing green allocations         |
| `new_phase_splits`    | `object`       | Proposed green allocations         |
| `new_phase_durations` | `array<float>` | Proposed phase durations           |
| `before_max_queue`    | `integer`      | Current maximum queue              |
| `after_est_queue`     | `float`        | Estimated queue after optimisation |
| `before_avg_wait`     | `float`        | Current average wait               |
| `after_est_wait`      | `float`        | Estimated average wait             |
| `improvement_pct`     | `float`        | Estimated improvement              |
| `explanation`         | `string`       | Human-readable explanation         |
| `created_at`          | `string`       | Recommendation timestamp           |

#### Operator Response

Clients respond by accepting or rejecting a recommendation.

##### Message

```json
{
  "action": "accept",
  "recommendation_id": "eab8f9c2-4d3e-4a1b-9f5e-2c3d4e5f6a7b"
}
```

or

```json
{
  "action": "reject",
  "recommendation_id": "eab8f9c2-4d3e-4a1b-9f5e-2c3d4e5f6a7b"
}
```

##### Fields

| Field               | Type     | Description               |
|:--------------------|:---------|:--------------------------|
| `action`            | `string` | `accept` or `reject`      |
| `recommendation_id` | `string` | Recommendation identifier |

#### Decision Status Updates

After the operator sends an `accept` or `reject` action, the backend applies the signal timing change in the simulation and streams **decision result** updates back over the same websocket.

##### Status Update Message

###### Message Type

```json
{
  "type": "decision_result",
  "data": {
    "recommendation_id": "eab8f9c2-4d3e-4a1b-9f5e-2c3d4e5f6a7b",
    "junction_id": "1396454306",
    "status": "queued"
  }
}
```

Or later, when the change is applied or fails:

```json
{
  "type": "decision_result",
  "data": {
    "recommendation_id": "eab8f9c2-4d3e-4a1b-9f5e-2c3d4e5f6a7b",
    "junction_id": "1396454306",
    "status": "applied"
  }
}
```

```json
{
  "type": "decision_result",
  "data": {
    "recommendation_id": "eab8f9c2-4d3e-4a1b-9f5e-2c3d4e5f6a7b",
    "junction_id": "1396454306",
    "status": "failed"
  }
}
```

##### Status Fields

| Field               | Type     | Description                                                                |
|:--------------------|:---------|:---------------------------------------------------------------------------|
| `recommendation_id` | `string` | Identifier of the recommendation this status refers to                     |
| `junction_id`       | `string` | Junction where the signal program change was attempted                     |
| `status`            | `string` | One of `queued`, `applied`, or `failed`, representing the change lifecycle |

- `queued`: The recommendation was accepted and queued for application in the simulation.  
- `applied`: The new signal program was successfully applied at the junction.  
- `failed`: The attempt to apply the new signal program failed (see server logs for details).

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

| Parameter     | Type     | Description         |
|:--------------|:---------|:--------------------|
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

## Database Schema

The application uses PostgreSQL to persist static junction metadata and maintain an audit log of accepted traffic signal optimisation recommendations.

---

### `junctions`

Stores the geographical information for each signalised junction in the SUMO road network. This table is populated during system initialisation and serves as a reference for mapping and reporting.

| Column        | Type     | Description                                              |
|:--------------|:---------|:---------------------------------------------------------|
| `junction_id` | `string` | Unique identifier of the traffic junction (Primary Key). |
| `lat`         | `float`  | Latitude of the junction.                                |
| `lng`         | `float`  | Longitude of the junction.                               |

---

### `accepted_recommendations`

Stores an audit record for every optimisation recommendation accepted by the operator. After a recommendation is applied, the system measures the resulting traffic performance and records both the baseline and post-optimisation metrics.

| Column                | Type       | Description                                                                                         |
|:----------------------|:-----------|:----------------------------------------------------------------------------------------------------|
| `id`                  | `integer`  | Unique record identifier (Primary Key).                                                             |
| `junction_id`         | `string`   | Identifier of the junction where the optimisation was applied.                                      |
| `queue_reduction_pct` | `float`    | Measured percentage reduction in average queue length.                                              |
| `wait_reduction_pct`  | `float`    | Measured percentage reduction in average vehicle waiting time.                                      |
| `before_avg_queue`    | `float`    | Average queue length before applying the optimisation.                                              |
| `after_avg_queue`     | `float`    | Average queue length after applying the optimisation.                                               |
| `before_avg_wait`     | `float`    | Average vehicle waiting time before optimisation (seconds).                                         |
| `after_avg_wait`      | `float`    | Average vehicle waiting time after optimisation (seconds).                                          |
| `measured_at`         | `float`    | Simulation timestamp when the post-optimisation measurements were recorded.                         |
| `accepted_at`         | `datetime` | Timestamp when the recommendation was accepted and logged. Automatically generated by the database. |

## Authors

- [Ruhao Yang](https://github.com/YangRuhao)
- [Princeton Jose](https://github.com/princetonjose17-dotcom)
- [Yuyao Wang](https://github.com/KiriWang2002)
- [Finan Fagan](https://github.com/FinanF)