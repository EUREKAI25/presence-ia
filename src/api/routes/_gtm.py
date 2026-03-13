"""
GTM helpers — Google Tag Manager snippet + dataLayer events.
GTM_ID env var : "GTM-XXXXXXX" (vide = GTM désactivé).
"""
import os

_GTM_ID = None  # chargé lazily


def _get_id() -> str:
    global _GTM_ID
    if _GTM_ID is None:
        _GTM_ID = os.getenv("GTM_ID", "")
    return _GTM_ID


def gtm_head() -> str:
    """Snippet à injecter juste après <head>."""
    gid = _get_id()
    if not gid:
        return ""
    return (
        f"<!-- Google Tag Manager -->\n"
        f"<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':\n"
        f"new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],\n"
        f"j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=\n"
        f"'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);\n"
        f"}})(window,document,'script','dataLayer','{gid}');</script>\n"
        f"<!-- End Google Tag Manager -->"
    )


def gtm_body() -> str:
    """Snippet noscript à injecter juste après <body>."""
    gid = _get_id()
    if not gid:
        return ""
    return (
        f'<!-- Google Tag Manager (noscript) -->\n'
        f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gid}" '
        f'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n'
        f'<!-- End Google Tag Manager (noscript) -->'
    )


def gtm_push(event: str, **kwargs) -> str:
    """
    Génère un bloc <script> qui pousse un event dans dataLayer.
    Ex: gtm_push("landing_visit", city="Rennes", profession="couvreur")
    """
    gid = _get_id()
    if not gid:
        return ""
    import json
    payload = {"event": event, **kwargs}
    return f"<script>window.dataLayer=window.dataLayer||[];dataLayer.push({json.dumps(payload, ensure_ascii=False)});</script>"
