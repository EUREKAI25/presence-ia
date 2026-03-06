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
import threading
import urllib.parse
import webbrowser
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

SCOPES = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8765/callback"

_auth_code = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>OK - Autorisation Google Calendar obtenue. Ferme cet onglet.</h2>")

    def log_message(self, *args):
        pass  # silence


def run_auth_flow():
    global _auth_code
    client_id = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("GOOGLE_CALENDAR_CLIENT_ID et GOOGLE_CALENDAR_CLIENT_SECRET requis dans secrets.env")
        sys.exit(1)

    # Démarrer le serveur local en arrière-plan
    server = HTTPServer(("localhost", 8765), _CallbackHandler)
    t = threading.Thread(target=server.handle_request)
    t.daemon = True
    t.start()

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
    print("Ouverture du navigateur... Autorise l'accès puis reviens ici.\n")
    webbrowser.open(auth_url)

    t.join(timeout=120)
    server.server_close()

    if not _auth_code:
        print("Timeout — aucun code recu.")
        sys.exit(1)

    # Echanger le code contre un refresh_token
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": _auth_code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    r.raise_for_status()
    data = r.json()

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print("Pas de refresh_token dans la reponse. Relance.")
        print(data)
        sys.exit(1)

    print("\nSucces ! Ajoute ces lignes dans /Users/nathalie/.bigboff/secrets.env :\n")
    print(f"GOOGLE_CALENDAR_REFRESH_TOKEN={refresh_token}")
    print(f"GOOGLE_CALENDAR_ID=primary  # ou l'ID trouve avec --list-calendars")
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
