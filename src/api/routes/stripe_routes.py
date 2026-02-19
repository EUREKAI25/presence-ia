"""
Stripe Checkout — Audit 97€

POST /api/stripe/checkout-session?token=LANDING_TOKEN
  → Crée une session Checkout Stripe pour le prospect identifié par son landing token
  → Retourne {"checkout_url": "https://checkout.stripe.com/..."}

GET /success?session_id=...
  → Page de confirmation (HTML)

POST /api/stripe/webhook
  → Reçoit les événements Stripe (checkout.session.completed)
  → Marque le prospect comme paid=True
"""
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_by_token

log = logging.getLogger(__name__)
router = APIRouter(tags=["Stripe"])


def _stripe():
    import stripe as _s
    _s.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not _s.api_key:
        raise HTTPException(500, "STRIPE_SECRET_KEY non configurée")
    return _s


# ── Checkout session ─────────────────────────────────────────────────────────

@router.post("/api/stripe/checkout-session")
def create_checkout(token: str, db: Session = Depends(get_db)):
    p = db_get_by_token(db, token)
    if not p:
        raise HTTPException(404, "Token invalide")

    s = _stripe()
    base_url = os.getenv("BASE_URL", "http://localhost:8001")

    # Lire le prix FLASH depuis offers_module
    from offers_module.database import db_list_offers
    flash_offers = db_list_offers(db)
    flash = next((o for o in flash_offers if "flash" in o.name.lower()), None)
    unit_amount = int(flash.price * 100) if flash else 9700  # fallback 97€

    session = s.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": unit_amount,
                "product_data": {
                    "name": f"Audit Visibilité IA — {p.name} ({p.city})",
                    "description": "Audit complet IA sur 3 modèles × 5 requêtes + plan d'action",
                },
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}&token={token}",
        cancel_url=f"{base_url}/couvreur?t={token}",
        metadata={"landing_token": token, "prospect_id": p.prospect_id},
    )

    log.info("Checkout session créée %s pour prospect %s", session.id, p.prospect_id)
    return {"checkout_url": session.url, "session_id": session.id}


# ── Page succès ──────────────────────────────────────────────────────────────

@router.get("/success", response_class=HTMLResponse)
def success_page(session_id: str, token: str = "", db: Session = Depends(get_db)):
    # Marquer le prospect comme payé si token présent
    if token:
        p = db_get_by_token(db, token)
        if p and not p.paid:
            p.paid = True
            p.stripe_session_id = session_id
            db.commit()
            log.info("Prospect %s marqué PAID via success page", p.prospect_id)

    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Merci !</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Segoe UI',sans-serif;
background:#0f0f1a;color:#e8e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#1a1a2e;border:1px solid #2ecc71;border-radius:16px;padding:60px 40px;text-align:center;max-width:520px}
.icon{font-size:64px;margin-bottom:24px}h1{color:#2ecc71;font-size:28px;margin-bottom:16px}
p{color:#aaa;line-height:1.6;margin-bottom:8px}strong{color:#fff}</style></head>
<body><div class="card">
<div class="icon">✅</div>
<h1>Paiement confirmé !</h1>
<p>Merci pour votre confiance.</p>
<p>Vous recevrez votre <strong>rapport d'audit IA complet</strong> par email <strong>d'ici quelques minutes</strong>.</p>
<p style="margin-top:24px;color:#555;font-size:13px">© PRESENCE_IA — contact@presence-ia.com</p>
</div></body></html>""")


# ── Webhook ──────────────────────────────────────────────────────────────────

@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    s = _stripe()
    try:
        if webhook_secret:
            event = s.Webhook.construct_event(payload, sig, webhook_secret)
        else:
            event = json.loads(payload)
            log.warning("STRIPE_WEBHOOK_SECRET absent — signature non vérifiée")
    except Exception as e:
        log.error("Webhook Stripe invalide : %s", e)
        raise HTTPException(400, f"Webhook invalide : {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        token = session.get("metadata", {}).get("landing_token", "")
        pid   = session.get("metadata", {}).get("prospect_id", "")

        if token:
            p = db_get_by_token(db, token)
            if p and not p.paid:
                p.paid = True
                p.stripe_session_id = session["id"]
                db.commit()
                log.info("Webhook: prospect %s (token=%s) marqué PAID", pid, token)

    return {"received": True}
