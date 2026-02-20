#!/bin/bash
#
# Script de déploiement manuel PRESENCE_IA
# Usage: ./deploy/trigger-deploy.sh
#

set -e

# Configuration
DEPLOY_SECRET="${DEPLOY_SECRET:-$(grep DEPLOY_SECRET ~/.bigboff/secrets.env 2>/dev/null | cut -d= -f2)}"
WEBHOOK_URL="https://presence-ia.com:9001/deploy"

if [ -z "$DEPLOY_SECRET" ]; then
    echo "❌ DEPLOY_SECRET non trouvé"
    echo "Définir DEPLOY_SECRET dans ~/.bigboff/secrets.env"
    exit 1
fi

echo "🚀 Déclenchement du déploiement PRESENCE_IA..."
echo "📡 Webhook: $WEBHOOK_URL"

# Appeler le webhook avec le token
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "X-Deploy-Token: $DEPLOY_SECRET" \
    "$WEBHOOK_URL?token=$DEPLOY_SECRET" \
    2>&1)

# Séparer le body et le code HTTP
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

echo ""
if [ "$http_code" = "200" ]; then
    echo "✅ Déploiement réussi !"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
else
    echo "❌ Erreur HTTP $http_code"
    echo "$body"
    exit 1
fi
