"""
Backfill historique Brevo → v3_prospects.

Lit les événements transactionnels email + SMS depuis l'API Brevo
et met à jour les colonnes de tracking dans notre DB.

Fenêtre : 30 jours (limite max API Brevo)
Mapping : email → token prospect (dernier envoi)

Usage : python3 scripts/brevo_backfill.py [--dry-run]
"""
import os
import sys
import sqlite3
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DRY_RUN = "--dry-run" in sys.argv

DB_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "presence_ia.db")
API_BASE = "https://api.brevo.com/v3"

def _load_key():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("BREVO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("BREVO_API_KEY introuvable dans .env")

# ── Brevo API helpers ─────────────────────────────────────────────────────────
def _get_email_events(api_key: str, days: int = 30) -> list:
    headers = {"api-key": api_key}
    events  = []
    offset  = 0
    limit   = 500
    print(f"[BREVO] Récupération événements email (fenêtre {days} jours)...")
    while True:
        r = requests.get(
            f"{API_BASE}/smtp/statistics/events",
            headers=headers,
            params={"limit": limit, "offset": offset, "days": days},
            timeout=30,
        )
        if not r.ok:
            print(f"[BREVO] Erreur API email {r.status_code}: {r.text[:200]}")
            break
        data   = r.json()
        batch  = data.get("events", [])
        events.extend(batch)
        print(f"  offset={offset} → {len(batch)} events (total: {len(events)})")
        if len(batch) < limit:
            break
        offset += limit
    return events

def _get_sms_logs(api_key: str) -> list:
    headers = {"api-key": api_key}
    logs    = []
    offset  = 0
    limit   = 500
    print("[BREVO] Récupération logs SMS...")
    while True:
        r = requests.get(
            f"{API_BASE}/transactionalSMS/statistics",
            headers=headers,
            params={
                "startDate": "2026-04-01",
                "endDate":   datetime.utcnow().strftime("%Y-%m-%d"),
                "limit":     limit,
                "offset":    offset,
            },
            timeout=30,
        )
        if not r.ok:
            print(f"[BREVO] SMS API {r.status_code}: {r.text[:300]}")
            break
        data  = r.json()
        # L'API SMS Brevo retourne directement une liste ou un objet
        batch = data if isinstance(data, list) else data.get("statistics", data.get("logs", []))
        if not batch:
            break
        logs.extend(batch)
        print(f"  offset={offset} → {len(batch)} logs SMS (total: {len(logs)})")
        if len(batch) < limit:
            break
        offset += limit
    return logs

# ── Mapping événements Brevo → statut interne ─────────────────────────────────
EMAIL_EVENT_MAP = {
    "delivered":   "delivered",
    "opened":      "opened",
    "clicks":      "clicked",
    "softBounces": "bounced",
    "hardBounces": "bounced",
    "spam":        "bounced",
    "unsubscribed":"bounced",
    # noms alternatifs API v3
    "click":       "clicked",
    "open":        "opened",
    "hardBounce":  "bounced",
    "softBounce":  "bounced",
    "unsubscribe": "bounced",
}

STATUS_PRIORITY = {
    "sent": 0, "delivered": 1, "opened": 2, "clicked": 3, "bounced": 1,
}

def _higher(current: str | None, new: str) -> bool:
    """Retourne True si new_status est plus informatif que current."""
    if not current:
        return True
    return STATUS_PRIORITY.get(new, 0) > STATUS_PRIORITY.get(current, 0)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    api_key = _load_key()
    db      = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # Index email → token (dernier envoi par email)
    c.execute("""
        SELECT email, token, email_status, email_sent_at,
               email_opened_at, email_bounced_at, email_clicked_at
        FROM v3_prospects
        WHERE email IS NOT NULL
        ORDER BY email_sent_at DESC
    """)
    by_email: dict = {}
    for row in c.fetchall():
        email = (row["email"] or "").lower().strip()
        if email and email not in by_email:
            by_email[email] = dict(row)

    print(f"[DB] {len(by_email)} prospects avec email en DB")

    # ── Email events ──────────────────────────────────────────────────────────
    email_events = _get_email_events(api_key)
    print(f"\n[EMAIL] {len(email_events)} événements Brevo récupérés")

    from collections import Counter
    type_counts = Counter(e.get("event") for e in email_events)
    print("[EMAIL] Distribution types:", dict(type_counts))

    updates_email = 0
    for ev in email_events:
        email      = (ev.get("email") or "").lower().strip()
        event_type = ev.get("event", "")
        ts_raw     = ev.get("date") or ev.get("ts")

        if not email or email not in by_email:
            continue

        new_status = EMAIL_EVENT_MAP.get(event_type)
        if not new_status:
            continue

        try:
            if ts_raw:
                if isinstance(ts_raw, (int, float)):
                    event_dt = datetime.utcfromtimestamp(int(ts_raw)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    event_dt = str(ts_raw)[:19]
            else:
                event_dt = None
        except Exception:
            event_dt = None

        row    = by_email[email]
        token  = row["token"]
        fields = {}

        # email_status : prendre le plus informatif
        if _higher(row.get("email_status"), new_status):
            fields["email_status"] = new_status
            row["email_status"] = new_status  # màj index local

        # timestamps spécifiques
        if new_status == "opened" and not row.get("email_opened_at") and event_dt:
            fields["email_opened_at"] = event_dt
            row["email_opened_at"] = event_dt
        if new_status == "clicked" and not row.get("email_clicked_at") and event_dt:
            fields["email_clicked_at"] = event_dt
            row["email_clicked_at"] = event_dt
            if not row.get("email_opened_at") and event_dt:
                fields["email_opened_at"] = event_dt
                row["email_opened_at"] = event_dt
        if new_status == "bounced" and not row.get("email_bounced_at") and event_dt:
            fields["email_bounced_at"] = event_dt
            row["email_bounced_at"] = event_dt

        if fields and not DRY_RUN:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            c.execute(
                f"UPDATE v3_prospects SET {set_clause} WHERE token=?",
                list(fields.values()) + [token],
            )
            updates_email += 1
        elif fields:
            updates_email += 1

    if not DRY_RUN:
        db.commit()
    print(f"\n[EMAIL] {updates_email} prospects mis à jour{'  (DRY RUN)' if DRY_RUN else ''}")

    # ── SMS logs ──────────────────────────────────────────────────────────────
    sms_logs = _get_sms_logs(api_key)
    print(f"\n[SMS] {len(sms_logs)} logs Brevo récupérés")

    # Résumé final DB
    c.execute("SELECT email_status, COUNT(*) FROM v3_prospects WHERE email_sent_at IS NOT NULL GROUP BY email_status")
    print("\n[RÉSULTAT] Distribution email_status après backfill:")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")

    c.execute("SELECT COUNT(*) FROM v3_prospects WHERE sent_method='sms'")
    print(f"[RÉSULTAT] SMS envoyés (sent_method='sms'): {c.fetchone()[0]}")

    db.close()
    print("\n✅ Backfill terminé.")

if __name__ == "__main__":
    main()
