"""
Routes livrables clients — chantier 10
POST /api/generate/prospect/{pid}/faq
POST /api/generate/prospect/{pid}/jsonld
POST /api/generate/prospect/{pid}/checklist
POST /api/generate/prospect/{pid}/dossier
POST /api/generate/prospect/{pid}/all-livrables
GET  /api/livrables/{pid}
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_prospect
from ...livrables.faq import generate_faq
from ...livrables.jsonld import generate_jsonld
from ...livrables.checklist import generate_checklist
from ...livrables.dossier import generate_dossier
from ...livrables.outreach import generate_outreach

router = APIRouter(tags=["Livrables"])


def _prospect_or_404(pid: str, db: Session):
    p = db_get_prospect(db, pid)
    if not p:
        raise HTTPException(404, "Prospect introuvable")
    return p


# ── FAQ ─────────────────────────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/faq")
def api_faq(pid: str, db: Session = Depends(get_db)):
    p = _prospect_or_404(pid, db)
    try:
        result = generate_faq(db, p)
        return {
            "success": True,
            "result": {
                "count": result["count"],
                "files": result["files"],
                "index_file": result["index_file"],
                "jsonld_items": result["jsonld_items"],
            },
            "message": f"{result['count']} page(s) FAQ générée(s) pour {p.name}",
            "error": None,
        }
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "FAQ_ERROR", "detail": str(e)}}


# ── JSON-LD ──────────────────────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/jsonld")
def api_jsonld(pid: str, db: Session = Depends(get_db)):
    p = _prospect_or_404(pid, db)
    try:
        # Générer la FAQ en premier pour enrichir le FAQPage schema
        faq_result = generate_faq(db, p)
        result = generate_jsonld(p, faq_items=faq_result["jsonld_items"])
        return {
            "success": True,
            "result": {
                "blocks": list(result["blocks"].keys()),
                "html_snippet": result["html_snippet"],
                "instructions": result["instructions"],
                "files": result["files"],
            },
            "message": f"JSON-LD généré ({', '.join(result['blocks'].keys())}) pour {p.name}",
            "error": None,
        }
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "JSONLD_ERROR", "detail": str(e)}}


# ── Checklist ────────────────────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/checklist")
def api_checklist(pid: str, db: Session = Depends(get_db)):
    p = _prospect_or_404(pid, db)
    try:
        result = generate_checklist(p)
        return {
            "success": True,
            "result": {
                "total": result["total"],
                "done_count": result["done_count"],
                "completion_pct": result["completion_pct"],
                "file": result["file"],
            },
            "message": f"Checklist générée ({result['total']} actions) pour {p.name}",
            "error": None,
        }
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "CHECKLIST_ERROR", "detail": str(e)}}


@router.get("/api/generate/prospect/{pid}/checklist", response_class=HTMLResponse)
def api_checklist_view(pid: str, db: Session = Depends(get_db)):
    """Retourne directement le HTML de la checklist."""
    p = _prospect_or_404(pid, db)
    result = generate_checklist(p)
    return HTMLResponse(result["html"])


# ── Dossier stratégique ──────────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/dossier")
def api_dossier(pid: str, db: Session = Depends(get_db)):
    p = _prospect_or_404(pid, db)
    try:
        result = generate_dossier(db, p)
        return {
            "success": True,
            "result": {
                "summary": result["summary"],
                "file": result["file"],
            },
            "message": f"Dossier stratégique généré pour {p.name}",
            "error": None,
        }
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "DOSSIER_ERROR", "detail": str(e)}}


@router.get("/api/generate/prospect/{pid}/dossier", response_class=HTMLResponse)
def api_dossier_view(pid: str, db: Session = Depends(get_db)):
    """Retourne directement le HTML du dossier."""
    p = _prospect_or_404(pid, db)
    result = generate_dossier(db, p)
    return HTMLResponse(result["html"])


# ── Tout générer d'un coup ───────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/all-livrables")
def api_all_livrables(pid: str, db: Session = Depends(get_db)):
    """
    Génère tous les livrables du chantier 10 en une seule requête.
    Ordre : FAQ → JSON-LD (utilise FAQ) → Checklist → Dossier (parallélisable mais séquentiel ici).
    """
    p = _prospect_or_404(pid, db)
    results = {}
    errors = []

    try:
        faq = generate_faq(db, p)
        results["faq"] = {"count": faq["count"], "files": faq["files"]}
    except Exception as e:
        errors.append({"tool": "faq", "detail": str(e)})
        faq = None

    try:
        jsonld = generate_jsonld(p, faq_items=faq["jsonld_items"] if faq else None)
        results["jsonld"] = {"blocks": list(jsonld["blocks"].keys()), "files": jsonld["files"]}
    except Exception as e:
        errors.append({"tool": "jsonld", "detail": str(e)})

    try:
        checklist = generate_checklist(p)
        results["checklist"] = {"total": checklist["total"], "file": checklist["file"]}
    except Exception as e:
        errors.append({"tool": "checklist", "detail": str(e)})

    try:
        dossier = generate_dossier(db, p)
        results["dossier"] = {"summary": dossier["summary"], "file": dossier["file"]}
    except Exception as e:
        errors.append({"tool": "dossier", "detail": str(e)})

    success = len(errors) == 0
    return {
        "success": success,
        "result": results,
        "message": (
            f"{len(results)} livrable(s) générés pour {p.name}"
            + (f" — {len(errors)} erreur(s)" if errors else "")
        ),
        "error": {"code": "PARTIAL_ERROR", "detail": errors} if errors else None,
    }


# ── Outreach sans email (07) ─────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/outreach-messages")
def api_outreach(pid: str, db: Session = Depends(get_db)):
    p = _prospect_or_404(pid, db)
    try:
        result = generate_outreach(p)
        return {
            "success": True,
            "result": result,
            "message": f"Messages outreach générés pour {p.name} ({result['char_count_court']} car. SMS)",
            "error": None,
        }
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "OUTREACH_ERROR", "detail": str(e)}}


# ── Liste des livrables disponibles ─────────────────────────────────────────

@router.get("/api/livrables/{pid}")
def api_list_livrables(pid: str, t: str = "", db: Session = Depends(get_db)):
    """
    Liste les livrables déjà générés pour un prospect.
    Paramètre optionnel t= pour validation par landing_token.
    """
    p = _prospect_or_404(pid, db)
    if t and t != p.landing_token:
        raise HTTPException(403, "Token invalide")

    from pathlib import Path
    import os
    livrable_dir = Path(__file__).parent.parent.parent.parent / "dist" / pid / "livrables"
    available = []
    if livrable_dir.exists():
        for f in livrable_dir.rglob("*"):
            if f.is_file():
                available.append({
                    "name": f.name,
                    "path": str(f.relative_to(livrable_dir.parent.parent)),
                    "size": f.stat().st_size,
                })
    return {
        "success": True,
        "result": {
            "prospect_id": pid,
            "name": p.name,
            "livrables": available,
            "count": len(available),
        },
        "message": f"{len(available)} fichier(s) disponible(s)",
        "error": None,
    }
