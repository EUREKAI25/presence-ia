"""
Agenda visuel Closer — vue semaines + vue jour sélectionné.

GET /closer/agenda           → interface démo (données de test)
GET /closer/{token}/agenda   → même interface (à brancher sur vraies données)
"""
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Closer Agenda"])

# ─── Données de démonstration ─────────────────────────────────────────────────

_PROSPECTS = [
    {"id": "p0",  "company": "Couverture Moreau",   "city": "Nantes",      "profession": "Couvreur",     "score": 87, "elements": ["Note Google : 2.8★ sur 14 avis (contre 4.6★ pour le concurrent n°1)", "3 couvreurs concurrents ont publié des avis ce mois-ci", "Dernier avis reçu il y a 8 mois — fiche en décrochage"]},
    {"id": "p1",  "company": "Élec Pro Dupont",      "city": "Bordeaux",    "profession": "Électricien",  "score": 72, "elements": ["Fiche Google sans aucune photo (0 sur la fiche)", "Site non adapté mobile — 68% du trafic local est sur téléphone", "Absent sur les 4 recherches vocales prioritaires pour son métier"]},
    {"id": "p2",  "company": "Plomberie Leroux",     "city": "Lyon",        "profession": "Plombier",     "score": 91, "elements": ["URGENT : un concurrent a publié 12 avis cette semaine — il dépasse Leroux en classement", "Fiche Google non revendiquée — n'importe qui peut modifier ses infos", "Son nom n'apparaît sur aucune réponse IA testée (ChatGPT, Perplexity, Gemini)"]},
    {"id": "p3",  "company": "Menuiserie Aubert",    "city": "Toulouse",    "profession": "Menuisier",    "score": 68, "elements": ["Site construit en 2018, non mis à jour depuis — pénalisé par Google", "Aucune page répondant aux questions clients (devis, délais, zones)", "2 concurrents directs ont du contenu structuré que Google valorise"]},
    {"id": "p4",  "company": "Peinture Martin",      "city": "Lille",       "profession": "Peintre",      "score": 79, "elements": ["Fiche Google non mise à jour depuis 6 mois — score de fraîcheur bas", "Absent sur les recherches de type « peintre Lille avis »", "La zone Villeneuve d'Ascq (forte densité) n'est pas couverte sur sa fiche"]},
    {"id": "p5",  "company": "Chauffage Expert",     "city": "Strasbourg",  "profession": "Chauffagiste", "score": 64, "elements": ["Dernier avis Google reçu il y a 2 ans — fiche considérée inactive", "Un concurrent direct affiche 4.9★ avec 83 avis récents", "Site sans HTTPS — signalé comme non sécurisé sur certains navigateurs"]},
    {"id": "p6",  "company": "Toitures Girard",      "city": "Rennes",      "profession": "Couvreur",     "score": 83, "elements": ["Son nom n'apparaît sur aucune réponse IA testée", "12 requêtes locales à fort volume sans aucun contenu associé", "Fiche GMB avec horaires incorrects — clients qui appellent pour rien"]},
    {"id": "p7",  "company": "Serrurier Express",    "city": "Montpellier", "profession": "Serrurier",    "score": 76, "elements": ["8 serruriers certifiés Quali'Serv dans la même zone — concurrence forte", "Aucune photo sur la fiche Google — facteur de méfiance pour les urgences", "Absent des résultats de recherche pour « serrurier urgence Montpellier »"]},
    {"id": "p8",  "company": "Plaquiste Renard",     "city": "Nice",        "profession": "Plaquiste",    "score": 71, "elements": ["Site sans menu de navigation — taux de rebond estimé très élevé", "Un concurrent est cité nommément dans les réponses de ChatGPT et Perplexity", "Fiche Google sans description de service ni zone d'intervention"]},
    {"id": "p9",  "company": "Maçonnerie Bonnet",    "city": "Paris 15e",   "profession": "Maçon",        "score": 94, "elements": ["URGENT : site détecté hors ligne ce matin — perte de visibilité en cours", "2 avis négatifs récents sans réponse — visible par tous les visiteurs", "Un concurrent du 14e vient de lancer une campagne Google ciblant le 15e"]},
    {"id": "p10", "company": "Carrelage Lefort",     "city": "Grenoble",    "profession": "Carreleur",    "score": 66, "elements": ["Aucune photo de réalisation sur la fiche Google ni sur le site", "Absent des recherches « carreleur salle de bain Grenoble » (volume : 320/mois)", "Pas de balises structurées — Google ne comprend pas le contenu du site"]},
    {"id": "p11", "company": "Isolation Roux",       "city": "Marseille",   "profession": "Isolateur",    "score": 88, "elements": ["URGENT : fiche Google non revendiquée — un concurrent l'a signalée comme fermée", "Un concurrent occupe la 1ère position sur Google Maps dans un rayon de 2 km", "Absent sur les recherches « isolation combles Marseille » malgré 5 ans d'activité"]},
    {"id": "p12", "company": "Dépannage Lebrun",     "city": "Tours",       "profession": "Dépanneur",    "score": 73, "elements": ["Site générique sans aucune référence locale (pas de ville, pas de quartier)", "Aucune page FAQ — or 40% des recherches locales sont des questions", "La zone Joué-lès-Tours (forte demande) n'est couverte par aucun contenu"]},
    {"id": "p13", "company": "Rénovation Garnier",   "city": "Dijon",       "profession": "Rénovateur",   "score": 81, "elements": ["Adresse et horaires incorrects sur la fiche Google depuis 3 mois", "Aucun article ni contenu publié depuis l'ouverture du site", "Forte demande sur « rénovation appartement Dijon » — aucun contenu positionné"]},
    {"id": "p14", "company": "Climatisation Faure",  "city": "Toulon",      "profession": "Climaticien",  "score": 77, "elements": ["Certification RGE non mentionnée sur le site ni sur la fiche Google — argument de conversion perdu", "Pas d'avis récents malgré une activité visible sur les réseaux", "Absent sur les requêtes saisonnières (climatisation réversible Toulon) — pic de demande dans 3 semaines"]},
]


