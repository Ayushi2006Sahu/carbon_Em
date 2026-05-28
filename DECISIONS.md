# Strategic Design Decisions — Breathe ESG

This document details the engineering, scientific, and architectural decisions made while designing the Breathe ESG carbon data platform.

---

## 1. CSV Upload vs. Live API Integrations

We chose flat CSV uploads for the initial phase of Breathe ESG for three primary reasons:

| Source | The "Real-World" API Reality | Why CSV is the Pragmatic Choice |
| :--- | :--- | :--- |
| **SAP (ERP)** | SAP enterprise integration requires complex, expensive ABAP middleware setups, NetWeaver RFCs, or IDoc configurations, which typically take months of custom consultation. | Standard financial/procurement reports are easily exported as flat CSV files (*BSEG*, *MSEG* tables) by any SAP admin in minutes. |
| **Utilities** | Global utility companies have fragmented IT infrastructure. Green Button APIs exist but are only supported by a small fraction of North American municipal grids. Most European/Asian providers only issue PDFs or simple portal CSVs. | Flat CSV billing portal extracts are universally available, allowing clients to ingest invoices immediately without custom integrations. |
| **Concur (Travel)** | Concur provides REST APIs, but accessing travel data programmatically requires expensive enterprise developer tokens, OAuth handshakes, and navigation of complex expense approval schemas. | Standard monthly travel reports are easily exported as CSV by HR/finance teams in seconds, containing flight routes and hotel nights. |

CSV is the **lowest common denominator**. It allows clients to achieve value on day one without requiring integration cycles from their internal IT departments.

---

## 2. Emission Factors Registry

The platform uses environmental multipliers drawn from internationally recognized frameworks:
* **Scope 1 (Fuels)**: Sourced from the **GHG Protocol Emission Factors Hub** and **DEFRA (UK Department for Environment, Food and Rural Affairs)**. 
  - Diesel: `2.68 kgCO2e/L`
  - Petrol: `2.31 kgCO2e/L`
  - Natural Gas: `2.04 kgCO2e/m3`
* **Scope 2 (Electricity)**: Grid averages vary widely. We applied the **India Grid Average (CEA)** of `0.82 kgCO2e/kWh`. This choice represents a heavy-coal grid, which helps highlight the environmental benefit of transitioning to renewable energy during analyst audits.
* **Scope 3 (Travel)**: Sourced from the **DEFRA Business Travel Registry**:
  - Flight Economy: `0.255 kgCO2e/km` (represents high passenger densities, lower per-capita impact).
  - Flight Business: `0.612 kgCO2e/km` (includes a 2.4x seating multiplier to account for the larger space occupied by premium seats).
  - Hotel Stays: `31.2 kgCO2e/night` (global hotel average).
  - Ground Transit: `0.21 kgCO2e/km` (average gasoline passenger vehicle).

---

## 3. Unit Normalization & Mass-to-Volume Densities

Carbon reporting requires all quantities of a single category to be normalized to a standard unit. For fuels, we normalized everything to weight (**Kilograms - KG**). 
However, fuel is typically purchased by volume (Liters, Gallons, Cubic Meters). To normalize volume to weight, we applied standard physical fuel densities (at $15^\circ\text{C}$):

$$\text{Weight (kg)} = \text{Volume (L)} \times \text{Density (kg/L)}$$

* **Diesel Density**: `0.84 kg/L`
  - *Conversion Example*: 500 Liters of Diesel = $500 \times 0.84 = 420\text{ kg}$.
  - *CO2 Calculation*: Liter volume is preserved to apply the factor: $500\text{ L} \times 2.68\text{ kgCO2e/L} = 1,340\text{ kgCO2e}$.
* **Petrol Density**: `0.74 kg/L`
  - *Conversion Example*: 100 Gallons of Petrol = $100 \times 3.78541\text{ (L/Gal)} \times 0.74\text{ (kg/L)} = 280.12\text{ kg}$.
  - *CO2 Calculation*: $378.54\text{ L} \times 2.31\text{ kgCO2e/L} = 874.4\text{ kgCO2e}$.
* **Natural Gas Density**: `0.80 kg/m3`
  - *Conversion Example*: 1,000 Cubic Meters ($m^3$) = $1,000 \times 0.80 = 800\text{ kg}$.
  - *CO2 Calculation*: $1,000\text{ m3} \times 2.04\text{ kgCO2e/m3} = 2,040\text{ kgCO2e}$.

---

## 4. Plant Code Lookup Approach

In the SAP parser, plant codes (`WERKS` field) are mapped to physical locations via a hardcoded dictionary. 
* *Why?* SAP plant codes (e.g., `1000`, `1100`) are abstract IDs. To audit carbon, analysts must know *where* emissions occur to understand regional grid footprints.
* *Production scaling*: While a lookup dict is ideal for a fast-moving MVP, a production system would replace the dict with a database table (`PlantCodeLocation`) managed by administrators, allowing plants to be mapped dynamically to real-world addresses and latitudes/longitudes.

---

## 5. Questions for the Product Manager (PM)

If pair-programming with our PM, we would raise these strategic questions:
1. **Can we implement a PDF Parser for Utilities?** Real utility bills are issued as PDFs, not clean CSVs. Should we integrate an OCR pipeline (like AWS Textract or Document AI) to pull meter IDs and billing dates directly from utility bill PDFs?
2. **How should we handle currency conversion?** Upstream files contain multiple currencies (EUR, USD, INR). Should we integrate a daily currency exchange API (like ECB or Open Exchange Rates) to normalize all net spending value columns to a single reporting currency (e.g., USD) for financial carbon correlation?
3. **What is the protocol for re-uploading corrected data?** If an analyst rejects an SAP upload containing 20 rows because 1 row had a bad unit, should the system allow them to upload only the 1 corrected row, or should they re-upload the entire CSV file with a duplicate prevention check?
