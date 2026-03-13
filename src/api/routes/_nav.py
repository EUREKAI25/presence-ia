"""Nav admin partagé — importé par toutes les pages admin.

Sidebar fixe à gauche, accordéons fermés par défaut (sauf section active).
Favicon injecté automatiquement via script inline.
"""
import os


def admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


def admin_nav(token: str, active: str = "") -> str:
    sections = [
        ("PROSPECTION", [
            ("v3",          "Contacts"),
            ("prospection", "Campagnes"),
            ("scan",        "Scan IA"),
            ("send-queue",  "File d'envoi"),
            ("analytics",   "Analytics"),
            ("scheduler",   "Planificateur"),
        ]),
        ("CRM", [
            ("crm",                  "Pipeline CRM"),
            ("crm/closers",          "Closers"),
            ("crm/closer-messages",  "Messages recrutement"),
            ("crm/closer-content",   "Contenu portail"),
            ("crm/slots",            "Créneaux RDV"),
        ]),
        ("CONTENU", [
            ("templates",   "Messages"),
            ("sequences",   "Séquences"),
            ("content",     "Textes pages"),
            ("cms",         "Blocs CMS"),
            ("offers",      "Offres"),
        ]),
        ("SITE", [
            ("evidence",    "Preuves"),
            ("headers",     "Headers"),
            ("theme",       "Thème"),
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
        # Ouvrir uniquement la section contenant la page active — toutes les autres fermées
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
        # Layout : sidebar fixe 180px desktop, drawer mobile
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
        # Favicon injecté dynamiquement
        f'<script>(function(){{var l=document.createElement("link");l.rel="icon";'
        f'l.type="image/png";l.href="/assets/favicon.png";document.head.appendChild(l);}})();</script>'
        # Hamburger (mobile)
        f'<button id="pres-hamburger" aria-label="Menu" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.toggle(\'open\');'
        f'document.getElementById(\'pres-overlay\').classList.toggle(\'show\')'
        f'">☰</button>'
        # Overlay (mobile)
        f'<div id="pres-overlay" onclick="'
        f'document.querySelector(\'.pres-sidebar\').classList.remove(\'open\');'
        f'this.classList.remove(\'show\')'
        f'"></div>'
        # Sidebar
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
        f'</nav>'
        # Accordéon exclusif : un seul ouvert à la fois
        f'<script>'
        f'(function(){{'
        f'  function initAcc(){{'
        f'    document.querySelectorAll(".pres-acc summary").forEach(function(s){{'
        f'      s.addEventListener("click",function(e){{'
        f'        var me=s.closest("details");'
        f'        if(me.hasAttribute("open")) return;'  # va se fermer, laisser faire
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
    )
