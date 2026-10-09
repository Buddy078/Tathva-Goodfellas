import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

app = FastAPI(title="CivicPulse Core API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/civicpulse_db")

def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# --- Pydantic Data Models ---
class HazardReport(BaseModel):
    title: str
    category: str  # ROAD, SANITATION, ELECTRICAL, WATER
    description: Optional[str] = ""
    severity: Optional[str] = "MEDIUM"
    latitude: float
    longitude: float

class PublicNoticeCreate(BaseModel):
    title: str
    category: str
    description: str
    affected_areas: str
    department: str
    start_time: datetime
    end_time: datetime
    is_critical: Optional[bool] = False

class HazardStatusUpdate(BaseModel):
    status: str  # PENDING_TRIAGE, IN_PROGRESS, RESOLVED

# --- Health Check ---
@app.get("/health")
def health_check():
    return {"status": "online", "system": "CivicPulse Core"}

# 1. HAZARD INGESTION WITH SPATIAL DEDUPLICATION (50-meter PostGIS check)
@app.post("/api/v1/hazards")
def report_hazard(report: HazardReport):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        dedup_query = """
            SELECT id, title, upvotes, 
                   ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) as distance_meters
            FROM hazards
            WHERE category = %s
              AND status != 'RESOLVED'
              AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 50)
            ORDER BY distance_meters ASC
            LIMIT 1;
        """
        cur.execute(dedup_query, (report.longitude, report.latitude, report.category, report.longitude, report.latitude))
        existing = cur.fetchone()

        if existing:
            update_query = """
                UPDATE hazards 
                SET upvotes = upvotes + 1 
                WHERE id = %s 
                RETURNING id, title, upvotes, status;
            """
            cur.execute(update_query, (existing["id"],))
            updated_hazard = cur.fetchone()
            conn.commit()
            return {
                "action": "DEDUPLICATED_AND_MERGED",
                "message": f"Hazard already reported {round(existing['distance_meters'])}m away. Upvote added to escalate priority.",
                "data": updated_hazard
            }

        sla_hours = 24 if report.severity == "CRITICAL" else (48 if report.severity == "HIGH" else 168)
        sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)

        insert_query = """
            INSERT INTO hazards (title, category, severity, status, description, upvotes, geom, sla_deadline)
            VALUES (%s, %s, %s, 'PENDING_TRIAGE', %s, 1, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
            RETURNING id, title, category, severity, status, upvotes, sla_deadline;
        """
        cur.execute(insert_query, (
            report.title, report.category, report.severity, report.description,
            report.longitude, report.latitude, sla_deadline
        ))
        new_hazard = cur.fetchone()
        conn.commit()
        return {
            "action": "CREATED",
            "message": "New civic hazard ticket created successfully.",
            "data": new_hazard
        }
    finally:
        cur.close()
        conn.close()

# 2. GET ALL HAZARDS (For Admin GIS Map & Queue)
@app.get("/api/v1/hazards")
def list_hazards():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT id, title, category, severity, status, description, upvotes,
                   ST_Y(geom) as latitude, ST_X(geom) as longitude,
                   created_at, sla_deadline
            FROM hazards
            ORDER BY upvotes DESC, created_at DESC;
        """
        cur.execute(query)
        hazards = cur.fetchall()
        return {"count": len(hazards), "hazards": hazards}
    finally:
        cur.close()
        conn.close()

# 3. UPDATE HAZARD WORK-ORDER STATUS (Admin Triage Workflow)
@app.patch("/api/v1/hazards/{hazard_id}/status")
def update_hazard_status(hazard_id: int, payload: HazardStatusUpdate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE hazards SET status = %s WHERE id = %s RETURNING id, title, status;",
            (payload.status, hazard_id)
        )
        updated = cur.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Hazard ticket not found")
        conn.commit()
        return {"action": "UPDATED", "hazard": updated}
    finally:
        cur.close()
        conn.close()

# 4. GET GOVERNANCE NOTICES (For Citizen Home Feed)
@app.get("/api/v1/notices")
def list_notices():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM public_notices ORDER BY is_critical DESC, start_time ASC;")
        notices = cur.fetchall()
        return {"notices": notices}
    finally:
        cur.close()
        conn.close()

# 5. PUBLISH NOTICE (For Admin Portal Broadcast)
@app.post("/api/v1/notices")
def create_notice(notice: PublicNoticeCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        insert_query = """
            INSERT INTO public_notices (title, category, description, affected_areas, department, start_time, end_time, is_critical)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *;
        """
        cur.execute(insert_query, (
            notice.title, notice.category, notice.description, notice.affected_areas,
            notice.department, notice.start_time, notice.end_time, notice.is_critical
        ))
        created = cur.fetchone()
        conn.commit()
        return {"action": "PUBLISHED", "notice": created}
    finally:
        cur.close()
        conn.close()