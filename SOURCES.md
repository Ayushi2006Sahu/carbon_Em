# Data Sources & Ingestion Schemas — Breathe ESG

This document details the structures of the three carbon data sources, how the synthetic sample files represent real-world corporate records, and what challenges would need to be addressed in production.

---

## 1. SAP Fuel & Procurement Ingestion

### Real-World SAP Table Schema
In production, corporate fuel transactions and procurement reports are extracted from the **BSEG** (Accounting Document Segment) and **MSEG** (Document Segment: Material) tables.

| Field Code | Description | Data Type | Sample Values |
| :--- | :--- | :--- | :--- |
| **MANDT** | Client number | CLNT (3) | `100` |
| **WERKS** | Plant code | CHAR (4) | `1000`, `1100`, `2000` |
| **MATNR** | Material number | CHAR (18) | `MAT-FUEL-DIESEL`, `MAT-PROC-STEEL` |
| **MEINS** | Base unit of measure | UNIT (3) | `L`, `KG`, `GAL`, `M3` |
| **MENGE** | Quantity | DEC (13,3) | `450.00`, `5000.00` |
| **NETWR** | Net value | DEC (15,2) | `1200.00`, `15000.00` |
| **WAERS** | Currency key | CUKY (5) | `EUR`, `USD`, `INR` |
| **BLDAT** | Document Date | DATS (8) | `15.05.2026` (DD.MM.YYYY German format) |

### Synthetic Sample Representation
Our synthetic `sap_sample.csv` and `sap_sample_german.csv` files contain 20 rows that mirror these ERP exports:
* **Scope 1 Rows**: Material numbers containing `DIESEL`, `PETROL`, or `GAS`, bought in volume units like Liters (`L`), Gallons (`GAL`), or Cubic Meters (`M3`).
* **Scope 3 Rows**: General procurement items like `STEEL`, `PLASTIC`, and `COPPER`, which are mapped to category `fuel` and normalized using mass (KG) at a default procurement factor.
* **Deliberate Anomalies (Testing Suspicion)**:
  - Row 10: Negative quantity (`-50.00` Liters) to simulate a credit note or error.
  - Row 11: Zero quantity (`0.00`) to test invalid transactions.
  - Row 12: An unmapped unit (`LB` - Pounds) to test our unit fallback checks.
  - Row 17: A statistical outlier ($90,000$ Liters of diesel) that exceeds three times the historical plant average, triggering a suspicion flag.
  - Row 19: A future document date (`2028-12-28`).

### What breaks in production
* **Varying Material Naming Conventions**: Different corporate divisions use completely different name strings for fuel (e.g. `DIESEL_FUEL`, `GASOIL`, `HEATING_OIL`). 
  - *Mitigation*: Replace simple keyword matching with a database-backed **Material Classification Mapping** interface.
* **German Date String Drift**: Invoices can have document dates in different formats (e.g. German `DD.MM.YYYY`, ISO `YYYY-MM-DD`, or US `MM/DD/YYYY`).
  - *Mitigation*: We integrated a multi-format date parsing loop that attempts multiple standard date layouts before falling back to the current date.

---

## 2. Utility Electricity Ingestion

### Green Button XML/CSV Standard Format
Electric utility providers export data in formats based on the **ESPI (Energy Services Provider Interface)** standard, often called **Green Button**.

| Field Code | Description | Data Type | Sample Values |
| :--- | :--- | :--- | :--- |
| **account_number** | Customer account identifier | VARCHAR | `ACCT-99281` |
| **meter_id** | Physical meter sensor ID | VARCHAR | `MTR-1001`, `MTR-1002` |
| **service_address** | Facility address | VARCHAR | `Munich Assembly Facility` |
| **billing_period_start**| Billing cycle start date | DATE (ISO) | `2025-01-01` |
| **billing_period_end** | Billing cycle end date | DATE (ISO) | `2025-01-31` |
| **kwh_consumed** | Total electricity consumed | DECIMAL | `14200.00` |
| **peak_demand_kw** | Max power demand in month | DECIMAL | `45.0` |
| **tariff_code** | Rate class code | VARCHAR | `IND-HEAVY` |
| **amount_billed** | Bill total | DECIMAL | `3200.00` |

