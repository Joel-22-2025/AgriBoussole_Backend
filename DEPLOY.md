# Déploiement AgriBoussole

## Backend — Render

1. Créer un dépôt GitHub avec le contenu de ce dossier (`agriboussolebackend`).
2. Sur Render : **New → Web Service → From a Git repository**.
3. Choisir le dépôt backend. Le fichier `render.yaml` est détecté automatiquement (Blueprint).
4. Renseigner les variables `sync: false` dans l’onglet **Environment** :
   - `GROQ_API_KEY` (ou l’ancienne variable `cley_grok`) ;
   - `CORS_ALLOWED_ORIGINS` = URL Vercel, ex. `https://agriboussole.vercel.app` ;
   - `CSRF_TRUSTED_ORIGINS` = la même URL ;
   - `DEFAULT_SUPERADMIN_EMAIL` et `DEFAULT_SUPERADMIN_PASSWORD`.
5. Le build exécute `bash build.sh` : dépendances, `collectstatic`, `migrate`, puis création de l’administrateur.
6. Le démarrage utilise Gunicorn. Le health check est `/api/schema/`.

Variables importantes :
- `DATABASE_URL` est fournie par la base PostgreSQL Render et prioritaire sur `DB_*`.
- `DEBUG=False` et `ALLOWED_HOSTS=.onrender.com` sont définis dans `render.yaml`.
- Les fichiers statiques sont servis par WhiteNoise.

## Frontend — Vercel

1. Importer le dépôt `AgriBoussole` dans Vercel.
2. Framework preset : **Vite**. `vercel.json` gère le build et les rewrites SPA.
3. Ajouter la variable d’environnement :
   - `VITE_API_URL=https://<votre-service>.onrender.com/api`
4. Déployer.

## Ordre recommandé

1. Déployer le backend et récupérer son URL Render.
2. Mettre cette URL dans `VITE_API_URL` sur Vercel.
3. Redéployer le frontend.
4. Vérifier `/api/schema/`, puis la connexion depuis le site.
