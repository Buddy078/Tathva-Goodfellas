-- Enable PostGIS spatial extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Hazards & Grievances Table
CREATE TABLE IF NOT EXISTS hazards (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_TRIAGE',
    description TEXT,
    upvotes INT DEFAULT 1,
    image_data TEXT, -- Stores uploaded image Base64/URL
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sla_deadline TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Spatial GIST Index for Sub-Millisecond Radius Lookups
CREATE INDEX IF NOT EXISTS idx_hazards_geom ON hazards USING GIST (geom);

-- 2. Public Governance Notices Table
CREATE TABLE IF NOT EXISTS public_notices (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL, -- POWER_SHUTDOWN, WATER_OUTAGE, TRAFFIC_DIVERSION, CIVIC_EVENT
    description TEXT NOT NULL,
    affected_areas VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    is_critical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed Initial Mock Records for Offline Demo
INSERT INTO hazards (title, category, severity, status, description, upvotes, geom, sla_deadline)
VALUES 
('Open Stormwater Drain Near Bus Stop', 'ROAD', 'CRITICAL', 'PENDING_TRIAGE', 'Severe foot hazard for commuters.', 12, ST_SetSRID(ST_MakePoint(76.9558, 11.0168), 4326), NOW() + INTERVAL '24 hours'),
('Overflowing Secondary Waste Dump', 'SANITATION', 'HIGH', 'IN_PROGRESS', 'Garbage bin overflowing onto main carriageway.', 5, ST_SetSRID(ST_MakePoint(76.9620, 11.0210), 4326), NOW() + INTERVAL '48 hours');

INSERT INTO public_notices (title, category, description, affected_areas, department, start_time, end_time, is_critical)
VALUES 
('Scheduled 11kV Substation Grid Maintenance', 'POWER_SHUTDOWN', 'Transformer maintenance leading to feeder disconnection.', 'Gandhipuram, Cross Cut Rd, 7th Ward', 'TANGEDCO Electricity Board', NOW(), NOW() + INTERVAL '6 hours', TRUE),
('Primary Water Line Replacement', 'WATER_OUTAGE', 'Pipeline repairs will cause low pressure or temporary disruption.', 'South Zone, Sectors 2 & 3', 'Municipal Water Supply Board', NOW() + INTERVAL '1 day', NOW() + INTERVAL '1 day 8 hours', FALSE);