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
def create_checkout(token: str, offer_id: str = "", db: Session = Depends(get_db)):
    p = db_get_by_token(db, token)
    if not p:
        raise HTTPException(404, "Token invalide")

    s = _stripe()
    base_url = os.getenv("BASE_URL", "http://localhost:8001")

    # Résoudre l'offre : par ID si fourni, sinon première offre "flash"
    from offers_module.database import db_list_offers, db_get_offer
    if offer_id:
        offer = db_get_offer(db, offer_id)
        if not offer or not offer.active:
            raise HTTPException(404, f"Offre '{offer_id}' introuvable ou inactive")
    else:
        all_offers = db_list_offers(db)
        offer = next((o for o in all_offers if "flash" in o.name.lower()), None)
        if not offer:
            offer = all_offers[0] if all_offers else None

    if not offer:
        raise HTTPException(500, "Aucune offre active configurée")

    # Montant en centimes — round() évite les erreurs float (ex: 500+5*100 = 1000 → 100000c)
    unit_amount = int(round(offer.price * 100))
    if unit_amount <= 0:
        raise HTTPException(500, f"Prix invalide : {offer.price}€")

    # Si stripe_price_id configuré → utiliser le Price Stripe existant
    if offer.stripe_price_id:
        line_item = {"price": offer.stripe_price_id, "quantity": 1}
    else:
        line_item = {
            "price_data": {
                "currency": "eur",
                "unit_amount": unit_amount,
                "product_data": {
                    "name": f"{offer.name} — {p.name} ({p.city})",
                    "description": "Audit Visibilité IA · 3 modèles × 5 requêtes · Plan d'action",
                },
            },
            "quantity": 1,
        }

    session = s.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[line_item],
        mode="payment",
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}&token={token}",
        cancel_url=f"{base_url}/couvreur?t={token}",
        metadata={"landing_token": token, "prospect_id": p.prospect_id, "offer_id": offer.id},
    )

    log.info("Checkout session %s — offre '%s' %s€ — prospect %s", session.id, offer.name, offer.price, p.prospect_id)
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
<p style="margin-top:24px;color:#555;font-size:13px">© PRESENCE_IA — {os.getenv("SENDER_EMAIL", "contact@presence-ia.com")}</p>
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
