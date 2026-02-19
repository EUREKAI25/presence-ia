# PRESENCE_IA — Rapport MVP · Démo 2026-02-19

---

## URLs démo

| Page | URL |
|------|-----|
| **HOME** | https://presence-ia.com/ |
| **Landing (Couverture Dupont, Lyon, score 6/10)** | https://presence-ia.com/couvreur?t=d311a7f848944ab2b8546a1e |
| **Landing (score 9/10 — plus impactant)** | https://presence-ia.com/couvreur?t=2c51b42d57034e3d9fcea917 |
| **Admin dashboard** | https://presence-ia.com/admin?token=jmj6PUwbBwYCQvNRk3Uj4RQUYaKe5CwctZe7Xuri |
| **Admin Contenus** | https://presence-ia.com/admin/content?token=jmj6PUwbBwYCQvNRk3Uj4RQUYaKe5CwctZe7Xuri |
| **Admin Offres** | https://presence-ia.com/admin/offers?token=jmj6PUwbBwYCQvNRk3Uj4RQUYaKe5CwctZe7Xuri |

---

## Ce qui est en place ✅

### Pipeline prospection
- Scan Google Places → prospects qualifiés (nom, ville, téléphone, avis, site)
- Tests multi-IA : ChatGPT / Gemini / Claude · 5 requêtes × 3 modèles
- Scoring /10 + détection des concurrents cités à la place du prospect
- Génération email personnalisé + script vidéo 90s
- Queue d'envoi manuelle (export CSV/JSON)

### Landing page personnalisée
- URL unique par prospect — `/couvreur?t=TOKEN`
- Tableau des résultats des tests IA (requête par requête)
- Bouton Stripe → paiement 97€ sécurisé
- Webhook Stripe → prospect marqué `paid = True` automatiquement
- Textes (titre, CTA, FAQ) dynamiques depuis la DB

### Admin — 6 onglets
| Onglet | Fonction |
|--------|----------|
| 👥 Contacts | Pipeline SUSPECT → PROSPECT → CLIENT |
| 💶 Offres | Prix éditables, répercutés sur HOME + LANDING |
| 📊 Analytics | KPIs, CA, carte des villes |
| 📸 Preuves | Screenshots partagés par ville/métier |
| ✏️ Contenus | Tous les textes HOME + LANDING sans redéploiement |
| 📤 Envoi | Queue manuelle |

### Infra
- VPS IONOS — `presence-ia.com` HTTPS (Certbot)
- SQLite persistant + migrations automatiques au démarrage
- 84 tests unitaires — tous verts

---

## Ce qui manque

| Élément | Impact démo | Effort |
|---------|-------------|--------|
| Vidéo background header HOME | Visuel uniquement | Moyen |
| Screenshots IA réels (captures partagées par ville) | Preuve sociale | Moyen |
| Email prospect reçu réellement | Si démo paiement end-to-end | Brevo à configurer |
| Logo / favicon | Cosmétique | Petit |

**Pour la démo de demain** : HOME + Landing + Paiement Stripe + Admin Contenus sont suffisants. Les screenshots et la vidéo sont du polish, pas du fonctionnel bloquant.

---

## Notes techniques

- Prix sur la landing : placeholder `{price}` dans le bloc `cta_label` → lu depuis `PricingConfigDB` (FLASH = 97€ une fois). Si le prix change dans Admin > Offres, le bouton se met à jour sans redéploiement.
- Token admin : `jmj6PUwbBwYCQvNRk3Uj4RQUYaKe5CwctZe7Xuri` — ne pas partager publiquement.
- 18 prospects en DB avec runs IA, dont 2 à score 9/10 (Couvreur Test 1 et 3, Rennes).
