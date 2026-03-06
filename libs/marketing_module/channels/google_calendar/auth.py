"""
auth.py — Script one-time pour obtenir le refresh_token Google Calendar.

Usage :
    python -m marketing_module.channels.google_calendar.auth

Pré-requis :
    1. Google Cloud Console → APIs & Services → Credentials
    2. Créer un OAuth2 client ID (type: Desktop app)
    3. Télécharger le JSON → extraire client_id et client_secret
    4. Renseigner GOOGLE_CALENDAR_CLIENT_ID et GOOGLE_CALENDAR_CLIENT_SECRET dans secrets.env

Le script ouvre le navigateur pour autorisation, puis affiche le refresh_token à copier.
"""
import os
import sys
import urllib.parse
import webbrowser
import requests

SCOPES = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # code affiché dans le navigateur


def run_auth_flow():
    client_id = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("❌ GOOGLE_CALENDAR_CLIENT_ID et GOOGLE_CALENDAR_CLIENT_SECRET requis dans secrets.env")
        sys.exit(1)

    # Construire l'URL d'autorisation
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n=== Google Calendar — Autorisation OAuth2 ===\n")
    print("1. Ouverture du navigateur pour autorisation...")
    webbrowser.open(auth_url)
    print(f"\n   (Si le navigateur ne s'ouvre pas, copie cette URL manuellement :)\n   {auth_url}\n")

    code = input("2. Colle ici le code affiché par Google après autorisation : ").strip()

    # Échanger le code contre un refresh_token
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    r.raise_for_status()
    data = r.json()

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print("❌ Pas de refresh_token dans la réponse. Relance avec prompt=consent.")
        print(data)
        sys.exit(1)

    print("\n✅ Succès ! Ajoute ces lignes dans /Users/nathalie/.bigboff/secrets.env :\n")
    print(f"GOOGLE_CALENDAR_REFRESH_TOKEN={refresh_token}")
    print(f"GOOGLE_CALENDAR_ID=PRESENCE_IA_CALENDAR_ID  # à remplacer par l'ID réel")
    print("\nPour trouver l'ID de l'agenda PRESENCE IA :")
    print("  python -m marketing_module.channels.google_calendar.auth --list-calendars")


def list_calendars():
    """Lister les agendas pour trouver l'ID du calendrier PRESENCE IA."""
    import os
    from .client import GoogleCalendarClient
    client = GoogleCalendarClient()
    calendars = client.list_calendars()
    print("\n=== Agendas disponibles ===\n")
    for c in calendars:
        primary = " ← PRINCIPAL" if c["primary"] else ""
        print(f"  ID      : {c['id']}")
        print(f"  Nom     : {c['summary']}{primary}")
        print()


if __name__ == "__main__":
    if "--list-calendars" in sys.argv:
        list_calendars()
    else:
        run_auth_flow()
