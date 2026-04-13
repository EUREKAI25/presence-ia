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
        bg     = "#1f0a0e" if is_active else "transparent"
        color  = "#e94560" if is_active else "#c9d1d9"
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
            f'color:#6b7280;letter-spacing:.08em;list-style:none;display:flex;align-items:center;'
            f'justify-content:space-between;border-radius:4px;user-select:none;'
            f'background:transparent;outline:none" '
            f'onmouseover="this.style.color=\'#9ca3af\'" '
            f'onmouseout="this.style.color=\'#6b7280\'">'
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
        f'l.type="image/svg+xml";l.href="/assets/favicon.svg";document.head.appendChild(l);}})();</script>'
        f'<button id="pres-hamburger" aria-label="Menu" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.toggle(\'open\');'
        f'document.getElementById(\'pres-overlay\').classList.toggle(\'show\')'
        f'">☰</button>'
        f'<div id="pres-overlay" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.remove(\'open\');'
        f'this.classList.remove(\'show\')'
        f'"></div>'
        f'<nav class="pres-sidebar" style="position:fixed;top:0;left:0;width:180px;height:100vh;'
        f'background:#000;border-right:1px solid #1f2937;overflow-y:auto;z-index:1000;'
        f'padding-bottom:24px;display:flex;flex-direction:column">'
        f'<a href="/admin?token={token}" '
        f'style="display:flex;align-items:center;justify-content:center;'
        f'padding:14px 12px;border-bottom:1px solid #1f2937;text-decoration:none;flex-shrink:0">'
        f'<img src="/assets/logoadmin.svg" alt="PRESENCE_IA" style="width:148px;height:auto"></a>'
        f'<div style="padding:10px 8px;flex:1">'
        f'{sections_html}'
        f'</div>'
        f'<div style="padding:8px;border-top:1px solid #1f2937;flex-shrink:0">'
        f'<a href="https://presence-ia.com" target="_blank" rel="noopener" '
        f'style="display:block;width:100%;padding:7px 8px;background:transparent;border:1px solid #374151;'
        f'border-radius:5px;font-size:11px;color:#9ca3af;cursor:pointer;text-align:left;'
        f'text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
        f'margin-bottom:6px;box-sizing:border-box">🌐 Voir le site</a>'
        f'<button onclick="pipelineHistoryOpen(\'{token}\')" '
        f'style="width:100%;padding:7px 8px;background:transparent;border:1px solid #374151;'
        f'border-radius:5px;font-size:11px;color:#9ca3af;cursor:pointer;text-align:left;'
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
        '<div id="ph-overlay" onclick="pipelineHistoryClose()" '
        'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1100"></div>'
        '<div id="ph-drawer" style="display:none;position:fixed;top:0;right:0;'
        'width:min(780px,95vw);height:100vh;background:#fff;'
        'box-shadow:-4px 0 24px rgba(0,0,0,.12);z-index:1101;'
        'overflow-y:auto;padding:24px 28px;box-sizing:border-box">'
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">'
        '<h2 style="margin:0;font-size:17px;font-weight:700;color:#111">Journal de pilotage</h2>'
        '<button onclick="pipelineHistoryClose()" style="background:none;border:none;'
        'font-size:22px;cursor:pointer;color:#6b7280;line-height:1">&#x2715;</button>'
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
        '          "<p style=\'color:#9ca3af;text-align:center;margin-top:40px\'>'
        'Aucune donn\u00e9e \u2014 le journal se remplit au prochain run outbound.</p>";\n'
        '        return;\n'
        '      }\n'
        '      var last=_phRows[0];\n'
        '      var sColor={"running":"#10b981","top_up":"#f59e0b","idle":"#6b7280","saturated":"#3b82f6"};\n'
        '      var sc=sColor[last.statut]||"#9ca3af";\n'
        '      function kpi(l,v,c){\n'
        '        var d=document.createElement("div");\n'
        '        d.style.cssText="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px 14px;min-width:120px";\n'
        '        d.innerHTML="<div style=\'font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px\'>"+l+"</div>"\n'
        '          +"<div style=\'font-size:16px;font-weight:700;color:"+c+"\'>"+v+"</div>";\n'
        '        return d;\n'
        '      }\n'
        '      var sum=document.getElementById("ph-summary");\n'
        '      sum.innerHTML="";\n'
        '      [kpi("Mode",last.mode,"#1e3a5f"),\n'
        '       kpi("Statut",last.statut.toUpperCase(),sc),\n'
        '       kpi("Paire",last.paire,"#374151"),\n'
        '       kpi("Couverture",last.taux_couverture!=null?last.taux_couverture+"%":"---","#6366f1"),\n'
        '       kpi("Cap g\u00e9n\u00e9r\u00e9",last.cap_genere!=null?last.cap_genere:"---","#0ea5e9")\n'
        '      ].forEach(function(el){sum.appendChild(el);});\n'
        '      var sBg={"running":"#d1fae5","top_up":"#fef3c7","idle":"#f3f4f6","saturated":"#dbeafe"};\n'
        '      var sFg={"running":"#065f46","top_up":"#92400e","idle":"#374151","saturated":"#1e40af"};\n'
        '      var tbl=document.createElement("table");\n'
        '      tbl.style.cssText="border-collapse:collapse;width:100%;font-size:13px";\n'
        '      tbl.innerHTML="<thead><tr style=\'background:#f9fafb\'>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:left;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>Date</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:left;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>Paire</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>Couverture</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:left;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>Statut</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>En file</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>N\u00e9cessaires</th>"\n'
        '        +"<th style=\'padding:8px 10px;text-align:right;color:#6b7280;font-weight:600;font-size:11px;border-bottom:1px solid #e5e7eb\'>Cap</th>"\n'
        '        +"</tr></thead><tbody></tbody>";\n'
        '      var tbody=tbl.querySelector("tbody");\n'
        '      _phRows.forEach(function(r,i){\n'
        '        var tr=document.createElement("tr");\n'
        '        tr.style.background=i%2===0?"#fff":"#f9fafb";\n'
        '        tr.style.cursor="pointer";\n'
        '        tr.dataset.idx=i;\n'
        '        tr.addEventListener("click",function(){phDetail(parseInt(this.dataset.idx));});\n'
        '        var sbg=sBg[r.statut]||"#f3f4f6";\n'
        '        var sfg=sFg[r.statut]||"#374151";\n'
        '        tr.innerHTML=\n'
        '          "<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6;white-space:nowrap\'>"+r.ts+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6\'>"+r.paire+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right\'>"+(r.taux_couverture!=null?r.taux_couverture+"%":"---")+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6\'><span style=\'display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;background:"+sbg+";color:"+sfg+"\'>"+r.statut.toUpperCase()+"</span></td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right\'>"+(r.leads_en_file!=null?r.leads_en_file:"---")+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right\'>"+(r.leads_necessaires!=null?r.leads_necessaires:"---")+"</td>"\n'
        '          +"<td style=\'padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:right;font-weight:600\'>"+(r.cap_genere!=null?r.cap_genere:"---")+"</td>";\n'
        '        tbody.appendChild(tr);\n'
        '      });\n'
        '      var wrap=document.getElementById("ph-body");\n'
        '      wrap.innerHTML="";\n'
        '      wrap.appendChild(tbl);\n'
        '      var hint=document.createElement("p");\n'
        '      hint.style.cssText="font-size:11px;color:#9ca3af;margin-top:8px";\n'
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
