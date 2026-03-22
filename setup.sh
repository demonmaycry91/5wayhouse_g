#!/bin/bash
set -e

echo "==========================================="
echo "   5 Way House - Local Setup Script"
echo "==========================================="

if ! command -v python3 &> /dev/null; then
    echo "[!] Error: python3 is not installed."
    exit 1
fi

echo "[1/4] Setting up Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  -> Created new virtual environment 'venv'."
fi
source venv/bin/activate

echo "[2/4] Installing Python Requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/4] Initializing Environment Variables..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        # Cross-platform sed for Mac and Linux
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY='${SECRET_KEY}'|" .env
        else
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY='${SECRET_KEY}'|" .env
        fi
        echo "  -> Created .env and generated a secure SECRET_KEY."
    else
        echo "  [!] Warning: .env.example not found. Please create .env manually."
    fi
else
    echo "  -> .env already exists, skipping."
fi

echo "[4/4] Applying Database Migrations..."
if command -v flask &> /dev/null; then
    # To prevent 'flask db upgrade' from hanging or failing if DB isn't running in Docker, 
    # we just warn the user to run it when ready.
    echo "  -> Note: Database migration applies best inside Docker. Run 'docker-compose up -d --build' next, which automatically initializes and seeds the DB."
else
    echo "  [!] Flask CLI not found. Is your venv active?"
fi

echo "==========================================="
echo " Setup complete!"
echo " IMPORTANT MANUAL STEP: "
echo " You must manually place a valid 'token.json' in the root directory for"
echo " Google API (Classroom, Sheets, Tasks) to function."
echo " Check dev_manual.md for specific generation instructions."
echo "==========================================="
