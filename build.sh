#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

# Fonctionne aussi bien depuis la racine du dépôt que depuis le dossier backend/.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/manage.py" ]; then
  APP_DIR="$SCRIPT_DIR"
else
  APP_DIR="$SCRIPT_DIR/backend"
fi
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
  REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
else
  REQUIREMENTS="$SCRIPT_DIR/../requirements.txt"
fi

python -m pip install --upgrade pip --disable-pip-version-check
python -m pip install --disable-pip-version-check -r "$REQUIREMENTS"

python "$APP_DIR/manage.py" collectstatic --no-input
python "$APP_DIR/manage.py" migrate --no-input

# Import optionnel de la base transmise (URL HTTPS).
if [ -n "${DATA_FIXTURE_URL:-}" ]; then
  python "$APP_DIR/manage.py" import_initial_data --url "$DATA_FIXTURE_URL"
fi

# Crée l'administrateur initial si les variables sont définies dans Render.
if [ -n "${DEFAULT_SUPERADMIN_EMAIL:-}" ] && [ -n "${DEFAULT_SUPERADMIN_PASSWORD:-}" ]; then
  python "$APP_DIR/manage.py" create_default_superadmin
fi
