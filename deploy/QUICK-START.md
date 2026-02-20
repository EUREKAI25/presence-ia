# Guide rapide — Installation du webhook (5 min)

## 1️⃣ Connexion au VPS via panel IONOS

1. Aller sur **https://my.ionos.com**
2. Se connecter
3. **Serveurs** → Sélectionner le VPS (212.227.80.241)
4. Cliquer **Ouvrir la console web** (ou **Web Terminal**)

## 2️⃣ Installation du webhook

Copier-coller ces commandes dans la console :

```bash
# Aller dans le projet
cd /opt/presence-ia

# Pull les nouveaux fichiers
git pull origin main

# Installer Flask (si pas déjà fait)
pip3 install flask

# Copier le service systemd
cp deploy/webhook.service /etc/systemd/system/presence-ia-webhook.service

# Éditer le service pour ajouter le token secret
nano /etc/systemd/system/presence-ia-webhook.service
```

**Dans l'éditeur nano :**
- Chercher la ligne `Environment="DEPLOY_SECRET=YOUR_SECRET_TOKEN_HERE"`
- Remplacer `YOUR_SECRET_TOKEN_HERE` par :
  ```
  571cc969753751ba330808b1f28f220384c6eade3fd0f55f8bf1d9c3e58dc6a0
  ```
- Sauvegarder : `Ctrl+O` puis `Entrée`
- Quitter : `Ctrl+X`

**Continuer l'installation :**

```bash
# Activer et démarrer le webhook
systemctl daemon-reload
systemctl enable presence-ia-webhook
systemctl start presence-ia-webhook

# Vérifier que ça fonctionne
systemctl status presence-ia-webhook

# Test local
curl http://localhost:9001/health
# Doit afficher : {"status":"ok","service":"presence-ia-webhook"}
```

## 3️⃣ Ouvrir le port 9001

**Option A : Via le firewall UFW (Ubuntu)**
```bash
ufw allow 9001/tcp
ufw reload
ufw status
```

**Option B : Via le panel IONOS**
1. Dans le panel IONOS → **Pare-feu / Firewall**
2. **Ajouter une règle**
3. Port : `9001`
4. Protocole : `TCP`
5. Source : `Anywhere` (ou limiter à l'IP de GitHub Actions)
6. **Sauvegarder**

## 4️⃣ Configurer GitHub Secret

1. Aller sur https://github.com/EUREKAI25/presence-ia/settings/secrets/actions
2. Cliquer **New repository secret**
3. Name : `DEPLOY_SECRET`
4. Value : `571cc969753751ba330808b1f28f220384c6eade3fd0f55f8bf1d9c3e58dc6a0`
5. Cliquer **Add secret**

## 5️⃣ Test final

**Depuis le terminal local :**
```bash
cd /Users/nathalie/Dropbox/____BIG_BOFF___/PROJETS/PRO/PRESENCE_IA
./deploy/trigger-deploy.sh
```

**Résultat attendu :**
```
🚀 Déclenchement du déploiement PRESENCE_IA...
📡 Webhook: https://presence-ia.com:9001/deploy

✅ Déploiement réussi !
{
  "status": "success",
  "git_pull": { ... },
  "restart": { ... }
}
```

---

## ✅ C'est tout !

**Maintenant, à chaque `git push origin main` :**
- GitHub Actions déclenche automatiquement le déploiement
- Le webhook pull les changements
- Le service redémarre
- Le site est mis à jour ! 🚀

**Voir les déploiements :**
https://github.com/EUREKAI25/presence-ia/actions

---

## 🔧 Troubleshooting rapide

**Le webhook ne démarre pas :**
```bash
journalctl -u presence-ia-webhook -n 50
```

**Port 9001 non accessible :**
```bash
netstat -tlnp | grep 9001
# Vérifier que Python écoute bien sur 0.0.0.0:9001
```

**Déploiement échoue :**
```bash
# Voir les logs en temps réel
journalctl -u presence-ia-webhook -f
```
