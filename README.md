# 🍃 Breathe ESG — Carbon Ingestion & Analyst Review Platform

Welcome to **Breathe ESG**, a multi-tenant enterprise carbon emissions data ingestion, normalization, and verification platform. 

Companies generate massive volumes of carbon footprint data across different operations. **Breathe ESG** provides a clean, audit-ready space to ingest raw operational data from three primary streams—**SAP Fuel & Procurement**, **Grid Utility Invoices**, and **Corporate Concur Travel logs**—normalizes them into standard Metric Tonnes of $\text{CO}_2\text{e}$, runs them through automated statistical anomaly detectors, and lets sustainability analysts review and authorize records before they reach external auditors.

---

## 🚀 Key Features

* **Multi-Tenant Data Security**: Complete, logical database-level isolation. All users, data sources, ingestion logs, and emission records are securely scoped to their respective organizational `Tenant`.
* **Three Specialized ESG Parsers**:
  - **SAP Parser**: Detects direct fuel combustion (Scope 1) vs. material procurement (Scope 3). Normalizes volumetric fuel values (L, GAL, $M^3$) into mass (KG) using physical densities. Parses German localized date strings (`DD.MM.YYYY`) and maps abstract plant codes (`WERKS`) to locations.
  - **Utility Parser**: Standardizes grid utility invoice cycles (Scope 2) into `kWh` and applies localized grid intensities. Gracefully handles misaligned billing cycles.
  - **Travel Parser**: Standardizes flight travel cabin classes, hotel stays, and ground transit (Scope 3). Automatically calculates geodesic distances using the **Haversine formula** against a coordinate database of the top 30 global airports if flight distances are missing.
* **Automated Suspicion Detection**: Flags data entries immediately if they contain negative values, are dated in the future or older than 2 years, or exceed **3x the tenant's approved historical average** for that environmental category.
* **Immutable Compliance Audit Trail**: Every ingestion run, analyst approval, and rejection with textual reasons is committed to an immutable ledger (`AuditLog`), recording complete before-and-after JSON snapshots.

---

## 🛠️ Technology Stack

* **Backend**: Django (4.2+) & Django REST Framework (DRF)
* **Frontend**: React (18+) served via Vite (powered by custom premium ESG Glassmorphism CSS)
* **Database**: SQLite (Zero-config local fallback) / PostgreSQL (Fully ready for Production deployment)
* **Deployments**: Railway-compliant configurations (`Procfile` and `railway.toml` with automatic migrations)

---

## 📂 Directory Structure

```
c:\Project\Carbonem\
├── backend\                 # Django REST Framework Backend
│   ├── breathe_esg\         # Core settings and URL routing
│   ├── emissions\           # ESG Business Logic App
│   │   ├── parsers\         # Specialized CSV parsing engines
│   │   ├── models.py        # Database models (Tenant, record, log)
│   │   ├── views.py         # REST endpoints & action state machine
│   │   ├── suspicion.py     # Anomaly checking algorithms
│   │   └── utils.py         # Haversine geodesic calculations & airport coordinates
│   ├── sample_data\         # Synthetic seed CSVs
│   └── requirements.txt     # Python backend dependencies
├── frontend\                # React Frontend
│   ├── src\
│   │   ├── components\      # Reusable visual widgets
│   │   ├── App.jsx          # Dashboard, upload forms, and review ledger
│   │   ├── index.css        # "Emerald Forest" Glassmorphism theme
│   │   └── main.jsx         # React DOM mount point
│   ├── index.html           # HTML template & Google Font links
│   ├── package.json         # Node packaging & scripts
│   └── vite.config.js       # Vite development proxy mapping /api -> port 8000
├── Procfile                 # Railway process commands
├── railway.toml             # Railway deployment configurations
└── README.md                # This developer documentation
```

---

## ⚡ Quick Start Guide (Local Setup)

To get Breathe ESG up and running on your machine, you need **Python 3.10+** and **Node.js 18+** installed.

### 1. Setup the Backend
Open a terminal window and navigate to the `backend/` directory:
```bash
# Navigate to backend
cd backend

# Create tables and initialize database (creates local db.sqlite3)
python manage.py migrate

# Start development server (runs on http://127.0.0.1:8000)
python manage.py runserver
```

### 2. Setup the Frontend
Open a **second, separate** terminal window and navigate to the `frontend/` directory:
```bash
# Navigate to frontend
cd frontend

# Install package dependencies
npm install

# Start Vite dev server (runs on http://localhost:3000)
npm run dev
```

Now, open your browser and navigate to: **`http://localhost:3000`**

---

## 📊 How to Seed & Test the App

We have pre-generated three highly realistic, synthetic CSV files loaded with real-world scenarios and deliberate compliance errors. You can upload them using the **Ingestion Cards** on the left panel:

1. **SAP Ingestion**: Upload `sap_sample.csv` (or `sap_sample_german.csv` to test multilingual column recognition).
   - *Anomalies to check*: You will notice a negative row (Row 10), a zero quantity (Row 11), a bad unit box/lb (Row 12), a future date (Row 19), and a major **outlier value** ($90,000$ Liters of Diesel, Row 17) flagged in bright red!
2. **Utility Ingestion**: Upload `utility_sample.csv`.
   - *Anomalies to check*: Highlights multi-meter tracking and flags Row 11 in red due to a date mismatch (billing period end date is before the start date).
3. **Travel Ingestion**: Upload `travel_sample.csv`.
   - *Anomalies to check*: Flight lines DEL-LHR and JFK-LAX have **no distances** listed! The travel parser will automatically resolve their airport codes and calculate their geodesic distances ($6,781\text{ km}$ and $3,974\text{ km}$) under the hood! It also flags a future travel date (Row 10) and negative hotel nights (Row 14).

---

## 🧪 Running the Verification Tests

To verify that the environmental multipliers, unit scalings, geodesic distance algorithms, and statistical outlier engines are functioning accurately, you can run our test suite:

```bash
cd backend
python manage.py test emissions
```

### Expected Output:
```
Found 5 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.....
----------------------------------------------------------------------
Ran 5 tests in 0.024s

OK
Destroying test database for alias 'default'...
```

---

## 📚 ESG Science Reference Sheet

### Carbon Conversion Constants Applied
* **Diesel Combustion**: `2.68 kgCO2e/L` (Scope 1)
* **Petrol Combustion**: `2.31 kgCO2e/L` (Scope 1)
* **Natural Gas**: `2.04 kgCO2e/m3` (Scope 1)
* **Grid Electricity (India Avg)**: `0.82 kgCO2e/kWh` (Scope 2)
* **Flight Economy Ticket**: `0.255 kgCO2e/km` (Scope 3)
* **Flight Business Ticket**: `0.612 kgCO2e/km` (Scope 3 - includes comfort class multiplier)
* **Hotel Standard Stay**: `31.2 kgCO2e/night` (Scope 3)
* **Ground Vehicle**: `0.21 kgCO2e/km` (Scope 3)
* **General Goods Procurement**: `1.25 kgCO2e/kg` (Scope 3 - Category 1)

### Physical Fuel Densities Used (at $15^\circ\text{C}$)
Used to convert volumetric purchase bills (Liters, Gallons) into normalized reporting weights (Kilograms):
* **Diesel**: `0.84 kg/L`
* **Petrol**: `0.74 kg/L`
* **Natural Gas**: `0.80 kg/m3`

Author - Ayushi Sahu