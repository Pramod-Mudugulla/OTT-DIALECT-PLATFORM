# Known Limitations & Scoped Trade-offs

This document outlines architectural decisions and production elements that were **intentionally left incomplete or simplified** to remain strictly within the suggested 10–12 hour time budget while prioritizing core correctness, testability, and clarity.

---

## 1. Storage & State Persistence Layer
- **Current Implementation:** Per-viewer state is maintained as atomic JSON documents saved to the local file system (`sample_run/viewer_state/<viewer_id>.json`).
- **Production Architecture:** At scale (10 million viewers), this would be replaced with a distributed low-latency document or key-value store such as **Amazon DynamoDB**, **ScyllaDB**, or a **Redis Cluster** partitioned by `hash(viewer_id)` with strong consistency or read-your-writes guarantees.

---

## 2. Real-Time Streaming Architecture
- **Current Implementation:** Triggers are processed sequentially from a local `.jsonl` file via a single Python runner process.
- **Production Architecture:** Production streaming would use **Apache Kafka** or **AWS Kinesis** with consumer groups keyed by `viewer_id`. This guarantees in-order event processing per viewer while allowing parallel horizontal scaling across multiple worker instances.

---

## 3. Cross-Dialect Content Matching & Vector Embeddings
- **Current Implementation:** Dialect matching uses exact string matching (`d1` through `d6`) and rule-based fallback mapping (e.g. `d1` mapping to adjacent dialects `d2`/`d3` in rule v2).
- **Production Architecture:** Production would incorporate a multilingual embedding model (e.g., `multilingual-e5-large` or `IndicBERT`) to calculate semantic and cultural affinity scores between regional dialects, enabling nuanced recommendations when active dialect inventory is low.

---

## 4. Exploration Strategy (Contextual Bandits)
- **Current Implementation:** Goal selection follows deterministic heuristic eligibility rules based on viewer lifecycle stage (onboarding -> first episode -> paid conversion -> retention).
- **Production Architecture:** A production system would employ a **Contextual Multi-Armed Bandit** (e.g., LinUCB or Thompson Sampling) with a bounded exploration budget (e.g., 5% random exploration) to discover novel viewer preferences without violating policy constraints.

---

## 5. Bidirectional Messaging Webhooks
- **Current Implementation:** Outcomes are simulated via telemetric play/purchase events logged to the trigger stream.
- **Production Architecture:** Production would maintain dedicated inbound webhook receivers for WhatsApp Business Solution Providers (BSPs) and Push notification gateways (FCM/APNs) to track `delivered`, `read`, and `button_click` receipts in real time.