def _build_demo_slots():
    """Génère les créneaux de test relatifs à la date du jour (lundi de la semaine courante)."""
    today  = date.today()
    monday = today - timedelta(days=today.weekday())

    # (offset depuis lundi, heure début, heure fin, statut, index prospect ou None)
    _raw = [
        # ── Semaine 1 ──────────────────────────────────────────────
        (0,  "09:00", "09:20", "accessible",        4),
        (0,  "09:20", "09:40", "accessible",        11),
        (0,  "10:00", "10:20", "inaccessible",      None),
        (0,  "14:00", "14:20", "accessible",        7),
        (0,  "15:00", "15:20", "claimed_me",        13),
        (1,  "09:00", "09:20", "accessible_urgent", 2),
        (1,  "09:20", "09:40", "accessible",        0),
        (1,  "10:00", "10:20", "accessible",        5),
        (1,  "11:00", "11:20", "inaccessible",      None),
        (1,  "14:00", "14:20", "claimed_other",     8),
        (1,  "14:20", "14:40", "accessible",        14),
        (2,  "10:00", "10:20", "inaccessible",      None),
        (2,  "10:20", "10:40", "inaccessible",      None),
        (2,  "14:00", "14:20", "inaccessible",      None),
        (3,  "09:00", "09:20", "accessible_urgent", 9),
        (3,  "09:20", "09:40", "accessible",        0),
        (3,  "10:00", "10:20", "accessible",        1),
        (3,  "11:00", "11:20", "claimed_me",        3),
        (3,  "14:00", "14:20", "accessible_urgent", 4),
        (3,  "14:20", "14:40", "accessible",        6),
        (3,  "15:00", "15:20", "inaccessible",      None),
        (4,  "09:00", "09:20", "accessible",        12),
        (4,  "09:20", "09:40", "accessible",        11),
        (4,  "10:00", "10:20", "inaccessible",      None),
        (4,  "14:00", "14:20", "claimed_other",     7),
        (4,  "15:00", "15:20", "inaccessible",      None),
        # ── Semaine 2 ──────────────────────────────────────────────
        (7,  "09:00", "09:20", "accessible_urgent", 9),
        (7,  "09:20", "09:40", "accessible",        5),
        (7,  "10:00", "10:20", "accessible",        13),
        (7,  "14:00", "14:20", "accessible",        2),
        (7,  "14:20", "14:40", "inaccessible",      None),
        (8,  "09:00", "09:20", "accessible",        6),
        (8,  "09:20", "09:40", "accessible",        14),
        (8,  "10:00", "10:20", "inaccessible",      None),
        (8,  "14:00", "14:20", "accessible",        3),
        (9,  "09:00", "09:20", "accessible",        1),
        (9,  "14:00", "14:20", "accessible",        8),
        (9,  "14:20", "14:40", "accessible",        10),
        (10, "09:00", "09:20", "accessible_urgent", 11),
        (10, "09:20", "09:40", "accessible",        4),
        (10, "10:00", "10:20", "claimed_me",        0),
        (10, "14:00", "14:20", "accessible",        7),
        (11, "09:00", "09:20", "inaccessible",      None),
        (11, "14:00", "14:20", "inaccessible",      None),
        # ── Semaine 3 ──────────────────────────────────────────────
        (14, "09:00", "09:20", "accessible",        3),
        (14, "09:20", "09:40", "accessible",        12),
        (14, "14:00", "14:20", "accessible_urgent", 9),
        (15, "09:00", "09:20", "accessible",        5),
        (15, "10:00", "10:20", "accessible",        6),
        (17, "09:00", "09:20", "accessible",        0),
        (17, "14:00", "14:20", "accessible",        13),
        (17, "14:20", "14:40", "claimed_other",     2),
        # ── Semaine 4 ──────────────────────────────────────────────
        (21, "09:00", "09:20", "accessible_urgent", 9),
        (21, "14:00", "14:20", "accessible",        11),
        (22, "09:00", "09:20", "accessible",        4),
        (24, "09:00", "09:20", "accessible",        7),
        (24, "09:20", "09:40", "accessible",        1),
        (24, "14:00", "14:20", "inaccessible",      None),
    ]

    slots = []
    for i, (offset, ts, te, status, pid) in enumerate(_raw):
        d = monday + timedelta(days=offset)
        slots.append({
            "id":         f"s{i}",
            "date":       d.isoformat(),
            "time_start": ts,
            "time_end":   te,
            "status":     status,
            "prospect":   _PROSPECTS[pid] if pid is not None else None,
        })
    return slots


