# CivicPulse 🏛️⚡

> **Intelligent Urban Hazard Triage & Proactive Governance Dispatcher**  
> *Track 4: Civic Tech & Governance*

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791.svg)](https://postgis.net/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Executive Summary & Problem Statement

Urban Local Bodies (ULBs) face significant structural challenges in managing civic reporting and citizen communication:

1. **Grievance Noise & Redundancy:** Up to 60% of citizen reports during infrastructure breakdowns (e.g., open drains, water bursts, arterial potholes) are redundant duplicates from adjacent coordinates, bogging down manual triage teams.
2. **Asymmetric Communication:** Municipal utility disruptions (power grid maintenance, pipeline repairs, road closures) are often broadcast via outdated paper gazettes or disparate portals, leading to preventable public distress and inbound complaint spikes.
3. **Accountability & SLA Tracking Gaps:** Without rigorous spatial indexing and automated severity scoring, high-risk hazards fail to receive rapid dispatch timelines.
4. **Data Friction & Spoofing:** Citizen reporting often requires manual address lookup or text descriptions that lack ground-truth validation and geographic accuracy.

**CivicPulse** is an offline-first, dual-channel municipal platform that solves these challenges through **spatial deduplication**, **hardware EXIF GPS extraction**, **interactive GIS triage**, **dynamic SLA dispatch**, and **hyper-local governance broadcasting**.

---

## 💡 Key Architectural Innovations & Features

### 1. Spatial Deduplication Engine

Incoming citizen tickets run against an automated PostGIS proximity query:

```sql
SELECT id, title, upvotes,
       ST_Distance(
           geom::geography,
           ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
       ) AS distance_meters
FROM hazards
WHERE category = :category
  AND status != 'RESOLVED'
  AND ST_DWithin(
      geom::geography,
      ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
      50
  )
ORDER BY distance_meters ASC
LIMIT 1;
```

If an unresolved ticket exists in the same category within 50 meters, the platform suppresses duplicate work-order generation, links the citizen's photographic evidence, and increments the master ticket's community upvote counter.

### 2. Client-Side EXIF GPS Extraction & Camera Geotagging

- **Zero-Friction Geotagging:** When a citizen captures or uploads a photo from their smartphone, the client parses embedded hardware EXIF metadata (`exif-js`) directly in the browser.
- **Automated Coordinate Resolution:** Converts Degree-Minute-Second (DMS) coordinates to decimal latitude/longitude in real time, removing the need for manual address entry.
- **Hardware Fallback:** Falls back seamlessly to HTML5 Device Geolocation (`navigator.geolocation`) if camera metadata is stripped.

### 3. Store-and-Forward Offline Resilience

- **Offline Dead-Zone Queue:** If a citizen reports a hazard in an area with zero cellular or Wi-Fi connectivity, the incident payload and base64 photographic proof are cached locally in browser `localStorage`.
- **Automatic Background Synchronization:** Listens for `window.addEventListener('online')` to automatically replay and flush cached reports to the backend once connectivity is re-established.

### 4. Interactive GIS Command Center with Fly-To Inspection

- **ESRI Dark Canvas GIS Map:** Renders high-contrast dark vector tiles without API keys, watermarks, or usage limits.
- **One-Click Fly-To Focus:** Clicking any ticket row in the work order queue triggers an animated Leaflet camera flight (`map.flyTo([lat, lon], 16)`) directly to the hazard coordinates.
- **In-App Lightbox Proof Modal:** High-resolution photographic evidence expands in a dedicated modal overlay, bypassing browser popup blockers and data-URL restrictions.

### 5. Dynamic SLA Prioritization & Workflow State Machine

Work orders are auto-ranked using an impact equation balancing inherent hazard severity against citizen density:

\[
\text{Priority Score} = (\text{Severity Weight} \times 0.6) + (\text{Upvotes} \times 0.4)
\]

- **Critical (24h SLA):** Exposed live cables, open manholes, active structural collapse hazards.
- **High (48h SLA):** Major road cave-ins, water pipeline ruptures, uncollected sanitation piles.
- **Standard (168h SLA):** Defective public streetlights, damaged sidewalk curbs.
- **Inline Status Patching:** Municipal officers can update lifecycle states (`PENDING` → `DISPATCHED` → `RESOLVED`) directly from the table using asynchronous PATCH endpoints.

### 6. Proactive Governance Broadcast Feed

Allows ward officers to push geo-targeted advisories (power cuts, water shutoffs, traffic reroutes) directly to citizens, featuring category filters and urgent emergency priority flags.

### 7. Unified Authentication Gateway

A dual-portal authentication screen (`login.html`) supporting both Citizen Access and Municipal Officer Access, equipped with one-click evaluation presets to ensure rapid, fail-safe live demo execution.

---

## 🏗️ System Architecture

```text
+----------------------------------------------------------------------------------------------------+
|                                      CLIENT LAYER (Frontend)                                       |
|                                                                                                    |
|   +------------------------------------+           +-------------------------------------------+   |
|   |         CITIZEN WEB / PWA          |           |              ADMIN DASHBOARD              |   |
|   |  - EXIF GPS Auto-Extractor         |           |  - ESRI Dark GIS Map (Leaflet)            |   |
|   |  - Store-and-Forward Offline Sync  |           |  - One-Click Fly-To Incident Zoom         |   |
|   |  - Photo Proof Compression         |           |  - In-App Lightbox Photo Inspection       |   |
|   |  - Governance Broadcast Feed       |           |  - Interactive Status Selector (PATCH)    |   |
|   +-----------------+------------------+           +---------------------+---------------------+   |
+---------------------|----------------------------------------------------|-------------------------+
                      |                                                    |
                      | HTTPS / REST                                       | HTTPS / REST
                      v                                                    v
+----------------------------------------------------------------------------------------------------+
|                                    API GATEWAY & REVERSE PROXY                                     |
|                                         (Nginx / Docker)                                           |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  CORE BACKEND APPLICATION LAYER                                    |
|                                      (Python FastAPI / Uvicorn)                                    |
|                                                                                                    |
|   +------------------------+  +--------------------------+  +----------------------------------+   |
|   |    INGESTION ENGINE    |  |   SPATIAL DEDUPLICATION  |  |      GOVERNANCE DISPATCHER       |   |
|   |  - EXIF / Geo Validator|  |   - PostGIS ST_DWithin   |  |   - Ward-targeted advisories     |   |
|   |  - Base64 Image Parser |  |   - Auto-upvote merge    |  |   - Category & SLA routing       |   |
|   +------------------------+  +--------------------------+  +----------------------------------+   |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         v                                                 v
+--------------------------------------------------+  +----------------------------------------------+
|                PRIMARY DATABASE                  |  |             MEDIA EVIDENCE STORE             |
|             (PostgreSQL + PostGIS)               |  |               (Database Text / MinIO)        |
|  - Spatial tables: `hazards` (GiST index)        |  |  - High-res citizen photo captures           |
|  - Relational tables: `public_notices`           |  |  - Geotag metadata records                   |
+--------------------------------------------------+  +----------------------------------------------+
```

## 🛠️ Technology Decisions & Trade-Off Matrix

Every architectural component in CivicPulse was selected to optimize for low latency, zero external API dependencies during evaluations, and zero-cost municipal deployment.

| Architectural Layer | Selected Technology | Evaluated Alternatives | Deciding Factor & Trade-Off Analysis |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | Python (FastAPI) | Node.js (Express), Django, Spring Boot | **Why FastAPI:** Native asynchronous event loops (`asyncio`) handle concurrent citizen report spikes with low memory consumption. Built-in Pydantic validation guarantees strict GeoJSON payload validation at runtime.<br><br>**Trade-off:** Python is dynamically typed compared to Go/Java, but FastAPI’s type hints and async throughput outweigh this for rapid hackathon iteration. |
| **Spatial Database** | PostgreSQL + PostGIS | MongoDB (2dsphere), MySQL (Spatial), SQLite | **Why PostGIS:** Industry benchmark for spatial indexing (`GIST(geom)`). Supports complex geometric algorithms natively (e.g., `ST_DWithin`, spatial clustering) in sub-millisecond execution times without loading coordinates into app memory.<br><br>**Trade-off:** Higher base memory footprint (~150MB) compared to SQLite, but mandatory for high-concurrency municipal queries. |
| **GIS & Mapping Client** | Leaflet.js + ESRI Dark Canvas Basemap | Google Maps JS API, Mapbox GL JS (Cloud) | **Why Leaflet + ESRI:** Zero API keys, zero rate-limit watermarks, and reliable local execution. Works smoothly during stage presentations without cloud quota failures.<br><br>**Trade-off:** Lacks native 3D building extrusions found in Mapbox GL, but ensures total presentation reliability. |
| **Client Geolocation** | Client-Side EXIF Metadata Parser (`exif-js`) | Cloud Vision API, Server-Side ExifTool | **Why Client EXIF:** Extracts coordinates directly inside the user's browser before transmission. Reduces server upload latency and works offline in network dead zones.<br><br>**Trade-off:** Relies on device camera location permissions being active at capture time. |
| **Citizen & Admin Frontend** | Responsive PWA (Tailwind CSS, HTML5, Vanilla JS) | React Native, Flutter, Native Android | **Why PWA:** Eliminates app-store friction. Citizens access the portal instantly by scanning a QR code at bus stops or municipal notices. Uses native browser `navigator.geolocation` and camera capture.<br><br>**Trade-off:** Slightly less hardware-level access than a native APK, but dramatically increases citizen adoption rates. |
| **Deployment & Orchestration** | Docker & Docker Compose | Bare-metal Localhost, Managed Cloud (AWS/GCP), Kubernetes | **Why Docker Compose:** Creates an isolated, containerized local network. Booting the database, backend, and static client requires a single terminal command (`docker compose up`), eliminating environment drift and presentation crashes.<br><br>**Trade-off:** Adds an initial container build overhead, but provides reproducible, zero-internet reliability. |
| **Communication Protocol** | RESTful JSON + Async PATCH | gRPC, GraphQL | **Why REST:** Universal compatibility with existing municipal Smart City command centers (ICCC) and lightweight client execution.<br><br>**Trade-off:** GraphQL offers flexible querying, but introduces parsing overhead unnecessary for structured municipal schemas. |

## 💻 System Requirements & Software Prerequisites

To ensure reproducible, zero-internet offline evaluation during the finale presentation, verify that your machine meets the specifications outlined below.

### 1. Hardware Requirements

| Specification | Minimum Required | Recommended (For Smooth Demo) |
| :--- | :--- | :--- |
| **Processor (CPU)** | Dual-Core Intel/AMD or Apple Silicon (M-series) | Quad-Core 2.0+ GHz Intel/AMD or Apple Silicon (M1/M2/M3) |
| **RAM (Memory)** | 4 GB | 8 GB or higher (ensures Docker container headroom) |
| **Storage (Disk)** | 5 GB available SSD storage | 10 GB available SSD storage (for Docker base images & logs) |
| **Display Resolution** | 1280 × 720 (HD) | 1920 × 1080 (Full HD) for multi-window presentation view |
| **Network** | Offline-capable | Zero Internet Required (all services run on `localhost`) |

### 2. Software Prerequisites

Make sure the following runtimes and container engines are installed on your host system:

- **Containerization Engine:**
  - Docker Engine (v20.10.0 or higher).
  - Docker Compose (v2.0.0 or higher).
  - Alternative for GUI users: Docker Desktop on Windows/macOS.
- **Version Control:**
  - Git (v2.30.0 or higher).
- **Web Browser (Evaluation UI):**
  - Modern Chromium or WebKit browser with Developer Tools enabled (Google Chrome, Brave, Microsoft Edge, or Mozilla Firefox) for testing mobile viewport and HTML5 Geolocation simulation.

### 3. Optional Local Development Tooling (Without Docker)

If running the application natively without Docker containers:

- **Backend Runtime:**
  - Python (v3.10 to v3.12).
  - `pip` & `virtualenv`.
- **Database Engine:**
  - PostgreSQL (v15.x or v16.x) with the PostGIS spatial extension (v3.3+) enabled:

    ```sql
    CREATE EXTENSION postgis;
    ```

- **Reverse Proxy / Static Web Server:**
  - Nginx (v1.20+) or Python simple HTTP server (`python -m http.server 3000`).

---

## 📂 Repository Layout

```text
civicpulse/
├── backend/
│   ├── app/
│   │   └── main.py          # REST endpoints, PostGIS spatial queries, and auth
│   ├── Dockerfile
│   └── requirements.txt     # FastAPI, Uvicorn, Psycopg2, Pydantic
├── frontend/
│   ├── assets/              # Offline script fallbacks and styles
│   ├── login.html           # Unified authentication gateway with role presets
│   ├── index.html           # Citizen PWA: EXIF photo capture, offline sync & governance
│   └── admin.html           # Ward Command Center: ESRI GIS map, fly-to zoom & lightbox modal
├── database/
│   └── init.sql             # PostGIS extension, spatial tables, and initial seed fixtures
├── docker-compose.yml       # Production-mirrored local container network
└── README.md
```

## 🚀 Quickstart & Offline Deployment

The system is engineered to run completely offline on localhost without external network access or cloud API dependencies.

### 1. Clone the Repository

```bash
git clone [https://github.com/Buddy078/Tathva-Goodfellas.git](https://github.com/Buddy078/Tathva-Goodfellas.git)
cd civicpulse
```

### 2. Boot the Full Environment

```bash
docker compose up -d
```

### 3. Access Portals

| Service | Local Path | Description |
| :--- | :--- | :--- |
| **Auth Gateway** | `frontend/login.html` | Unified login with 1-click evaluation presets |
| **Citizen Hub** | `frontend/index.html` | Geotagged reporting & public governance feed |
| **Command Center** | `frontend/admin.html` | GIS incident map, fly-to inspection & notice publisher |
| **API Documentation** | `http://localhost:8000/docs` | Interactive Swagger UI for testing REST endpoints |

## 📊 Live Evaluation Demo Walkthrough

### Gateway Login

1. Open `frontend/login.html`.
2. Click **Autofill Citizen**, then click **Enter CivicPulse Portal** to launch the Citizen View.

### Geotagged Photo Reporting & Spatial Deduplication

1. Under **Report Hazard**, select or drag a geotagged photo. Notice that the latitude and longitude automatically populate via EXIF parsing.
2. Click **Submit Work Order** at coordinates `(11.0168, 76.9558)`.
3. The system detects proximity to an existing ticket, informs the user the issue is known, and merges the report to boost priority upvotes.

### Offline Store-and-Forward Verification

1. Disconnect your computer from Wi-Fi or turn off your backend container.
2. Submit another ticket. The client queues the payload inside `localStorage` with a notice: “Stored Offline”.
3. Re-enable the connection. The background listener detects connectivity and automatically flushes the queue to the backend.

### Municipal GIS Triage & Photo Inspection

1. Open `frontend/login.html`, click **Autofill Officer**, and log in to `frontend/admin.html`.
2. Click **↻ Sync GIS Coordinates**.
3. Click any ticket row with a 📷 Proof badge. The map automatically flies to the coordinates, centers the marker, and opens the popup.
4. Click the preview photo inside the popup. The image opens in an in-app lightbox modal.
5. Change the status dropdown from `PENDING` to `DISPATCHED` to trigger an instant database update.

### Governance Advisory Broadcast

1. In the right-hand panel of `frontend/admin.html`, draft and publish a scheduled utility notice.
2. Return to `frontend/index.html`, switch to the Governance tab, and click **↻ Refresh** to view the advisory pinned at the top of the feed.

---

## 👥 Core Contributors

Tathva-Goodfellas Team

## 📄 License

This project is open-sourced under the MIT License.