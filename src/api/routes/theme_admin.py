"""
Admin thème — visualiser et éditer le ThemePreset stocké en DB.

Routes :
  GET  /admin/theme          → UI d'édition du thème
  POST /api/admin/theme      → Sauvegarde le ThemePreset
  POST /api/admin/theme/reset → Réinitialise au preset par défaut
"""
import json, os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_theme, db_upsert_theme, _DEFAULT_THEME_PRESET, SessionLocal

router = APIRouter()

_STYLE_PRESETS = ["rounded", "flat", "elevated", "minimal", "bold", "dark"]
_ANIMATIONS    = ["none", "subtle", "moderate", "rich"]
_BG_PROMINENCE = ["none", "subtle", "strong", "dominant"]


def _require_admin(request: Request):
    token = request.query_params.get("token", "") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        from fastapi import HTTPException
        raise HTTPException(403, "Accès refusé")


# ── GET /admin/theme ──────────────────────────────────────────────────────────

@router.get("/admin/theme", response_class=HTMLResponse)
def admin_theme(request: Request):
    _require_admin(request)
    with SessionLocal() as db:
        theme = db_get_theme(db)

    cs      = theme.get("color_system", {})
    primary = cs.get("primary",   {})
    sec     = cs.get("secondary", {})

    def opt(lst, current):
        return "\n".join(
            f'<option value="{v}"{"selected" if v == current else ""}>{v}</option>'
            for v in lst
        )

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Admin — Thème</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; }}
    .topbar {{ background: #1a1a2e; color: #fff; padding: 12px 24px; display: flex; align-items: center; gap: 16px; }}
    .topbar a {{ color: #aaa; text-decoration: none; font-size: 14px; }}
    .topbar a:hover {{ color: #fff; }}
    .container {{ max-width: 900px; margin: 32px auto; padding: 0 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 24px; }}
    .card {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .card h2 {{ font-size: 15px; font-weight: 600; color: #555; margin-bottom: 16px; text-transform: uppercase; letter-spacing: .5px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .field label {{ display: block; font-size: 13px; font-weight: 500; color: #555; margin-bottom: 4px; }}
    .field input, .field select {{ width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }}
    .field input:focus, .field select:focus {{ outline: none; border-color: #667eea; }}
    .color-row {{ display: flex; align-items: center; gap: 8px; }}
    .color-row input[type=color] {{ width: 40px; height: 38px; padding: 2px; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; }}
    .color-row input[type=text] {{ flex: 1; }}
    .btn {{ padding: 10px 24px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; font-weight: 600; }}
    .btn-primary {{ background: #667eea; color: #fff; }}
    .btn-secondary {{ background: #f0f0f0; color: #555; }}
    .btn:hover {{ opacity: .9; }}
    .actions {{ display: flex; gap: 12px; }}
    .swatch {{ display: inline-block; width: 16px; height: 16px; border-radius: 50%; border: 1px solid rgba(0,0,0,.1); vertical-align: middle; margin-right: 6px; }}
    .notice {{ background: #fffbeb; border: 1px solid #f59e0b; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #92400e; margin-bottom: 24px; }}
  </style>
</head>
<body>
  <div class="topbar">
    <strong>PRESENCE_IA</strong>
    <a href="/admin/content">Contenu</a>
    <a href="/admin/theme">Thème</a>
    <a href="/admin/headers">Visuels</a>
  </div>

  <div class="container">
    <h1>Thème — Paramétrage visuel</h1>

    <div class="notice">
      La palette de couleurs a été extraite de <strong>myhealthprac.com</strong> via ThemeComposer.
      Le style preset est choisi indépendamment. Tout est éditable ci-dessous.
    </div>

    <form id="themeForm">
      <!-- Identité -->
      <div class="card">
        <h2>Identité</h2>
        <div class="grid2">
          <div class="field">
            <label>Nom du thème</label>
            <input type="text" name="name" value="{theme.get('name', '')}">
          </div>
          <div class="field">
            <label>Style preset</label>
            <select name="style_preset_name">{opt(_STYLE_PRESETS, theme.get('style_preset_name', 'rounded'))}</select>
          </div>
          <div class="field">
            <label>Animation</label>
            <select name="animation_style">{opt(_ANIMATIONS, theme.get('animation_style', 'subtle'))}</select>
          </div>
          <div class="field">
            <label>Arrière-plan hero</label>
            <select name="bg_prominence">{opt(_BG_PROMINENCE, theme.get('bg_prominence', 'strong'))}</select>
          </div>
        </div>
      </div>

      <!-- Couleurs -->
      <div class="card">
        <h2>Couleurs — Palette</h2>
        <div class="grid2">
          <div class="field">
            <label>Primaire (base)</label>
            <div class="color-row">
              <input type="text" name="primary_base" value="{primary.get('base', 'rgb(176,144,111)')}" placeholder="rgb(...)">
            </div>
          </div>
          <div class="field">
            <label>Primaire (clair)</label>
            <input type="text" name="primary_light" value="{primary.get('light', 'rgb(204,188,172)')}" placeholder="rgb(...)">
          </div>
          <div class="field">
            <label>Primaire (foncé)</label>
            <input type="text" name="primary_dark" value="{primary.get('dark', 'rgb(124,72,34)')}" placeholder="rgb(...)">
          </div>
          <div class="field">
            <label>Secondaire (base)</label>
            <input type="text" name="secondary_base" value="{sec.get('base', 'rgb(152,108,67)')}" placeholder="rgb(...)">
          </div>
          <div class="field">
            <label>Secondaire (clair)</label>
            <input type="text" name="secondary_light" value="{sec.get('light', 'rgb(204,188,172)')}" placeholder="rgb(...)">
          </div>
          <div class="field">
            <label>Secondaire (foncé)</label>
            <input type="text" name="secondary_dark" value="{sec.get('dark', 'rgb(80,36,16)')}" placeholder="rgb(...)">
          </div>
        </div>
      </div>

      <!-- Typographie -->
      <div class="card">
        <h2>Typographie</h2>
        <div class="grid2">
          <div class="field">
            <label>Police titres</label>
            <input type="text" name="font_family_headings" value="{theme.get('font_family_headings', 'Inter')}">
          </div>
          <div class="field">
            <label>Police corps</label>
            <input type="text" name="font_family_body" value="{theme.get('font_family_body', 'Inter')}">
          </div>
          <div class="field" style="grid-column:span 2">
            <label>Google Fonts URL (optionnel)</label>
            <input type="text" name="font_google_url" value="{theme.get('font_google_url', '')}" placeholder="https://fonts.googleapis.com/...">
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="actions">
        <button type="submit" class="btn btn-primary">Enregistrer</button>
        <button type="button" class="btn btn-secondary" onclick="resetTheme()">Réinitialiser (myhealthprac)</button>
        <a href="/" target="_blank" class="btn btn-secondary" style="text-decoration:none">Aperçu home →</a>
        <a href="/landing" target="_blank" class="btn btn-secondary" style="text-decoration:none">Aperçu landing →</a>
      </div>
    </form>
  </div>

  <script>
    const token = new URLSearchParams(location.search).get("token") || "";
    const qs = token ? "?token=" + token : "";

    document.getElementById("themeForm").addEventListener("submit", async (e) => {{
      e.preventDefault();
      const fd = new FormData(e.target);
      const data = Object.fromEntries(fd.entries());
      const r = await fetch("/api/admin/theme" + qs, {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify(data),
      }});
      const j = await r.json();
      if (j.ok) alert("Thème enregistré ✓"); else alert("Erreur : " + (j.error || "inconnue"));
    }});

    async function resetTheme() {{
      if (!confirm("Réinitialiser au preset myhealthprac ?")) return;
      const r = await fetch("/api/admin/theme/reset" + qs, {{ method: "POST" }});
      const j = await r.json();
      if (j.ok) location.reload(); else alert("Erreur");
    }}
  </script>
</body>
</html>""")


# ── POST /api/admin/theme ─────────────────────────────────────────────────────

@router.post("/api/admin/theme")
async def save_theme(request: Request):
    _require_admin(request)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)

    with SessionLocal() as db:
        current = db_get_theme(db)

    # Mettre à jour uniquement les champs envoyés
    current["name"]             = data.get("name", current.get("name", ""))
    current["style_preset_name"] = data.get("style_preset_name", current.get("style_preset_name", "rounded"))
    current["animation_style"]  = data.get("animation_style", current.get("animation_style", "subtle"))
    current["bg_prominence"]    = data.get("bg_prominence", current.get("bg_prominence", "strong"))
    current["font_family_headings"] = data.get("font_family_headings", current.get("font_family_headings", "Inter"))
    current["font_family_body"]     = data.get("font_family_body", current.get("font_family_body", "Inter"))
    current["font_google_url"]      = data.get("font_google_url", current.get("font_google_url", ""))

    # Couleurs
    cs = current.setdefault("color_system", {})
    cs.setdefault("primary",   {})
    cs.setdefault("secondary", {})
    if data.get("primary_base"):   cs["primary"]["base"]    = data["primary_base"]
    if data.get("primary_light"):  cs["primary"]["light"]   = data["primary_light"]
    if data.get("primary_dark"):   cs["primary"]["dark"]    = data["primary_dark"]
    if data.get("secondary_base"): cs["secondary"]["base"]  = data["secondary_base"]
    if data.get("secondary_light"):cs["secondary"]["light"] = data["secondary_light"]
    if data.get("secondary_dark"): cs["secondary"]["dark"]  = data["secondary_dark"]

    with SessionLocal() as db:
        db_upsert_theme(db, current)

    # Invalider le cache SCSS (si le renderer l'a compilé)
    try:
        from page_builder.src.renderer.css import invalidate_scss_cache
        invalidate_scss_cache()
    except Exception:
        pass

    return JSONResponse({"ok": True})


# ── POST /api/admin/theme/reset ───────────────────────────────────────────────

@router.post("/api/admin/theme/reset")
def reset_theme(request: Request):
    _require_admin(request)
    with SessionLocal() as db:
        db_upsert_theme(db, _DEFAULT_THEME_PRESET.copy())
    return JSONResponse({"ok": True})
