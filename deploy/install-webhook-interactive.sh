#!/bin/bash
#
# Script d'installation interactive du webhook PRESENCE_IA
# Génère les commandes à exécuter dans la console web IONOS
#

set -e

DEPLOY_SECRET="571cc969753751ba330808b1f28f220384c6eade3fd0f55f8bf1d9c3e58dc6a0"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Installation du webhook PRESENCE_IA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 ÉTAPE 1/6 : Ouvrir la console IONOS"
echo ""
echo "1. Aller sur https://my.ionos.com"
echo "2. Se connecter"
echo "3. Menu Serveurs → VPS (212.227.80.241)"
echo "4. Cliquer 'Ouvrir la console web' ou 'Web Terminal'"
echo ""
read -p "✅ Console ouverte ? (Entrée pour continuer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ÉTAPE 2/6 : Mise à jour du code"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Copie cette commande dans la console VPS :"
echo ""
echo "cd /opt/presence-ia && git pull origin main"
echo ""
read -p "✅ Commande exécutée ? (Entrée pour continuer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ÉTAPE 3/6 : Installation de Flask"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Copie cette commande :"
echo ""
echo "pip3 install flask"
echo ""
read -p "✅ Flask installé ? (Entrée pour continuer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ÉTAPE 4/6 : Configuration du service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Copie cette commande pour créer le fichier service :"
echo ""
cat <<'EOFSERVICE'
cat > /etc/systemd/system/presence-ia-webhook.service <<'EOF'
[Unit]
Description=PRESENCE_IA Webhook Deploy Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/presence-ia/deploy
Environment="DEPLOY_SECRET=571cc969753751ba330808b1f28f220384c6eade3fd0f55f8bf1d9c3e58dc6a0"
ExecStart=/usr/bin/python3 /opt/presence-ia/deploy/webhook-server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
EOFSERVICE
echo ""
read -p "✅ Service créé ? (Entrée pour continuer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ÉTAPE 5/6 : Activation du service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Copie ces commandes une par une :"
echo ""
echo "systemctl daemon-reload"
echo "systemctl enable presence-ia-webhook"
echo "systemctl start presence-ia-webhook"
echo "systemctl status presence-ia-webhook"
echo ""
read -p "✅ Service démarré (voir 'active (running)') ? (Entrée pour continuer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ÉTAPE 6/6 : Ouvrir le port 9001"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Copie cette commande :"
echo ""
echo "ufw allow 9001/tcp && ufw reload"
echo ""
echo "Ou si pas ufw, ouvrir manuellement dans le panel IONOS :"
echo "  Firewall → Ajouter règle → Port 9001 TCP → Sauvegarder"
echo ""
read -p "✅ Port ouvert ? (Entrée pour continuer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Installation terminée !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔍 Test du webhook..."
echo ""

# Test local depuis la machine de Nathalie
if curl -s -f "https://presence-ia.com:9001/health" > /dev/null 2>&1; then
    echo "✅ Webhook accessible depuis l'extérieur !"
else
    echo "⚠️  Webhook pas encore accessible (peut prendre quelques secondes)"
    echo "   Teste manuellement : curl https://presence-ia.com:9001/health"
fi

echo ""
echo "📝 DERNIÈRE ÉTAPE : Configurer GitHub Secret"
echo ""
echo "1. Aller sur https://github.com/EUREKAI25/presence-ia/settings/secrets/actions"
echo "2. New repository secret"
echo "3. Name: DEPLOY_SECRET"
echo "4. Value: $DEPLOY_SECRET"
echo "5. Add secret"
echo ""
read -p "✅ Secret GitHub configuré ? (Entrée pour terminer) " -r

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ TOUT EST PRÊT !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Test du déploiement maintenant..."
echo ""

./deploy/trigger-deploy.sh
