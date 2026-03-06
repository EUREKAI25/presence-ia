"""
MARKETING_MODULE — Core orchestrator
Dispatches to email/SMS/social channels. Rotation, warmup, compliance.
"""
import logging
import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .database import (
    db_campaign_stats, db_create_delivery, db_get_campaign,
    db_get_mailbox, db_get_rotation, db_get_warmup, db_increment_sent,
    db_list_mailboxes, db_list_rules, db_mailbox_stats, db_prospect_already_contacted,
    db_prospect_replied, db_update_campaign, db_update_delivery, db_update_mailbox,
)
from .models import (
    BounceType, CampaignStatus, Channel, ComplianceAction, DeliveryStatus,
    EurkaiOutput, ReputationStatus, RotationAlgorithm, SendingMailboxDB,
    WarmupStatus,
)

log = logging.getLogger("mkt.engine")


# ── Rotation ───────────────────────────────────────────────────────────────────

def choose_next_mailbox(db: Session, campaign_id: str,
                        domain_id: Optional[str] = None) -> Optional[SendingMailboxDB]:
    campaign = db_get_campaign(db, campaign_id)
    if not campaign:
        return None

    rotation = db_get_rotation(db, campaign.rotation_strategy_id) if campaign.rotation_strategy_id else None
    algorithm = RotationAlgorithm(rotation.algorithm) if rotation else RotationAlgorithm.round_robin
    per_mailbox_cap = rotation.per_mailbox_daily_cap if rotation else 50

    mailboxes = db_list_mailboxes(db, project_id=campaign.project_id,
                                  domain_id=domain_id, active_only=True)
    candidates = []
    for mb in mailboxes:
        if (mb.sent_today or 0) >= mb.daily_limit:
            continue
        if (mb.sent_this_hour or 0) >= mb.hourly_limit:
            continue
        if (mb.sent_today or 0) >= per_mailbox_cap:
            continue
        if mb.reputation_status == ReputationStatus.blacklisted:
            continue
        if mb.warmup_status == WarmupStatus.in_progress:
            warmup = db_get_warmup(db, (mb.meta or {}).get("warmup_strategy_id", ""))
            if warmup:
                cap = _warmup_day_cap(warmup, mb.warmup_day or 0)
                if (mb.sent_today or 0) >= cap:
                    continue
        candidates.append(mb)

    if not candidates:
        return None

    if algorithm == RotationAlgorithm.round_robin:
        candidates.sort(key=lambda m: m.last_send_at or datetime.min)
        return candidates[0]
    elif algorithm == RotationAlgorithm.least_used:
        candidates.sort(key=lambda m: m.sent_today or 0)
        return candidates[0]
    elif algorithm == RotationAlgorithm.random:
        return random.choice(candidates)
    elif algorithm == RotationAlgorithm.weighted:
        total = sum(mb.daily_limit - (mb.sent_today or 0) for mb in candidates)
        if not total:
            return candidates[0]
        r = random.uniform(0, total)
        acc = 0
        for mb in candidates:
            acc += mb.daily_limit - (mb.sent_today or 0)
            if r <= acc:
                return mb
    elif algorithm == RotationAlgorithm.health_priority:
        def _score(mb):
            s = 0
            if mb.reputation_status == ReputationStatus.healthy: s += 3
            if mb.warmup_status == WarmupStatus.completed: s += 2
            return s
        candidates.sort(key=_score, reverse=True)
        return candidates[0]

    return candidates[0]


def _warmup_day_cap(warmup, day: int) -> int:
    cap = warmup.max_daily_volume
    for entry in (warmup.ramp_schedule or []):
        if isinstance(entry, dict) and entry.get("day", 0) <= day:
            cap = entry.get("volume", cap)
    return cap


# ── Warmup ─────────────────────────────────────────────────────────────────────

