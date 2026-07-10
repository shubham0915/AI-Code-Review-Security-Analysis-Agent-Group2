# Project Cleanup Plan

A thorough audit of the project has been completed. Here is what will be removed, and why.

## User Review Required

> [!IMPORTANT]
> No production code or working functionality will be touched. All active routes, models, RAG logic, and the Streamlit UI will remain intact.

> [!WARNING]
> `chat_handover_summary.md` is a development-only internal file (a note from one AI session to the next). It should not be in the final repository.

---

## Proposed Changes

### Files to DELETE (Clutter & Empty Stubs)

| File/Folder | Reason |
|---|---|
| `chat_handover_summary.md` | Internal AI session handover note. Not needed in the final project. |
| `deep-research-report.md` | Internal AI planning/research document. Not needed in production. |
| `.coverage` | Auto-generated binary file from `pytest --cov`. Should not be committed. |
| `htmlcov/` | Auto-generated HTML coverage report directory. Should not be committed. |
| `app/agents/__init__.py` | The `app/agents/` directory is an empty stub (only has `__init__.py`). Will be cleaned up in Milestone 2 when agents are implemented. |
| `app/linters/__init__.py` | The `app/linters/` directory is an empty stub. Same as above. |
| `app/report/templates/__init__.py` | Empty stub inside a directory with no templates yet. |
| `frontend/components/` | Completely empty directory. |
| `tests/evaluation/vuln_test_suite/__init__.py` | Empty stub — no evaluation tests have been written yet. |

### Files to ADD to `.gitignore`

These are auto-generated and should never be committed to Git:

| Pattern | Reason |
|---|---|
| `.coverage` | Binary pytest coverage database |
| `htmlcov/` | HTML coverage report |

### Files to KEEP (Previously Considered)

| File | Reason to Keep |
|---|---|
| `AI_Code_Review_Security_Agent_Final_Report.md` | Official project report — should stay. |
| `Ai Code review.docx` | Official source requirements document — should stay. |
| `deep-research-report.md` | Contains the RAG architecture research. Will keep for reference. |
| `monitoring/` | Contains `prometheus.yml` + Grafana config. Needed for Milestone 5. Keep. |
| `uv.lock` | Lock file for reproducible installs. Keep. |
| `docker-compose.yml` | Needed for Milestone 5 deployment. Keep. |

## Verification Plan

After cleanup, run:
```bash
git status   # confirm all deleted files are staged
git push     # push clean state to GitHub
```
