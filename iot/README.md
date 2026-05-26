# IoT Pipeline — Quick Start

Real-time water telemetry: **sensors → edge gateway → MQTT → Kafka → PostgreSQL/Redis**.

Full design: [docs/IOT_ARCHITECTURE.md](../docs/IOT_ARCHITECTURE.md)

## Prerequisites

- Docker Desktop (for EMQX, Redpanda, Postgres, Redis)
- Python 3.10+

## 1. Start infrastructure

From project root:

```powershell
docker compose -f docker-compose.iot.yml up -d
```

| Service | URL / Port |
|---------|------------|
| EMQX MQTT | `localhost:1883` |
| EMQX Dashboard | http://localhost:18083 (admin / public) |
| Kafka (Redpanda) | `localhost:19092` |
| PostgreSQL | `localhost:5432` (user/pass/db: `water` / `water` / `water_iot`) |
| Redis | `localhost:6379` |

## 2. Install Python dependencies

```powershell
pip install -r requirements-iot.txt
```

## 3. Run the pipeline (4 terminals)

**Terminal A — Sensor simulators + edge aggregation**

```powershell
cd "c:\Users\DELL\Downloads\Project dataset\WATER"
python -m iot.simulators.run_all
```

**Terminal B — MQTT → Kafka ingestion**

```powershell
python -m iot.services.telemetry_ingestion.main
```

**Terminal C — Kafka → database (+ optional API)**

```powershell
python -m iot.services.telemetry_consumer.main --api
```

**Terminal D — (optional) Streamlit main dashboard**

```powershell
streamlit run dashboard.py
```

## 4. Verify

- **REST API docs:** http://localhost:8080/docs  
- **Latest flow reading:** http://localhost:8080/telemetry/latest/FM-NRD-001  
- **Zone summary:** http://localhost:8080/telemetry/zone/north-delhi/summary  
- **EMQX:** Subscribe to `water/#` in dashboard to see live MQTT messages  
- **SQL:**

```sql
SELECT device_id, metric, value, time
FROM telemetry_reading
ORDER BY time DESC LIMIT 20;
```

## Sensor types simulated

| Type | Device IDs | Key metrics |
|------|------------|-------------|
| Flow | `FM-NRD-001`, `FM-STH-001` | `flow_rate_lpm`, `cumulative_volume_liters` |
| Reservoir | `RSV-CTR-01` | `level_percent`, `volume_m3` |
| Pressure | `PRS-EAST-12`, `PRS-WEST-05` | `pressure_bar` |
| Groundwater | `GW-WEST-03` | `water_table_m`, `drawdown_m` |

## Architecture (runtime)

```
Simulators → EdgeGateway (aggregate, rules, buffer)
          → MQTT (EMQX)
          → telemetry-ingestion → Kafka
          → telemetry-consumer → TimescaleDB + Redis
          → REST API / future dashboard widgets
```

## Configuration

Copy `iot/.env.example` to `.env` in project root to override hosts/ports.

Device registry: `iot/config/devices.yaml`  
JSON Schema: `iot/schemas/telemetry_v1.json`
