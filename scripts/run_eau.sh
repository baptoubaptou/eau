#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
LOG_FILE="${PROJECT_DIR}/logs/eau.log"
LOCK_FILE="/tmp/eau_scraper.lock"

mkdir -p "${PROJECT_DIR}/logs"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date '+%F %T') [INFO] Job deja en cours, sortie." >> "${LOG_FILE}"
  exit 0
fi

cd "${PROJECT_DIR}"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "$(date '+%F %T') [ERROR] Python virtuel introuvable: ${PYTHON_BIN}" >> "${LOG_FILE}"
  exit 1
fi

max_attempts=3
attempt=1
sleep_between=120

while [ "${attempt}" -le "${max_attempts}" ]; do
  echo "$(date '+%F %T') [INFO] Tentative ${attempt}/${max_attempts}" >> "${LOG_FILE}"

  if "${PYTHON_BIN}" "${PROJECT_DIR}/main.py" >> "${LOG_FILE}" 2>&1; then
    echo "$(date '+%F %T') [OK] Execution terminee." >> "${LOG_FILE}"
    exit 0
  fi

  echo "$(date '+%F %T') [WARN] Echec tentative ${attempt}." >> "${LOG_FILE}"
  attempt=$((attempt + 1))
  if [ "${attempt}" -le "${max_attempts}" ]; then
    sleep "${sleep_between}"
  fi
done

echo "$(date '+%F %T') [ERROR] Echec apres ${max_attempts} tentatives." >> "${LOG_FILE}"
exit 1
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
LOG_FILE="${PROJECT_DIR}/logs/eau.log"
LOCK_FILE="/tmp/eau_scraper.lock"

mkdir -p "${PROJECT_DIR}/logs"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date '+%F %T') [INFO] Job deja en cours, sortie." >> "${LOG_FILE}"
  exit 0
fi

cd "${PROJECT_DIR}"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "$(date '+%F %T') [ERROR] Python virtuel introuvable: ${PYTHON_BIN}" >> "${LOG_FILE}"
  exit 1
fi

max_attempts=3
attempt=1
sleep_between=120

while [ "${attempt}" -le "${max_attempts}" ]; do
  echo "$(date '+%F %T') [INFO] Tentative ${attempt}/${max_attempts}" >> "${LOG_FILE}"

  if "${PYTHON_BIN}" "${PROJECT_DIR}/main.py" >> "${LOG_FILE}" 2>&1; then
    echo "$(date '+%F %T') [OK] Execution terminee." >> "${LOG_FILE}"
    exit 0
  fi

  echo "$(date '+%F %T') [WARN] Echec tentative ${attempt}." >> "${LOG_FILE}"
  attempt=$((attempt + 1))
  if [ "${attempt}" -le "${max_attempts}" ]; then
    sleep "${sleep_between}"
  fi
done

echo "$(date '+%F %T') [ERROR] Echec apres ${max_attempts} tentatives." >> "${LOG_FILE}"
exit 1
