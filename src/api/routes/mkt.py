"""
Routes /mkt/ — séquences email/SMS et étapes.
Stockage SQLite via ContentBlockDB (JSON).
"""
import json, uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ...database import SessionLocal

router = APIRouter(prefix="/mkt", tags=["Mkt"])

# ── Helpers JSON storage ──────────────────────────────────────────────────────

def _get_all(key: str) -> list:
    from ...models import ContentBlockDB
    with SessionLocal() as db:
        row = db.query(ContentBlockDB).filter_by(page_type="_mkt", section_key=key, field_key="data").first()
        if row and row.value:
            try: return json.loads(row.value)
            except: pass
    return []


def _save_all(key: str, data: list):
    from ...models import ContentBlockDB
    from ...database import set_block
    with SessionLocal() as db:
        set_block(db, "_mkt", key, "data", json.dumps(data, ensure_ascii=False))


# ── Sequences ─────────────────────────────────────────────────────────────────

@router.get("/sequences")
def list_sequences(project_id: str = Query(default="")):
    seqs = _get_all("sequences")
    if project_id:
        seqs = [s for s in seqs if s.get("project_id") == project_id]
    return JSONResponse({"result": seqs})


@router.post("/sequences")
async def create_sequence(request):
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Nom requis")
    seq = {
        "id": str(uuid.uuid4()),
        "name": name,
        "project_id": data.get("project_id", "presence_ia"),
        "campaign_id": data.get("campaign_id", "default"),
        "is_active": True,
        "steps": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    seqs = _get_all("sequences")
    seqs.append(seq)
    _save_all("sequences", seqs)
    return JSONResponse({"result": seq})


@router.get("/sequences/{seq_id}")
def get_sequence(seq_id: str):
    seqs = _get_all("sequences")
    for s in seqs:
        if s["id"] == seq_id:
            return JSONResponse({"result": s})
    raise HTTPException(404)


@router.patch("/sequences/{seq_id}")
async def update_sequence(seq_id: str, request):
    data = await request.json()
    seqs = _get_all("sequences")
    for s in seqs:
        if s["id"] == seq_id:
            if "is_active" in data:
                s["is_active"] = bool(data["is_active"])
            if "name" in data:
                s["name"] = data["name"]
            _save_all("sequences", seqs)
            return JSONResponse({"result": s})
    raise HTTPException(404)


@router.delete("/sequences/{seq_id}")
def delete_sequence(seq_id: str):
    seqs = _get_all("sequences")
    seqs = [s for s in seqs if s["id"] != seq_id]
    _save_all("sequences", seqs)
    return JSONResponse({"ok": True})


# ── Steps ─────────────────────────────────────────────────────────────────────

@router.post("/sequences/{seq_id}/steps")
async def add_step(seq_id: str, request):
    data = await request.json()
    seqs = _get_all("sequences")
    for s in seqs:
        if s["id"] == seq_id:
            step = {
                "id": str(uuid.uuid4()),
                "sequence_id": seq_id,
                "channel": data.get("channel", "email"),
                "delay_days": int(data.get("delay_days", 0)),
                "step_number": int(data.get("step_number", 1)),
                "subject": data.get("subject", ""),
                "body_text": data.get("body_text", ""),
                "created_at": datetime.utcnow().isoformat(),
            }
            s.setdefault("steps", []).append(step)
            _save_all("sequences", seqs)
            return JSONResponse({"result": step})
    raise HTTPException(404)


@router.patch("/sequences/{seq_id}/steps/{step_id}")
async def update_step(seq_id: str, step_id: str, request):
    data = await request.json()
    seqs = _get_all("sequences")
    for s in seqs:
        if s["id"] == seq_id:
            for step in s.get("steps", []):
                if step["id"] == step_id:
                    for k in ("channel", "delay_days", "step_number", "subject", "body_text"):
                        if k in data:
                            step[k] = data[k]
                    _save_all("sequences", seqs)
                    return JSONResponse({"result": step})
    raise HTTPException(404)


@router.delete("/sequences/{seq_id}/steps/{step_id}")
def delete_step(seq_id: str, step_id: str):
    seqs = _get_all("sequences")
    for s in seqs:
        if s["id"] == seq_id:
            s["steps"] = [st for st in s.get("steps", []) if st["id"] != step_id]
            _save_all("sequences", seqs)
            return JSONResponse({"ok": True})
    raise HTTPException(404)