### Synthetic Sample Representation
Our `utility_sample.csv` file contains 12 rows representing monthly electric bills:
* **Multi-Meter Tracking**: Tracks two meters (`MTR-1001` and `MTR-1002`) at the same facility to test simultaneous active sources.
* **Deliberate Anomalies**:
  - Row 11: A billing period date mismatch where the billing end date (`2025-05-15`) is before the start date (`2025-06-01`).
  - Row 12: A negative consumption value (`-1200.00` kWh).

### What breaks in production
* **Overlapping Billing Cycles**: Invoices from the same meter can have overlapping dates due to invoice adjustments or estimated readings, leading to double-counting.
  - *Mitigation*: Implement a database constraint that prevents overlapping dates (`period_start` to `period_end`) for the same `meter_id`.
* **Varying Energy Units**: Some utility reports export in Mega-Watt Hours (`MWh`) or British Thermal Units (`BTU`).
  - *Mitigation*: Add an energy unit detection helper to convert non-standard inputs to standard `kWh`.

---

## 3. Corporate Travel Ingestion

### Concur Travel Log Export Format
Corporate travel agencies (such as SAP Concur) export travel expenses as CSV tables containing travel dates, categories, airport routing details, and classes of service.

| Field Code | Description | Data Type | Sample Values |
| :--- | :--- | :--- | :--- |
| **expense_id** | Unique corporate expense ID | VARCHAR | `EXP-5001` |
| **traveler_name** | Employee name | VARCHAR | `John Doe` |
| **travel_date** | Date travel commenced | DATE | `2026-05-10` |
| **travel_type** | Travel category | CHAR | `FLIGHT`, `HOTEL`, `GROUND` |
| **origin** / **destination** | Geolocation codes | CHAR (3) / VARCHAR| `DEL` / `LHR`, `JFK` / `LAX` |
| **distance_km** | Distance in kilometers | DECIMAL | `1140.00` (can be empty) |
| **nights** | Duration of hotel stays | INTEGER | `4`, `0` (for transit) |
| **travel_class** | Class of flight ticket | VARCHAR | `ECONOMY`, `BUSINESS` |
| **amount** / **currency** | Cost details | DEC / CHAR | `850.00` / `USD` |

### Synthetic Sample Representation
Our `travel_sample.csv` contains 15 rows:
* **Missing Flight Distance Fallback**: Flight rows DEL-LHR (Delhi to London) and JFK-LAX (New York to Los Angeles) have empty `distance_km` columns, triggering our Haversine algorithm to compute the distances automatically using the airport database coordinates.
* **Travel Class Multipliers**: Flight EXP-5004 is a `BUSINESS` flight, which applies a higher emission factor (`0.612 kgCO2e/km`) compared to `ECONOMY` (`0.255 kgCO2e/km`).
* **Deliberate Anomalies**:
  - Row 9: Missing distance with an unknown airport code (`XYZ`), which triggers a suspicion flag because the coordinates are not in our database.
  - Row 10: An expense dated in the future (`2028-12-15`).
  - Row 14: Negative hotel nights (`-2`).

### What breaks in production
* **Multi-Segment Flights**: A trip from DEL to LAX via LHR is often recorded in Concur as a single row (`DEL-LAX`) rather than two segments. A direct geodesic calculation will under-represent the actual flight distance.
  - *Mitigation*: Log and calculate each segment separately, or apply a standard flight detour multiplier.
* **Large Datasets / Missing Airport Codes**: An enterprise travel file can contain thousands of rows and reference small regional airports not included in a hardcoded dictionary.
  - *Mitigation*: Integrate with a public airport API database (like OpenFlights) or a third-party geographic database to resolve airport coordinates dynamically.
