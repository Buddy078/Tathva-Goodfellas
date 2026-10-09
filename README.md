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

**CivicPulse** is an offline-first, dual-channel municipal platform that solves these challenges through **spatial deduplication**, **dynamic SLA dispatch**, and **hyper-local governance broadcasting**.

---

## 💡 Key Architectural Innovations

### 1. Spatial Deduplication Engine

Incoming citizen tickets run against an automated PostGIS proximity query:

```text
ST_DWithin(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography, 50)
```

If an unresolved ticket exists in the same category within **50 meters**, the platform suppresses duplicate work-order generation, links the citizen's photographic evidence, and increments the master ticket's community upvote counter.

### 2. SLA Prioritization State Machine

Work orders are auto-ranked using an impact equation balancing inherent hazard severity against citizen density:

```text
Priority Score = (Severity Weight × 0.6) + (Upvotes × 0.4)
```

- **Critical (24h SLA):** Exposed live cables, open manholes, active structural collapse hazards.
- **High (48h SLA):** Major road cave-ins, water pipeline ruptures, uncollected sanitation piles.
- **Standard (168h SLA):** Defective public streetlights, damaged sidewalk curbs.

### 3. Proactive Governance Broadcast Feed

Allows ward officers to push geo-targeted advisories (power cuts, water shutoffs, traffic reroutes) directly to citizens, featuring category filters and one-click calendar integration.

---

## 🏗️ System Architecture

```text
+----------------------------------------------------------------------------------------------------+
|                                      CLIENT LAYER (Frontend)                                       |
|                                                                                                    |
|   +------------------------------------+           +-------------------------------------------+   |
|   |         CITIZEN WEB / PWA          |           |              ADMIN DASHBOARD              |   |
|   |  - Hazard Report Form (Cam/Geo)    |           |  - GIS Cluster Map (Leaflet / MapLibre)   |   |
|   |  - Public Governance Feed          |           |  - Triage & SLA Priority Queue            |   |
|   |  - Live Status Tracker & Upvotes   |           |  - Notice Publisher (Broadcast Engine)    |   |
|   +-----------------+------------------+           +---------------------+---------------------+   |
+---------------------|----------------------------------------------------|-------------------------+
                      |                                                    |
                      | HTTPS / REST / WebSockets                          | HTTPS / REST / WS
                      v                                                    v
+----------------------------------------------------------------------------------------------------+
|                                    API GATEWAY & REVERSE PROXY                                     |
|                                         (Nginx / Caddy)                                            |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  CORE BACKEND APPLICATION LAYER                                    |
|                                      (Python FastAPI / Go)                                         |
|                                                                                                    |
|   +------------------------+  +--------------------------+  +----------------------------------+   |
|   |    INGESTION ENGINE    |  |   SPATIAL DEDUPLICATION  |  |      GOVERNANCE DISPATCHER       |   |
|   |  - Geo-metadata parser |  |   - PostGIS ST_DWithin   |  |   - Ward-targeted advisories     |   |
|   |  - Input sanitization  |  |   - Auto-upvote merge    |  |   - WebSocket push pipeline      |   |
|   +------------------------+  +--------------------------+  +----------------------------------+   |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         v                                                 v
+--------------------------------------------------+  +----------------------------------------------+
|                PRIMARY DATABASE                  |  |             OBJECT & STATIC STORE            |
|             (PostgreSQL + PostGIS)               |  |               (Local / MinIO)                |
|  - Spatial tables: `hazards`, `reports`          |  |  - Evidence photo uploads                    |
|  - Relational tables: `public_notices`           |  |  - Offline vector map tiles & asset bundles  |
+--------------------------------------------------+  +----------------------------------------------+
```

## 🛠️ Technology Decisions & Trade-Off Matrix

Every architectural component in **CivicPulse** was selected to optimize for low latency, zero external API dependencies during evaluations, and zero-cost municipal deployment.

