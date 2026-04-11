"""Nav admin partagé — importé par toutes les pages admin.

Sidebar fixe à gauche, accordéons fermés par défaut (sauf section active).
Favicon injecté automatiquement via script inline.
"""
import os


def admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


def admin_nav(token: str, active: str = "") -> str:
    sections = [
        ("LEADS", [
            ("leads-hub",        "Accueil"),
            ("contacts",         "Contacts"),
            ("prospection",      "Automation"),
            ("suspects",         "Suspects"),
            ("scheduler",        "Scheduler"),
            ("pipeline-health",  "⚡ Pipeline Health"),
        ]),
        ("MARKETING", [
            ("marketing",       "Stats globales"),
            ("campaigns",       "Campagnes"),
            ("outbound-stats",  "Outbound"),
        ]),
        ("CLOSERS", [
            ("closers-hub",       "Accueil"),
            ("crm",               "Pipeline"),
            ("crm/closers",       "Liste closers"),
            ("recrutement",       "Recrutement"),
            ("crm/paiements",     "Paiements"),
        ]),
        ("FINANCES", [
            ("finances",    "Revenus & Coûts"),
            ("analytics",   "Stats ventes"),
        ]),
    ]

    def _link(slug, label):
        is_active = slug == active
        bg     = "#fef2f4" if is_active else "transparent"
        color  = "#e94560" if is_active else "#374151"
        weight = "600"     if is_active else "400"
        border = "3px solid #e94560" if is_active else "3px solid transparent"
        return (
            f'<a href="/admin/{slug}?token={token}" '
            f'style="display:block;padding:7px 10px;border-radius:4px;text-decoration:none;'
            f'font-size:12px;font-weight:{weight};background:{bg};color:{color};'
            f'border-left:{border};margin-bottom:1px;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis">'
            f'{label}</a>'
        )

    sections_html = ""
    for i, (sec_label, tabs) in enumerate(sections):
        is_open = any(slug == active for slug, _ in tabs)
        open_attr = " open" if is_open else ""
        links = "".join(_link(slug, label) for slug, label in tabs)
        sections_html += (
            f'<details{open_attr} class="pres-acc" style="margin-bottom:2px">'
            f'<summary style="cursor:pointer;padding:8px 10px;font-size:10px;font-weight:700;'
            f'color:#9ca3af;letter-spacing:.08em;list-style:none;display:flex;align-items:center;'
            f'justify-content:space-between;border-radius:4px;user-select:none;'
            f'background:transparent;outline:none" '
            f'onmouseover="this.style.color=\'#6b7280\'" '
            f'onmouseout="this.style.color=\'#9ca3af\'">'
            f'{sec_label} <span style="font-size:9px">▾</span></summary>'
            f'<div style="padding:2px 0 6px 4px">{links}</div>'
            f'</details>'
        )

    return (
        f'<style>'
        f'body{{margin:0!important;padding-left:180px!important;box-sizing:border-box}}'
        f'.pres-sidebar details summary::-webkit-details-marker{{display:none}}'
        f'#pres-hamburger{{display:none}}'
        f'#pres-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:998}}'
        f'#pres-overlay.show{{display:block}}'
        f'@media(max-width:640px){{'
        f'body{{padding-left:0!important;padding-top:52px!important}}'
        f'#pres-hamburger{{display:flex!important;position:fixed;top:8px;left:10px;z-index:1001;'
        f'background:#fff;border:1px solid #e5e7eb;border-radius:6px;'
        f'width:38px;height:38px;align-items:center;justify-content:center;'
        f'font-size:20px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.1)}}'
        f'.pres-sidebar{{transform:translateX(-190px);transition:transform .22s ease}}'
        f'.pres-sidebar.open{{transform:translateX(0)}}'
        f'}}'
        f'</style>'
        f'<script>(function(){{var l=document.createElement("link");l.rel="icon";'
        f'l.type="image/png";l.href="/assets/favicon.png";document.head.appendChild(l);}})();</script>'
        f'<button id="pres-hamburger" aria-label="Menu" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.toggle(\'open\');'
        f'document.getElementById(\'pres-overlay\').classList.toggle(\'show\')'
        f'">☰</button>'
        f'<div id="pres-overlay" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.remove(\'open\');'
        f'this.classList.remove(\'show\')'
        f'"></div>'
        f'<nav class="pres-sidebar" style="position:fixed;top:0;left:0;width:180px;height:100vh;'
        f'background:#fff;border-right:1px solid #e5e7eb;overflow-y:auto;z-index:1000;'
        f'padding-bottom:24px;display:flex;flex-direction:column">'
        f'<a href="/admin?token={token}" '
        f'style="display:flex;align-items:center;justify-content:center;'
        f'padding:14px 12px;border-bottom:1px solid #e5e7eb;text-decoration:none;flex-shrink:0">'
        f'<img src="/assets/logo.svg" alt="PRESENCE_IA" style="width:148px;height:auto"></a>'
        f'<div style="padding:10px 8px;flex:1">'
        f'{sections_html}'
        f'</div>'
        f'<div style="padding:8px;border-top:1px solid #f3f4f6;flex-shrink:0">'
        f'<button onclick="pipelineHistoryOpen(\'{token}\')" '
        f'style="width:100%;padding:7px 8px;background:#f9fafb;border:1px solid #e5e7eb;'
        f'border-radius:5px;font-size:11px;color:#6b7280;cursor:pointer;text-align:left;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis" '
        f'title="Journal des décisions de pilotage outbound">'
        f'📋 Journal pilotage</button>'
        f'</div>'
        f'</nav>'
        f'<script>'
        f'(function(){{'
        f'  function initAcc(){{'
        f'    document.querySelectorAll(".pres-acc summary").forEach(function(s){{'
        f'      s.addEventListener("click",function(e){{'
        f'        var me=s.closest("details");'
        f'        if(me.hasAttribute("open")) return;'
        f'        document.querySelectorAll(".pres-acc[open]").forEach(function(d){{'
        f'          if(d!==me) d.removeAttribute("open");'
        f'        }});'
        f'      }});'
        f'    }});'
        f'  }}'
        f'  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",initAcc);'
        f'  else initAcc();'
        f'}})();'
        f'</script>'
        f'<!-- Drawer journal pilotage -->'
        f'<div id="ph-overlay" onclick="pipelineHistoryClose()" '
        f'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1100"></div>'
        f'<div id="ph-drawer" '
        f'style="display:none;position:fixed;top:0;right:0;width:min(780px,95vw);height:100vh;'
        f'background:#fff;box-shadow:-4px 0 24px rgba(0,0,0,.12);z-index:1101;'
        f'overflow-y:auto;padding:24px 28px;box-sizing:border-box">'
        f'  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">'
        f'    <h2 style="margin:0;font-size:17px;font-weight:700;color:#111">Journal de pilotage</h2>'
        f'    <button onclick="pipelineHistoryClose()" '
        f'      style="background:none;border:none;font-size:22px;cursor:pointer;color:#6b7280;line-height:1">✕</button>'
        f'  </div>'
        f'  <div id="ph-summary" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px"></div>'
        f'  <div id="ph-body">Chargement…</div>'
        f'</div>'
        f'<script>'
        f'var _phToken="";'
        f'function pipelineHistoryOpen(tok){{'
        f'  _phToken=tok;'
        f'  document.getElementById("ph-overlay").style.display="block";'
        f'  document.getElementById("ph-drawer").style.display="block";'
        f'  document.getElementById("ph-body").innerHTML="Chargement…";'
        f'  document.getElementById("ph-summary").innerHTML="";'
        f'  fetch("/api/admin/pipeline-history?token="+tok)'
        f'    .then(r=>r.json())'
        f'    .then(function(d){{'
        f'      var rows=d.rows||[];'
        f'      if(!rows.length){{document.getElementById("ph-body").innerHTML='
        f'        \'<p style="color:#9ca3af;text-align:center;margin-top:40px">Aucune donnée — le journal se remplit au prochain run outbound.</p>\';return;}}'
        f'      // Résumé (dernière ligne)'
        f'      var last=rows[0];'
        f'      var statColor={{"running":"#10b981","top_up":"#f59e0b","idle":"#6b7280","saturated":"#3b82f6"}}[last.statut]||"#9ca3af";'
        f'      function _kpi(l,v,c){{'
        f'        return \'<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px 14px;min-width:120px">\''
        f'          +\'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px">\'+l+\'</div>\''
        f'          +\'<div style="font-size:16px;font-weight:700;color:\'+c+\'">\'+v+\'</div></div>\';'
        f'      }}'
        f'      document.getElementById("ph-summary").innerHTML='
        f'        _kpi("Mode",last.mode,"#1e3a5f")'
        f'        +_kpi("Statut",last.statut.toUpperCase(),statColor)'
        f'        +_kpi("Paire",last.paire,"#374151")'
        f'        +_kpi("Couverture",(last.taux_couverture!=null?last.taux_couverture+"%":"—"),"#6366f1")'
        f'        +_kpi("Cap généré",(last.cap_genere!=null?last.cap_genere:"—"),"#0ea5e9");'
        f'      // Tableau'
        f'      var html=\'<table style="border-collapse:collapse;width:100%;font-size:13px">\''
        f'        +\'<thead><tr style="background:#f9fafb">\''
        f'        +\'<th style="padding:8px 10px;text-align:left;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">Date</th>\''
        f'        +\'<th style="padding:8px 10px;text-align:left;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">Paire</th>\''
        f'        +\'<th style="padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">Couverture</th>\''
        f'        +\'<th style="padding:8px 10px;text-align:left;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">Statut</th>\''
        f'        +\'<th style="padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">En file</th>\''
        f'        +\'<th style="padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">Nécessaires</th>\''
        f'        +\'<th style="padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb">Cap</th>\''
        f'        +\'</tr></thead><tbody>\';'
        f'      var statBg={{"running":"#d1fae5","top_up":"#fef3c7","idle":"#f3f4f6","saturated":"#dbeafe"}};'
        f'      var statFg={{"running":"#065f46","top_up":"#92400e","idle":"#374151","saturated":"#1e40af"}};'
        f'      rows.forEach(function(r,i){{'
        f'        var bg=i%2===0?"#fff":"#f9fafb";'
        f'        var sbg=statBg[r.statut]||"#f3f4f6";'
        f'        var sfg=statFg[r.statut]||"#374151";'
        f'        html+=\'<tr style="background:\'+bg+\';cursor:pointer" onclick="phDetail(\'+JSON.stringify(r).replace(/</g,"&lt;")+\')"><td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;white-space:nowrap">\'+r.ts+\'</td>\''
        f'          +\'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6">\'+r.paire+\'</td>\''
        f'          +\'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right">\''
        f'          +(r.taux_couverture!=null?r.taux_couverture+"%":"—")+\'</td>\''
        f'          +\'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6"><span style="display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;background:\'+sbg+\';color:\'+sfg+\'">\'+r.statut.toUpperCase()+\'</span></td>\''
        f'          +\'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right">\''
        f'          +(r.leads_en_file!=null?r.leads_en_file:"—")+\'</td>\''
        f'          +\'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right">\''
        f'          +(r.leads_necessaires!=null?r.leads_necessaires:"—")+\'</td>\''
        f'          +\'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right;font-weight:600">\''
        f'          +(r.cap_genere!=null?r.cap_genere:"—")+\'</td></tr>\';'
        f'      }});'
        f'      html+=\'</tbody></table>\''
        f'        +\'<p style="font-size:11px;color:#9ca3af;margin-top:8px">Cliquer sur une ligne pour le détail complet.</p>\';'
        f'      document.getElementById("ph-body").innerHTML=html;'
        f'    }}).catch(function(e){{document.getElementById("ph-body").innerHTML="Erreur: "+e;}});'
        f'}}'
        f'function pipelineHistoryClose(){{'
        f'  document.getElementById("ph-overlay").style.display="none";'
        f'  document.getElementById("ph-drawer").style.display="none";'
        f'}}'
        f'function phDetail(r){{'
        f'  var lines=['
        f'    "Date : "+r.ts,'
        f'    "Mode : "+r.mode,'
        f'    "Paire : "+r.paire,'
        f'    "Source slots : "+r.source_slots,'
        f'    "——— Slots ———",'
        f'    "Proches : "+r.slots_proches_remplis+"/"+r.slots_proches_total+" réservés",'
        f'    "Moyens : "+r.slots_moyens_remplis+"/"+r.slots_moyens_total+" réservés",'
        f'    "Lointains : "+r.slots_lointains_remplis+"/"+r.slots_lointains_total+" réservés",'
        f'    "Taux couverture : "+(r.taux_couverture!=null?r.taux_couverture+"%":"—"),'
        f'    "——— Leads ———",'
        f'    "En file : "+r.leads_en_file,'
        f'    "Nécessaires : "+r.leads_necessaires,'
        f'    "——— Décision ———",'
        f'    "Statut : "+r.statut.toUpperCase(),'
        f'    "Cap généré : "+r.cap_genere,'
        f'  ];'
        f'  alert(lines.join("\\n"));'
        f'}}'
        f'</script>'
    )
