"""
Setup sessions Playwright — à lancer UNE FOIS par compte.
Lance un navigateur visible, tu te connectes manuellement, la session est sauvegardée.

Usage :
    python scripts/setup_sessions.py chatgpt free
    python scripts/setup_sessions.py chatgpt paid
    python scripts/setup_sessions.py claude free
    python scripts/setup_sessions.py claude paid
    python scripts/setup_sessions.py gemini free
    python scripts/setup_sessions.py gemini paid

Les fichiers sont sauvegardés dans sessions/{platform}_{tier}.json
"""
import asyncio
import sys
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

URLS = {
    "chatgpt": "https://chatgpt.com/",
    "claude":  "https://claude.ai/",
    "gemini":  "https://gemini.google.com/",
}


async def setup(platform: str, tier: str):
    from playwright.async_api import async_playwright

    url         = URLS[platform]
    session_out = SESSIONS_DIR / f"{platform}_{tier}.json"

    print(f"\n{'='*60}")
    print(f"  Setup session : {platform} ({tier})")
    print(f"  URL : {url}")
    print(f"  Sortie : {session_out}")
    print(f"{'='*60}")
    print(f"\n  → Un navigateur va s'ouvrir.")
    print(f"  → Connecte-toi au compte {tier} {platform}.")
    print(f"  → Une fois connecté et sur la page principale, appuie sur ENTRÉE ici.")
    print()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx     = await browser.new_context(viewport={"width": 1280, "height": 800})
        page    = await ctx.new_page()
        await page.goto(url)

        input("  [ENTRÉE quand tu es connecté et sur la page principale] ")

        await ctx.storage_state(path=str(session_out))
        print(f"\n  ✅ Session sauvegardée : {session_out}")
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in URLS or sys.argv[2] not in ("free", "paid"):
        print("Usage : python scripts/setup_sessions.py [chatgpt|claude|gemini] [free|paid]")
        sys.exit(1)

    asyncio.run(setup(sys.argv[1], sys.argv[2]))
