#!/bin/bash
#
# Déploiement SSH direct PRESENCE_IA
# Plus simple et plus fiable que le webhook
#

set -e

VPS_PASSWORD="${VPS_PASSWORD:-$(grep VPS_PASSWORD ~/.bigboff/secrets.env 2>/dev/null | cut -d= -f2)}"
VPS_IP="212.227.80.241"

echo "🚀 Déploiement PRESENCE_IA via SSH..."
echo ""

sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no root@$VPS_IP << 'EOF'
set -e

echo "📥 Git pull..."
cd /opt/presence-ia
git pull origin main

echo "🔄 Restart service..."
systemctl restart presence-ia

echo "✅ Déploiement terminé !"
systemctl status presence-ia --no-pager | head -10

EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Déployé sur https://presence-ia.com"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
