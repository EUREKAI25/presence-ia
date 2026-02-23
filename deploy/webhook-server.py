#!/usr/bin/env python3
"""
Webhook server pour déploiement automatique PRESENCE_IA
Écoute sur port 9001, vérifie un token secret, puis git pull + restart
"""
import os
import subprocess
import hmac
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
DEPLOY_SECRET = os.getenv("DEPLOY_SECRET", "CHANGE_ME_IN_PRODUCTION")
PROJECT_PATH = "/opt/presence-ia"
SERVICE_NAME = "presence-ia"

def verify_signature(payload, signature):
    """Vérifie la signature HMAC du webhook GitHub."""
    if not signature:
        return False
    expected = 'sha256=' + hmac.new(
        DEPLOY_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "presence-ia-webhook"})

def setup_cron():
    """Met à jour le cron refresh-ia (lun/jeu/dim à 9h, 15h, 19h)."""
    token = ""
    try:
        for line in open("/opt/presence-ia/.env"):
            if line.startswith("ADMIN_TOKEN="):
                token = line.strip().split("=", 1)[1].strip('"').strip("'")
                break
    except Exception:
        return
    if not token:
        return
    url = f"https://presence-ia.com/api/v3/refresh-ia?token={token}"
    new_entries = [
        f"0 9  * * 1,4,0 curl -s -X POST '{url}' > /dev/null 2>&1",
        f"0 15 * * 1,4,0 curl -s -X POST '{url}' > /dev/null 2>&1",
        f"0 19 * * 1,4,0 curl -s -X POST '{url}' > /dev/null 2>&1",
    ]
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    existing_lines = [l for l in (result.stdout if result.returncode == 0 else "").splitlines()
                      if 'refresh-ia' not in l and l.strip()]
    new_cron = "\n".join(existing_lines + new_entries) + "\n"
    subprocess.run(['crontab', '-'], input=new_cron, text=True)


@app.route('/deploy', methods=['POST'])
def deploy():
    """Endpoint de déploiement - vérifie le token et déploie."""
    # Vérifier le token (query param ou header)
    token = request.args.get('token') or request.headers.get('X-Deploy-Token')

    if token != DEPLOY_SECRET:
        # Essayer aussi la signature GitHub
        signature = request.headers.get('X-Hub-Signature-256')
        if not verify_signature(request.data, signature):
            return jsonify({"error": "Invalid token"}), 403

    try:
        # Git pull
        result_pull = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            cwd=PROJECT_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Restart service
        result_restart = subprocess.run(
            ['systemctl', 'restart', SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10
        )

        setup_cron()

        return jsonify({
            "status": "success",
            "git_pull": {
                "stdout": result_pull.stdout,
                "stderr": result_pull.stderr,
                "code": result_pull.returncode
            },
            "restart": {
                "stdout": result_restart.stdout,
                "stderr": result_restart.stderr,
                "code": result_restart.returncode
            }
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"🚀 Webhook server starting on port 9001")
    print(f"📁 Project: {PROJECT_PATH}")
    print(f"🔧 Service: {SERVICE_NAME}")
    app.run(host='0.0.0.0', port=9001)
