"""
Module GENERATE — audit HTML + landing token + email draft + video script + SendQueue CSV
AUCUN ENVOI AUTO.
"""
import csv, json, os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from .database import db_get_prospect, db_list_prospects, db_list_runs, jl
from .models import ProspectDB, ProspectStatus

SQ_DIR   = Path(__file__).parent.parent / "send_queue"
DIST_DIR = Path(__file__).parent.parent / "dist"
SQ_DIR.mkdir(exist_ok=True)
DIST_DIR.mkdir(exist_ok=True)

BASE_URL  = os.getenv("BASE_URL", "http://localhost:8001")
SIGNATURE = os.getenv("SENDER_SIGNATURE", "L'équipe PRESENCE_IA")


# ── Helpers ──────────────────────────────────────────────────────────

def _comps(p: ProspectDB, n: int = 2) -> List[str]:
    try: return [c.title() for c in json.loads(p.competitors_cited or "[]")[:n]]
    except: return []

def _summary(db: Session, p: ProspectDB) -> Dict:
    runs = db_list_runs(db, p.prospect_id)
    qm = [0]*5; ql = [""]*5
    for r in runs:
        for qi, (m, q) in enumerate(zip(jl(r.mention_per_query), jl(r.queries))):
            if qi < 5:
                if m: qm[qi] += 1
                if not ql[qi] and q: ql[qi] = q
    return {
        "runs":    len(runs),
        "models":  list({r.model for r in runs}),
        "dates":   sorted({r.ts.strftime("%d/%m/%Y") for r in runs})[:3],
        "qm": qm, "ql": ql,
    }

def landing_url(p: ProspectDB) -> str:
    return f"{BASE_URL}/{p.profession}?t={p.landing_token}"


# ── Audit HTML ────────────────────────────────────────────────────────

