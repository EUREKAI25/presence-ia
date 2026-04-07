"""
Routes livrables clients — chantier 10
POST /api/generate/prospect/{pid}/faq
POST /api/generate/prospect/{pid}/jsonld
POST /api/generate/prospect/{pid}/checklist
POST /api/generate/prospect/{pid}/dossier
POST /api/generate/prospect/{pid}/all-livrables
POST /api/generate/prospect/{pid}/content-rewrite
GET  /api/livrables/{pid}

Rapports IA (V3 prospects) :
GET  /api/reports/v3/{token}/audit          → HTML audit initial
GET  /api/reports/v3/{token}/monthly        → HTML rapport mensuel
POST /api/reports/v3/{token}/monthly        → avec previous_data JSON
GET  /api/reports/v3/{token}/snapshot       → JSON snapshot (pour rapport suivant)
"""
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_prospect
from ...models import V3ProspectDB
from ...livrables.report_generator import (
    generate_audit_report,
    generate_monthly_report,
    build_snapshot,
    run_monthly,
)
from ...livrables.faq import generate_faq
from ...livrables.jsonld import generate_jsonld
from ...livrables.checklist import generate_checklist
from ...livrables.dossier import generate_dossier
from ...livrables.outreach import generate_outreach
from ...livrables.content_rewriter import generate_content_rewrite

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


# ── Content Rewrite (10C) ────────────────────────────────────────────────────

@router.post("/api/generate/prospect/{pid}/content-rewrite")
def api_content_rewrite(pid: str, db: Session = Depends(get_db)):
    p = _prospect_or_404(pid, db)
    try:
        result = generate_content_rewrite(p)
        return {
            "success": True,
            "result": {
                "pages_scraped": result["pages_scraped"],
                "pages_failed": result["pages_failed"],
                "file": result["file"],
            },
            "message": f"{result['pages_scraped']} page(s) réécrite(s) pour {p.name}",
            "error": None,
        }
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "REWRITE_ERROR", "detail": str(e)}}


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


# ── Rapports HTML — V3 prospects ──────────────────────────────────────────────

def _v3_or_404(token: str, db: Session) -> V3ProspectDB:
    p = db.query(V3ProspectDB).filter(V3ProspectDB.token == token).first()
    if not p:
        raise HTTPException(404, "Prospect V3 introuvable")
    if not p.ia_results:
        raise HTTPException(422, "Aucun résultat IA disponible pour ce prospect")
    return p


@router.get("/api/reports/v3/{token}/audit", response_class=HTMLResponse)
def api_audit_report(
    token: str,
    next_step: str = "",
    db: Session = Depends(get_db),
):
    """
    Génère le rapport d'audit initial HTML pour un prospect V3.
    Paramètre optionnel : next_step (texte prochaine étape, adapté à l'offre vendue).
    """
    p    = _v3_or_404(token, db)
    html = generate_audit_report(p, db=db, next_step=next_step)
    return HTMLResponse(html)


