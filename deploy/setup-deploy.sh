#!/bin/bash
#
# Script de configuration initiale du déploiement automatique
# Usage: ./deploy/setup-deploy.sh
#

set -e

echo "🔧 Configuration du système de déploiement PRESENCE_IA"
echo ""

# Générer un token secret si inexistant
SECRETS_FILE="$HOME/.bigboff/secrets.env"
if grep -q "DEPLOY_SECRET=" "$SECRETS_FILE" 2>/dev/null; then
    echo "✅ DEPLOY_SECRET déjà configuré dans $SECRETS_FILE"
    DEPLOY_SECRET=$(grep DEPLOY_SECRET= "$SECRETS_FILE" | cut -d= -f2)
else
    echo "🔑 Génération d'un nouveau DEPLOY_SECRET..."
    DEPLOY_SECRET=$(openssl rand -hex 32)
    echo "DEPLOY_SECRET=$DEPLOY_SECRET" >> "$SECRETS_FILE"
    echo "✅ Token ajouté à $SECRETS_FILE"
fi

echo ""
echo "📋 Token secret : $DEPLOY_SECRET"
echo ""

# Rendre le script de déploiement exécutable
chmod +x deploy/trigger-deploy.sh
echo "✅ Script trigger-deploy.sh rendu exécutable"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 PROCHAINES ÉTAPES :"
echo ""
echo "1️⃣  Commit et push les fichiers de déploiement :"
echo "   git add deploy/ .github/workflows/"
echo "   git commit -m 'feat: système de déploiement automatique'"
echo "   git push origin main"
echo ""
echo "2️⃣  Configurer GitHub Secret :"
echo "   • Aller sur: https://github.com/EUREKAI25/presence-ia/settings/secrets/actions"
echo "   • Créer un secret 'DEPLOY_SECRET' avec la valeur:"
echo "   $DEPLOY_SECRET"
echo ""
echo "3️⃣  Installer le webhook sur le VPS (voir deploy/INSTALL.md)"
echo "   • Se connecter au VPS via panel IONOS"
echo "   • Suivre les étapes d'installation"
echo ""
echo "4️⃣  Tester le déploiement :"
echo "   ./deploy/trigger-deploy.sh"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
