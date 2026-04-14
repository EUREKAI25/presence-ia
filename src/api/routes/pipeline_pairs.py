"""
pipeline_pairs.py — Avancement pipeline par profession × ville × segments SIRENE.

GET /admin/pipeline-pairs
Accordéons imbriqués :
  Niveau 1 : Profession  (% envoyés global + stock dispo)
  Niveau 2 : Ville       (% envoyés + stock)
  Niveau 3 : Segments SIRENE (numérotés 1..N, badges pending/running/done/error)
"""
import os
import math
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ._nav import admin_nav, admin_token

router = APIRouter()

# ── Mapping département → label court ────────────────────────────────────────
_DEPT = {
    "01":"Ain","02":"Aisne","03":"Allier","04":"Alpes-H.-Prov.","05":"Hautes-Alpes",
    "06":"Alpes-Mar. (Nice)","07":"Ardèche","08":"Ardennes","09":"Ariège","10":"Aube",
    "11":"Aude","12":"Aveyron","13":"Bouches-du-Rhône (Marseille)","14":"Calvados",
    "15":"Cantal","16":"Charente","17":"Charente-Maritime","18":"Cher","19":"Corrèze",
    "2A":"Corse-du-Sud","2B":"Haute-Corse","21":"Côte-d'Or","22":"Côtes-d'Armor",
    "23":"Creuse","24":"Dordogne","25":"Doubs","26":"Drôme","27":"Eure",
    "28":"Eure-et-Loir","29":"Finistère (Brest)","30":"Gard",
    "31":"Haute-Garonne (Toulouse)","32":"Gers","33":"Gironde (Bordeaux)",
    "34":"Hérault (Montpellier)","35":"Ille-et-Vilaine (Rennes)","36":"Indre",
    "37":"Indre-et-Loire","38":"Isère (Grenoble)","39":"Jura","40":"Landes",
    "41":"Loir-et-Cher","42":"Loire","43":"Haute-Loire",
    "44":"Loire-Atlantique (Nantes)","45":"Loiret","46":"Lot","47":"Lot-et-Garonne",
    "48":"Lozère","49":"Maine-et-Loire","50":"Manche","51":"Marne","52":"Haute-Marne",
    "53":"Mayenne","54":"Meurthe-et-Moselle","55":"Meuse","56":"Morbihan",
    "57":"Moselle","58":"Nièvre","59":"Nord (Lille)","60":"Oise","61":"Orne",
    "62":"Pas-de-Calais","63":"Puy-de-Dôme","64":"Pyr.-Atlantiques",
    "65":"Hautes-Pyr.","66":"Pyr.-Orientales","67":"Bas-Rhin (Strasbourg)",
    "68":"Haut-Rhin","69":"Rhône (Lyon)","70":"Haute-Saône","71":"Saône-et-Loire",
    "72":"Sarthe","73":"Savoie","74":"Haute-Savoie","75":"Paris",
    "76":"Seine-Maritime (Rouen)","77":"Seine-et-Marne","78":"Yvelines",
    "79":"Deux-Sèvres","80":"Somme","81":"Tarn","82":"Tarn-et-Garonne",
    "83":"Var","84":"Vaucluse","85":"Vendée","86":"Vienne","87":"Haute-Vienne",
    "88":"Vosges","89":"Yonne","90":"Terr. de Belfort","91":"Essonne",
    "92":"Hauts-de-Seine","93":"Seine-Saint-Denis","94":"Val-de-Marne",
    "95":"Val-d'Oise",
}


def _check_token(request: Request):
    token = request.query_params.get("token", "")
    if token != admin_token():
        return HTMLResponse("403 Forbidden", status_code=403)
    return None


def _pct(a, b):
    return round(a / b * 100) if b else 0


def _progress_bar(pct, color="#6366f1", height=6):
    return (
        f'<div style="background:#e5e7eb;border-radius:3px;height:{height}px;'
        f'width:100%;margin-top:4px">'
        f'<div style="background:{color};width:{pct}%;height:100%;border-radius:3px;'
        f'transition:width .3s"></div></div>'
    )


