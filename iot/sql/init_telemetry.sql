-- IoT telemetry schema (runs on first Postgres/TimescaleDB start)

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS iot_device (
    device_id       VARCHAR(64) PRIMARY KEY,
    device_type     VARCHAR(32) NOT NULL,
    city_id         VARCHAR(32) NOT NULL DEFAULT 'delhi-ncr',
    zone_code       VARCHAR(32) NOT NULL,
    asset_name      VARCHAR(128),
    edge_gateway_id VARCHAR(64),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    last_seen_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS telemetry_reading (
    time            TIMESTAMPTZ NOT NULL,
    device_id       VARCHAR(64) NOT NULL,
    device_type     VARCHAR(32) NOT NULL,
    zone_code       VARCHAR(32) NOT NULL,
    metric          VARCHAR(64) NOT NULL,
    value           DOUBLE PRECISION NOT NULL,
    unit            VARCHAR(16),
    quality         VARCHAR(16) DEFAULT 'good',
    event_id        UUID,
    PRIMARY KEY (time, device_id, metric)
);

SELECT create_hypertable('telemetry_reading', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_telemetry_zone_time ON telemetry_reading (zone_code, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_time ON telemetry_reading (device_id, time DESC);

CREATE TABLE IF NOT EXISTS telemetry_alert (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ DEFAULT now(),
    device_id       VARCHAR(64) NOT NULL,
    zone_code       VARCHAR(32) NOT NULL,
    alert_type      VARCHAR(64) NOT NULL,
    severity        VARCHAR(16) NOT NULL,
    message         TEXT NOT NULL,
    metric          VARCHAR(64),
    value           DOUBLE PRECISION,
    threshold       DOUBLE PRECISION,
    source          VARCHAR(32) DEFAULT 'edge',
    acknowledged    BOOLEAN DEFAULT FALSE
);

-- Seed devices (Delhi NCR demo)
INSERT INTO iot_device (device_id, device_type, zone_code, asset_name, edge_gateway_id) VALUES
    ('FM-NRD-001', 'flow_meter', 'north-delhi', 'North DMA Inlet', 'edge-north-01'),
    ('FM-STH-001', 'flow_meter', 'south-delhi', 'South Trunk Flow', 'edge-south-01'),
    ('RSV-CTR-01', 'reservoir_level', 'central-delhi', 'Central Reservoir', 'edge-central-01'),
    ('PRS-EAST-12', 'pressure_sensor', 'east-delhi', 'East Main Pressure', 'edge-east-01'),
    ('PRS-WEST-05', 'pressure_sensor', 'west-delhi', 'West Pump Discharge', 'edge-west-01'),
    ('GW-WEST-03', 'groundwater', 'west-delhi', 'West Aquifer Well 3', 'edge-west-01')
ON CONFLICT (device_id) DO NOTHING;