@router.get("/api/reports/v3/{token}/monthly", response_class=HTMLResponse)
def api_monthly_report_get(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Génère un rapport mensuel depuis le dernier snapshot en DB.
    Charge automatiquement le snapshot précédent pour calculer le delta.
    """
    p    = _v3_or_404(token, db)
    html = generate_monthly_report(p, db=db)
    return HTMLResponse(html)


@router.post("/api/reports/v3/{token}/monthly", response_class=HTMLResponse)
def api_monthly_report_post(
    token: str,
    body: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    """
    Génère un rapport mensuel avec actions et étapes passées en body.

    Body JSON :
    {
      "actions_done": [
        {"date": "15 avr.", "title": "Google Business Profile mis à jour",
         "desc": "Description, catégories, photos.", "status": "done"}
      ],
      "next_actions": [
        {"title": "FAQ 8 questions", "desc": "Questions posées aux IA."}
      ],
      "periode":   "mai 2026",
      "note":      "Texte libre...",
      "reviews_count":   12,
      "annuaires_count":  3,
      "next_retest":     "7 juin 2026",
      "prochain_mois":   "Juin"
    }
    Le snapshot précédent est chargé automatiquement depuis ia_snapshots.
    """
    p = _v3_or_404(token, db)
    # Données extra optionnelles à passer au rapport (KPIs, dates)
    extra = {k: body[k] for k in ("reviews_count", "annuaires_count", "next_retest", "prochain_mois")
             if k in body}
    html = generate_monthly_report(
        p,
        db           = db,
        previous_data= extra if extra else None,   # None → charge depuis DB
        actions_done = body.get("actions_done"),
        next_actions = body.get("next_actions"),
        periode      = body.get("periode", ""),
        note         = body.get("note", ""),
    )
    return HTMLResponse(html)


@router.get("/api/reports/v3/{token}/snapshot")
def api_report_snapshot(
    token: str,
    db: Session = Depends(get_db),
):
    """Retourne le dernier snapshot JSON d'un prospect."""
    from ...livrables.report_generator import _load_last_snapshot
    p    = _v3_or_404(token, db)
    snap = _load_last_snapshot(db, p.token)
    if not snap:
        raise HTTPException(404, "Aucun snapshot trouvé pour ce prospect")
    return JSONResponse(snap)


@router.get("/api/reports/v3/{token}/history")
def api_report_history(
    token: str,
    db: Session = Depends(get_db),
):
    """Liste tous les snapshots d'un prospect (historique des scores)."""
    from ...models import IaSnapshotDB
    _v3_or_404(token, db)
    snaps = (
        db.query(IaSnapshotDB)
        .filter(IaSnapshotDB.prospect_token == token)
        .order_by(IaSnapshotDB.created_at.asc())
        .all()
    )
    return {
        "token":    token,
        "count":    len(snaps),
        "history": [
            {
                "id":          s.id,
                "type":        s.report_type,
                "date":        s.created_at.isoformat() if s.created_at else None,
                "score":       s.score,
                "nb_mentions": s.nb_mentions,
                "nb_total":    s.nb_total,
            }
            for s in snaps
        ],
    }


# ── ia_reports — moteur réel branché aux données V3 ──────────────────────────

@router.post("/api/ia-reports/{token}/audit")
def api_ia_audit(token: str, db: Session = Depends(get_db)):
    """
    Génère l'audit initial HTML pour un prospect V3.
    Appelle create_initial_audit_for_prospect() depuis src/ia_reports/service.py.
    Sauvegarde le snapshot en DB + le fichier HTML sur disque.
    """
    try:
        from ...ia_reports.service import create_initial_audit_for_prospect
        result = create_initial_audit_for_prospect(token, db)
        return {
            "success": True,
            "result": {
                "audit_path":     result["audit_path"],
                "cms_guide_path": result["cms_guide_path"],
                "snapshot_id":    result["snapshot_id"],
                "score":          result["summary"]["score"],
                "citations":      f"{result['summary']['total_citations']}/{result['summary']['total_possible']}",
                "checklist_level": result["summary"]["checklist_level"],
                "competitors":    result["summary"]["competitors"],
            },
            "message": f"Audit généré pour {result['name']} — score {result['summary']['score']}/10",
            "error": None,
        }
    except ValueError as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "NOT_FOUND", "detail": str(e)}}
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "AUDIT_ERROR", "detail": str(e)}}


@router.post("/api/ia-reports/{token}/monthly")
def api_ia_monthly(token: str, body: dict = Body(default={}), db: Session = Depends(get_db)):
    """
    Génère le rapport mensuel HTML pour un prospect V3.
    Charge automatiquement le dernier snapshot depuis ia_snapshots.
    Nécessite qu'un audit initial ait été généré au préalable.

    Body JSON optionnel :
    {
      "actions_done": [{"date": "...", "title": "...", "desc": "...", "status": "done"}],
      "next_actions": [{"title": "...", "desc": "..."}],
      "periode": "mai 2026",
      "note": "Texte libre...",
      "reviews_count": 12,
      "annuaires_count": 3,
      "next_retest": "7 juin 2026"
    }
    """
    try:
        from ...ia_reports.service import create_monthly_report_for_prospect
        result = create_monthly_report_for_prospect(
            token, db,
            actions_done    = body.get("actions_done"),
            next_actions    = body.get("next_actions"),
            periode         = body.get("periode", ""),
            note            = body.get("note", ""),
            reviews_count   = body.get("reviews_count", "—"),
            annuaires_count = body.get("annuaires_count", "—"),
            next_retest     = body.get("next_retest", "à définir"),
        )
        return {
            "success": True,
            "result": {
                "report_path": result["report_path"],
                "snapshot_id": result["snapshot_id"],
                "num_test":    result["num_test"],
                "score":       result["summary"]["score"],
                "prev_score":  result["summary"]["prev_score"],
                "delta":       result["summary"]["delta"],
            },
            "message": f"Rapport mensuel Test n°{result['num_test']} généré — score {result['summary']['score']}/10 (delta {result['summary']['delta']:+.1f})",
            "error": None,
        }
    except ValueError as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "NOT_FOUND", "detail": str(e)}}
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "MONTHLY_ERROR", "detail": str(e)}}


@router.post("/api/ia-reports/{token}/bundle")
def api_ia_bundle(token: str, db: Session = Depends(get_db)):
    """
    Génère tous les livrables disponibles pour un prospect V3 :
    - Audit initial (toujours)
    - Rapport mensuel (si un audit précédent existait déjà)
    - Chemin du guide CMS adapté
    """
    try:
        from ...ia_reports.service import create_full_deliverable_bundle
        result = create_full_deliverable_bundle(token, db)
        return {
            "success": len(result["errors"]) == 0,
            "result": {
                "audit_path":     result["audit_path"],
                "report_path":    result["report_path"],
                "cms_guide_path": result["cms_guide_path"],
                "snapshot_id":    result["snapshot_id"],
                "score":          result["summary"].get("score"),
                "errors":         result["errors"],
            },
            "message": f"Bundle généré pour {result['name']}" + (f" — {len(result['errors'])} erreur(s)" if result["errors"] else ""),
            "error": {"code": "PARTIAL_ERROR", "detail": result["errors"]} if result["errors"] else None,
        }
    except ValueError as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "NOT_FOUND", "detail": str(e)}}
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "BUNDLE_ERROR", "detail": str(e)}}


