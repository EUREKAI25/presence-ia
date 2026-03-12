"""Nav admin partagé — importé par toutes les pages admin."""
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
        bg = "#e94560" if is_active else "transparent"
        color = "#fff" if is_active else "#374151"
        weight = "600" if is_active else "400"
        return (f'<a href="/admin/{slug}?token={token}" '
                f'style="padding:7px 12px;border-radius:5px;text-decoration:none;'
                f'font-size:12px;font-weight:{weight};background:{bg};color:{color};white-space:nowrap">'
                f'{label}</a>')

    sections_html = ""
    for sec_label, tabs in sections:
        links = "".join(_link(slug, label) for slug, label in tabs)
        sections_html += (
            f'<div style="display:flex;align-items:center;gap:2px;padding:0 8px;'
            f'border-left:1px solid #e5e7eb">'
            f'<span style="font-size:10px;color:#9ca3af;font-weight:600;'
            f'letter-spacing:.05em;margin-right:4px;white-space:nowrap">{sec_label}</span>'
            f'{links}</div>'
        )

    return (
        f'<div style="background:#fff;border-bottom:2px solid #e5e7eb;padding:0 16px;'
        f'display:flex;align-items:center;gap:0;flex-wrap:wrap;min-height:48px">'
        f'<a href="/admin?token={token}" style="color:#e94560;font-weight:700;font-size:15px;'
        f'padding:12px 16px 12px 0;text-decoration:none;white-space:nowrap;margin-right:8px">'
        f'PRESENCE_IA</a>'
        f'{sections_html}'
        f'</div>'
    )
