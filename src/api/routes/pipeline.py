"""
Runner unique — POST /api/pipeline/run
Exécute SCAN → TEST → SCORE → GENERATE → QUEUE en une seule commande.
Aucun envoi email.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db, db_list_prospects
from ...models import PipelineRunInput, ProspectStatus
from ...scan import scan_prospects, ProspectScanInput
from ...ia_test import run_campaign
from ...scoring import run_scoring
from ...generate import generate_campaign

router = APIRouter(prefix="/api", tags=["Pipeline"])


@router.post("/pipeline/run")
def api_pipeline_run(data: PipelineRunInput, db: Session = Depends(get_db)):
    """
    Runner complet : SCAN → TEST → SCORE → GENERATE → QUEUE
    Retourne un rapport d'exécution complet par étape.
    Aucun email envoyé automatiquement.
    """
    report = {}

    # 1 — SCAN
    scan_input = ProspectScanInput(
        city=data.city, profession=data.profession,
        max_prospects=data.max_prospects,
        manual_prospects=data.manual_prospects,
    )
    prospects = scan_prospects(db, scan_input)
    campaign_id = prospects[0].campaign_id if prospects else None
    report["scan"] = {"campaign_id": campaign_id, "prospects_created": len(prospects)}

    if not campaign_id:
        return {"status": "error", "step": "SCAN", "detail": "Aucun prospect créé", "report": report}

    # 2 — TEST
    test_result = run_campaign(db, campaign_id, dry_run=data.dry_run)
    report["test"] = test_result

    # Repasser TESTED pour le scoring
    for p in db_list_prospects(db, campaign_id, status=ProspectStatus.TESTING.value):
        p.status = ProspectStatus.TESTED.value
    db.commit()

    # 3 — SCORE
    score_result = run_scoring(db, campaign_id)
    report["score"] = score_result

    # 4 — GENERATE (pour les éligibles SCORED uniquement — assets manquants attendus)
    # Note : GENERATE complet nécessite assets (video_url + screenshot_url).
    # Ici on génère audit + email + script pour les éligibles, mais on ne passe pas READY_TO_SEND.
    eligible = [p for p in db_list_prospects(db, campaign_id) if p.eligibility_flag]
    gen_report = {"eligible": len(eligible), "generated": 0, "files": []}
    from ...generate import audit_generate, email_generate, video_script
    for p in eligible:
        try:
            audit_generate(db, p)
            email_generate(db, p)
            video_script(p)
            gen_report["generated"] += 1
            gen_report["files"].append(p.prospect_id)
        except Exception as e:
            gen_report.setdefault("errors", []).append({"id": p.prospect_id, "err": str(e)})
    report["generate"] = gen_report

    # 5 — QUEUE (CSV des éligibles — sans video/screenshot donc incomplet → à compléter manuellement)
    from ...generate import delivery
    csv_path = delivery(db, eligible)
    report["queue"] = {
        "csv": csv_path,
        "note": "CSV généré. Ajouter video_url + screenshot_url via POST /api/prospect/{id}/assets, puis POST /api/prospect/{id}/mark-ready."
    }

    return {
        "status":      "ok",
        "campaign_id": campaign_id,
        "dry_run":     data.dry_run,
        "report":      report,
    }