def _seg_badge(num, status):
    cfg = {
        "done":    ("#d1fae5", "#065f46", "✓"),   # extrait SIRENE
        "running": ("#fef3c7", "#92400e", "⟳"),   # extraction en cours
        "pending": ("#f3f4f6", "#9ca3af", "○"),   # à extraire
        "error":   ("#fee2e2", "#991b1b", "✕"),
    }.get(status, ("#f3f4f6", "#9ca3af", "?"))
    status_label = {"done": "extrait", "running": "en cours", "pending": "à traiter", "error": "erreur"}.get(status, status)
    bg, fg, icon = cfg
    return (
        f'<span title="{status_label}" style="display:inline-flex;align-items:center;'
        f'justify-content:center;width:28px;height:28px;border-radius:4px;'
        f'background:{bg};color:{fg};font-size:11px;font-weight:700;'
        f'margin:2px;cursor:default">{num}{icon}</span>'
    )


@router.get("/admin/pipeline-pairs", response_class=HTMLResponse)
def pipeline_pairs(request: Request):
    if (r := _check_token(request)) is not None:
        return r
    token = admin_token()

    from ...database import SessionLocal
    from ...models import (
        ProfessionDB, ScoringConfigDB, SireneSegmentDB,
        SireneSuspectDB, V3ProspectDB,
    )
    from ...active_pair import get_active_pair
    from ...database import db_score_global
    from sqlalchemy import func, or_, case

    with SessionLocal() as db:

        # ── Paire active ─────────────────────────────────────────────────────
        active = get_active_pair()

        cfg = db.query(ScoringConfigDB).filter_by(id="default").first()

        # ── Fraîcheur IA de la paire active ──────────────────────────────────
        active_ia_tested_at = None
        if active:
            from sqlalchemy import func as _func
            _row = db.query(_func.max(V3ProspectDB.ia_tested_at)).filter(
                V3ProspectDB.city       == active["city"],
                V3ProspectDB.profession == active["profession"],
                V3ProspectDB.ia_tested_at.isnot(None),
            ).scalar()
            active_ia_tested_at = _row

        # ── Professions actives triées par score desc ─────────────────────────
        profs = (
            db.query(ProfessionDB)
            .filter(ProfessionDB.actif == True)
            .all()
        )
        scored_profs = sorted(
            profs,
            key=lambda p: db_score_global(p, cfg) if cfg else 0.0,
            reverse=True,
        )

        # ── Stats V3Prospects par (profession, city) ─────────────────────────
        v3_rows = db.query(
            V3ProspectDB.profession,
            V3ProspectDB.city,
            func.count().label("total"),
            func.sum(case((V3ProspectDB.sent_at.isnot(None), 1), else_=0)).label("sent"),
            func.sum(case((
                (V3ProspectDB.email.isnot(None)) &
                (V3ProspectDB.sent_at.is_(None)) &
                (V3ProspectDB.ia_results.isnot(None)) &
                (
                    (V3ProspectDB.email_status.is_(None)) |
                    (V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"]))
                ),
                1), else_=0)).label("dispo"),
        ).group_by(V3ProspectDB.profession, V3ProspectDB.city).all()

        # Index profession : accepte LABEL ou ID (slug) pour matcher V3ProspectDB.profession
        _prof_key_to_id: dict = {}
        for p in scored_profs:
            if p.label:
                _prof_key_to_id[p.label.strip().lower()] = p.id
            _prof_key_to_id[p.id.strip().lower()] = p.id

        # Index : prof_id → city → stats  (agrégation si label + slug existent)
        v3_by_prof: dict = defaultdict(lambda: defaultdict(lambda: {"total":0,"sent":0,"dispo":0}))
        for r in v3_rows:
            pid = _prof_key_to_id.get((r.profession or "").strip().lower())
            if not pid:
                continue   # profession inconnue — ignorée
            city_stats = v3_by_prof[pid][r.city]
            city_stats["total"] += r.total
            city_stats["sent"]  += r.sent
            city_stats["dispo"] += r.dispo

        # ── Segments SIRENE par (profession_id, departement) ─────────────────
        segs_rows = (
            db.query(SireneSegmentDB)
            .order_by(SireneSegmentDB.profession_id, SireneSegmentDB.score.desc())
            .all()
        )
        # Index : prof_id → dept → list of (num, segment)
        # Numérotation locale par (profession_id, departement) — repart de 1 par dept
        segs_by_prof: dict = defaultdict(lambda: defaultdict(list))
        dept_seg_counter: dict = defaultdict(int)  # clé : (prof_id, dept)
        for seg in segs_rows:
            key = (seg.profession_id, seg.departement)
            dept_seg_counter[key] += 1
            segs_by_prof[seg.profession_id][seg.departement].append(
                (dept_seg_counter[key], seg)
            )

        # ── Suspects SIRENE total par profession_id ───────────────────────────
        sus_rows = db.query(
            SireneSuspectDB.profession_id,
            func.count().label("total"),
            func.sum(case((SireneSuspectDB.enrichi_at.isnot(None), 1), else_=0)).label("enriched"),
            func.sum(case((SireneSuspectDB.contactable == True, 1), else_=0)).label("contactable"),
        ).group_by(SireneSuspectDB.profession_id).all()
        sus_by_prof = {r.profession_id: r for r in sus_rows}

    # ── Prochaine paire (2e dans le classement, hors paire active) ───────────
    next_pair = None
    ranked_pairs = []
    for p in scored_profs:
        cities_data = v3_by_prof.get(p.id, {})
        p_score = db_score_global(p, cfg) if cfg else 0.0
        for city, cdata in cities_data.items():
            n = cdata["dispo"]
            if n > 0:
                combined = p_score * 2 + math.log1p(n)
                ranked_pairs.append((city, p.label, n, p_score, combined))
    ranked_pairs.sort(key=lambda x: x[4], reverse=True)
    for city_r, prof_r, n_r, score_r, _ in ranked_pairs:
        is_current = (
            active and
            active.get("city", "").lower() == city_r.lower() and
            active.get("profession", "").lower() == prof_r.lower()
        )
        if not is_current:
            next_pair = {"city": city_r, "profession": prof_r, "n": n_r, "score": score_r}
            break

    # ── Bannière paire active ─────────────────────────────────────────────────
    def _ia_freshness(tested_at):
        """Retourne label + couleur selon fraîcheur du dernier test IA."""
        if not tested_at:
            return "Jamais testé", "#dc2626", "🔴"
        if isinstance(tested_at, str):
            try:
                tested_at = datetime.fromisoformat(tested_at)
            except Exception:
                return "Date invalide", "#9ca3af", "⚪"
        age_h = (datetime.utcnow() - tested_at).total_seconds() / 3600
        if age_h < 24:
            return f"Il y a {int(age_h)}h", "#10b981", "🟢"
        age_d = int(age_h / 24)
        if age_d <= 4:
            return f"Il y a {age_d}j", "#10b981", "🟢"
        if age_d <= 8:
            return f"Il y a {age_d}j", "#f59e0b", "🟡"
        return f"Il y a {age_d}j", "#dc2626", "🔴"

    if active:
        ia_label, ia_color, ia_dot = _ia_freshness(active_ia_tested_at)
        started = active.get("started_at", "")[:10] if active.get("started_at") else "—"
        banner = (
            f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
            f'padding:14px 18px;margin-bottom:16px;display:flex;align-items:center;'
            f'gap:16px;flex-wrap:wrap">'
            f'<div style="flex:1;min-width:200px">'
            f'<div style="font-size:12px;font-weight:700;color:#065f46;'
            f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">Paire active</div>'
            f'<div style="font-size:15px;font-weight:700;color:#111">'
            f'{active["profession"]} — {active["city"]}</div>'
            f'<div style="font-size:12px;color:#6b7280;margin-top:2px">'
            f'Score {active.get("score", 0):.1f} &nbsp;·&nbsp; démarrée le {started}'
            f'{"&nbsp;·&nbsp;<strong style=\"color:#7c3aed\">FORCÉE</strong>" if active.get("override") else ""}'
            f'</div>'
            f'</div>'
            f'<div style="text-align:center">'
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:2px">Résultats IA</div>'
            f'<div style="font-size:13px;font-weight:700;color:{ia_color}">'
            f'{ia_dot} {ia_label}</div>'
            f'</div>'
            + (
                f'<div style="border-left:1px solid #d1fae5;padding-left:16px;min-width:180px">'
                f'<div style="font-size:12px;font-weight:700;color:#374151;'
                f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">Prochaine paire</div>'
                f'<div style="font-size:13px;font-weight:600;color:#374151">'
                f'{next_pair["profession"]} — {next_pair["city"]}</div>'
                f'<div style="font-size:11px;color:#6b7280">'
                f'Score {next_pair["score"]:.1f} &nbsp;·&nbsp; {next_pair["n"]} dispo</div>'
                f'</div>'
                if next_pair else
                f'<div style="border-left:1px solid #d1fae5;padding-left:16px">'
                f'<div style="font-size:12px;color:#9ca3af">Aucune autre paire disponible</div>'
                f'</div>'
            )
            + f'</div>'
        )
    else:
        next_label = (
            f'{next_pair["profession"]} — {next_pair["city"]} '
            f'(score {next_pair["score"]:.1f} · {next_pair["n"]} dispo)'
            if next_pair else "Aucune paire disponible"
        )
        banner = (
            f'<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;'
            f'padding:14px 18px;margin-bottom:16px;display:flex;align-items:center;gap:12px">'
            f'<span style="font-size:20px">⏸</span>'
            f'<div>'
            f'<div style="font-size:13px;font-weight:700;color:#92400e">Aucune paire active</div>'
            f'<div style="font-size:12px;color:#6b7280">'
            f'Prochaine : {next_label}</div>'
            f'</div>'
            f'</div>'
        )

    # ── Rendu HTML ────────────────────────────────────────────────────────────

    # Accordéons professions
    prof_blocks = []
    for prof in scored_profs:
        cities_data = v3_by_prof.get(prof.id, {})
        if not cities_data and prof.id not in segs_by_prof:
            continue  # skip professions sans données

        total_v3   = sum(c["total"] for c in cities_data.values())
        total_sent = sum(c["sent"]  for c in cities_data.values())
        total_dispo = sum(c["dispo"] for c in cities_data.values())
        pct_sent   = _pct(total_sent, total_v3)

        sus        = sus_by_prof.get(prof.id)
        sus_total  = sus.total    if sus else 0
        sus_enrich = sus.enriched if sus else 0

        prof_score = db_score_global(prof, cfg) if cfg else 0.0

        is_active_prof = (
            active and
            active.get("profession", "").lower() == prof.label.lower()
        )
        open_attr = " open" if is_active_prof else ""

        # Couleur barre selon % envoyé
        bar_color = "#6366f1" if pct_sent < 50 else "#10b981" if pct_sent < 80 else "#f59e0b"

        # Header profession
        sum_html = (
            f'<summary style="cursor:pointer;list-style:none;padding:14px 16px;'
            f'display:flex;align-items:center;gap:10px;border-radius:6px;'
            f'background:{"#f0fdf4" if is_active_prof else "#f9fafb"};'
            f'border:1px solid {"#86efac" if is_active_prof else "#e5e7eb"}">'
            f'<span style="font-size:16px">{"📍" if is_active_prof else "📂"}</span>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">'
            f'<strong style="font-size:14px;color:#111">{prof.label_pluriel}</strong>'
            f'<span style="font-size:11px;color:#6b7280">score {prof_score:.1f}</span>'
            f'</div>'
            f'<div style="font-size:12px;color:#6b7280;margin-top:2px">'
            f'SIRENE {sus_enrich:,}/{sus_total:,} enrichis &nbsp;·&nbsp; '
            f'V3 {total_sent:,}/{total_v3:,} envoyés ({pct_sent}%) &nbsp;·&nbsp; '
            f'<strong style="color:{"#10b981" if total_dispo > 0 else "#9ca3af"}">'
            f'{total_dispo:,} dispo</strong>'
            f'</div>'
            f'{_progress_bar(pct_sent, bar_color)}'
            f'</div>'
            f'<span style="font-size:11px;color:#9ca3af;flex-shrink:0">▾</span>'
            f'</summary>'
        )

        # Accordéons villes
        city_blocks = []
        for city in sorted(cities_data, key=lambda c: -cities_data[c]["dispo"]):
            cdata = cities_data[city]
            c_pct = _pct(cdata["sent"], cdata["total"])
            is_active_city = (
                is_active_prof and
                active.get("city", "").upper() == city.upper()
            )
            c_open = " open" if is_active_city else ""

            city_sum = (
                f'<summary style="cursor:pointer;list-style:none;padding:10px 14px;'
                f'display:flex;align-items:center;gap:8px;border-radius:4px;'
                f'background:{"#ecfdf5" if is_active_city else "transparent"}">'
                f'<span style="font-size:13px">{"🏙" if is_active_city else "📌"}</span>'
                f'<div style="flex:1">'
                f'<div style="font-size:13px;font-weight:600;color:#374151">{city}</div>'
                f'<div style="font-size:11px;color:#6b7280">'
                f'{cdata["sent"]:,} envoyés · '
                f'<strong style="color:{"#10b981" if cdata["dispo"] > 0 else "#9ca3af"}">'
                f'{cdata["dispo"]:,} dispo</strong> · '
                f'{cdata["total"]:,} total &nbsp;({c_pct}%)'
                f'</div>'
                f'{_progress_bar(c_pct, "#10b981" if is_active_city else "#6366f1", 4)}'
                f'</div>'
                f'<span style="font-size:10px;color:#9ca3af">▾</span>'
                f'</summary>'
            )

            city_blocks.append(
                f'<details{c_open} style="margin:4px 0;border:1px solid #e5e7eb;'
                f'border-radius:6px;overflow:hidden">'
                f'{city_sum}'
                f'<div style="padding:8px 14px 12px"></div>'
                f'</details>'
            )

        # Accordéon segments par département
        dept_blocks = []
        for dept, seg_list in sorted(
            segs_by_prof.get(prof.id, {}).items(),
            key=lambda x: -sum(1 for _, s in x[1] if s.status == "done")
        ):
            done    = [i for i, s in seg_list if s.status == "done"]
            running = [i for i, s in seg_list if s.status == "running"]
            pending = [i for i, s in seg_list if s.status == "pending"]
            error   = [i for i, s in seg_list if s.status == "error"]

            dept_label = _DEPT.get(dept, f"Dept. {dept}")
            n_total    = len(seg_list)
            n_done     = len(done)
            dept_pct   = _pct(n_done, n_total)

            # Résumé texte
            # "extrait" = suspects SIRENE insérés en base (pas encore prospecté)
            # "traité"  = prospection exécutée (email/SMS envoyé) — calculé sur V3
            parts = []
            if done:
                nums = sorted(done)
                if len(nums) == 1:
                    parts.append(f"Seg. {nums[0]} extrait")
                else:
                    parts.append(f"Seg. {nums[0]}–{nums[-1]} extraits ({len(nums)})")
            if running:
                parts.append(f"Seg. {running[0]} en cours")
            if pending:
                nums = sorted(pending)
                if len(nums) == 1:
                    parts.append(f"Seg. {nums[0]} à traiter")
                else:
                    parts.append(f"Seg. {nums[0]}–{nums[-1]} à traiter ({len(nums)})")
            if error:
                parts.append(f"{len(error)} erreur(s)")
            seg_summary_text = " · ".join(parts) if parts else "Aucun segment"

            # Badges
            badges = "".join(
                _seg_badge(num, seg.status) for num, seg in seg_list
            )

            # Total insérés
            total_inserted = sum(s.nb_inserted for _, s in seg_list)

            dept_blocks.append(
                f'<details style="margin:4px 0;border:1px solid #e5e7eb;'
                f'border-radius:6px;overflow:hidden">'
                f'<summary style="cursor:pointer;list-style:none;padding:10px 14px;'
                f'display:flex;align-items:center;gap:8px;background:#fafafa">'
                f'<span style="font-size:12px">🗂</span>'
                f'<div style="flex:1">'
                f'<div style="font-size:12px;font-weight:600;color:#374151">'
                f'{dept_label} <span style="color:#9ca3af;font-weight:400">'
                f'(dept. {dept})</span></div>'
                f'<div style="font-size:11px;color:#6b7280">'
                f'{n_done}/{n_total} extraits · {seg_summary_text} · '
                f'{total_inserted:,} suspects insérés</div>'
                f'{_progress_bar(dept_pct, "#8b5cf6", 4)}'
                f'</div>'
                f'<span style="font-size:10px;color:#9ca3af">▾</span>'
                f'</summary>'
                f'<div style="padding:10px 14px">'
                f'<div style="display:flex;flex-wrap:wrap;margin-bottom:8px">{badges}</div>'
                f'<p style="font-size:11px;color:#6b7280;margin:0">{seg_summary_text}</p>'
                f'</div>'
                f'</details>'
            )

        # Regrouper villes + depts dans 2 sections
        cities_section = ""
        if city_blocks:
            cities_section = (
                '<h4 style="font-size:11px;font-weight:600;color:#9ca3af;'
                'text-transform:uppercase;letter-spacing:.5px;margin:12px 0 6px">'
                'Prospects V3 par ville</h4>'
                + "".join(city_blocks)
            )

        depts_section = ""
        if dept_blocks:
            depts_section = (
                '<h4 style="font-size:11px;font-weight:600;color:#9ca3af;'
                'text-transform:uppercase;letter-spacing:.5px;margin:12px 0 6px">'
                'Segments SIRENE par département</h4>'
                + "".join(dept_blocks)
            )

        prof_blocks.append(
            f'<details{open_attr} style="margin-bottom:8px;border:1px solid #e5e7eb;'
            f'border-radius:8px;overflow:hidden">'
            f'{sum_html}'
            f'<div style="padding:12px 16px">'
            f'{cities_section}'
            f'{depts_section}'
            f'</div>'
            f'</details>'
        )

    prof_html = "".join(prof_blocks) or (
        '<p style="color:#9ca3af;text-align:center;padding:40px">Aucune profession active.</p>'
    )

    nav = admin_nav(token, "pipeline-pairs")
    now = datetime.utcnow().strftime("%d/%m %H:%M")
    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Pipeline Paires — Présence IA</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;margin:0;padding:0;color:#1a1a2e}}
.wrap{{max-width:960px;margin:0 auto;padding:24px}}
h1{{font-size:20px;font-weight:700;margin:0 0 4px}}
.sub{{color:#6b7280;font-size:13px;margin:0 0 20px}}
details summary::-webkit-details-marker{{display:none}}
details[open]>summary{{border-bottom:1px solid #e5e7eb}}
</style>
</head><body>
{nav}
<div class="wrap">
<h1>Avancement pipeline</h1>
<p class="sub">Professions · Villes · Segments SIRENE &nbsp;·&nbsp;
<a href="/admin/pipeline-pairs?token={token}" style="color:#6366f1">↺ {now} UTC</a></p>
{banner}
{prof_html}
</div></body></html>""")
