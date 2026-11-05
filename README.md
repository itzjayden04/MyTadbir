# MyTadbir

Multi-agent digital desk officer for Malaysian public services. Built for the Agentic AI Challenge, Festival Idea Putrajaya 2026.

## Architecture

```
Citizen input (webapp, BM/EN)
  -> Intent Router            classifies only, never executes
  -> Case Manager             runs one case at a time; queues sequential handoffs
  -> ONE Department Main Module (owns the case)
  -> its own sub-modules, in order, as needed
  -> Shared Agent Services    policy RAG, multimodal, execution, identity, notification, audit
  -> one Case ID, one citizen thread, one audit ledger
```

Cross-department work only happens by sequential handoff carrying the same Case ID. There is no parallel fan-out.

## Layout

| Path | What |
| --- | --- |
| `backend/app/core` | Module contract and registry, case context bundle, live trace bus |
| `backend/app/router` | Intent Router and Case Manager |
| `backend/app/departments` | 10 department main modules and their 50 sub-modules |
| `backend/app/modules` | Always-on modules (reasoning, next-step suggestions) |
| `backend/app/services` | Shared agent services |
| `backend/app/mocks` | Mock government APIs (REST/JSON) |
| `corpus/` | Public legal documents, forms and notices, with a source manifest |
| `frontend/` | React web app |
| `demo/` | Demo script, sample inputs |

## Run (backend)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs. Tests: `.venv/Scripts/python -m pytest tests`.
