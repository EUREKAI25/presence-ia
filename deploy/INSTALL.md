# Installation du système de déploiement automatique

## Vue d'ensemble

Système de déploiement automatique via webhook pour PRESENCE_IA :
- **Webhook server** : écoute sur port 9001, reçoit les notifications de déploiement
- **GitHub Actions** : déclenche automatiquement à chaque push sur `main`
- **Script manuel** : permet de déclencher un déploiement depuis le terminal local

---

## Installation sur le VPS (une seule fois)

### 1. Générer un token secret

```bash
# Sur ta machine locale
DEPLOY_SECRET=$(openssl rand -hex 32)
echo "DEPLOY_SECRET=$DEPLOY_SECRET" >> ~/.bigboff/secrets.env
echo "Token généré: $DEPLOY_SECRET"
```

### 2. Installer le webhook sur le VPS

**Via le panel web IONOS ou console :**

```bash
# Se connecter au VPS
ssh root@212.227.80.241

# Créer le dossier deploy
mkdir -p /opt/presence-ia/deploy
cd /opt/presence-ia

# Copier les fichiers (depuis git après commit)
git pull origin main

# Installer Flask si nécessaire
pip3 install flask

# Configurer le service systemd
cp deploy/webhook.service /etc/systemd/system/presence-ia-webhook.service

# Éditer le service pour ajouter le token secret
nano /etc/systemd/system/presence-ia-webhook.service
# Remplacer YOUR_SECRET_TOKEN_HERE par le token généré

# Activer et démarrer le service
systemctl daemon-reload
systemctl enable presence-ia-webhook
systemctl start presence-ia-webhook

# Vérifier que ça fonctionne
systemctl status presence-ia-webhook
curl http://localhost:9001/health
```

### 3. Ouvrir le port 9001 dans le firewall

```bash
# Si ufw (Ubuntu)
ufw allow 9001/tcp

# Si firewalld (CentOS/RHEL)
firewall-cmd --permanent --add-port=9001/tcp
firewall-cmd --reload

# Ou via le panel IONOS : Firewall → Ajouter règle → Port 9001 TCP
```

### 4. Configurer HTTPS (optionnel mais recommandé)

```bash
# Ajouter le webhook au reverse proxy nginx
nano /etc/nginx/sites-available/presence-ia.com

# Ajouter dans le bloc server {} :
location /deploy {
    proxy_pass http://localhost:9001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# Recharger nginx
nginx -t && systemctl reload nginx
```

---

## Configuration GitHub

### 1. Ajouter le secret DEPLOY_SECRET

1. Aller sur https://github.com/EUREKAI25/presence-ia/settings/secrets/actions
2. Cliquer **New repository secret**
3. Name: `DEPLOY_SECRET`
4. Value: Le token généré à l'étape 1
5. Cliquer **Add secret**

### 2. Activer GitHub Actions

Le workflow `.github/workflows/deploy.yml` sera automatiquement détecté au prochain push.

---

## Utilisation

### Déploiement automatique (recommandé)

À chaque `git push origin main`, le déploiement se fait automatiquement :

```bash
git add .
git commit -m "fix: correction bug"
git push origin main
# → Déploiement automatique déclenché ! 🚀
```

Suivi sur : https://github.com/EUREKAI25/presence-ia/actions

### Déploiement manuel depuis le terminal

```bash
cd /Users/nathalie/Dropbox/____BIG_BOFF___/PROJETS/PRO/PRESENCE_IA
chmod +x deploy/trigger-deploy.sh
./deploy/trigger-deploy.sh
```

### Déploiement manuel depuis GitHub

1. Aller sur https://github.com/EUREKAI25/presence-ia/actions
2. Sélectionner **Deploy to VPS**
3. Cliquer **Run workflow** → **Run workflow**

---

## Vérification

```bash
# Vérifier que le webhook fonctionne
curl https://presence-ia.com:9001/health

# Tester le déploiement (avec ton token)
curl -X POST -H "X-Deploy-Token: TON_TOKEN" \
  "https://presence-ia.com:9001/deploy?token=TON_TOKEN"

# Voir les logs du webhook
ssh root@212.227.80.241 "journalctl -u presence-ia-webhook -f"
```

---

## Sécurité

- ✅ Token secret aléatoire de 64 caractères
- ✅ Vérification HMAC des webhooks GitHub
- ✅ Service systemd isolé
- ✅ Timeout des commandes (30s git, 10s restart)
- ⚠️  HTTPS recommandé (via nginx reverse proxy)
- ⚠️  Limiter l'accès au port 9001 par IP (optionnel)

---

## Troubleshooting

**Le webhook ne répond pas :**
```bash
ssh root@212.227.80.241
systemctl status presence-ia-webhook
journalctl -u presence-ia-webhook -n 50
```

**Port 9001 fermé :**
```bash
netstat -tlnp | grep 9001
ufw status
```

**GitHub Actions échoue :**
- Vérifier que le secret `DEPLOY_SECRET` est bien configuré
- Vérifier que le port 9001 est accessible depuis internet
- Voir les logs : https://github.com/EUREKAI25/presence-ia/actions

**Déploiement réussi mais changements non visibles :**
```bash
# Vider le cache nginx
ssh root@212.227.80.241 "nginx -s reload"

# Vérifier la version du code
ssh root@212.227.80.241 "cd /opt/presence-ia && git log -1 --oneline"
```
