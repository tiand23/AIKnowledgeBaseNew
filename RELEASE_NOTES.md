# Release Notes

## v0.1.0-draft

### Highlights
- End-to-end flow from upload to Q&A
- Hybrid retrieval (vector + text)
- VLM-assisted structure extraction for image-heavy content
- Access control based on user/org/public scope
- Evaluation center for online/offline quality checks

### Infrastructure
- FastAPI + WebSocket
- PostgreSQL / Redis / MinIO / Elasticsearch / Kafka
- OpenAI API integration for embedding/chat/vision

### Stability Improvements
- Kafka multi-consumer support for document processing
- Idempotent processing lock and done-marker to avoid duplicate indexing
- DLQ routing for repeated parse failures

### Known Limitations
- Single-node oriented deployment by default
- Horizontal autoscaling and enterprise ops dashboards are not bundled
- Some defaults are for demo/staging, not production hardening

### Next Milestones
- Role hierarchy and admin console enhancements
- Expanded evaluation dataset and dashboards
- Production deployment blueprints and observability templates
