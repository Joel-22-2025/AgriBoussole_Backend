#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

python -m pip install --upgrade pip --disable-pip-version-check
python -m pip install --disable-pip-version-check -r requirements.txt

python backend/manage.py collectstatic --no-input
python backend/manage.py migrate --no-input

# Import optionnel de la base transmise (fichier local ou URL).
if [ -n "${DATA_FIXTURE_URL:-}" ]; then
  python backend/manage.py import_initial_data --url "$DATA_FIXTURE_URL"
fi

# Crée l'administrateur initial si les variables sont définies dans Render.
if [ -n "${DEFAULT_SUPERADMIN_EMAIL:-}" ] && [ -n "${DEFAULT_SUPERADMIN_PASSWORD:-}" ]; then
  python backend/manage.py create_default_superadmin
fi
