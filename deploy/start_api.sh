#!/usr/bin/env bash
# ==============================================================================
# Backend API - Production Startup Script for Debian (Python 3.13 / 3.12)
# ==============================================================================
set -e

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Starting Backend API Service ==="
echo "Project directory: $PROJECT_DIR"

# 1. Resolve and link .env file from parent directory ($PROJECT_DIR/../.env)
ENV_FILE="$PROJECT_DIR/../.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Configuration file not found at $ENV_FILE"
    exit 1
fi

echo "Linking external configuration: $ENV_FILE -> $PROJECT_DIR/.env"
ln -sf "$ENV_FILE" "$PROJECT_DIR/.env"

# 2. Virtual environment setup and Python activation
VENV_PATH="${VENV_PATH:-$PROJECT_DIR/venv}"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    PYTHON_CMD="$(command -v python3.13 || command -v python3 || true)"
    if [ -z "$PYTHON_CMD" ]; then
        echo "ERROR: Python 3 is not installed on this system."
        exit 1
    fi
    echo "Virtual environment not found. Creating at $VENV_PATH using $PYTHON_CMD..."
    "$PYTHON_CMD" -m venv "$VENV_PATH"
fi

echo "Activating virtual environment: $VENV_PATH"
# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

# 3. Verify and install production dependencies
# Only runs pip install if gunicorn/whitenoise are missing or UPGRADE_DEPS is set
if ! python -c "import gunicorn, whitenoise" &> /dev/null || [ "${UPGRADE_DEPS:-0}" = "1" ]; then
    echo "Installing/updating production dependencies from requirements/production.txt..."
    pip install --upgrade pip
    pip install -r "$PROJECT_DIR/requirements/production.txt"
else
    echo "Production dependencies verified (gunicorn, whitenoise present)."
fi

# Display Python runtime information
PYTHON_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
echo "Active Python runtime: $PYTHON_VER"

# 4. Ensure Production Django Settings
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
echo "Django Settings Module: $DJANGO_SETTINGS_MODULE"

cd "$PROJECT_DIR"

# Ensure staticfiles directory exists
mkdir -p "$PROJECT_DIR/staticfiles"

# 5. Run database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# 6. Collect static files for WhiteNoise / Nginx caching
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 7. Launch Gunicorn server
GUNICORN_BIN="$VENV_PATH/bin/gunicorn"
if [ ! -x "$GUNICORN_BIN" ]; then
    GUNICORN_BIN="$(command -v gunicorn)"
fi

echo "Starting Gunicorn server..."
exec "$GUNICORN_BIN" --config "$PROJECT_DIR/deploy/gunicorn.conf.py" config.wsgi:application
