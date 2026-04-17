"""
Stripe Checkout + Webhook → Pipeline auto

POST /api/stripe/checkout-session?token=LANDING_TOKEN
  → Crée une session Checkout Stripe pour le prospect identifié par son landing token
  → Retourne {"checkout_url": "https://checkout.stripe.com/..."}

GET /success?session_id=...
  → Page de confirmation (HTML)

POST /api/stripe/webhook
  → Reçoit les événements Stripe (checkout.session.completed / payment_intent.succeeded)
  → Marque le prospect CLIENT
  → Lance le pipeline correspondant à l'offre (methode/implantation/domination)
  → Envoie email de confirmation

GET /api/stripe/pipeline-job/{job_id}
  → Statut d'un job pipeline (pending/running/done/error + score + path)

GET /admin/pipeline-jobs
  → UI admin — liste tous les jobs avec statut
"""
import json
import logging
import os
import uuid

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_by_token
from ...models import V3ProspectDB, PipelineJobDB

log = logging.getLogger(__name__)
router = APIRouter(tags=["Stripe"])


def _convert_to_client(db: Session, p) -> None:
    """Marque le prospect V3ProspectDB comme payé / CLIENT."""
    from datetime import datetime as _dt
    # Lookup V3ProspectDB directement par email ou nom+ville
    prospect = None
    if p.email:
        prospect = db.query(V3ProspectDB).filter(V3ProspectDB.email == p.email).first()
    if not prospect:
        prospect = db.query(V3ProspectDB).filter_by(name=p.name, city=p.city).first()
    if prospect:
        prospect.status = "CLIENT"
        prospect.paid = True
        prospect.date_payment = _dt.utcnow()
        log.info("V3Prospect %s passe en CLIENT", prospect.token)
    else:
        # p est lui-même un V3ProspectDB — mise à jour directe
        p.status = "CLIENT"
        p.paid = True
        p.date_payment = _dt.utcnow()
        log.info("V3Prospect %s converti CLIENT (direct)", p.token)


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

    unit_amount = int(round(offer.price * 100))
    if unit_amount <= 0:
        raise HTTPException(500, f"Prix invalide : {offer.price}€")

    base_params = dict(
        payment_method_types=["card"],
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}&token={token}",
        cancel_url=f"{base_url}/couvreur?t={token}",
        metadata={"landing_token": token, "prospect_id": p.prospect_id, "offer_id": offer.id},
    )

    # ── Mode subscription (stripe_price_id = price mensuel récurrent) ──────────
    # → 1 seule validation client : setup fee (price) + mensualités auto
    if offer.stripe_price_id and offer.stripe_price_id.startswith("price_"):
        # Vérifie si c'est un price récurrent (pour le mode subscription)
        price_obj = s.Price.retrieve(offer.stripe_price_id)
        if price_obj.get("recurring"):
            # Setup fee = paiement unique en tête de subscription
            setup_fee_amount = unit_amount  # 500€ → 50000 centimes
            session = s.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": offer.stripe_price_id, "quantity": 1}],
                subscription_data={
                    "add_invoice_items": [{
                        "price_data": {
                            "currency": "eur",
                            "unit_amount": setup_fee_amount,
                            "product_data": {"name": f"{offer.name} — Frais d'activation"},
                        }
                    }],
                    "metadata": {"offer_id": offer.id, "months": "5"},
                },
                **base_params,
            )
            log.info("Checkout SUBSCRIPTION %s — setup %s€ + mensuel — prospect %s",
                     session.id, offer.price, p.prospect_id)
            return {"checkout_url": session.url, "session_id": session.id}

    # ── Mode paiement unique (défaut — Flash 97€, Tout inclus 3500€) ───────────
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
        mode="payment",
        line_items=[line_item],
        **base_params,
    )
    log.info("Checkout PAYMENT %s — offre '%s' %s€ — prospect %s",
             session.id, offer.name, offer.price, p.prospect_id)
    return {"checkout_url": session.url, "session_id": session.id}


# ── Page succès ──────────────────────────────────────────────────────────────

