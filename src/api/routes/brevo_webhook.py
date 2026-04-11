"""
Webhook Brevo — tracking emails outbound v3_prospects.

Endpoint : POST /webhooks/brevo
Événements traités : delivered, open, bounce, spam, unsubscribe

Brevo envoie un tableau JSON : [{"event": "...", "email": "...", "ts": ...}, ...]
Doc : https://developers.brevo.com/docs/transactional-webhooks
"""
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
router = APIRouter()

# Mapping event Brevo → email_status interne
_EVENT_MAP = {
    "delivered":   "delivered",
    "open":        "opened",
    "click":       "clicked",
    "bounce":      "bounced",
    "hardBounce":  "bounced",
    "softBounce":  "bounced",
    "spam":        "bounced",  # traité comme bounce pour la délivrabilité
    "unsubscribe": "bounced",
}


def _find_prospect_by_email(db, email: str):
    """Retourne le v3_prospect le plus récemment envoyé pour cet email."""
    from ..database import SessionLocal
    from ..models import V3ProspectDB
    return (
        db.query(V3ProspectDB)
        .filter(V3ProspectDB.email == email)
        .order_by(V3ProspectDB.email_sent_at.desc().nullslast())
        .first()
    )


def _validate_payload(payload: Any) -> List[Dict]:
    """Valide la structure minimale du payload Brevo.
    Brevo envoie soit un objet unique, soit une liste.
    """
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise HTTPException(400, "Payload invalide : liste ou objet attendu")
    for item in payload:
        if not isinstance(item, dict):
            raise HTTPException(400, "Chaque événement doit être un objet JSON")
        if "event" not in item or "email" not in item:
            raise HTTPException(400, "Champs 'event' et 'email' requis")
    return payload


@router.post("/webhooks/brevo")
async def brevo_webhook(request: Request):
    """Reçoit les événements Brevo et met à jour le tracking v3_prospects."""
    # ── Lecture payload ────────────────────────────────────────────────────────
    try:
        payload = await request.json()
    except Exception as e:
        log.warning("[BREVO_WEBHOOK] payload JSON invalide : %s", e)
        raise HTTPException(400, "JSON invalide")

    events = _validate_payload(payload)
    log.info("[BREVO_WEBHOOK] %d événement(s) reçu(s)", len(events))

    # ── Traitement ─────────────────────────────────────────────────────────────
    from ..database import SessionLocal

    processed = 0
    skipped   = 0

    for evt in events:
        event_type = evt.get("event", "").lower()
        email      = (evt.get("email") or "").lower().strip()
        ts_raw     = evt.get("ts") or evt.get("timestamp")

        log.info("[BREVO_WEBHOOK] event=%s  email=%s  ts=%s", event_type, email, ts_raw)

        new_status = _EVENT_MAP.get(event_type)
        if not new_status:
            log.info("[BREVO_WEBHOOK] événement ignoré (non mappé) : %s", event_type)
            skipped += 1
            continue

        if not email:
            log.warning("[BREVO_WEBHOOK] email manquant — event=%s", event_type)
            skipped += 1
            continue

        # Timestamp
        try:
            if ts_raw:
                event_dt = datetime.utcfromtimestamp(int(ts_raw))
            else:
                event_dt = datetime.utcnow()
        except (ValueError, TypeError):
            event_dt = datetime.utcnow()

        # Mise à jour DB
        try:
            with SessionLocal() as db:
                from ..models import V3ProspectDB
                prospect = (
                    db.query(V3ProspectDB)
                    .filter(V3ProspectDB.email == email)
                    .order_by(V3ProspectDB.email_sent_at.desc().nullslast())
                    .first()
                )
                if not prospect:
                    log.info("[BREVO_WEBHOOK] prospect introuvable pour %s", email)
                    skipped += 1
                    continue

                prospect.email_status = new_status
                if new_status == "opened" and not prospect.email_opened_at:
                    prospect.email_opened_at = event_dt
                if new_status == "clicked":
                    if not prospect.email_clicked_at:
                        prospect.email_clicked_at = event_dt
                    # un clic implique une ouverture
                    if not prospect.email_opened_at:
                        prospect.email_opened_at = event_dt
                if new_status == "bounced" and not prospect.email_bounced_at:
                    prospect.email_bounced_at = event_dt
                db.commit()

            log.info("[BREVO_WEBHOOK] ✓ %s → %s  [%s]", email, new_status, event_type)
            processed += 1

        except Exception as e:
            log.error("[BREVO_WEBHOOK] erreur DB pour %s : %s", email, e)
            skipped += 1

    return JSONResponse({"ok": True, "processed": processed, "skipped": skipped})
