# AI Knowledge Base Platform

This repository provides an enterprise-oriented knowledge base platform with:
- document upload and async parsing
- hybrid retrieval (vector + keyword)
- evidence-grounded Q&A
- organization-based access control
- online/offline evaluation data

## Documentation

- User guide (Japanese): [README_ja.md](./README_ja.md)
- User guide (English): [README_en.md](./README_en.md)
- Architecture details (Japanese): [docs/architecture_ja.md](./docs/architecture_ja.md)
- Security policy: [SECURITY.md](./SECURITY.md)
- Contributing guide: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Release notes: [RELEASE_NOTES.md](./RELEASE_NOTES.md)

## Quick Start (Docker)

```bash
cp .env.example .env
# edit .env (OPENAI_API_KEY, passwords, etc.)
cd app
./start_docker.sh pg up
```

Check health:

```bash
curl http://localhost:8000/health
```

Stop:

```bash
cd app
./start_docker.sh pg down
```

## Notes

- For interview/demo usage, start from `README_ja.md` and `docs/architecture_ja.md`.
- For production usage, review environment variables and security settings before deployment.