@router.get("/success", response_class=HTMLResponse)
def success_page(session_id: str, token: str = "", db: Session = Depends(get_db)):
    # Marquer le prospect comme payé si token présent
    if token:
        p = db_get_by_token(db, token)
        if p and not p.paid:
            _convert_to_client(db, p)
            p.stripe_session_id = session_id
            db.commit()
            log.info("Prospect %s converti CLIENT via success page", p.prospect_id)

    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><link rel="icon" type="image/svg+xml" href="/assets/favicon.svg"><title>Merci !</title>
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
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = await request.body()
    sig     = request.headers.get("stripe-signature", "")
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

    event_type = event.get("type", "")
    event_id   = event.get("id", "")

    # ── checkout.session.completed ────────────────────────────────────────
    if event_type == "checkout.session.completed":
        session    = event["data"]["object"]
        token      = session.get("metadata", {}).get("landing_token", "")
        pid        = session.get("metadata", {}).get("prospect_id", "")
        offer_id   = session.get("metadata", {}).get("offer_id", "")
        session_id = session.get("id", "")

        # Email depuis customer_details (le plus fiable pour le checkout)
        customer_email = (
            session.get("customer_details", {}).get("email")
            or session.get("customer_email")
            or ""
        )

        # ── 1. Convertir prospect CLIENT (comportement existant) ──────────
        prospect = None
        if token:
            prospect = db_get_by_token(db, token)
            if prospect and not prospect.paid:
                _convert_to_client(db, prospect)
                try:
                    prospect.stripe_session_id = session_id
                except Exception:
                    pass
                db.commit()
                log.info("Webhook: prospect %s converti CLIENT", pid)

        # ── 2. Idempotence : ne pas relancer si event déjà traité ─────────
        if event_id:
            existing = db.query(PipelineJobDB).filter(
                PipelineJobDB.stripe_event_id == event_id
            ).first()
            if existing:
                log.info("Webhook: event %s déjà traité (job %s)", event_id, existing.id)
                return {"received": True}

        # ── 3. Résoudre offre → pipeline_type ────────────────────────────
        offer_name    = ""
        pipeline_type = "methode"
        if offer_id:
            try:
                from offers_module.database import db_get_offer
                offer = db_get_offer(db, offer_id)
                if offer:
                    offer_name    = offer.name
                    pipeline_type = _resolve_pipeline_type(offer.name)
            except Exception as e:
                log.warning("Impossible de charger offre %s : %s", offer_id, e)

        # Fallback : déduire depuis amount_total si offre inconnue
        if not offer_name:
            amount = session.get("amount_total", 0)
            if amount >= 900_00:
                pipeline_type = "domination"
            elif amount >= 350_00:
                pipeline_type = "implantation"

        # ── 4. Construire paramètres client ───────────────────────────────
        company_name  = ""
        city          = ""
        business_type = ""
        website       = ""

        if prospect:
            company_name  = prospect.name or ""
            city          = prospect.city or ""
            business_type = prospect.profession or ""
            website       = prospect.website or ""
            if not customer_email:
                customer_email = prospect.email or ""

        # Fallback si prospect absent (paiement direct via payment_link)
        if not company_name:
            cd = session.get("customer_details", {})
            company_name = cd.get("name") or customer_email or "Client"

        if not city or not business_type:
            log.warning("Webhook: city/business_type manquants pour job %s — pipeline skippé côté IA", event_id)

        # ── 5. Créer le PipelineJobDB ─────────────────────────────────────
        db_url = _get_db_url()
        job = PipelineJobDB(
            id                = str(uuid.uuid4()),
            stripe_event_id   = event_id or str(uuid.uuid4()),
            stripe_session_id = session_id,
            offer_id          = offer_id or None,
            offer_name        = offer_name or pipeline_type,
            pipeline_type     = pipeline_type,
            email             = customer_email or None,
            company_name      = company_name or "Client",
            city              = city or "France",
            business_type     = business_type or "entreprise",
            website           = website or None,
            status            = "pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id_str = job.id
        log.info("Webhook: PipelineJob %s créé — %s — %s/%s",
                 job_id_str, pipeline_type, company_name, city)

        # ── 6. Email immédiat "paiement reçu, analyse en cours" ───────────
        if customer_email:
            background_tasks.add_task(
                _send_payment_email,
                customer_email, company_name,
                offer_name or pipeline_type, pipeline_type,
            )

        # ── 7. Lancer le pipeline en arrière-plan ─────────────────────────
        background_tasks.add_task(_run_pipeline_job, job_id_str, db_url)

    return {"received": True}


# ── Helpers webhook ───────────────────────────────────────────────────────────

def _resolve_pipeline_type(offer_name: str) -> str:
    name = (offer_name or "").lower()
    if "domination" in name:
        return "domination"
    if "implantation" in name:
        return "implantation"
    return "methode"


def _get_db_url() -> str:
    import os
    from pathlib import Path
    db_path = os.getenv(
        "DB_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data" / "presence_ia.db"),
    )
    return f"sqlite:///{db_path}"


def _send_payment_email(email, company_name, offer_name, pipeline_type):
    try:
        from ...payments.pipeline_dispatcher import send_payment_received_email
        send_payment_received_email(email, company_name, offer_name, pipeline_type)
    except Exception as e:
        log.warning("Email paiement reçu : %s", e)


def _run_pipeline_job(job_id: str, db_url: str):
    try:
        from ...payments.pipeline_dispatcher import run_pipeline_job
        run_pipeline_job(job_id, db_url)
    except Exception as e:
        log.exception("_run_pipeline_job %s : %s", job_id, e)


# ── Endpoint statut job ───────────────────────────────────────────────────────