def apply_warmup_step(db: Session, mailbox_id: str) -> EurkaiOutput:
    mb = db_get_mailbox(db, mailbox_id)
    if not mb or mb.warmup_status != WarmupStatus.in_progress:
        return EurkaiOutput(success=True, result=None, message="Not in warmup")

    warmup = db_get_warmup(db, (mb.meta or {}).get("warmup_strategy_id", ""))
    if not warmup:
        return EurkaiOutput(success=True, result=None, message="No warmup strategy")

    new_day = (mb.warmup_day or 0) + 1
    schedule_days = [e.get("day", 0) for e in (warmup.ramp_schedule or []) if isinstance(e, dict)]
    updates = {"warmup_day": new_day}

    if new_day >= (max(schedule_days) if schedule_days else 30):
        updates["warmup_status"] = WarmupStatus.completed

    if warmup.auto_pause_on_issue:
        stats = db_mailbox_stats(db, mailbox_id)
        if stats["bounce_rate"] > (warmup.health_rules or {}).get("max_bounce_rate", 0.05):
            updates["warmup_status"] = WarmupStatus.paused
            updates["reputation_status"] = ReputationStatus.at_risk

    db_update_mailbox(db, mailbox_id, updates)
    return EurkaiOutput(success=True, result=updates, message="Warmup step applied")


# ── Compliance ─────────────────────────────────────────────────────────────────

def check_compliance(db: Session, project_id: str, mailbox_id: str, campaign_id: str) -> list[dict]:
    triggered = []
    for rule in db_list_rules(db, project_id):
        if rule.scope == "mailbox":
            stats = db_mailbox_stats(db, mailbox_id, window_hours=rule.window_hours)
        elif rule.scope == "campaign":
            stats = db_campaign_stats(db, campaign_id)
        else:
            continue
        value = stats.get(rule.rule_type, 0)
        if value > rule.threshold:
            triggered.append({
                "rule_id": rule.id, "rule_name": rule.name,
                "rule_type": rule.rule_type, "value": value,
                "threshold": rule.threshold, "action": rule.action_on_trigger,
            })
    return triggered


def enforce_compliance(db: Session, triggered: list[dict], mailbox_id: str, campaign_id: str):
    for t in triggered:
        if t["action"] == ComplianceAction.pause_mailbox:
            db_update_mailbox(db, mailbox_id, {"is_active": False})
        elif t["action"] == ComplianceAction.stop_campaign:
            db_update_campaign(db, campaign_id, {"status": CampaignStatus.stopped})


# ── Send batch ─────────────────────────────────────────────────────────────────

