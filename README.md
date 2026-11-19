# Orientation Entrepreneurs (SAEI) — Backend Django

API d'orientation des entrepreneurs agri-agro vers les structures d'accompagnement (SAEI) au **Bénin**, au **Sénégal** et en **Côte d'Ivoire**.

## Structure du projet

```
backend/
├── config/          # settings, urls
│   ├── settings.py
│   ├── urls.py
│   └── exceptions.py
├── accounts/        # utilisateurs, profiles, views, serializers, permissions
│   ├── models.py
│   ├── apps.py
│   ├── migrations/
│   ├── urls.py
│   ├── admin.py
│   ├── views.py
│   ├── serializers.py
│   ├── permissions.py
│   └── management/
│       ├── __init__.py
│       ├── commands/
│       │   ├── __init__.py
│       │   └── create_default_superadmin.py
│       └── migrations/
└── structures/      # modèle Structure
    ├── models.py
    ├── apps.py
    ├── migrations/
    └── admin.py
```

## Stack

- Python 3.12
- Django 5.2
- Django REST Framework
- `djangorestframework-simplejwt` (avec blacklist)
- `django-cors-headers`
- `drf-spectacular`
- `python-decouple` (env vars)
- PostgreSQL (en prod)

Tests : pytest-django

## Installation

1. Cloner / créer le projet.
2. Activer l'environnement virtuel :

   ```bash
   .venv\Scripts\activate
   ```

3. Installer les dépendances :

   ```bash
   pip install -r requirements.txt   # ou exécuter la commande installée ci-dessus
   ```

4. Copier `.env.example` → `.env` et adapter les variables :

   ```
   SECRET_KEY=
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   DB_ENGINE=django.db.backends.postgresql   # pour PostgreSQL
   DEFAULT_FROM_EMAIL=saei-orientation@example.com
   ADMIN_EMAIL=admin@example.com
   DEFAULT_SUPERADMIN_EMAIL=superadmin@saei.bj
   DEFAULT_SUPERADMIN_PASSWORD=SuperAdminSecret123!
   ```

5. Générer le super administrateur par défaut (idempotent) :

   ```bash
   python manage.py create_default_superadmin
   ```

6. Créer les bases de données :

   ```bash
   python manage.py migrate
   ```

7. Lancer les tests :

   ```bash
   pytest backend/accounts/tests/ backend/structures/tests/ -v
   ```

8. Démarrer le serveur :

   ```bash
   python manage.py runserver
   ```

   L'interface sera disponible à `/api/auth/`, `/api/admin/`, `/api/docs/`.

## Import initial des SAEI (XLSX)

Le fichier `backend/data/SAEI_Benin_Senegal_CoteIvoire_base_unifiee.xlsx` contient 165 structures (Bénin, Sénégal, Côte d'Ivoire). La commande Django `import_saei_from_xlsx` les importe et crée un compte SAEI par structure.

1. Configurer PostgreSQL dans `backend/.env` :

   ```
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=saei_db
   DB_USER=postgres
   DB_PASSWORD=<votre-mot-de-passe>
   DB_HOST=localhost
   DB_PORT=5432
   ```

2. Créer la base `saei_db` si elle n'existe pas, puis lancer :

   ```bash
   python manage.py migrate
   python manage.py create_default_superadmin
   python manage.py import_saei_from_xlsx
   ```

Par défaut, l'import crée 165 `Structure` (et les `Ville` associées), 165 comptes `User` de rôle `SAEI` et de statut `APPROVED`, et 165 `SaeiProfile`. Les emails sont fictifs et séquentiels : `saei001@example.com` … `saei165@example.com`. Le mot de passe commun est `Saei@2026`.

La commande est idempotente : un second lancement met à jour les enregistrements existants sans créer de doublon. Options utiles :

```bash
python manage.py import_saei_from_xlsx --password "AutreMotDePasse123" --email-domain fixture.test --email-prefix saei --file chemin/vers/autre.xlsx
```

## API principale

### Authentification publique

| Méthode | Endpoint |
|---|---|
| Register entrepreneur | `POST /api/auth/register/entrepreneur/` |
| Register SAEI (PENDING) | `POST /api/auth/register/saei/` |
| Login | `POST /api/auth/login/` |
| Refresh token | `POST /api/auth/token/refresh/` |
| Logout | `POST /api/auth/logout/` |
| Changer mot de passe | `POST /api/auth/password/change/` |
| Réinitialiser mot de passe | `POST /api/auth/password/reset/` & `POST /api/auth/password/reset/confirm/` |

### Accès connecté

- `GET /api/auth/me/` — user et profil
- `PATCH /api/auth/me/` — mettre à jour

### Administrateur (ADMIN / SUPER_ADMIN)

- `GET /api/admin/saei-requests/?status=PENDING` — liste paginée des demandes
- `POST /api/admin/saei-requests/{id}/approve/` — passer en APPROVED, set approved_by & approved_at, attach structure (`structure_id`)
- `POST /api/admin/saei-requests/{id}/reject/` — motif obligatoire
- `GET /api/admin/users/` — filtre role, status, pays, recherche
- `PATCH /api/admin/users/{id}/` — activer/désactiver
- `POST /api/admin/admins/` — créer un ADMIN
- `DELETE /api/admin/admins/{id}/` — supprimer un ADMIN

### Super administrateur

- `POST /api/admin/admins/` — créer un ADMIN (via command `create_default_superadmin` ou ce point)
- `DELETE /api/admin/admins/{id}/` — supprimer

## JWT

- Access token : 15 minutes
- Refresh token : 7 jours (rotation activée, blacklist après rotation)
- Les tokens contiennent les claims `role` et `status`.

## Permissions

- `IsSuperAdmin` — SUPER_ADMIN uniquement
- `IsAdminOrSuperAdmin` — ADMIN ou SUPER_ADMIN
- `IsApprovedSaei` — SAEI avec statut APPROVED
- `IsEntrepreneur` — ENTREPRENEUR

## Documentation OpenAPI

`GET /api/docs/` rend l'OpenAPI via drf-spectacular.

## Notifications email

- À l'admin lors de la création d'une demande SAEI
- À la SAEI lors de l'approbation ou du rejet (console backend en dev)

## Tests

```bash
pytest backend/accounts/tests/ backend/structures/tests/ -v
```

## Exemple curl

```bash
# Créer un entrepreneur
curl -X POST http://127.0.0.1:8000/api/auth/register/entrepreneur/ \
  -H "Content-Type: application/json" \
  -d '{"email":"jean.dupont@example.com","password":"Passew0rd123","first_name":"Jean","last_name":"Dupont"}'

# Obtenir le token
TOKEN=$(curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"jean.dupont@example.com","password":"Passew0rd123"}')

# Vérifier le profil
curl http://127.0.0.1:8000/api/auth/me/

# Approuver une demande SAEI
curl -X POST http://127.0.0.1:8000/api/admin/saei-requests/1/approve/
```