def audit_generate(db: Session, p: ProspectDB) -> str:
    s = _summary(db, p); comps = _comps(p, 5); score = p.ia_visibility_score or 0
    qrows = "".join(
        f"<tr><td>{l or f'Q{i+1}'}</td><td>{'<span class=cited>Cité</span>' if c>0 else '<span class=ncited>Non cité</span>'}</td></tr>"
        for i,(l,c) in enumerate(zip(s["ql"], s["qm"])) if l
    )
    citems = "".join(f"<li>{c}</li>" for c in comps) or "<li>—</li>"
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Audit PRESENCE_IA — {p.name}</title>
<style>body{{font-family:Arial,sans-serif;max-width:860px;margin:40px auto;color:#222}}
h1{{border-bottom:3px solid #e94560;padding-bottom:10px}}h2{{margin-top:40px;color:#1a1a2e}}
.score{{background:#f0f4ff;border-left:5px solid #e94560;padding:20px 30px;margin:20px 0}}
.score b{{font-size:52px;color:#e94560}}
table{{border-collapse:collapse;width:100%}}th{{background:#16213e;color:#fff;padding:10px}}
td{{padding:9px;border-bottom:1px solid #eee}}.cited{{color:#2ecc71;font-weight:bold}}
.ncited{{color:#e74c3c;font-weight:bold}}
.plan{{background:#fffbea;border:1px solid #f1c40f;padding:20px;margin-top:30px;border-radius:6px}}
.plan li{{margin:8px 0}}.plan li::before{{content:"☑ ";color:#2ecc71}}</style></head><body>
<h1>🤖 Audit PRESENCE_IA — Visibilité IA</h1>
<p><b>Entreprise :</b> {p.name} | <b>Ville :</b> {p.city} | <b>Secteur :</b> {p.profession}<br>
<b>Date :</b> {datetime.utcnow().strftime("%d/%m/%Y")} | <b>Runs :</b> {s['runs']} sur {", ".join(s['models']) or "—"}</p>
<div class="score"><div>Score de visibilité IA</div><div><b>{score}</b>/10</div>
<div>{(p.score_justification or "").split(chr(10))[0]}</div></div>
<h2>📊 Résultats par requête</h2>
<table><tr><th>Requête</th><th>Résultat</th></tr>{qrows}</table>
<h2>🏆 Concurrents identifiés</h2><ul>{citems}</ul>
<div class="plan"><h2>✅ Plan d'action prioritaire</h2><ul>
<li>Google Business Profile — compléter à 100 %</li>
<li>Viser 40+ avis Google avec réponses systématiques</li>
<li>5-10 pages FAQ répondant aux requêtes testées</li>
<li>Citations locales (PagesJaunes, Yelp, Houzz…)</li>
<li>JSON-LD LocalBusiness + AggregateRating sur le site</li>
<li>Cohérence NAP (Nom/Adresse/Téléphone) sur toutes plateformes</li>
<li>H1 incluant ville + profession ex : « Couvreur à {p.city} »</li>
<li>1 article presse locale ou interview = signal fort pour LLMs</li>
</ul><p><em>Délai estimé : 2-4 mois pour apparaître dans les réponses IA.</em></p></div>
<footer style="margin-top:60px;color:#888;font-size:12px;border-top:1px solid #ddd;padding-top:20px">
© PRESENCE_IA — Les réponses IA peuvent varier ; résultats basés sur tests répétés horodatés.</footer>
</body></html>"""
    out = DIST_DIR / p.prospect_id; out.mkdir(parents=True, exist_ok=True)
    (out / "audit.html").write_text(html, encoding="utf-8")
    return html


# ── Email ─────────────────────────────────────────────────────────────

def email_generate(db: Session, p: ProspectDB) -> Dict:
    comps = _comps(p); c1 = comps[0] if comps else "vos concurrents"; c2 = comps[1] if len(comps)>1 else ""
    l = landing_url(p); vid = p.video_url or "[VIDEO A AJOUTER]"
    c2_part = f" (et parfois {c2})" if c2 else ""
    # Lire le template depuis la DB si disponible
    try:
        from .database import db_get_template
        tpl = db_get_template(db, "email_prospection")
    except Exception:
        tpl = None
    if tpl and tpl.subject and tpl.body:
        subj = (tpl.subject
                .replace("{city}", p.city).replace("{profession}", p.profession)
                .replace("{c1}", c1).replace("{c2}", c2))
        body = (tpl.body
                .replace("{name}", p.name or "").replace("{city}", p.city)
                .replace("{profession}", p.profession).replace("{c1}", c1)
                .replace("{c2}", c2).replace("{c2_part}", c2_part)
                .replace("{video_url}", vid).replace("{landing_url}", l))
    else:
        subj = f"A {p.city}, ChatGPT recommande {c1}. Pas vous."
        body = (f"Bonjour,\n\nJ'ai teste ce que repondent plusieurs IA lorsqu'un client cherche un "
                f"{p.profession} a {p.city}.\n\nSur des tests repetes, {c1}"
                f"{c2_part} est regulierement cite. "
                f"Votre entreprise n'apparait pas.\n\nVideo (90s) : {vid}\nSynthese + options : {l}\n\n-- {SIGNATURE}")
    data = {"prospect_id": p.prospect_id, "name": p.name, "city": p.city,
            "subject": subj, "body": body, "landing_url": l,
            "video_url": vid, "c1": c1, "c2": c2}
    out = DIST_DIR / p.prospect_id; out.mkdir(parents=True, exist_ok=True)
    (out / "email.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    (out / "email_body.txt").write_text(f"SUBJECT: {subj}\n\n{body}", encoding="utf-8")
    return data


# ── Video script ──────────────────────────────────────────────────────

def video_script(p: ProspectDB) -> str:
    comps = _comps(p); c1 = comps[0] if comps else "[concurrent 1]"; c2 = comps[1] if len(comps)>1 else "[concurrent 2]"
    l = landing_url(p)
    sc = (f"SCRIPT VIDÉO — {p.name} / {p.city}\n\n"
          f"1. « Bonjour {p.name}, j'ai testé ce que répondent les IA quand un client cherche un {p.profession} à {p.city}. »\n"
          f"2. « Voici la requête — je lance le test. »\n"
          f"3. (silence + scroll) « Comme vous voyez, {c1} et {c2} sont cités. »\n"
          f"4. (scroll) « Votre entreprise n'apparaît pas dans ces résultats. »\n"
          f"5. « On a répété ces tests sur plusieurs créneaux et plusieurs IA : le constat est stable. »\n"
          f"6. « Je vous ai préparé la synthèse + plan d'action ici : {l} »\n")
    out = DIST_DIR / p.prospect_id; out.mkdir(parents=True, exist_ok=True)
    (out / "video_script.txt").write_text(sc, encoding="utf-8")
    return sc


# ── SendQueue ─────────────────────────────────────────────────────────

def delivery(db: Session, prospects: List[ProspectDB]) -> str:
    rows = []
    for p in prospects:
        if not p.eligibility_flag: continue
        ed = email_generate(db, p); audit_generate(db, p); video_script(p)
        rows.append({"prospect_id": p.prospect_id, "name": p.name, "city": p.city,
                     "profession": p.profession, "email": "", "phone": p.phone or "",
                     "website": p.website or "", "score": p.ia_visibility_score or 0,
                     "c1": ed["c1"], "c2": ed["c2"], "subject": ed["subject"],
                     "landing_url": ed["landing_url"], "video_url": ed["video_url"], "status": p.status})
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    path = SQ_DIR / f"send_queue_{ts}.csv"
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    return str(path)


def generate_campaign(db: Session, campaign_id: str, prospect_ids: Optional[List[str]] = None) -> Dict:
    if prospect_ids:
        prospects = [p for pid in prospect_ids if (p := db_get_prospect(db, pid))]
    else:
        all_p = db_list_prospects(db, campaign_id)
        _ok = {ProspectStatus.SCORED.value, ProspectStatus.READY_ASSETS.value, ProspectStatus.READY_TO_SEND.value}
        prospects = [p for p in all_p if p.status in _ok and p.eligibility_flag]
    csv_path = delivery(db, prospects)
    return {"generated": len(prospects), "send_queue_csv": csv_path,
            "dist_dir": str(DIST_DIR), "ids": [p.prospect_id for p in prospects]}
