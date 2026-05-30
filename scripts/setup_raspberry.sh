#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/6] Installation des paquets systeme..."
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  libnss3 \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libdrm2 \
  libxkbcommon0 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libgbm1 \
  libasound2 \
  libpango-1.0-0 \
  libcairo2 \
  libx11-xcb1 \
  libxcb1 \
  libxext6 \
  libx11-6 \
  ca-certificates

echo "[2/6] Creation du venv..."
python3 -m venv "${PROJECT_DIR}/.venv"

echo "[3/6] Installation des dependances Python..."
"${PROJECT_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${PROJECT_DIR}/.venv/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"

echo "[4/6] Installation navigateur Playwright (Chromium)..."
"${PROJECT_DIR}/.venv/bin/python" -m playwright install chromium

echo "[5/6] Permissions scripts..."
chmod +x "${PROJECT_DIR}/scripts/run_eau.sh"
chmod +x "${PROJECT_DIR}/scripts/setup_raspberry.sh"

echo "[6/6] Verifications..."
if [ ! -f "${PROJECT_DIR}/config.env" ]; then
  cp "${PROJECT_DIR}/config.env.example" "${PROJECT_DIR}/config.env"
  echo "config.env cree depuis l'exemple. Pense a renseigner les secrets."
fi

echo "Setup termine."
echo "Prochaine etape: installation du service systemd (voir README)."
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/6] Installation des paquets systeme..."
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  libnss3 \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libdrm2 \
  libxkbcommon0 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libgbm1 \
  libasound2 \
  libpango-1.0-0 \
  libcairo2 \
  libx11-xcb1 \
  libxcb1 \
  libxext6 \
  libx11-6 \
  ca-certificates

echo "[2/6] Creation du venv..."
python3 -m venv "${PROJECT_DIR}/.venv"

echo "[3/6] Installation des dependances Python..."
"${PROJECT_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${PROJECT_DIR}/.venv/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"

echo "[4/6] Installation navigateur Playwright (Chromium)..."
"${PROJECT_DIR}/.venv/bin/python" -m playwright install chromium

echo "[5/6] Permissions scripts..."
chmod +x "${PROJECT_DIR}/scripts/run_eau.sh"
chmod +x "${PROJECT_DIR}/scripts/setup_raspberry.sh"

echo "[6/6] Verifications..."
if [ ! -f "${PROJECT_DIR}/config.env" ]; then
  cp "${PROJECT_DIR}/config.env.example" "${PROJECT_DIR}/config.env"
  echo "config.env cree depuis l'exemple. Pense a renseigner les secrets."
fi

echo "Setup termine."
echo "Prochaine etape: installation du service systemd (voir README)."
