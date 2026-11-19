#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

python -m pip install --upgrade pip --disable-pip-version-check
python -m pip install --disable-pip-version-check -r requirements.txt

python backend/manage.py collectstatic --no-input
python backend/manage.py migrate --no-input

# Crée l'administrateur initial si les variables sont définies dans Render.
if [ -n "${DEFAULT_SUPERADMIN_EMAIL:-}" ] && [ -n "${DEFAULT_SUPERADMIN_PASSWORD:-}" ]; then
  python backend/manage.py create_default_superadmin
fi
