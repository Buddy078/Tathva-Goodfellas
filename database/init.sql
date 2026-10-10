-- Enable PostGIS spatial extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Application users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('citizen', 'admin')),
    ward VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Hazards & Grievances Table
CREATE TABLE IF NOT EXISTS hazards (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_TRIAGE',
    description TEXT,
    upvotes INT DEFAULT 1,
    image_data TEXT,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sla_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    assigned_to VARCHAR(150),
    assigned_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_hazards_geom ON hazards USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_hazards_status_sla ON hazards (status, sla_deadline);

-- 3. Immutable ticket audit timeline
CREATE TABLE IF NOT EXISTS hazard_updates (
    id SERIAL PRIMARY KEY,
    hazard_id INT NOT NULL REFERENCES hazards(id) ON DELETE CASCADE,
    author_email VARCHAR(255) NOT NULL,
    author_role VARCHAR(20) NOT NULL,
    update_type VARCHAR(30) NOT NULL CHECK (update_type IN ('COMMENT', 'STATUS_CHANGE', 'ASSIGNMENT')),
    message TEXT,
    status_from VARCHAR(30),
    status_to VARCHAR(30),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hazard_updates_hazard ON hazard_updates (hazard_id, created_at DESC);

-- 4. Public Governance Notices Table
CREATE TABLE IF NOT EXISTS public_notices (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    affected_areas VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    is_critical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed users. Demo passwords: admin123 / citizen123
INSERT INTO users (email, full_name, password_hash, role, ward)
VALUES
(
    'admin@coimbatore.gov.in',
    'Engineer J. Ramanathan',
    'pbkdf2_sha256$100000$ccc331c2efd3d5c1e09e8642c749f6c5$e89db6213a833fdf7512647f651bb6a3432193abc88490a68edb0bffeadb3016',
    'admin',
    'Zone 4 (Central)'
),
(
    'citizen@civicpulse.in',
    'Demo Citizen',
    'pbkdf2_sha256$100000$8e68f917430d7627b43a8f259f6d24d7$5d8a9bb67ebfa3574c46061874b90a0da75845305714969a057e0118e38a2435',
    'citizen',
    'Ward 7'
)
ON CONFLICT (email) DO NOTHING;

-- Seed Initial Mock Records for Offline Demo
INSERT INTO hazards (title, category, severity, status, description, upvotes, geom, sla_deadline)
VALUES 
('Open Stormwater Drain Near Bus Stop', 'ROAD', 'CRITICAL', 'PENDING_TRIAGE', 'Severe foot hazard for commuters.', 12, ST_SetSRID(ST_MakePoint(76.9558, 11.0168), 4326), NOW() + INTERVAL '24 hours'),
('Overflowing Secondary Waste Dump', 'SANITATION', 'HIGH', 'IN_PROGRESS', 'Garbage bin overflowing onto main carriageway.', 5, ST_SetSRID(ST_MakePoint(76.9620, 11.0210), 4326), NOW() + INTERVAL '48 hours');

INSERT INTO public_notices (title, category, description, affected_areas, department, start_time, end_time, is_critical)
VALUES 
('Scheduled 11kV Substation Grid Maintenance', 'POWER_SHUTDOWN', 'Transformer maintenance leading to feeder disconnection.', 'Gandhipuram, Cross Cut Rd, 7th Ward', 'TANGEDCO Electricity Board', NOW(), NOW() + INTERVAL '6 hours', TRUE),
('Primary Water Line Replacement', 'WATER_OUTAGE', 'Pipeline repairs will cause low pressure or temporary disruption.', 'South Zone, Sectors 2 & 3', 'Municipal Water Supply Board', NOW() + INTERVAL '1 day', NOW() + INTERVAL '1 day 8 hours', FALSE);
