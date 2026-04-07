"""
ia_reports — Moteur de génération d'audits et rapports mensuels IA.

Point d'entrée principal : service.py
  from src.ia_reports.service import (
      create_initial_audit_for_prospect,
      create_monthly_report_for_prospect,
      create_full_deliverable_bundle,
  )
"""
from .service import (
    create_initial_audit_for_prospect,
    create_monthly_report_for_prospect,
    create_full_deliverable_bundle,
)

__all__ = [
    "create_initial_audit_for_prospect",
    "create_monthly_report_for_prospect",
    "create_full_deliverable_bundle",
]
