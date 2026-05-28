# Product Trade-offs — Breathe ESG

To maintain a fast time-to-market and ensure a highly stable core system, we deliberately deferred three enterprise-grade features. This document explains why, and outlines the architectural paths to build them in the future.

---

## 1. Real SAP IDoc / OData Gateway Listener

In a mature enterprise deployment, carbon data should flow automatically in real time rather than requiring manual CSV uploads.

* **What was deferred**: Building an RFC destination, SAP OData Service, or IDoc (Intermediate Document) listener endpoint that acts as a webhook to catch material movements (*MSEG*) and invoice postings (*BSEG*) in real time.
* **Why it was deferred**:
  - **Consulting overhead**: SAP integrations are never "plug-and-play". They require writing custom ABAP code inside the client's SAP landscape and configuring custom firewall pathways.
  - **MVP simplicity**: An analyst review platform's value lies in its data cleaning, anomaly detection, and verification workflows. Standardizing on CSV exports allows us to deliver immediate value to customers without waiting for months of SAP consulting cycles.
* **Production path**: Implement a **Django Celery Task Queue** that exposes a secure REST webhook. Upstream SAP environments can then trigger an OData pull to send JSON payloads directly to `/api/ingest/sap/realtime/`.

---

## 2. Live Utility Provider APIs (Green Button Connect)

Manual retrieval of electric utility CSVs from portals can be tedious for large companies with hundreds of meters.

* **What was deferred**: Integrating with **Green Button Connect My Data (CMD)** OAuth endpoints or direct utility provider API aggregators (such as Arcadia or Urjanet) to automatically pull monthly energy invoices.
* **Why it was deferred**:
  - **High integration costs**: Commercial aggregators charge substantial monthly licensing fees and require extensive contracting cycles.
  - **Infrastructure fragmentation**: Grid providers outside North America and Western Europe rarely support standard APIs, meaning manual PDF and CSV ingestion remains a required fallback anyway.
* **Production path**: Integrate with a commercial ESG data aggregator (like Arcadia) to pull meter readings dynamically. These pulled readings would map directly into our existing `RawIngestion` model, reusing our current normalization and suspicion checking pipelines unchanged.

---

## 3. Geodesic Distance via GIS Routing APIs (Google Maps/OSRM)

Our travel distance calculator computes geodesic distance using a hardcoded airport coordinate dictionary.

* **What was deferred**: Querying a live routing API (such as the Google Maps Distance Matrix API or Open Source Routing Machine (OSRM)) to calculate real-world rail or road travel distances, and a live GIS service for flight routes.
* **Why it was deferred**:
  - **API pricing & latency**: Live GIS queries add latency to file processing and incur significant API usage costs (e.g., Google Maps charges \$5 per 1,000 requests).
  - **Negligible precision gains**: Geodesic distance (great-circle) calculated via the Haversine formula is the standard accepted method for corporate carbon accounting (GHG Protocol). The difference between a real flight path and a great-circle path is minimal for emissions calculations, as flight emissions factors already include a standard 8-10% uplift factor to account for detours and holding patterns.
* **Production path**: Continue using the Haversine formula for flights, but integrate OSRM (a free, open-source routing engine) via a Docker container for high-accuracy road/rail travel distance calculations without external API charges or latency spikes.
