"""
seed_loader.py — Load a project seed JSON into the MARKETING_MODULE database.

Usage:
    python -m marketing_module.configs.seed_loader configs/presence_ia_seed.json
    python -m marketing_module.configs.seed_loader configs/sublym_seed.json [--reset]
"""
import json
import os
import sys
import uuid
from pathlib import Path


def load_seed(seed_path: str, reset: bool = False):
    seed = json.loads(Path(seed_path).read_text())
    project_id = seed["project_id"]

    from ..database import (
        SessionLocal, init_db,
        db_create_domain, db_create_mailbox, db_create_warmup,
        db_create_rotation, db_create_rule, db_create_campaign,
        db_create_sequence, db_create_sequence_step,
    )
    from ..models import (
        DnsStatus, SendingDomainDB, SendingMailboxDB, WarmupStrategyDB,
        RotationStrategyDB, ComplianceRuleDB, CampaignDB, WarmupStatus,
    )

    init_db()
    db = SessionLocal()

    try:
        if reset:
            # Delete existing records for this project
            for model in [SendingMailboxDB, SendingDomainDB, WarmupStrategyDB,
                          RotationStrategyDB, ComplianceRuleDB, CampaignDB]:
                db.query(model).filter(model.project_id == project_id).delete()
            db.commit()
            print(f"[seed_loader] Reset project '{project_id}'")

        # ── Domains ────────────────────────────────────────────────────────
        domain_map = {}  # domain_str → domain_id
        for d in seed.get("domains", []):
            obj = db_create_domain(db, {
                "project_id": project_id,
                "domain": d["domain"],
                "role": d.get("role", "sending"),
                "dns_status": d.get("dns_status", DnsStatus.pending),
            })
            domain_map[d["domain"]] = obj.id
            print(f"  [domain] {d['domain']} → {obj.id}")

        # ── Warmup strategy ────────────────────────────────────────────────
        warmup_id = None
        if "warmup_strategy" in seed:
            ws = seed["warmup_strategy"]
            obj = db_create_warmup(db, {
                "project_id": project_id,
                "name": ws["name"],
                "max_daily_volume": ws.get("max_daily_volume", 200),
                "total_days": ws.get("total_days", 21),
                "auto_pause_on_issue": ws.get("auto_pause_on_issue", True),
                "health_rules": ws.get("health_rules", {}),
                "ramp_schedule": ws.get("ramp_schedule", []),
            })
            warmup_id = obj.id
            print(f"  [warmup] {ws['name']} → {warmup_id}")

        # ── Mailboxes ──────────────────────────────────────────────────────
        for mb in seed.get("mailboxes", []):
            domain_str = mb.get("domain", "")
            did = domain_map.get(domain_str)
            obj = db_create_mailbox(db, {
                "project_id": project_id,
                "domain_id": did,
                "email": mb["email"],
                "display_name": mb.get("display_name", ""),
                "daily_limit": mb.get("daily_limit", 50),
                "hourly_limit": mb.get("hourly_limit", 10),
                "warmup_status": WarmupStatus.in_progress if warmup_id else WarmupStatus.not_started,
                "meta": {"warmup_strategy_id": warmup_id} if warmup_id else {},
            })
            print(f"  [mailbox] {mb['email']} → {obj.id}")

        # ── Rotation strategy ──────────────────────────────────────────────
        rotation_id = None
        if "rotation_strategy" in seed:
            rs = seed["rotation_strategy"]
            obj = db_create_rotation(db, {
                "project_id": project_id,
                "name": rs["name"],
                "algorithm": rs.get("algorithm", "round_robin"),
                "per_mailbox_daily_cap": rs.get("per_mailbox_daily_cap", 50),
                "domain_rotation": rs.get("domain_rotation", False),
            })
            rotation_id = obj.id
            print(f"  [rotation] {rs['name']} → {rotation_id}")

        # ── Compliance rules ───────────────────────────────────────────────
        for rule in seed.get("compliance_rules", []):
            obj = db_create_rule(db, {
                "project_id": project_id,
                "name": rule["name"],
                "rule_type": rule["rule_type"],
                "scope": rule.get("scope", "mailbox"),
                "threshold": rule["threshold"],
                "window_hours": rule.get("window_hours", 24),
                "action_on_trigger": rule["action_on_trigger"],
            })
            print(f"  [rule] {rule['name']} → {obj.id}")

        # ── Campaign ───────────────────────────────────────────────────────
        campaign_id = None
        if "campaign" in seed:
            c = seed["campaign"]
            obj = db_create_campaign(db, {
                "project_id": project_id,
                "name": c["name"],
                "channels": c.get("channels", ["email"]),
                "status": "draft",
                "rotation_strategy_id": rotation_id,
                "stop_on_reply": c.get("stop_on_reply", True),
                "stop_on_meeting": c.get("stop_on_meeting", True),
            })
            campaign_id = obj.id
            print(f"  [campaign] {c['name']} → {campaign_id}")

        # ── Sequences ──────────────────────────────────────────────────────
        for seq in seed.get("sequences", []):
            sobj = db_create_sequence(db, {
                "project_id": project_id,
                "campaign_id": campaign_id,
                "name": seq["name"],
                "is_active": True,
            })
            print(f"  [sequence] {seq['name']} → {sobj.id}")
            for step in seq.get("steps", []):
                stobj = db_create_sequence_step(db, {
                    "sequence_id": sobj.id,
                    "step_number": step["step_number"],
                    "channel": step.get("channel", "email"),
                    "delay_days": step.get("delay_days", 0),
                    "subject": step.get("subject", ""),
                    "body_html": step.get("body_html", ""),
                    "body_text": step.get("body_text", ""),
                    "sms_body": step.get("sms_body", ""),
                })
                print(f"    [step {step['step_number']}] → {stobj.id}")

        print(f"\n[seed_loader] ✓ Project '{project_id}' loaded successfully.")
        print(f"  campaign_id={campaign_id}")

    except Exception as e:
        db.rollback()
        print(f"[seed_loader] ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m marketing_module.configs.seed_loader <seed.json> [--reset]")
        sys.exit(1)
    path = sys.argv[1]
    do_reset = "--reset" in sys.argv
    load_seed(path, reset=do_reset)
