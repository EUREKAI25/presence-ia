"""
Admin login / logout — authentification par mot de passe + cookie de session.

GET  /admin/login  → page formulaire
POST /admin/login  → valide ADMIN_PASSWORD, pose le cookie admin_token, redirige vers /admin
GET  /admin/logout → efface le cookie, redirige vers /admin/login
"""
import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["Auth"])


def _admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


def _admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "zorbec")


_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;
  padding:48px 40px;width:100%;max-width:380px;text-align:center}
.logo{font-size:1.4rem;font-weight:bold;color:#fff;margin-bottom:4px}
.logo span{color:#e94560}
.sub{color:#555;font-size:13px;margin-bottom:36px}
label{display:block;text-align:left;color:#9ca3af;font-size:12px;margin-bottom:6px}
input[type=password]{width:100%;background:#0f0f1a;border:1px solid #2a2a4e;
  color:#e8e8f0;border-radius:6px;padding:12px 14px;font-size:15px;
  font-family:inherit;outline:none}
input[type=password]:focus{border-color:#e94560}
.btn{display:block;width:100%;margin-top:20px;background:#e94560;color:#fff;
  border:none;padding:14px;border-radius:8px;font-size:15px;font-weight:700;
  cursor:pointer;transition:opacity .2s}
.btn:hover{opacity:.88}
.err{color:#e94560;font-size:13px;margin-top:14px}
"""


@router.get("/admin/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    err_html = f'<p class="err">Mot de passe incorrect.</p>' if error else ""
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connexion — PRESENCE_IA</title>
<style>{_CSS}</style>
</head><body>
<div class="card">
  <div class="logo">Présence<span>IA</span></div>
  <p class="sub">Espace administration</p>
  <form method="POST" action="/admin/login">
    <label>Mot de passe</label>
    <input type="password" name="password" autofocus placeholder="••••••••">
    <button class="btn" type="submit">Connexion →</button>
  </form>
  {err_html}
</div>
</body></html>""")


@router.post("/admin/login")
async def login_submit(request: Request):
    form = await request.form()
    password = form.get("password", "")

    if password != _admin_password():
        resp = RedirectResponse("/admin/login?error=1", status_code=303)
        return resp

    # Mot de passe OK → pose le cookie admin_token
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(
        key="admin_token",
        value=_admin_token(),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,   # 7 jours
        secure=False,                 # True en prod HTTPS (nginx s'en charge)
    )
    return resp


@router.get("/admin/logout")
def logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie("admin_token")
    return resp