def execute_send_batch(
    db: Session,
    project_id: str,
    campaign_id: str,
    prospect_ids: list[str],
    sequence_step_id: str,
    channel_provider,           # email: AbstractEmailProvider | sms: TwilioProvider | etc.
    channel: str = Channel.email,
    scheduled_at: Optional[datetime] = None,
    dry_run: bool = False,
) -> EurkaiOutput:

    campaign = db_get_campaign(db, campaign_id)
    if not campaign:
        return EurkaiOutput(success=False, result=None, message=f"Campaign {campaign_id} not found")
    if campaign.status != CampaignStatus.active:
        return EurkaiOutput(success=False, result=None,
                            message=f"Campaign status is {campaign.status}, not active")

    results = {"sent": 0, "skipped": 0, "failed": 0, "deliveries": []}

    for prospect_id in prospect_ids:
        if db_prospect_already_contacted(db, campaign_id, prospect_id, sequence_step_id):
            results["skipped"] += 1
            continue
        if db_prospect_replied(db, campaign_id, prospect_id):
            results["skipped"] += 1
            continue

        # For email: pick mailbox via rotation
        mailbox = None
        if channel == Channel.email:
            mailbox = choose_next_mailbox(db, campaign_id)
            if not mailbox:
                results["failed"] += 1
                continue
            triggered = check_compliance(db, project_id, mailbox.id, campaign_id)
            if triggered:
                enforce_compliance(db, triggered, mailbox.id, campaign_id)
                if any(t["action"] != ComplianceAction.alert for t in triggered):
                    results["failed"] += len(prospect_ids) - results["sent"] - results["skipped"] - results["failed"]
                    break

        delivery = db_create_delivery(db, {
            "project_id": project_id,
            "campaign_id": campaign_id,
            "prospect_id": prospect_id,
            "channel": channel,
            "mailbox_id": mailbox.id if mailbox else None,
            "sequence_step_id": sequence_step_id,
            "scheduled_at": scheduled_at or datetime.utcnow(),
            "delivery_status": DeliveryStatus.pending,
        })

        if dry_run:
            results["sent"] += 1
            results["deliveries"].append({"delivery_id": delivery.id, "dry_run": True})
            continue

        # Delegate to channel provider
        try:
            send_result = channel_provider.send(
                mailbox=mailbox,
                delivery_id=delivery.id,
                prospect_id=prospect_id,
                sequence_step_id=sequence_step_id,
            ) if channel == Channel.email else channel_provider.send(
                to_number=prospect_id,
                body="",
                delivery_id=delivery.id,
            )

            if send_result.get("success"):
                db_update_delivery(db, delivery.id, {
                    "delivery_status": DeliveryStatus.sent,
                    "sent_at": datetime.utcnow(),
                    "provider_message_id": send_result.get("message_id"),
                })
                if mailbox:
                    db_increment_sent(db, mailbox.id)
                    apply_warmup_step(db, mailbox.id)
                results["sent"] += 1
                results["deliveries"].append({"delivery_id": delivery.id})
            else:
                db_update_delivery(db, delivery.id, {
                    "delivery_status": DeliveryStatus.failed,
                    "error_message": send_result.get("error", "Provider error"),
                })
                results["failed"] += 1
        except Exception as exc:
            log.exception("Send error for %s: %s", prospect_id, exc)
            db_update_delivery(db, delivery.id, {
                "delivery_status": DeliveryStatus.failed,
                "error_message": str(exc),
            })
            results["failed"] += 1

    return EurkaiOutput(
        success=True, result=results,
        message=f"Batch: {results['sent']} sent, {results['skipped']} skipped, {results['failed']} failed",
    )


# ── Event handlers ─────────────────────────────────────────────────────────────

def handle_bounce(db: Session, delivery_id: str, bounce_type: str, error: str = "") -> EurkaiOutput:
    from .database import db_get_delivery as _get
    delivery = _get(db, delivery_id)
    if not delivery:
        return EurkaiOutput(success=False, result=None, message="Delivery not found")
    db_update_delivery(db, delivery_id, {
        "bounce_type": bounce_type, "delivery_status": DeliveryStatus.bounced,
        "error_message": error,
    })
    if bounce_type == BounceType.hard and delivery.mailbox_id:
        stats = db_mailbox_stats(db, delivery.mailbox_id)
        if stats["bounce_rate"] > 0.10:
            db_update_mailbox(db, delivery.mailbox_id, {"reputation_status": ReputationStatus.at_risk})
    return EurkaiOutput(success=True, result={"delivery_id": delivery_id}, message="Bounce recorded")


def handle_reply(db: Session, delivery_id: str, reply_status: str) -> EurkaiOutput:
    from .database import db_get_delivery as _get
    if not _get(db, delivery_id):
        return EurkaiOutput(success=False, result=None, message="Delivery not found")
    db_update_delivery(db, delivery_id, {"reply_status": reply_status})
    return EurkaiOutput(success=True, result=None, message="Reply recorded")


def handle_open(db: Session, delivery_id: str) -> EurkaiOutput:
    db_update_delivery(db, delivery_id, {"opened_at": datetime.utcnow()})
    return EurkaiOutput(success=True, result=None, message="Open recorded")


def handle_click(db: Session, delivery_id: str) -> EurkaiOutput:
    db_update_delivery(db, delivery_id, {"clicked_at": datetime.utcnow()})
    return EurkaiOutput(success=True, result=None, message="Click recorded")
