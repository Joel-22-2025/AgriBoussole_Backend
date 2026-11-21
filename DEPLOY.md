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

### Si le service Render a été créé manuellement

Le fichier `render.yaml` n’est appliqué que lors d’un déploiement **Blueprint**. Pour un service créé à la main via le Dashboard, renseigne explicitement :

- **Root Directory** : la racine du dépôt (champ vide ou `.`), pas `backend`.
- **Build Command** : `bash build.sh`
- **Start Command** : `cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile -`
- **Environment** : `PYTHON_VERSION=3.12.7` (ou laisser le fichier `runtime.txt` le déclarer).

Sans cela, Render utilise sa commande par défaut `pip install -r requirements.txt && cd backend && ...`, ce qui échoue si le répertoire racine est réglé sur `backend`. Des copies de compatibilité (`backend/requirements.txt`, `backend/build.sh`, `backend/Procfile`, `backend/runtime.txt`) sont aussi fournies.

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

## Importer la base locale

1. En local, depuis `backend/`, génère la fixture :
   `../.venv/Scripts/python.exe manage.py export_initial_data`
   Fichier produit : `backend/data/initial_data.json` (non versionné volontairement : il contient emails et mots de passe hachés).
2. Deux options pour l'envoyer sur Render :
   - Héberger ce fichier sur une URL HTTPS et renseigner `DATA_FIXTURE_URL` dans les variables Render. Le build l'importe automatiquement après `migrate`.
   - Ou copier le fichier dans le service et lancer `python backend/manage.py import_initial_data --input <chemin>`.
3. L'ordre est important : `migrate` d'abord, import ensuite. `loaddata` est idempotent et met à jour les objets existants.