| Architectural Layer | Selected Technology | Evaluated Alternatives | Deciding Factor & Trade-Off Analysis |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | **Python (FastAPI)** | Node.js (Express), Django, Spring Boot | **Why FastAPI:** Native asynchronous event loops (`asyncio`) handle concurrent citizen report spikes with low memory consumption. Built-in Pydantic validation guarantees strict GeoJSON payload validation at runtime.<br><br>**Trade-off:** Python is dynamically typed compared to Go/Java, but FastAPI’s type hints and async throughput outweigh this for rapid hackathon iteration. |
| **Spatial Database** | **PostgreSQL + PostGIS** | MongoDB (2dsphere), MySQL (Spatial), SQLite | **Why PostGIS:** Industry benchmark for spatial indexing (`GIST(geom)`). Supports complex geometric algorithms natively (e.g., `ST_DWithin`, spatial clustering) in sub-millisecond execution times without loading coordinates into app memory.<br><br>**Trade-off:** Higher base memory footprint (~150MB) compared to SQLite, but mandatory for high-concurrency municipal queries. |
| **GIS & Mapping Client** | **Leaflet.js + Local Vector/Raster Tiles** | Google Maps JS API, Mapbox GL JS (Cloud) | **Why Leaflet (Local):** Zero external API dependencies, zero API billing risks, and 100% offline capability on `localhost`. Works during stage presentations without internet drops.<br><br>**Trade-off:** Lacks native 3D building extrusions found in Mapbox GL, but ensures total presentation reliability. |
| **Citizen & Admin Frontend** | **Responsive PWA (Tailwind CSS, HTML5, Vanilla JS)** | React Native, Flutter, Native Android | **Why PWA:** Eliminates app-store friction. Citizens access the portal instantly by scanning a QR code at bus stops or municipal notices. Uses native browser `navigator.geolocation` and camera capture.<br><br>**Trade-off:** Slightly less hardware-level access than a native APK, but dramatically increases citizen adoption rates. |
| **Deployment & Orchestration** | **Docker & Docker Compose** | Bare-metal Localhost, Managed Cloud (AWS/GCP), Kubernetes | **Why Docker Compose:** Creates an isolated, containerized local network. Booting the database, backend, and static client requires a single terminal command (`docker-compose up`), eliminating environment drift and presentation crashes.<br><br>**Trade-off:** Adds an initial container build overhead, but provides reproducible, zero-internet reliability. |
| **Communication Protocol** | **RESTful JSON + WebSockets** | gRPC, GraphQL | **Why REST + WS:** REST provides universal compatibility with existing municipal Smart City command centers (ICCC). WebSockets push instant notice broadcasts to connected citizen views without polling.<br><br>**Trade-off:** GraphQL offers flexible querying, but introduces parsing overhead unnecessary for structured municipal schemas. |

## 💻 System Requirements & Software Prerequisites

To ensure reproducible, zero-internet offline evaluation during the finale presentation, verify that your machine meets the specifications outlined below.

---

### 1. Hardware Requirements

| Specification | Minimum Required | Recommended (For Smooth Demo) |
| :--- | :--- | :--- |
| **Processor (CPU)** | Dual-Core Intel/AMD or Apple Silicon (M-series) | Quad-Core 2.0+ GHz Intel/AMD or Apple Silicon (M1/M2/M3) |
| **RAM (Memory)** | 4 GB | 8 GB or higher (ensures Docker container headroom) |
| **Storage (Disk)** | 5 GB available SSD storage | 10 GB available SSD storage (for Docker base images & logs) |
| **Display Resolution** | 1280 × 720 (HD) | 1920 × 1080 (Full HD) for multi-window presentation view |
| **Network** | Offline-capable | **Zero Internet Required** (all services run on `localhost`) |

---

### 2. Software Prerequisites

Make sure the following runtimes and container engines are installed on your host system:

- **Containerization Engine:**
  - **Docker Engine** (v20.10.0 or higher)
  - **Docker Compose** (v2.0.0 or higher)
  - **Alternative for GUI users: Docker Desktop on Windows/macOS**

- **Version Control:**
  - **Git** (v2.30.0 or higher)

- **Web Browser (Evaluation UI):**
  - Modern Chromium or WebKit browser with Developer Tools enabled (Google Chrome, Brave, Microsoft Edge, or Mozilla Firefox) for testing mobile viewport and HTML5 Geolocation simulation.

---

### 3. Optional Local Development Tooling (Without Docker)

If running the application natively without Docker containers:

- **Backend Runtime:**
  - **Python** (v3.10 to v3.12)
  - **pip** & **virtualenv**

- **Database Engine:**
  - **PostgreSQL** (v15.x or v16.x) with the **PostGIS** spatial extension (v3.3+) enabled:

    ```sql
    CREATE EXTENSION postgis;
    ```

- **Reverse Proxy / Static Web Server:**
  - **Nginx** (v1.20+) or Python simple HTTP server (`python -m http.server 3000`)

## LICENSE

This project is open-sourced under the MIT License.

# Tathva-Goodfellas