@router.post("/api/ia-reports/{token}/content")
def api_ia_content(token: str, db: Session = Depends(get_db)):
    """
    Génère le bundle de contenus IA-optimisés : FAQ + page service + JSON-LD.
    Utilise les queries du dernier snapshot ou ia_results si pas encore d'audit.
    """
    try:
        from ...content_engine.service import generate_content_bundle
        result = generate_content_bundle(token, db)
        return {
            "success": len(result["errors"]) == 0,
            "result": {
                "faq_count":   len(result["faq"]),
                "faq":         result["faq"],
                "paths":       result["paths"],
                "schema_snippet": result["schema"].get("html_snippet", "") if result["schema"] else "",
                "instructions":   result["schema"].get("instructions", "") if result["schema"] else "",
                "errors":      result["errors"],
            },
            "message": f"{len(result['faq'])} questions FAQ + page service + JSON-LD générés pour {result['name']}",
            "error": {"code": "PARTIAL_ERROR", "detail": result["errors"]} if result["errors"] else None,
        }
    except ValueError as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "NOT_FOUND", "detail": str(e)}}
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "CONTENT_ERROR", "detail": str(e)}}


@router.post("/api/ia-reports/{token}/publish")
def api_ia_publish(token: str, body: dict = Body(default={}), db: Session = Depends(get_db)):
    """
    Publie la page service du prospect sur son site.

    - WordPress : publication automatique via REST API si credentials fournis
    - Autres CMS : retourne instructions + contenu prêt à coller

    Body JSON optionnel (WordPress uniquement) :
    {
      "username":     "admin",
      "app_password": "xxxx xxxx xxxx xxxx xxxx xxxx"
    }
    """
    try:
        from ...publisher.service import publish_for_prospect
        credentials = None
        if body.get("username") and body.get("app_password"):
            credentials = {
                "username":     body["username"],
                "app_password": body["app_password"],
            }
        result = publish_for_prospect(token, db, credentials=credentials)
        return {
            "success": result["ok"],
            "result": {
                "method":       result["method"],
                "cms":          result["cms"],
                "status":       result["status"],
                "url":          result["url"],
                "edit_url":     result.get("edit_url"),
                "page_id":      result.get("page_id"),
                "instructions": result.get("instructions", ""),
            },
            "message": (
                f"Page publiée sur {result['url']}" if result["url"]
                else f"Package manuel prêt ({result['cms']})"
            ),
            "error": {"code": "PUBLISH_ERROR", "detail": result["error"]} if result.get("error") else None,
        }
    except ValueError as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "NOT_FOUND", "detail": str(e)}}
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "PUBLISH_ERROR", "detail": str(e)}}


# ── Maillage interne ─────────────────────────────────────────────────────────

@router.post("/api/ia-reports/{token}/mesh")
def api_ia_mesh(token: str, body: dict = Body(default={}), db: Session = Depends(get_db)):
    """
    Rafraîchit le maillage interne pour toutes les pages publiées d'un prospect.

    Pour chaque page :
    - Cherche les pages proches (même profession / même ville)
    - Construit les suggestions de liens (max 3)
    - Enregistre en DB (internal_links_json)
    - Retourne le HTML du bloc "À lire aussi" à injecter manuellement

    Body JSON optionnel (pour V2 WP auto-update — non encore implémenté) :
    { "username": "admin", "app_password": "xxxx" }
    """
    try:
        from ...publisher.mesh_service import refresh_internal_links_for_prospect
        from ...publisher.page_index import ensure_table
        from ...database import engine as _engine
        ensure_table(_engine)

        credentials = None
        if body.get("username") and body.get("app_password"):
            credentials = {"username": body["username"], "app_password": body["app_password"]}

        result = refresh_internal_links_for_prospect(token, db, credentials=credentials)
        return {
            "success": len(result["errors"]) == 0,
            "result": {
                "pages_updated": result["pages_updated"],
                "links_created": result["links_created"],
                "pages":         result["pages"],
            },
            "message": (
                f"{result['links_created']} lien(s) créé(s) pour {result['name']} "
                f"({result['pages_updated']} page(s))"
            ),
            "error": {"code": "PARTIAL_ERROR", "detail": result["errors"]} if result["errors"] else None,
        }
    except ValueError as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "NOT_FOUND", "detail": str(e)}}
    except Exception as e:
        return {"success": False, "result": None, "message": "", "error": {"code": "MESH_ERROR", "detail": str(e)}}


# ── Pipeline admin : run_monthly ──────────────────────────────────────────────

@router.post("/api/reports/run-monthly")
def api_run_monthly(db: Session = Depends(get_db)):
    """
    Génère les rapports mensuels pour tous les clients actifs.
    Un client actif = ia_results présents + au moins un audit snapshot.
    """
    results = run_monthly(db)
    ok_count  = sum(1 for r in results if r["ok"])
    err_count = len(results) - ok_count
    return {
        "total":  len(results),
        "ok":     ok_count,
        "errors": err_count,
        "results": results,
    }
