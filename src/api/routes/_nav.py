"""
_nav.py — Sidebar admin partagée + CSS global admin.

Inclus dans toutes les pages admin via admin_nav().
Injecte automatiquement :
  - Le thème admin complet (ADMIN_CSS depuis _theme.py)
  - La sidebar fixe (fond ardoise #394455, logo ADMIN)
  - Le drawer « Journal de pilotage »
  - Le favicon
  - La gestion mobile (hamburger)
"""
import os
from ._theme import ADMIN_CSS, C_BLUE, C_BLUE_DARK, C_BLUE_LIGHT, C_SLATE, C_GOLD, C_GOLD_VIVID


def admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


def admin_nav(token: str, active: str = "") -> str:
    sections = [
        ("LEADS", [
            ("leads-hub",        "Accueil"),
            ("pipeline-pairs",   "Avancement pipeline"),
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
        if is_active:
            bg     = "rgba(82,127,179,.18)"
            color  = "#ffffff"
            weight = "600"
            border = f"3px solid {C_BLUE}"
        else:
            bg     = "transparent"
            color  = "rgba(255,255,255,.55)"
            weight = "400"
            border = "3px solid transparent"
        return (
            f'<a href="/admin/{slug}?token={token}" '
            f'style="display:block;padding:6px 10px;border-radius:4px;text-decoration:none;'
            f'font-size:12px;font-weight:{weight};background:{bg};color:{color};'
            f'border-left:{border};margin-bottom:1px;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;transition:background .12s,color .12s" '
            f'onmouseover="if(!this.style.borderLeft.includes(\'{C_BLUE}\')){{this.style.background=\'rgba(255,255,255,.08)\';this.style.color=\'rgba(255,255,255,.8)\'}}" '
            f'onmouseout="if(!this.style.borderLeft.includes(\'{C_BLUE}\')){{this.style.background=\'transparent\';this.style.color=\'rgba(255,255,255,.55)\'}}">'
            f'{label}</a>'
        )

    sections_html = ""
    for i, (sec_label, tabs) in enumerate(sections):
        is_open = any(slug == active for slug, _ in tabs)
        open_attr = " open" if is_open else ""
        links = "".join(_link(slug, label) for slug, label in tabs)
        first_href = f'/admin/{tabs[0][0]}?token={token}'
        sections_html += (
            f'<details{open_attr} class="pres-acc" style="margin-bottom:1px">'
            f'<summary style="cursor:pointer;padding:7px 10px;font-size:10px;font-weight:700;'
            f'color:rgba(255,255,255,.35);letter-spacing:.1em;list-style:none;display:flex;'
            f'align-items:center;justify-content:space-between;border-radius:4px;'
            f'user-select:none;background:transparent;outline:none;transition:color .12s" '
            f'onmouseover="this.style.color=\'rgba(255,255,255,.6)\'" '
            f'onmouseout="this.style.color=\'rgba(255,255,255,.35)\'">'
            f'<a href="{first_href}" onclick="event.stopPropagation()" '
            f'style="flex:1;text-decoration:none;color:inherit;display:block;'
            f'letter-spacing:.08em">{sec_label}</a>'
            f'<span onclick="event.stopPropagation();var d=this.closest(\'details\');'
            f'd.hasAttribute(\'open\')?d.removeAttribute(\'open\'):d.setAttribute(\'open\',\'\');" '
            f'style="font-size:9px;padding:0 4px;cursor:pointer;opacity:.5">▾</span>'
            f'</summary>'
            f'<div style="padding:2px 0 6px 4px">{links}</div>'
            f'</details>'
        )

    return (
        # ── CSS global admin (thème + layout sidebar) ─────────────────────────
        f'<style>'
        f'{ADMIN_CSS}'
        f'body{{margin:0!important;padding-left:192px!important;'
        f'background:var(--c-bg)!important;box-sizing:border-box}}'
        f'.pres-sidebar details summary::-webkit-details-marker{{display:none}}'
        f'#pres-hamburger{{display:none}}'
        f'#pres-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:998}}'
        f'#pres-overlay.show{{display:block}}'
        f'@media(max-width:700px){{'
        f'body{{padding-left:0!important;padding-top:52px!important}}'
        f'#pres-hamburger{{display:flex!important;position:fixed;top:8px;left:10px;z-index:1001;'
        f'background:var(--c-surface);border:1px solid var(--c-border);border-radius:6px;'
        f'width:38px;height:38px;align-items:center;justify-content:center;'
        f'font-size:20px;cursor:pointer;box-shadow:var(--sh-sm)}}'
        f'.pres-sidebar{{transform:translateX(-204px);transition:transform .22s ease}}'
        f'.pres-sidebar.open{{transform:translateX(0)}}'
        f'}}'
        f'</style>'

        # ── Favicon ───────────────────────────────────────────────────────────
        f'<script>(function(){{var l=document.createElement("link");l.rel="icon";'
        f'l.type="image/svg+xml";l.href="/assets/favicon.svg";document.head.appendChild(l);}})();</script>'

        # ── Hamburger mobile ──────────────────────────────────────────────────
        f'<button id="pres-hamburger" aria-label="Menu" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.toggle(\'open\');'
        f'document.getElementById(\'pres-overlay\').classList.toggle(\'show\')'
        f'">☰</button>'
        f'<div id="pres-overlay" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.remove(\'open\');'
        f'this.classList.remove(\'show\')'
        f'"></div>'

        # ── Sidebar ───────────────────────────────────────────────────────────
        f'<nav class="pres-sidebar" '
        f'style="position:fixed;top:0;left:0;width:192px;height:100vh;'
        f'background:{C_SLATE};'
        f'border-right:1px solid rgba(255,255,255,.06);'
        f'overflow-y:auto;z-index:1000;padding-bottom:24px;'
        f'display:flex;flex-direction:column;'
        f'box-shadow:2px 0 16px rgba(0,0,0,.2)">'

        # Logo admin
        f'<a href="/admin?token={token}" '
        f'style="display:flex;align-items:center;justify-content:center;'
        f'padding:16px 12px 14px;border-bottom:1px solid rgba(255,255,255,.07);'
        f'text-decoration:none;flex-shrink:0;'
        f'background:rgba(0,0,0,.15)">'
        f'<img src="/assets/logoadmin.svg" alt="Présence IA" style="width:152px;height:auto"></a>'

        # Navigation
        f'<div style="padding:12px 8px;flex:1">'
        f'{sections_html}'
        f'</div>'

        # Footer sidebar
        f'<div style="padding:8px;border-top:1px solid rgba(255,255,255,.07);flex-shrink:0">'
        f'<a href="https://presence-ia.com" target="_blank" rel="noopener" '
        f'style="display:block;width:100%;padding:7px 10px;'
        f'background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);'
        f'border-radius:5px;font-size:11px;color:rgba(255,255,255,.45);cursor:pointer;'
        f'text-align:left;text-decoration:none;white-space:nowrap;overflow:hidden;'
        f'text-overflow:ellipsis;margin-bottom:6px;box-sizing:border-box;'
        f'transition:background .12s,color .12s" '
        f'onmouseover="this.style.background=\'rgba(255,255,255,.1)\';this.style.color=\'rgba(255,255,255,.7)\'" '
        f'onmouseout="this.style.background=\'rgba(255,255,255,.05)\';this.style.color=\'rgba(255,255,255,.45)\'">🌐 Voir le site</a>'
        f'<button onclick="pipelineHistoryOpen(\'{token}\')" '
        f'style="width:100%;padding:7px 10px;background:rgba(255,255,255,.05);'
        f'border:1px solid rgba(255,255,255,.08);border-radius:5px;'
        f'font-size:11px;color:rgba(255,255,255,.45);cursor:pointer;text-align:left;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
        f'transition:background .12s,color .12s" '
        f'onmouseover="this.style.background=\'rgba(255,255,255,.1)\';this.style.color=\'rgba(255,255,255,.7)\'" '
        f'onmouseout="this.style.background=\'rgba(255,255,255,.05)\';this.style.color=\'rgba(255,255,255,.45)\'" '
        f'title="Journal des décisions de pilotage outbound">📋 Journal pilotage</button>'
        f'</div>'
        f'</nav>'

        # ── Scripts accordion + pipeline journal ──────────────────────────────
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

        # ── Drawer journal pilotage ───────────────────────────────────────────
        '<div id="ph-overlay" onclick="pipelineHistoryClose()" '
        'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1100"></div>'
        '<div id="ph-drawer" style="display:none;position:fixed;top:0;right:0;'
        'width:min(780px,95vw);height:100vh;background:#fff;'
        'box-shadow:-4px 0 32px rgba(57,68,85,.18);z-index:1101;'
        'overflow-y:auto;padding:24px 28px;box-sizing:border-box">'
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">'
        '<h2 style="margin:0;font-size:17px;font-weight:700;color:#1e2a3a">Journal de pilotage</h2>'
        '<button onclick="pipelineHistoryClose()" style="background:none;border:none;'
        'font-size:22px;cursor:pointer;color:#8a9ab0;line-height:1">&#x2715;</button>'
        '</div>'
        '<div id="ph-summary" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px"></div>'
        '<div id="ph-body">Chargement&#8230;</div>'
        '</div>'
        '<script>\n'
        'var _phRows=[];\n'
        'function pipelineHistoryOpen(tok){\n'
        '  document.getElementById("ph-overlay").style.display="block";\n'
        '  document.getElementById("ph-drawer").style.display="block";\n'
        '  document.getElementById("ph-body").innerHTML="Chargement&#8230;";\n'
        '  document.getElementById("ph-summary").innerHTML="";\n'
        '  fetch("/api/admin/pipeline-history?token="+tok)\n'
        '    .then(function(r){return r.json();})\n'
        '    .then(function(d){\n'
        '      _phRows=d.rows||[];\n'
        '      if(!_phRows.length){\n'
        '        document.getElementById("ph-body").innerHTML=\n'
        '          "<p style=\'color:#8a9ab0;text-align:center;margin-top:40px\'>'
        'Aucune donn\u00e9e \u2014 le journal se remplit au prochain run outbound.</p>";\n'
        '        return;\n'
        '      }\n'
        '      var last=_phRows[0];\n'
        '      var sColor={"running":"#16a34a","top_up":"#d97706","idle":"#5a6880","saturated":"#527fb3"};\n'
        '      var sc=sColor[last.statut]||"#8a9ab0";\n'
        '      function kpi(l,v,c){\n'
        '        var d=document.createElement("div");\n'
        '        d.style.cssText="background:#f8fafc;border:1px solid #dce4ef;border-radius:8px;padding:10px 14px;min-width:120px;box-shadow:0 1px 3px rgba(82,127,179,.06)";\n'
        '        d.innerHTML="<div style=\'font-size:10px;color:#8a9ab0;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px;font-weight:600\'>"+l+"</div>"\n'
        '          +"<div style=\'font-size:16px;font-weight:700;color:"+c+"\'>"+v+"</div>";\n'
        '        return d;\n'
        '      }\n'
        '      var sum=document.getElementById("ph-summary");\n'
        '      sum.innerHTML="";\n'
        '      [kpi("Mode",last.mode,"#394455"),\n'
        '       kpi("Statut",last.statut.toUpperCase(),sc),\n'
        '       kpi("Paire",last.paire,"#1e2a3a"),\n'
        '       kpi("Couverture",last.taux_couverture!=null?last.taux_couverture+"%":"---","#527fb3"),\n'
        '       kpi("Cap g\u00e9n\u00e9r\u00e9",last.cap_genere!=null?last.cap_genere:"---","#996d2e")\n'
        '      ].forEach(function(el){sum.appendChild(el);});\n'
        '      var sBg={"running":"#dcfce7","top_up":"#fef3c7","idle":"#f1f5f9","saturated":"#e8f0fb"};\n'
        '      var sFg={"running":"#14532d","top_up":"#78350f","idle":"#394455","saturated":"#1e3a5f"};\n'
        '      var tbl=document.createElement("table");\n'
        '      tbl.style.cssText="border-collapse:collapse;width:100%;font-size:13px";\n'
        '      tbl.innerHTML="<thead><tr style=\'background:#f8fafc\'>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:left;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>Date</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:left;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>Paire</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>Couverture</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:left;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>Statut</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>En file</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>N\u00e9cessaires</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#5a6880;font-weight:600;font-size:11px;border-bottom:1px solid #dce4ef\'>Cap</th>"\n'
        '        +"</tr></thead><tbody></tbody>";\n'
        '      var tbody=tbl.querySelector("tbody");\n'
        '      _phRows.forEach(function(r,i){\n'
        '        var tr=document.createElement("tr");\n'
        '        tr.style.background=i%2===0?"#fff":"#f8fafc";\n'
        '        tr.style.cursor="pointer";\n'
        '        tr.dataset.idx=i;\n'
        '        tr.addEventListener("click",function(){phDetail(parseInt(this.dataset.idx));});\n'
        '        var sbg=sBg[r.statut]||"#f1f5f9";\n'
        '        var sfg=sFg[r.statut]||"#394455";\n'
        '        tr.innerHTML=\n'
        '          "<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7;white-space:nowrap\'>"+r.ts+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7\'>"+r.paire+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7;text-align:right\'>"+(r.taux_couverture!=null?r.taux_couverture+"%":"---")+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7\'><span style=\'display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:"+sbg+";color:"+sfg+"\'>"+r.statut.toUpperCase()+"</span></td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7;text-align:right\'>"+(r.leads_en_file!=null?r.leads_en_file:"---")+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7;text-align:right\'>"+(r.leads_necessaires!=null?r.leads_necessaires:"---")+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #eaeff7;text-align:right;font-weight:600;color:#527fb3\'>"+(r.cap_genere!=null?r.cap_genere:"---")+"</td>";\n'
        '        tbody.appendChild(tr);\n'
        '      });\n'
        '      var wrap=document.getElementById("ph-body");\n'
        '      wrap.innerHTML="";\n'
        '      wrap.appendChild(tbl);\n'
        '      var hint=document.createElement("p");\n'
        '      hint.style.cssText="font-size:11px;color:#8a9ab0;margin-top:8px";\n'
        '      hint.textContent="Cliquer sur une ligne pour le d\u00e9tail complet.";\n'
        '      wrap.appendChild(hint);\n'
        '    })\n'
        '    .catch(function(e){document.getElementById("ph-body").innerHTML="Erreur: "+e;});\n'
        '}\n'
        'function pipelineHistoryClose(){\n'
        '  document.getElementById("ph-overlay").style.display="none";\n'
        '  document.getElementById("ph-drawer").style.display="none";\n'
        '}\n'
        'function phDetail(i){\n'
        '  var r=_phRows[i];\n'
        '  if(!r)return;\n'
        '  var lines=[\n'
        '    "Date : "+r.ts,\n'
        '    "Mode : "+r.mode,\n'
        '    "Paire : "+r.paire,\n'
        '    "Source slots : "+r.source_slots,\n'
        '    "--- Slots ---",\n'
        '    "Proches : "+r.slots_proches_remplis+"/"+r.slots_proches_total+" r\u00e9serv\u00e9s",\n'
        '    "Moyens : "+r.slots_moyens_remplis+"/"+r.slots_moyens_total+" r\u00e9serv\u00e9s",\n'
        '    "Lointains : "+r.slots_lointains_remplis+"/"+r.slots_lointains_total+" r\u00e9serv\u00e9s",\n'
        '    "Taux couverture : "+(r.taux_couverture!=null?r.taux_couverture+"%":"---"),\n'
        '    "--- Leads ---",\n'
        '    "En file : "+r.leads_en_file,\n'
        '    "N\u00e9cessaires : "+r.leads_necessaires,\n'
        '    "--- D\u00e9cision ---",\n'
        '    "Statut : "+r.statut.toUpperCase(),\n'
        '    "Cap g\u00e9n\u00e9r\u00e9 : "+r.cap_genere\n'
        '  ];\n'
        '  alert(lines.join("\\n"));\n'
        '}\n'
        '</scr'+'ipt>'
    )