# ─── HTML de l'interface ──────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"><link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agenda — Présence IA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#0f0f1a;color:#e8e8f0;min-height:100vh}

/* Header */
.hdr{background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:13px 16px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}
.hdr-left{display:flex;align-items:center;gap:10px}
.hdr-title{font-size:14px;font-weight:700;color:#fff}
.hdr-demo{font-size:10px;font-weight:600;color:#6366f1;background:#6366f115;
  border:1px solid #6366f130;padding:2px 7px;border-radius:10px}
.hdr-back{color:#6366f1;font-size:12px;text-decoration:none;
  padding:6px 10px;border-radius:6px;background:#6366f112}

/* Container */
.main{max-width:560px;margin:0 auto;padding:20px 14px 60px}

/* Labels section */
.sec-lbl{color:#4b5563;font-size:10px;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;margin-bottom:10px}

/* Légende */
.legend{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}
.leg-item{display:flex;align-items:center;gap:5px;font-size:11px;color:#6b7280}
.leg-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}

/* Vue semaines */
.wk-hdrs{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;margin-bottom:4px}
.wk-hdr{text-align:center;font-size:9px;color:#4b5563;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;padding:2px 0}
.wk-row{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
.wk-sep{height:8px}

/* Case jour */
.day-cell{
  aspect-ratio:1;border-radius:7px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  cursor:pointer;transition:transform .12s,box-shadow .12s;position:relative;
  -webkit-tap-highlight-color:transparent;user-select:none}
.day-cell:not(.day-empty):not(.day-past):active{transform:scale(.93)}
.day-num{font-size:clamp(10px,2.8vw,14px);font-weight:700;line-height:1;color:#fff}
.day-mon{font-size:clamp(7px,1.4vw,9px);color:rgba(255,255,255,.65);margin-top:1px}

/* Couleurs */
.day-red    {background:#dc2626}
.day-green  {background:#16a34a}
.day-locked {background:#16a34a;opacity:.28;cursor:pointer}
.day-locked:hover{opacity:.42}
.day-empty  {background:transparent;border:1px solid #1a1a2e;cursor:default}
/* Jours passés — gris plat, quelle que soit leur couleur d'origine */
.day-past   {background:#1a1a2e!important;border:1px solid #1f2937!important;
             opacity:1!important;cursor:default!important}
.day-past .day-num{color:#2d3748}
.day-past .day-mon{color:#2d3748}

/* Sélection */
.day-selected{box-shadow:0 0 0 2.5px #6366f1,0 0 0 5px #6366f125;
  transform:scale(1.07)!important}
/* Point "aujourd'hui" */
.day-today::after{content:'';position:absolute;bottom:4px;left:50%;
  transform:translateX(-50%);width:4px;height:4px;background:rgba(255,255,255,.9);
  border-radius:50%}

/* Titre vue jour */
#day-heading{font-size:15px;font-weight:700;color:#fff;margin-top:28px;margin-bottom:14px;
  padding-bottom:12px;border-bottom:1px solid #1a1a2e}
.day-empty-msg{color:#374151;font-size:13px;padding:28px 0;text-align:center}

/* Créneau */
.slot{display:flex;align-items:center;padding:11px 13px;border-radius:8px;
  margin-bottom:5px;border:1px solid transparent;gap:10px;
  -webkit-tap-highlight-color:transparent;transition:background .1s}
.slot[data-clickable=true]{cursor:pointer}
.slot[data-clickable=true]:active{transform:scale(.98)}
.slot-time{font-size:12px;font-weight:600;color:#6b7280;min-width:96px;
  flex-shrink:0;white-space:nowrap;font-variant-numeric:tabular-nums}
.slot-state{flex:1;display:flex;align-items:center;gap:7px;min-width:0}
.slot-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.slot-label{font-size:12px;font-weight:600;white-space:nowrap}
.slot-badge{font-size:9px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;
  padding:2px 6px;border-radius:10px;background:#7f1d1d;color:#fca5a5;flex-shrink:0}
.slot-arrow{color:#374151;font-size:16px;flex-shrink:0;margin-left:auto}

/* Slot états */
.s-accessible      {background:#052e1622;border-color:#16a34a30}
.s-accessible:hover{background:#052e1640}
.s-urgent          {background:#450a0a22;border-color:#dc262630}
.s-urgent:hover    {background:#450a0a44}
.s-inaccessible    {background:#052e1618;border-color:#16a34a18;opacity:.38;cursor:pointer}
.s-inaccessible:hover{opacity:.55}
.s-claimed-me      {background:#2e106522;border-color:#7c3aed30}
.s-claimed-other   {background:#78350f22;border-color:#f59e0b30;opacity:.8}
.s-conflict        {background:#43140722;border-color:#f59e0b30}
.s-conflict:hover  {background:#43140744}
.s-safety          {background:#2e106518;border-color:#a78bfa28;opacity:.7}

/* Modal */
.m-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);
  z-index:200;align-items:flex-end;justify-content:center}
.m-overlay.open{display:flex}
@media(min-width:500px){
  .m-overlay{align-items:center;padding:20px}
}
.m-box{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:16px 16px 0 0;
  width:100%;max-width:460px;padding:22px 20px 28px;
  max-height:88vh;overflow-y:auto;position:relative;
  animation:slideUp .18s ease}
@media(min-width:500px){.m-box{border-radius:14px}}
@keyframes slideUp{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}

/* Poignée mobile */
.m-handle{width:36px;height:4px;background:#374151;border-radius:2px;
  margin:0 auto 18px}
.m-close{position:absolute;top:18px;right:16px;background:#1f2937;border:1px solid #374151;
  color:#9ca3af;width:28px;height:28px;border-radius:50%;cursor:pointer;
  font-size:14px;line-height:28px;text-align:center}

/* Contenu modal */
.m-tag{display:inline-block;font-size:9px;font-weight:800;text-transform:uppercase;
  letter-spacing:.09em;padding:3px 9px;border-radius:10px;margin-bottom:12px}
.m-company{font-size:20px;font-weight:800;color:#fff;line-height:1.2;margin-bottom:3px}
.m-meta{font-size:12px;color:#6b7280;margin-bottom:18px}
.m-score-wrap{background:#0f172a;border-radius:10px;padding:14px;margin-bottom:16px;
  display:flex;align-items:flex-start;gap:14px}
.m-score-num{font-size:32px;font-weight:900;min-width:48px;line-height:1}
.m-score-lbl{font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;
  margin-bottom:6px}
.m-elements{display:flex;flex-direction:column;gap:5px}
.m-elem{font-size:11px;color:#9ca3af;padding-left:13px;position:relative;line-height:1.5}
.m-elem::before{content:'—';position:absolute;left:0;color:#374151}
.m-divider{height:1px;background:#1f2937;margin:16px 0}
.m-datetime{font-size:12px;color:#6b7280;margin-bottom:18px;display:flex;align-items:center;gap:6px}
.m-datetime::before{content:'📅'}

/* Bouton */
.btn-claim{width:100%;padding:14px;background:#6366f1;border:none;border-radius:9px;
  color:#fff;font-size:14px;font-weight:700;cursor:pointer;letter-spacing:.02em;
  transition:background .12s,transform .1s}
.btn-claim:hover{background:#4f46e5}
.btn-claim:active{transform:scale(.98)}
.btn-claim:disabled{background:#1f2937;color:#4b5563;cursor:default;transform:none}
.m-info{text-align:center;font-size:13px;color:#4b5563;padding:24px 16px;line-height:1.6}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-left">
    <span class="hdr-title">Agenda</span>
    <span class="hdr-demo">démo</span>
  </div>
  <a href="/closer/demo" class="hdr-back">← Portail</a>
</div>

<div class="main">

  <!-- Légende -->
  <div class="sec-lbl">Vue globale</div>
  <div class="legend">
    <div class="leg-item"><div class="leg-dot" style="background:#dc2626"></div>Urgent</div>
    <div class="leg-item"><div class="leg-dot" style="background:#16a34a"></div>Disponible</div>
    <div class="leg-item"><div class="leg-dot" style="background:#16a34a;opacity:.3"></div>Verrouillé</div>
    <div class="leg-item"><div class="leg-dot" style="background:#0f0f1a;border:1px solid #1f2937"></div>Vide</div>
  </div>

  <!-- Vue semaines -->
  <div class="wk-hdrs" id="wk-hdrs"></div>
  <div id="wk-grid"></div>

  <!-- Vue jour -->
  <div id="day-heading">—</div>
  <div id="slots-list"></div>

</div>

<!-- Modal -->
<div class="m-overlay" id="m-overlay" onclick="handleOverlay(event)">
  <div class="m-box" id="m-box">
    <div class="m-handle"></div>
    <button class="m-close" onclick="closeModal()">✕</button>
    <div id="m-content"></div>
  </div>
</div>

<script>
// ── Données injectées depuis Python ─────────────────────────────────────────
const SLOTS = __SLOTS__;
const TODAY  = "__TODAY__";

// ── Index par date ───────────────────────────────────────────────────────────
const byDate = {};
SLOTS.forEach(s => { (byDate[s.date] = byDate[s.date] || []).push(s); });

function dayColor(iso) {
  const ss = byDate[iso] || [];
  if (!ss.length) return 'empty';
  if (ss.some(s => s.status === 'accessible_urgent')) return 'red';
  if (ss.some(s => s.status === 'accessible')) return 'green';
  return 'locked';
}

// ── Dates utils ──────────────────────────────────────────────────────────────
function parseIso(str) {
  const [y,m,d] = str.split('-').map(Number);
  return new Date(y, m-1, d);
}
function toIso(dt) {
  const y = dt.getFullYear(), m = String(dt.getMonth()+1).padStart(2,'0'),
        d = String(dt.getDate()).padStart(2,'0');
  return `${y}-${m}-${d}`;
}

const todayDt = parseIso(TODAY);
// Lundi de la semaine courante
const monday = new Date(todayDt);
monday.setDate(todayDt.getDate() - (todayDt.getDay() || 7) + 1);

const MONTHS_SHORT = ['jan','fév','mar','avr','mai','jun','jul','aoû','sep','oct','nov','déc'];
const DAYS_SHORT   = ['Lu','Ma','Me','Je','Ve','Sa','Di'];
const DAYS_LONG    = ['Dimanche','Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'];
const MONTHS_LONG  = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];

// ── Grille semaines ──────────────────────────────────────────────────────────
function renderGrid() {
  const hdrs = document.getElementById('wk-hdrs');
  DAYS_SHORT.forEach(l => {
    const el = document.createElement('div');
    el.className = 'wk-hdr'; el.textContent = l;
    hdrs.appendChild(el);
  });

  const grid = document.getElementById('wk-grid');
  const todayMidnight = new Date(todayDt.getFullYear(), todayDt.getMonth(), todayDt.getDate());

  for (let w = 0; w < 4; w++) {
    const row = document.createElement('div');
    row.className = 'wk-row';

    for (let d = 0; d < 7; d++) {
      const dt = new Date(monday);
      dt.setDate(monday.getDate() + w*7 + d);
      const iso    = toIso(dt);
      const color  = dayColor(iso);
      const isPast = dt < todayMidnight;
      const isToday = iso === TODAY;

      // Jours passés → gris plat uniquement ; jours futurs → leur vraie couleur
      const cellColor = isPast ? 'past' : color;
      const cell = document.createElement('div');
      let cls = 'day-cell day-' + cellColor;
      if (isToday) cls += ' day-today';
      cell.className = cls;
      cell.dataset.date = iso;

      const num = document.createElement('span');
      num.className = 'day-num'; num.textContent = dt.getDate();
      cell.appendChild(num);

      if (dt.getDate() === 1) {
        const mo = document.createElement('span');
        mo.className = 'day-mon'; mo.textContent = MONTHS_SHORT[dt.getMonth()];
        cell.appendChild(mo);
      }

      if (!isPast && color === 'locked') {
        cell.addEventListener('click', () => openLockModal());
      } else if (!isPast && color !== 'empty') {
        cell.addEventListener('click', () => selectDay(iso));
      }
      row.appendChild(cell);
    }
    grid.appendChild(row);

    if (w < 3) {
      const sep = document.createElement('div');
      sep.className = 'wk-sep';
      grid.appendChild(sep);
    }
  }
}

// ── Sélection jour ───────────────────────────────────────────────────────────
let selectedDate = TODAY;

function selectDay(iso) {
  selectedDate = iso;
  document.querySelectorAll('.day-cell').forEach(c => {
    c.classList.toggle('day-selected', c.dataset.date === iso);
  });
  renderDay(iso);
  // Scroll vers la vue détaillée
  const heading = document.getElementById('day-heading');
  setTimeout(() => heading.scrollIntoView({behavior:'smooth', block:'nearest'}), 50);
}

// ── Vue détaillée ────────────────────────────────────────────────────────────
const STATUS = {
  accessible:        {dot:'#16a34a', label:'Disponible',     cls:'s-accessible',    arrow:true},
  accessible_urgent: {dot:'#dc2626', label:'Disponible',     cls:'s-urgent',        arrow:true,  urgent:true},
  inaccessible:      {dot:'#16a34a', label:'',               cls:'s-inaccessible',  arrow:true},
  claimed_me:        {dot:'#7c3aed', label:'Pris — moi',     cls:'s-claimed-me',    arrow:true},
  claimed_other:     {dot:'#f59e0b', label:'Attribué',        cls:'s-claimed-other', arrow:false},
  conflict:          {dot:'#f59e0b', label:'Conflit',         cls:'s-conflict',      arrow:true},
  safety_margin:     {dot:'#a78bfa', label:'Marge de sécurité', cls:'s-safety',      arrow:false},
};

function renderDay(iso) {
  const dt = parseIso(iso);
  document.getElementById('day-heading').textContent =
    `${DAYS_LONG[dt.getDay()]} ${dt.getDate()} ${MONTHS_LONG[dt.getMonth()]} ${dt.getFullYear()}`;

  const slots = (byDate[iso] || []).slice().sort((a,b) => a.time_start < b.time_start ? -1 : 1);
  const list = document.getElementById('slots-list');
  list.innerHTML = '';

  if (!slots.length) {
    list.innerHTML = '<div class="day-empty-msg">Aucun créneau ce jour.</div>';
    return;
  }

  slots.forEach(slot => {
    const cfg = STATUS[slot.status] || STATUS.inaccessible;
    const div = document.createElement('div');
    div.className = 'slot ' + cfg.cls;
    div.dataset.clickable = cfg.arrow;

    // Heure
    const time = document.createElement('div');
    time.className = 'slot-time';
    time.textContent = slot.time_start + ' – ' + slot.time_end;

    // État
    const state = document.createElement('div');
    state.className = 'slot-state';

    const dot = document.createElement('div');
    dot.className = 'slot-dot'; dot.style.background = cfg.dot;

    const lbl = document.createElement('span');
    lbl.className = 'slot-label'; lbl.style.color = cfg.dot; lbl.textContent = cfg.label;

    state.appendChild(dot); state.appendChild(lbl);

    if (cfg.urgent) {
      const badge = document.createElement('span');
      badge.className = 'slot-badge'; badge.textContent = 'URGENT';
      state.appendChild(badge);
    }

    div.appendChild(time); div.appendChild(state);

    if (cfg.arrow) {
      const arrow = document.createElement('span');
      arrow.className = 'slot-arrow'; arrow.textContent = '›';
      div.appendChild(arrow);
      div.addEventListener('click', () => openModal(slot));
    }

    list.appendChild(div);
  });
}

// ── Modal ────────────────────────────────────────────────────────────────────
function scoreColor(sc) {
  return sc >= 85 ? '#ef4444' : sc >= 70 ? '#f59e0b' : '#22c55e';
}
function scoreLbl(sc) {
  return sc >= 85 ? 'Situation critique — conversion très probable'
       : sc >= 70 ? 'Écart de visibilité significatif'
       :            'Écart de visibilité modéré';
}

function openModal(slot) {
  const content = document.getElementById('m-content');

  if (slot.status === 'inaccessible') {
    content.innerHTML = `
      <div style="text-align:center;padding:28px 12px">
        <div style="font-size:36px;margin-bottom:18px">🔒</div>
        <p style="color:#e8e8f0;font-size:14px;font-weight:600;line-height:1.6;margin-bottom:8px">
          Ce créneau est bloqué. Prenez d'abord en charge le rendez-vous urgent disponible.
        </p>
      </div>`;
  } else if (slot.status === 'claimed_other') {
    content.innerHTML = '<div class="m-info">Ce créneau est déjà pris<br>par un autre closer.</div>';
  } else {
    const p = slot.prospect;
    const isUrgent = slot.status === 'accessible_urgent';
    const isMe     = slot.status === 'claimed_me';

    const tagBg    = isUrgent ? '#7f1d1d' : isMe ? '#2e1065' : '#052e16';
    const tagColor = isUrgent ? '#fca5a5' : isMe ? '#c4b5fd' : '#86efac';
    const tagTxt   = isUrgent ? 'URGENT'  : isMe ? 'Pris par moi' : 'Disponible';

    const elems = p ? p.elements.map(e => `<div class="m-elem">${e}</div>`).join('') : '';
    const sc = p ? p.score : 0;
    const scCol = scoreColor(sc);

    content.innerHTML = `
      <span class="m-tag" style="background:${tagBg};color:${tagColor}">${tagTxt}</span>
      ${p ? `
      <div class="m-company">${p.company}</div>
      <div class="m-meta">${p.city}&ensp;·&ensp;${p.profession}</div>
      <div class="m-score-wrap">
        <div class="m-score-num" style="color:${scCol}">${sc}</div>
        <div style="flex:1">
          <div class="m-score-lbl">${scoreLbl(sc)}</div>
          <div class="m-elements">${elems}</div>
        </div>
      </div>
      ` : ''}
      <div class="m-divider"></div>
      <div class="m-datetime">${slot.time_start} – ${slot.time_end}</div>
      ${isMe
        ? '<button class="btn-claim" disabled>Vous avez déjà ce créneau</button>'
        : '<button class="btn-claim" id="btn-claim">Prendre ce rendez-vous</button>'
      }
    `;

    if (!isMe) {
      document.getElementById('btn-claim').addEventListener('click', function() {
        claimSlot(this, slot);
      });
    }
  }

  document.getElementById('m-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

// ── Réservation + mise à jour instantanée ────────────────────────────────────
function claimSlot(btn, slot) {
  btn.textContent = '✓ Créneau réservé !';
  btn.style.background = '#16a34a';
  btn.disabled = true;

  // 1. Marquer le créneau comme pris par moi
  slot.status = 'claimed_me';

  // 2. Créneau suivant → marge de sécurité (si accessible)
  const daySlots = (byDate[slot.date] || [])
    .slice().sort((a,b) => a.time_start < b.time_start ? -1 : 1);
  const idx = daySlots.findIndex(s => s.id === slot.id);
  if (idx >= 0 && idx < daySlots.length - 1) {
    const next = daySlots[idx + 1];
    if (next.status === 'accessible' || next.status === 'accessible_urgent') {
      next.status = 'safety_margin';
    }
  }

  // 3. Rafraîchir vue jour + case calendrier
  setTimeout(() => {
    renderDay(slot.date);
    refreshDayCell(slot.date);
    closeModal();
  }, 450);

  // TODO: POST /closer/{token}/claim/{slot.id}
}

function refreshDayCell(iso) {
  const cell = document.querySelector('.day-cell[data-date="' + iso + '"]');
  if (!cell || cell.classList.contains('day-past')) return;
  const newColor = dayColor(iso);
  ['day-red','day-green','day-locked','day-empty'].forEach(c => cell.classList.remove(c));
  cell.classList.add('day-' + newColor);
  // Rebrancher clic si la couleur a changé (ex. locked → green)
  if (newColor !== 'empty' && newColor !== 'past') {
    cell.onclick = newColor === 'locked' ? () => openLockModal() : () => selectDay(iso);
  }
}

function openLockModal() {
  document.getElementById('m-content').innerHTML = `
    <div style="text-align:center;padding:28px 12px">
      <div style="font-size:36px;margin-bottom:18px">🔒</div>
      <p style="color:#e8e8f0;font-size:14px;font-weight:600;line-height:1.6">
        Ce créneau est bloqué. Prenez d'abord en charge le rendez-vous urgent disponible.
      </p>
    </div>`;
  document.getElementById('m-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('m-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
function handleOverlay(e) {
  if (e.target === document.getElementById('m-overlay')) closeModal();
}

// ── Init ─────────────────────────────────────────────────────────────────────
renderGrid();
selectDay(TODAY);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
</script>
</body>
</html>
"""


def _build_page() -> str:
    slots = _build_demo_slots()
    today_str = date.today().isoformat()
    page = _HTML.replace("__SLOTS__", json.dumps(slots, ensure_ascii=False, separators=(",", ":")))
    page = page.replace("__TODAY__", today_str)
    return page


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/closer/agenda", response_class=HTMLResponse)
def closer_agenda_demo():
    """Interface agenda — vrais RDV (vue admin sans token closer)."""
    slots = _build_real_slots("")
    if not slots:
        slots = _build_demo_slots()  # fallback démo si aucun vrai RDV
    today_str = date.today().isoformat()
    page = _HTML.replace("__SLOTS__", json.dumps(slots, ensure_ascii=False, separators=(",", ":")))
    page = page.replace("__TODAY__", today_str)
    return HTMLResponse(page)


def _build_real_slots(closer_token: str) -> list:
    """Charge les vrais RDV depuis v3_bookings pour ce closer."""
    from ...database import SessionLocal
    from ...models import V3BookingDB, V3ProspectDB
    from marketing_module.database import SessionLocal as MktSession
    from marketing_module.models import CloserDB as _CloserDB

    slots = []
    try:
        # Trouver le closer par token (optionnel — pour affichage futur)
        with MktSession() as mdb:
            closer = mdb.query(_CloserDB).filter_by(token=closer_token).first()

        # Charger tous les bookings (pour l'instant tous — à filtrer par closer quand multi-closers)
        with SessionLocal() as db:
            bookings = db.query(V3BookingDB).order_by(V3BookingDB.start_iso).all()
            for i, b in enumerate(bookings):
                # Extraire date et heure depuis start_iso / end_iso (format "2026-04-17T13:00:00")
                try:
                    dt_start = b.start_iso[:10]   # "2026-04-17"
                    t_start  = b.start_iso[11:16]  # "13:00"
                    t_end    = b.end_iso[11:16] if b.end_iso else ""
                except Exception:
                    continue

                # Prospect associé
                prospect = None
                if b.prospect_token:
                    p = db.query(V3ProspectDB).filter_by(token=b.prospect_token).first()
                    if p:
                        prospect = {
                            "id":         b.prospect_token,
                            "company":    p.name or b.name or "",
                            "city":       p.city or "",
                            "profession": p.profession or "",
                            "score":      0,
                            "elements":   [],
                            "email":      b.email or "",
                            "phone":      b.phone or "",
                            "website":    b.website or "",
                        }
                if not prospect:
                    prospect = {
                        "id": b.id, "company": b.name or b.email or "—",
                        "city": "", "profession": "", "score": 0, "elements": [],
                        "email": b.email or "", "phone": b.phone or "", "website": b.website or "",
                    }

                # Statut basé sur l'urgence temporelle (pas de claim tracking dans V3BookingDB)
                try:
                    dt_s = datetime.fromisoformat(b.start_iso)
                    delta_h = (dt_s - datetime.utcnow()).total_seconds() / 3600
                    _status = "accessible_urgent" if 0 <= delta_h < 48 else "accessible"
                except Exception:
                    _status = "accessible"

                slots.append({
                    "id":         b.id,
                    "date":       dt_start,
                    "time_start": t_start,
                    "time_end":   t_end,
                    "status":     _status,
                    "prospect":   prospect,
                    "gcal_url":   b.gcal_event_url or "",
                })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("_build_real_slots: %s", e)

    return slots


@router.get("/closer/{token}/agenda", response_class=HTMLResponse)
def closer_agenda_token(token: str):
    """Interface agenda visuel — vrais RDV depuis v3_bookings."""
    slots = _build_real_slots(token)
    # Si aucun vrai RDV, afficher quand même la page (vide)
    today_str = date.today().isoformat()
    page = _HTML.replace("__SLOTS__", json.dumps(slots, ensure_ascii=False, separators=(",", ":")))
    page = page.replace("__TODAY__", today_str)
    return HTMLResponse(page)
