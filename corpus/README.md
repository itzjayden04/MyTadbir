# Policy corpus

Official Malaysian legal and administrative documents used by the Legal & Policy RAG agent. Every citation the agent makes must point at an entry in `manifest.json`.

## Rebuild

```bash
.venv/Scripts/python corpus/fetch.py
```

The files land in `corpus/raw/<department>/` (git-ignored, about 75 MB). `manifest.json` records, for each file, the official source URL, title in BM and English, agency, the "as at" date, the download time and a SHA-256 hash.

## What's in it (5 Nov 2026)

96 documents across all 10 departments.

| Source | What | Count |
| --- | --- | --- |
| `agc_acts.tsv` | Federal Acts from the AGC Laws of Malaysia portal (lom.agc.gov.my), latest consolidated or reprint version, BM and English where published | 52 files, 29 Acts |
| `sources.tsv` | MBPJ by-laws, licensing guides and checklists | 19 |
| `sources.tsv` | JPJ forms (driving licence, vehicle) | 8 |
| `sources.tsv` | LHDN forms, explanatory notes, 2026 filing programme | 4 |
| `sources.tsv` | JKM guidelines and aid pages; JPA service circulars | 7 |
| `sources.tsv` | Official service pages (IMI, MyGOV, DOE e-Aduan, JPS Public Info Banjir) | 6 |

Tier 1 is everything the demo scenarios rely on (drain complaints, MBPJ business licensing, JPJ licence renewal and summons). Tier 2 is lighter coverage so every department has some grounding.

## Known gaps

These failed to download automatically and need fetching by hand or a different source:

- Passports Act 1966 (Act 150), English: AGC server error
- Electricity Supply Act 1990 (Act 447), both languages: AGC server error
- Water Services Industry Act 2006 (Act 655), BM: AGC server error
- KKM Medical Assistance Fund Form A: moh.gov.my blocks scripted downloads
- PDRM e-Reporting page: certificate chain not trusted by Python

Health (KKM) and Education (KPM) are the thinnest departments. Their forms are mostly behind online systems (MOEIS, MySejahtera) rather than published as PDFs.

## Rules

- Only official government domains are used as sources. News sites and blogs are not.
- Scenario-specific facts we could not find in a source (for example, whether an unpaid summons blocks licence renewal) are marked as assumptions in the app, never cited.
