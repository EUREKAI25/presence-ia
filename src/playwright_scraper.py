"""
Playwright scraper — résultats identiques aux interfaces web
Supporte free + paid pour ChatGPT, Claude, Gemini

Sessions : /opt/presence-ia/sessions/{platform}_{tier}.json
  → créées une fois via scripts/setup_sessions.py
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", Path(__file__).parent.parent / "sessions"))
TIMEOUT = 60_000   # 60s max par requête (les IA peuvent être lentes)
STREAM_IDLE = 4_000  # 4s sans nouveau texte = réponse terminée

Tier = Literal["free", "paid"]

# ── Sélecteurs par plateforme ─────────────────────────────────────────

SELECTORS = {
    "chatgpt": {
        "url":       "https://chatgpt.com/",
        "new_chat":  'a[href="/"]',
        "input":     "#prompt-textarea",
        "send":      '[data-testid="send-button"]',
        "response":  '[data-message-author-role="assistant"] .markdown',
        "stop":      '[data-testid="stop-button"]',          # streaming en cours
        "model_label": '[data-testid="model-switcher-dropdown-button"]',
    },
    "claude": {
        "url":       "https://claude.ai/new",
        "new_chat":  None,   # l'URL /new suffit
        "input":     'div.ProseMirror[contenteditable="true"]',
        "send":      'button[aria-label="Send Message"]',
        "response":  'div[data-is-streaming="false"] .font-claude-message, .claude-message',
        "stop":      'button[aria-label="Stop"]',
        "model_label": 'button[data-testid="model-selector-trigger"]',
    },
    "gemini": {
        "url":       "https://gemini.google.com/app",
        "new_chat":  'a[aria-label="New chat"]',
        "input":     'rich-textarea .ql-editor, textarea[aria-label]',
        "send":      'button[aria-label="Send message"], button.send-button',
        "response":  'model-response .response-content, message-content',
        "stop":      'button[aria-label="Stop response"]',
        "model_label": '.model-name, [data-model-id]',
    },
}


# ── Runner principal ──────────────────────────────────────────────────

async def _scrape(platform: str, tier: Tier, query: str) -> dict:
    """
    Retourne {
        "platform": str, "tier": str, "model": str|None,
        "text": str, "ok": bool, "error": str|None
    }
    """
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    session_file = SESSIONS_DIR / f"{platform}_{tier}.json"
    sel = SELECTORS[platform]

    if not session_file.exists():
        return {
            "platform": platform, "tier": tier, "model": None, "text": "",
            "ok": False, "error": f"Session manquante : {session_file} — lance scripts/setup_sessions.py"
        }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx     = await browser.new_context(
            storage_state=str(session_file),
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        )
        page = await ctx.new_page()

        try:
            # 1. Navigation
            await page.goto(sel["url"], wait_until="domcontentloaded", timeout=TIMEOUT)
            await page.wait_for_timeout(2000)

            # Nouveau chat si besoin
            if sel["new_chat"]:
                try:
                    await page.click(sel["new_chat"], timeout=5000)
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass

            # 2. Saisie de la requête
            input_el = await page.wait_for_selector(sel["input"], timeout=15000)
            await input_el.click()
            await page.wait_for_timeout(300)
            await input_el.fill(query)
            await page.wait_for_timeout(500)

            # Envoi (Enter ou bouton)
            try:
                send_btn = page.locator(sel["send"]).last
                if await send_btn.is_visible(timeout=3000):
                    await send_btn.click()
                else:
                    await input_el.press("Enter")
            except Exception:
                await input_el.press("Enter")

            # 3. Attente fin de streaming (poll toutes les 500ms, idle 4s = terminé)
            response_text = await _wait_for_response(page, sel, timeout_ms=TIMEOUT)

            # 4. Nom du modèle
            model_name = None
            try:
                m = page.locator(sel["model_label"]).first
                if await m.is_visible(timeout=2000):
                    model_name = (await m.inner_text()).strip()
            except Exception:
                pass

            return {
                "platform": platform, "tier": tier, "model": model_name,
                "text": response_text, "ok": bool(response_text), "error": None
            }

        except PWTimeout as e:
            log.error("[playwright] %s/%s timeout: %s", platform, tier, e)
            return {"platform": platform, "tier": tier, "model": None, "text": "",
                    "ok": False, "error": f"TIMEOUT — sélecteur probablement changé : {e}"}
        except Exception as e:
            log.error("[playwright] %s/%s erreur: %s", platform, tier, e)
            return {"platform": platform, "tier": tier, "model": None, "text": "",
                    "ok": False, "error": str(e)}
        finally:
            await browser.close()


async def _wait_for_response(page, sel: dict, timeout_ms: int) -> str:
    """Poll la réponse jusqu'à ce que le streaming s'arrête (4s sans changement)."""
    from playwright.async_api import TimeoutError as PWTimeout
    elapsed   = 0
    last_text = ""
    idle_for  = 0

    while elapsed < timeout_ms:
        await page.wait_for_timeout(500)
        elapsed += 500

        try:
            els = page.locator(sel["response"])
            count = await els.count()
            if count == 0:
                continue
            current = await els.last.inner_text()
        except Exception:
            continue

        if current == last_text:
            idle_for += 500
            if idle_for >= STREAM_IDLE and last_text:
                return last_text
        else:
            idle_for  = 0
            last_text = current

        # Stop button disparu = streaming terminé
        try:
            stop = page.locator(sel["stop"])
            if await stop.count() == 0 and last_text:
                await page.wait_for_timeout(1000)
                return await page.locator(sel["response"]).last.inner_text()
        except Exception:
            pass

    return last_text


# ── Interface publique ────────────────────────────────────────────────

def scrape(platform: str, tier: Tier, query: str) -> dict:
    """Synchrone — appelable depuis ia_test.py."""
    return asyncio.run(_scrape(platform, tier, query))


def scrape_all(query: str, tiers: list[Tier] = ("free", "paid")) -> list[dict]:
    """Lance ChatGPT + Claude + Gemini × tiers en parallèle."""
    async def _all():
        tasks = [
            _scrape(platform, tier, query)
            for platform in ("chatgpt", "claude", "gemini")
            for tier in tiers
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    results = asyncio.run(_all())
    out = []
    for r in results:
        if isinstance(r, Exception):
            out.append({"ok": False, "error": str(r), "text": "", "model": None})
        else:
            out.append(r)
    return out
