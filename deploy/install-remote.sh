#!/bin/bash
#
# Installation automatique webhook PRESENCE_IA
# Usage: curl -sSL URL | bash -s TOKEN
#

set -e

DEPLOY_SECRET="${1:-CHANGE_ME}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Installation automatique webhook PRESENCE_IA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Git pull
echo "📥 Mise à jour du code..."
cd /opt/presence-ia
git pull origin main
echo "✅ Code à jour"
echo ""

# 2. Install Flask
echo "📦 Installation de Flask..."
pip3 install -q flask
echo "✅ Flask installé"
echo ""

# 3. Créer le service
echo "⚙️  Configuration du service..."
cat > /etc/systemd/system/presence-ia-webhook.service <<EOF
[Unit]
Description=PRESENCE_IA Webhook Deploy Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/presence-ia/deploy
Environment="DEPLOY_SECRET=$DEPLOY_SECRET"
ExecStart=/usr/bin/python3 /opt/presence-ia/deploy/webhook-server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
echo "✅ Service configuré"
echo ""

# 4. Démarrer le service
echo "🔄 Démarrage du service..."
systemctl daemon-reload
systemctl enable presence-ia-webhook >/dev/null 2>&1
systemctl restart presence-ia-webhook
sleep 2
echo "✅ Service démarré"
echo ""

# 5. Ouvrir le port
echo "🔓 Ouverture du port 9001..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow 9001/tcp >/dev/null 2>&1 || true
    ufw reload >/dev/null 2>&1 || true
    echo "✅ Port ouvert (ufw)"
elif command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port=9001/tcp >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
    echo "✅ Port ouvert (firewalld)"
else
    echo "⚠️  Firewall non détecté - ouvrir manuellement le port 9001"
fi
echo ""

# 6. Test
echo "🧪 Test du webhook..."
sleep 1
if curl -s http://localhost:9001/health | grep -q "ok"; then
    echo "✅ Webhook fonctionnel !"
else
    echo "⚠️  Webhook démarré mais test échoué"
fi
echo ""

# 7. Status
echo "📊 Status du service:"
systemctl status presence-ia-webhook --no-pager | head -15
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation terminée !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Webhook accessible sur: https://presence-ia.com:9001"
echo "🔍 Health check: curl https://presence-ia.com:9001/health"
echo "📝 Logs: journalctl -u presence-ia-webhook -f"
echo ""
echo "⚠️  N'oublie pas de configurer le GitHub Secret DEPLOY_SECRET"
echo "   → https://github.com/EUREKAI25/presence-ia/settings/secrets/actions"
echo ""