@router.get("/api/stripe/pipeline-job/{job_id}")
def get_pipeline_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(PipelineJobDB).filter(PipelineJobDB.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job introuvable")
    return {
        "job_id":          job.id,
        "pipeline_type":   job.pipeline_type,
        "status":          job.status,
        "score":           job.score,
        "company_name":    job.company_name,
        "city":            job.city,
        "offer_name":      job.offer_name,
        "deliverable_path": job.deliverable_path,
        "error":           job.error,
        "created_at":      job.created_at.isoformat() if job.created_at else None,
        "completed_at":    job.completed_at.isoformat() if job.completed_at else None,
    }


# ── Admin — liste des jobs ────────────────────────────────────────────────────

def _admin_ok(request: Request) -> bool:
    token = request.query_params.get("token") or request.headers.get("X-Admin-Token", "")
    return token == os.getenv("ADMIN_TOKEN", "admin")


@router.get("/api/stripe/pipeline-job/{job_id}/result", response_class=HTMLResponse)
def get_pipeline_job_result(job_id: str, request: Request, db: Session = Depends(get_db)):
    if not _admin_ok(request):
        return HTMLResponse("<h1>403</h1>", status_code=403)
    job = db.query(PipelineJobDB).filter(PipelineJobDB.id == job_id).first()
    if not job or job.status != "done":
        return HTMLResponse("<h1>Livrable non disponible</h1>", status_code=404)
    if not job.deliverable_path:
        return HTMLResponse("<h1>Chemin livrable absent</h1>", status_code=404)
    from pathlib import Path
    path = Path(job.deliverable_path)
    if not path.exists():
        return HTMLResponse(f"<h1>Fichier introuvable : {path}</h1>", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/admin/pipeline-jobs", response_class=HTMLResponse)
def admin_pipeline_jobs(request: Request, db: Session = Depends(get_db)):
    if not _admin_ok(request):
        return HTMLResponse("<h1>403</h1>", status_code=403)

    token = request.query_params.get("token", "admin")
    jobs  = db.query(PipelineJobDB).order_by(PipelineJobDB.created_at.desc()).limit(100).all()

    rows = ""
    for j in jobs:
        status_color = {
            "done":    "#10b981",
            "error":   "#ef4444",
            "running": "#f59e0b",
            "pending": "#64748b",
        }.get(j.status, "#94a3b8")

        pipeline_badge = {
            "domination":   "#6366f1",
            "implantation": "#8b5cf6",
            "methode":      "#a78bfa",
        }.get(j.pipeline_type, "#64748b")

        result_link = ""
        if j.status == "done" and j.deliverable_path:
            result_link = f'<a href="/api/stripe/pipeline-job/{j.id}/result?token={token}" style="color:#818cf8" target="_blank">Livrable</a>'

        error_html = f'<span title="{j.error or ""}" style="color:#ef4444;font-size:0.8rem">⚠ {(j.error or "")[:40]}</span>' if j.error else ""
        score_html = f'<strong style="color:#6366f1">{round(j.score, 1)}/10</strong>' if j.score else "—"
        created    = j.created_at.strftime("%d/%m %H:%M") if j.created_at else "—"

        rows += f"""<tr>
          <td style="color:#94a3b8;font-size:0.8rem">{created}</td>
          <td>
            <div style="font-weight:600;color:#e2e8f0">{j.company_name}</div>
            <div style="color:#64748b;font-size:0.82rem">{j.city} · {j.email or '—'}</div>
          </td>
          <td><span style="background:{pipeline_badge}22;color:{pipeline_badge};padding:2px 8px;border-radius:10px;font-size:0.8rem;font-weight:600">{j.pipeline_type}</span></td>
          <td><span style="color:{status_color};font-weight:600">{j.status}</span></td>
          <td>{score_html}</td>
          <td>{result_link}{error_html}</td>
        </tr>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Admin — Pipeline Jobs</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#0f172a; color:#e2e8f0; padding:40px; }}
  .card {{ background:#1e293b; border-radius:12px; padding:24px; margin-bottom:20px; }}
  table {{ width:100%; border-collapse:collapse; }}
  td, th {{ padding:12px 14px; text-align:left; border-bottom:1px solid #0f172a; }}
  th {{ font-size:0.78rem; text-transform:uppercase; color:#64748b; font-weight:600; }}
  h1 {{ font-size:1.4rem; color:#fff; margin-bottom:6px; }}
  p  {{ color:#64748b; font-size:0.9rem; }}
</style>
</head>
<body>
<div style="max-width:1100px;margin:0 auto">
  <div class="card" style="background:linear-gradient(135deg,#1e1b4b,#312e81);border:1px solid #4338ca33;margin-bottom:28px">
    <h1>⚡ Pipeline Jobs — Stripe → Livrable</h1>
    <p>{len(jobs)} jobs · auto-refresh toutes les 30 secondes</p>
  </div>
  <div class="card">
    <table>
      <tr><th>Date</th><th>Client</th><th>Pipeline</th><th>Statut</th><th>Score</th><th>Action</th></tr>
      {rows or '<tr><td colspan="6" style="text-align:center;color:#475569;padding:32px">Aucun job — les jobs apparaissent dès qu\'un paiement Stripe est reçu</td></tr>'}
    </table>
  </div>
</div>
<script>setTimeout(() => location.reload(), 30000);</script>
</body>
</html>""")
