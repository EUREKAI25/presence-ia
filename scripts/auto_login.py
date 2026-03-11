"""
Login automatique Playwright — renouvelle toutes les sessions sans intervention humaine.
Lancé par cron toutes les 3 semaines ou via : python scripts/auto_login.py

Credentials lus depuis .env :
  CHATGPT_FREE_EMAIL / CHATGPT_FREE_PASSWORD
  CHATGPT_PAID_EMAIL / CHATGPT_PAID_PASSWORD
  CLAUDE_FREE_EMAIL  / CLAUDE_FREE_PASSWORD
  CLAUDE_PAID_EMAIL  / CLAUDE_PAID_PASSWORD
  GEMINI_FREE_EMAIL  / GEMINI_FREE_PASSWORD
  GEMINI_PAID_EMAIL  / GEMINI_PAID_PASSWORD
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)


# ── ChatGPT ───────────────────────────────────────────────────────────

async def login_chatgpt(page, email: str, password: str):
    await page.goto("https://chatgpt.com/auth/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    # Bouton "Log in"
    try:
        await page.click('button:has-text("Log in")', timeout=8000)
        await page.wait_for_timeout(1500)
    except Exception:
        pass

    await page.fill('input[name="username"], input[type="email"]', email)
    await page.click('button[type="submit"], button:has-text("Continue")')
    await page.wait_for_timeout(1500)

    await page.fill('input[name="password"], input[type="password"]', password)
    await page.click('button[type="submit"], button:has-text("Continue")')
    await page.wait_for_timeout(4000)

    # Attendre la page principale
    await page.wait_for_url("**/", timeout=20000)
    log.info("chatgpt — login OK")


# ── Claude ────────────────────────────────────────────────────────────

async def login_claude(page, email: str, password: str):
    await page.goto("https://claude.ai/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    await page.fill('input[type="email"]', email)
    await page.click('button[type="submit"], button:has-text("Continue")')
    await page.wait_for_timeout(1500)

    await page.fill('input[type="password"]', password)
    await page.click('button[type="submit"], button:has-text("Continue")')
    await page.wait_for_timeout(4000)

    await page.wait_for_url("**claude.ai/**", timeout=20000)
    log.info("claude — login OK")


# ── Gemini (Google) ───────────────────────────────────────────────────

async def login_gemini(page, email: str, password: str):
    """
    Google détecte les headless basiques → on utilise un user-agent réaliste
    et on désactive les flags headless détectables.
    Fonctionne avec des comptes Google sans 2FA (comptes dédiés).
    """
    await page.goto(
        "https://accounts.google.com/signin/v2/identifier"
        "?continue=https://gemini.google.com/",
        wait_until="domcontentloaded"
    )
    await page.wait_for_timeout(2000)

    await page.fill('input[type="email"]', email)
    await page.click('#identifierNext button, button:has-text("Next")')
    await page.wait_for_timeout(2000)

    await page.fill('input[type="password"]', password)
    await page.click('#passwordNext button, button:has-text("Next")')
    await page.wait_for_timeout(5000)

    # Accepter CGU si première connexion
    try:
        await page.click('button:has-text("Accept")', timeout=5000)
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    await page.wait_for_url("**gemini.google.com/**", timeout=30000)
    log.info("gemini — login OK")


# ── Runner principal ──────────────────────────────────────────────────

PLATFORMS = {
    "chatgpt": {
        "login_fn": login_chatgpt,
        "tiers": {
            "free": ("CHATGPT_FREE_EMAIL", "CHATGPT_FREE_PASSWORD"),
            "paid": ("CHATGPT_PAID_EMAIL", "CHATGPT_PAID_PASSWORD"),
        },
    },
    "claude": {
        "login_fn": login_claude,
        "tiers": {
            "free": ("CLAUDE_FREE_EMAIL", "CLAUDE_FREE_PASSWORD"),
            "paid": ("CLAUDE_PAID_EMAIL", "CLAUDE_PAID_PASSWORD"),
        },
    },
    "gemini": {
        "login_fn": login_gemini,
        "tiers": {
            "free": ("GEMINI_FREE_EMAIL", "GEMINI_FREE_PASSWORD"),
            "paid": ("GEMINI_PAID_EMAIL", "GEMINI_PAID_PASSWORD"),
        },
    },
}


async def _login_one(platform: str, tier: str, email_key: str, pass_key: str,
                     login_fn, pw) -> dict:
    email    = os.getenv(email_key)
    password = os.getenv(pass_key)
    out_file = SESSIONS_DIR / f"{platform}_{tier}.json"

    if not email or not password:
        log.warning("  %s/%s — credentials manquants (%s / %s), skip", platform, tier, email_key, pass_key)
        return {"platform": platform, "tier": tier, "ok": False, "error": "credentials manquants"}

    log.info("  %s/%s — connexion en cours (%s)…", platform, tier, email)

    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="fr-FR",
    )
    # Masquer Playwright aux détecteurs
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    page = await ctx.new_page()
    try:
        await login_fn(page, email, password)
        await ctx.storage_state(path=str(out_file))
        log.info("  ✅ %s/%s → session sauvegardée : %s", platform, tier, out_file)
        return {"platform": platform, "tier": tier, "ok": True, "error": None}
    except Exception as e:
        log.error("  ❌ %s/%s — échec : %s", platform, tier, e)
        return {"platform": platform, "tier": tier, "ok": False, "error": str(e)}
    finally:
        await browser.close()


async def run_all(platforms_filter=None, tiers_filter=None):
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as pw:
        for platform, cfg in PLATFORMS.items():
            if platforms_filter and platform not in platforms_filter:
                continue
            for tier, (email_key, pass_key) in cfg["tiers"].items():
                if tiers_filter and tier not in tiers_filter:
                    continue
                r = await _login_one(platform, tier, email_key, pass_key, cfg["login_fn"], pw)
                results.append(r)

    ok  = [r for r in results if r["ok"]]
    err = [r for r in results if not r["ok"]]
    log.info("\n=== Résultat : %d/%d sessions créées ===", len(ok), len(results))
    for r in err:
        log.error("  ✗ %s/%s : %s", r["platform"], r["tier"], r["error"])
    return results


if __name__ == "__main__":
    # Usage :
    #   python scripts/auto_login.py                    → tous
    #   python scripts/auto_login.py chatgpt            → ChatGPT free + paid
    #   python scripts/auto_login.py chatgpt free       → ChatGPT free seulement
    platforms_filter = [sys.argv[1]] if len(sys.argv) > 1 else None
    tiers_filter     = [sys.argv[2]] if len(sys.argv) > 2 else None
    asyncio.run(run_all(platforms_filter, tiers_filter))
