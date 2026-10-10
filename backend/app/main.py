import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

app = FastAPI(title="CivicPulse Core API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgrespassword@localhost:5432/civicpulse_db",
)
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 12

ALLOWED_STATUSES = {"PENDING_TRIAGE", "ASSIGNED", "IN_PROGRESS", "RESOLVED"}
ALLOWED_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


# --- Security helpers ---

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2_sha256$100000${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, iterations, salt, expected = stored_hash.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user: dict) -> str:
    payload = {
        "sub": user["email"],
        "role": user["role"],
        "name": user["full_name"],
        "ward": user.get("ward"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return payload


def require_officer(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Municipal officer access required")
    return user


# --- Pydantic models ---

class HazardReport(BaseModel):
    title: str
    category: str
    description: Optional[str] = ""
    severity: Optional[str] = "MEDIUM"
    latitude: float
    longitude: float
    image_data: Optional[str] = None


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
    status: str
    resolution_notes: Optional[str] = None


class HazardAssignment(BaseModel):
    assigned_to: str


class HazardComment(BaseModel):
    message: str


class UserLogin(BaseModel):
    username: str
    password: str
    role: str


# --- Health and authentication ---

@app.get("/health")
def health_check():
    return {"status": "online", "system": "CivicPulse Core"}


@app.post("/api/v1/auth/login")
def login(creds: UserLogin):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE email = %s AND role = %s", (creds.username, creds.role))
        user = cur.fetchone()
        if not user or not verify_password(creds.password, user["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

        token = create_access_token(user)
        return {
            "token": token,
            "role": user["role"],
            "name": user["full_name"],
            "ward": user["ward"],
            "redirect": "admin.html" if user["role"] == "admin" else "index.html",
        }
    finally:
        cur.close()
        conn.close()


# --- Hazard ingestion ---

@app.post("/api/v1/hazards")
def report_hazard(report: HazardReport, user: dict = Depends(get_current_user)):
    if report.severity not in ALLOWED_SEVERITIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid severity")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        dedup_query = """
            SELECT id, title, upvotes,
                   ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance_meters
            FROM hazards
            WHERE category = %s
              AND status != 'RESOLVED'
              AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 50)
            ORDER BY distance_meters ASC
            LIMIT 1;
        """
        cur.execute(
            dedup_query,
            (report.longitude, report.latitude, report.category, report.longitude, report.latitude),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """UPDATE hazards SET upvotes = upvotes + 1 WHERE id = %s
                   RETURNING id, title, upvotes, status;""",
                (existing["id"],),
            )
            updated = cur.fetchone()
            conn.commit()
            return {
                "action": "DEDUPLICATED_AND_MERGED",
                "message": f"Hazard already reported {round(existing['distance_meters'])}m away. Upvote added.",
                "data": updated,
            }

        sla_hours = 24 if report.severity == "CRITICAL" else (48 if report.severity == "HIGH" else 168)
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        cur.execute(
            """INSERT INTO hazards
               (title, category, severity, status, description, upvotes, image_data, geom, sla_deadline)
               VALUES (%s, %s, %s, 'PENDING_TRIAGE', %s, 1, %s,
                       ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
               RETURNING id, title, category, severity, status, upvotes, sla_deadline;""",
            (
                report.title,
                report.category,
                report.severity,
                report.description,
                report.image_data,
                report.longitude,
                report.latitude,
                sla_deadline,
            ),
        )
        new_hazard = cur.fetchone()

        cur.execute(
            """INSERT INTO hazard_updates
               (hazard_id, author_email, author_role, update_type, message, status_to)
               VALUES (%s, %s, %s, 'STATUS_CHANGE', %s, 'PENDING_TRIAGE');""",
            (new_hazard["id"], user["sub"], user["role"], "Hazard report created", ),
        )
        conn.commit()
        return {"action": "CREATED", "message": "New civic hazard ticket created.", "data": new_hazard}
    finally:
        cur.close()
        conn.close()


# --- Hazard queries ---

HAZARD_SELECT = """
    SELECT id, title, category, severity, status, description, upvotes, image_data,
           assigned_to, assigned_at, resolution_notes, resolved_at,
           ST_Y(geom) AS latitude, ST_X(geom) AS longitude,
           created_at, sla_deadline,
           (status != 'RESOLVED' AND sla_deadline < NOW()) AS is_overdue
    FROM hazards
"""


@app.get("/api/v1/hazards")
def list_hazards(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(HAZARD_SELECT + " ORDER BY is_overdue DESC, upvotes DESC, created_at DESC;")
        hazards = cur.fetchall()
        return {"count": len(hazards), "hazards": hazards}
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/hazards/overdue")
def list_overdue_hazards(user: dict = Depends(require_officer)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            HAZARD_SELECT
            + " WHERE status != 'RESOLVED' AND sla_deadline < NOW() ORDER BY sla_deadline ASC;"
        )
        overdue = cur.fetchall()
        return {"count": len(overdue), "hazards": overdue}
    finally:
        cur.close()
        conn.close()


def get_hazard_or_404(cur, hazard_id: int):
    cur.execute(HAZARD_SELECT + " WHERE id = %s;", (hazard_id,))
    hazard = cur.fetchone()
    if not hazard:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hazard ticket not found")
    return hazard


# --- Officer workflow ---

@app.patch("/api/v1/hazards/{hazard_id}/assign")
def assign_hazard(
    hazard_id: int,
    payload: HazardAssignment,
    user: dict = Depends(require_officer),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        hazard = get_hazard_or_404(cur, hazard_id)
        if hazard["status"] == "RESOLVED":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Resolved tickets cannot be assigned")

        cur.execute(
            """UPDATE hazards
               SET assigned_to = %s, assigned_at = NOW(),
                   status = CASE WHEN status = 'PENDING_TRIAGE' THEN 'ASSIGNED' ELSE status END
               WHERE id = %s
               RETURNING id, title, status, assigned_to, assigned_at;""",
            (payload.assigned_to, hazard_id),
        )
        updated = cur.fetchone()

        cur.execute(
            """INSERT INTO hazard_updates
               (hazard_id, author_email, author_role, update_type, message, status_from, status_to)
               VALUES (%s, %s, %s, 'ASSIGNMENT', %s, %s, %s);""",
            (
                hazard_id,
                user["sub"],
                user["role"],
                f"Assigned to {payload.assigned_to}",
                hazard["status"],
                updated["status"],
            ),
        )
        conn.commit()
        return {"action": "ASSIGNED", "hazard": updated}
    finally:
        cur.close()
        conn.close()


@app.patch("/api/v1/hazards/{hazard_id}/status")
def update_hazard_status(
    hazard_id: int,
    payload: HazardStatusUpdate,
    user: dict = Depends(require_officer),
):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid workflow status")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        hazard = get_hazard_or_404(cur, hazard_id)
        resolved_at = datetime.now(timezone.utc) if payload.status == "RESOLVED" else None

        cur.execute(
            """UPDATE hazards
               SET status = %s,
                   resolution_notes = COALESCE(%s, resolution_notes),
                   resolved_at = COALESCE(%s, resolved_at)
               WHERE id = %s
               RETURNING id, title, status, resolution_notes, resolved_at;""",
            (payload.status, payload.resolution_notes, resolved_at, hazard_id),
        )
        updated = cur.fetchone()

        cur.execute(
            """INSERT INTO hazard_updates
               (hazard_id, author_email, author_role, update_type, message, status_from, status_to)
               VALUES (%s, %s, %s, 'STATUS_CHANGE', %s, %s, %s);""",
            (
                hazard_id,
                user["sub"],
                user["role"],
                payload.resolution_notes or f"Status changed to {payload.status}",
                hazard["status"],
                payload.status,
            ),
        )
        conn.commit()
        return {"action": "UPDATED", "hazard": updated}
    finally:
        cur.close()
        conn.close()


# --- Citizen comments and timeline ---

@app.post("/api/v1/hazards/{hazard_id}/comments")
def add_hazard_comment(
    hazard_id: int,
    payload: HazardComment,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        get_hazard_or_404(cur, hazard_id)
        cur.execute(
            """INSERT INTO hazard_updates
               (hazard_id, author_email, author_role, update_type, message)
               VALUES (%s, %s, %s, 'COMMENT', %s)
               RETURNING id, hazard_id, author_email, author_role, message, created_at;""",
            (hazard_id, user["sub"], user["role"], payload.message),
        )
        comment = cur.fetchone()
        conn.commit()
        return {"action": "COMMENT_ADDED", "comment": comment}
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/hazards/{hazard_id}/timeline")
def get_hazard_timeline(hazard_id: int, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        get_hazard_or_404(cur, hazard_id)
        cur.execute(
            """SELECT id, hazard_id, author_email, author_role, update_type,
                      message, status_from, status_to, created_at
               FROM hazard_updates
               WHERE hazard_id = %s
               ORDER BY created_at ASC, id ASC;""",
            (hazard_id,),
        )
        return {"count": cur.rowcount, "timeline": cur.fetchall()}
    finally:
        cur.close()
        conn.close()


# --- Governance notices ---

@app.get("/api/v1/notices")
def list_notices():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM public_notices ORDER BY is_critical DESC, start_time ASC;")
        return {"notices": cur.fetchall()}
    finally:
        cur.close()
        conn.close()


@app.post("/api/v1/notices")
def create_notice(notice: PublicNoticeCreate, user: dict = Depends(require_officer)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO public_notices
               (title, category, description, affected_areas, department, start_time, end_time, is_critical)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *;""",
            (
                notice.title,
                notice.category,
                notice.description,
                notice.affected_areas,
                notice.department,
                notice.start_time,
                notice.end_time,
                notice.is_critical,
            ),
        )
        created = cur.fetchone()
        conn.commit()
        return {"action": "PUBLISHED", "notice": created}
    finally:
        cur.close()
        conn.close()
