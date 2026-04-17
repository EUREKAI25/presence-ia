"""
Synchronisation événements Brevo → v3_prospects.
Appelé par : scheduler quotidien, endpoint admin, script CLI.

Usage CLI :
    python -m src.api.services.brevo_sync [--days N]
"""
import os
import logging
import sqlite3
import pathlib
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

API_BASE = "https://api.brevo.com/v3"

EMAIL_EVENT_MAP = {
    "delivered":    "delivered",
    "opened":       "opened",
    "open":         "opened",
    "clicks":       "clicked",
    "click":        "clicked",
    "softBounces":  "bounced",
    "hardBounces":  "bounced",
    "softBounce":   "bounced",
    "hardBounce":   "bounced",
    "spam":         "bounced",
    "unsubscribed": "bounced",
    "unsubscribe":  "bounced",
}

STATUS_PRIORITY = {"sent": 0, "delivered": 1, "opened": 2, "clicked": 3, "bounced": 1}


def _higher(current: str | None, new: str) -> bool:
    if not current:
        return True
    return STATUS_PRIORITY.get(new, 0) > STATUS_PRIORITY.get(current, 0)


def _get_api_key() -> str:
    key = os.getenv("BREVO_API_KEY", "")
    if key:
        return key
    # fallback : lire .env local
    env_path = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
    try:
        for line in env_path.read_text().splitlines():
            if line.startswith("BREVO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


def _db_path() -> str:
    return str(pathlib.Path(__file__).parent.parent.parent.parent / "data" / "presence_ia.db")


def _ensure_sms_columns(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes SMS si elles n'existent pas (migration idempotente)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(v3_prospects)")
    existing = {row[1] for row in cur.fetchall()}
    for col, typ in [("sms_status", "TEXT"), ("sms_delivered_at", "DATETIME")]:
        if col not in existing:
            cur.execute(f"ALTER TABLE v3_prospects ADD COLUMN {col} {typ}")
            log.info("[BREVO SYNC] Colonne ajoutée : v3_prospects.%s", col)
    conn.commit()


def _to_dt_str(ts_raw) -> str | None:
    try:
        if not ts_raw:
            return None
        if isinstance(ts_raw, (int, float)):
            return datetime.utcfromtimestamp(int(ts_raw)).strftime("%Y-%m-%d %H:%M:%S")
        return str(ts_raw)[:19]
    except Exception:
        return None


def _fetch_email_events(api_key: str, days: int = 30) -> list:
    import requests
    events, offset = [], 0
    log.info("[BREVO SYNC] Récupération events email (derniers %d jours)…", days)
    while True:
        r = requests.get(
            f"{API_BASE}/smtp/statistics/events",
            headers={"api-key": api_key},
            params={"limit": 500, "offset": offset, "days": days},
            timeout=30,
        )
        if not r.ok:
            log.error("[BREVO SYNC] Email API %s : %s", r.status_code, r.text[:200])
            break
        batch = r.json().get("events", [])
        events.extend(batch)
        log.debug("[BREVO SYNC] Email offset=%d → %d events", offset, len(batch))
        if len(batch) < 500:
            break
        offset += 500
    return events


def _fetch_sms_reports(api_key: str, date_from: str, date_to: str) -> list:
    """Récupère les événements SMS par destinataire via /transactionalSMS/statistics/events."""
    import requests
    logs, offset = [], 0
    log.info("[BREVO SYNC] Récupération logs SMS (%s → %s)…", date_from, date_to)
    while True:
        r = requests.get(
            f"{API_BASE}/transactionalSMS/statistics/events",
            headers={"api-key": api_key},
            params={"startDate": date_from, "endDate": date_to,
                    "limit": 100, "offset": offset},
            timeout=30,
        )
        if not r.ok:
            log.warning("[BREVO SYNC] SMS API %s : %s", r.status_code, r.text[:300])
            break
        data  = r.json()
        batch = data.get("events", data) if isinstance(data, dict) else data
        if not batch:
            break
        logs.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    return logs


def sync_brevo_events(days: int = 30) -> dict:
    """
    Synchronise les événements Brevo (email + SMS) vers v3_prospects.
    Idempotent — ne remplace pas les données existantes.

    Returns:
        dict avec les compteurs : email_fetched, email_updated, sms_fetched, sms_updated, status_dist
    """
    api_key = _get_api_key()
    if not api_key:
        log.error("[BREVO SYNC] BREVO_API_KEY manquante — sync annulée")
        return {"error": "BREVO_API_KEY manquante"}

    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    _ensure_sms_columns(conn)

    # ── Index email → prospect (dernier envoi par email) ──────────────────────
    cur.execute("""
        SELECT token, email, email_status,
               email_opened_at, email_bounced_at, email_clicked_at
        FROM v3_prospects
        WHERE email IS NOT NULL AND email_sent_at IS NOT NULL
        ORDER BY email_sent_at DESC
    """)
    by_email: dict[str, dict] = {}
    for row in cur.fetchall():
        key = (row["email"] or "").lower().strip()
        if key and key not in by_email:
            by_email[key] = dict(row)
    log.info("[BREVO SYNC] %d prospects email indexés", len(by_email))

    # ── Index phone → prospect (SMS) ──────────────────────────────────────────
    cur.execute("""
        SELECT token, phone, sms_status, sms_delivered_at
        FROM v3_prospects
        WHERE phone IS NOT NULL AND sent_method = 'sms'
        ORDER BY sent_at DESC
    """)
    by_phone: dict[str, dict] = {}
    for row in cur.fetchall():
        raw = (row["phone"] or "").strip().replace(" ", "").replace("-", "")
        key = raw[-9:] if len(raw) >= 9 else raw
        if key and key not in by_phone:
            by_phone[key] = dict(row)
    log.info("[BREVO SYNC] %d prospects SMS indexés", len(by_phone))

    # ── Email events ──────────────────────────────────────────────────────────
    email_events  = _fetch_email_events(api_key, days=days)
    email_matched = 0
    email_updated = 0

    for ev in email_events:
        email      = (ev.get("email") or "").lower().strip()
        event_type = ev.get("event", "")
        if not email or email not in by_email:
            continue
        new_status = EMAIL_EVENT_MAP.get(event_type)
        if not new_status:
            continue

        email_matched += 1
        event_dt = _to_dt_str(ev.get("date") or ev.get("ts") or ev.get("timestamp"))
        row      = by_email[email]
        fields: dict = {}

        if _higher(row.get("email_status"), new_status):
            fields["email_status"] = new_status
            row["email_status"] = new_status

        if new_status == "opened" and not row.get("email_opened_at") and event_dt:
            fields["email_opened_at"] = event_dt
            row["email_opened_at"] = event_dt

        if new_status == "clicked":
            if not row.get("email_clicked_at") and event_dt:
                fields["email_clicked_at"] = event_dt
                row["email_clicked_at"] = event_dt
            if not row.get("email_opened_at") and event_dt:
                fields["email_opened_at"] = event_dt
                row["email_opened_at"] = event_dt

        if new_status == "bounced" and not row.get("email_bounced_at") and event_dt:
            fields["email_bounced_at"] = event_dt
            row["email_bounced_at"] = event_dt

        if fields:
            set_q = ", ".join(f"{k}=?" for k in fields)
            cur.execute(f"UPDATE v3_prospects SET {set_q} WHERE token=?",
                        [*fields.values(), row["token"]])
            email_updated += 1

    conn.commit()
    log.info("[BREVO SYNC] Email : %d events, %d matchés, %d mis à jour",
             len(email_events), email_matched, email_updated)

    # ── SMS reports ───────────────────────────────────────────────────────────
    date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to   = datetime.utcnow().strftime("%Y-%m-%d")
    # Brevo SMS API : startDate=today/endDate=today retourne les events intraday.
    # Une plage multi-jours exclut le jour courant → on fait 2 appels séparés :
    # 1) aujourd'hui (intraday)  2) jours précédents
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    sms_date_from = (datetime.utcnow() - timedelta(days=min(days, 3))).strftime("%Y-%m-%d")

    sms_logs = _fetch_sms_reports(api_key, today, today)
    if sms_date_from < today:
        sms_logs += _fetch_sms_reports(api_key, sms_date_from, yesterday)
    sms_matched = 0
    sms_updated = 0

    for entry in sms_logs:
        raw_phone = (entry.get("phone") or entry.get("phoneNumber")
                     or entry.get("number") or "").strip().replace(" ", "").replace("-", "")
        if not raw_phone:
            continue
        key = raw_phone[-9:] if len(raw_phone) >= 9 else raw_phone
        if key not in by_phone:
            continue
        sms_matched += 1

        # L'API /statistics/events retourne le champ "event", pas "status"
        brevo_status = (entry.get("event") or entry.get("status") or entry.get("state") or "").lower()
        new_status   = ({"delivered": "delivered", "success": "delivered",
                          "failed": "failed", "undelivered": "failed",
                          "hardbounce": "failed", "softbounce": "failed",
                          "softbounces": "failed", "bounce": "failed", "bounced": "failed",
                          "rejected": "failed", "blocked": "failed",
                          "sent": "sent", "accepted": "sent"}.get(brevo_status))
        event_dt = _to_dt_str(entry.get("date") or entry.get("sentAt") or entry.get("timestamp"))

        _SMS_PRIORITY = {"sent": 1, "failed": 1, "delivered": 2}

        row    = by_phone[key]
        fields = {}
        if new_status:
            cur_prio = _SMS_PRIORITY.get(row.get("sms_status") or "", 0)
            new_prio = _SMS_PRIORITY.get(new_status, 0)
            if new_prio >= cur_prio:
                fields["sms_status"] = new_status
                row["sms_status"] = new_status
        if new_status == "delivered" and not row.get("sms_delivered_at") and event_dt:
            fields["sms_delivered_at"] = event_dt
            row["sms_delivered_at"] = event_dt

        if fields:
            set_q = ", ".join(f"{k}=?" for k in fields)
            cur.execute(f"UPDATE v3_prospects SET {set_q} WHERE token=?",
                        [*fields.values(), row["token"]])
            sms_updated += 1

    conn.commit()
    log.info("[BREVO SYNC] SMS : %d logs, %d matchés, %d mis à jour",
             len(sms_logs), sms_matched, sms_updated)

    # ── Distribution statuts post-sync ────────────────────────────────────────
    cur.execute("""
        SELECT email_status, COUNT(*) as n FROM v3_prospects
        WHERE email_sent_at IS NOT NULL GROUP BY email_status
    """)
    status_dist = {row["email_status"]: row["n"] for row in cur.fetchall()}

    cur.execute("SELECT COUNT(*) FROM v3_prospects WHERE sms_delivered_at IS NOT NULL")
    sms_delivered_total = cur.fetchone()[0]

    conn.close()

    result = {
        "email_fetched":       len(email_events),
        "email_matched":       email_matched,
        "email_updated":       email_updated,
        "sms_fetched":         len(sms_logs),
        "sms_matched":         sms_matched,
        "sms_updated":         sms_updated,
        "sms_delivered_total": sms_delivered_total,
        "status_dist":         status_dist,
        "synced_at":           datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
    log.info("[BREVO SYNC] Terminé : %s", result)
    return result


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    days_arg = 30
    for arg in sys.argv[1:]:
        if arg.startswith("--days="):
            days_arg = int(arg.split("=")[1])
        elif arg == "--days" and sys.argv.index(arg) + 1 < len(sys.argv):
            days_arg = int(sys.argv[sys.argv.index(arg) + 1])

    res = sync_brevo_events(days=days_arg)
    print("\n=== RÉSULTAT SYNC BREVO ===")
    for k, v in res.items():
        print(f"  {k}: {v}")
