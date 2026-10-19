#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# send_daily_report.sh
# Wrapper script for the Tara Astro Vision daily booking report.
# Called by cron or systemd timer at 08:00 IST every day.
#
# Usage:
#   bash send_daily_report.sh              # today's report (IST)
#   bash send_daily_report.sh 2026-10-09   # specific date
#
# Scheduler (cron — add with: crontab -e):
#   # Run at 08:00 IST (= 02:30 UTC) every day
#   30 2 * * * /var/www/taraastrovision/send_daily_report.sh >> /var/log/tav_daily_report.log 2>&1
#
# Scheduler (systemd timer — see daily-report.timer / daily-report.service):
#   sudo systemctl enable --now tav-daily-report.timer
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Project directory (edit if deployed elsewhere) ────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
PYTHON="${PROJECT_DIR}/.venv/bin/python"
ENV_FILE="${PROJECT_DIR}/.env"

# ── Load environment variables ────────────────────────────────────
if [[ -f "${ENV_FILE}" ]]; then
    # Export only KEY=VALUE lines, skip comments and blank lines
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Z_]+=.' "${ENV_FILE}" | sed 's/#.*//')
    set +a
fi

# ── Validate Python venv ─────────────────────────────────────────
if [[ ! -x "${PYTHON}" ]]; then
    echo "[$(date -u +%FT%TZ)] ERROR: Python venv not found at ${PYTHON}" >&2
    exit 1
fi

# ── Run the report ───────────────────────────────────────────────
DATE_ARG="${1:-}"
echo "[$(date -u +%FT%TZ)] Starting daily report for date: ${DATE_ARG:-today (IST)}"

cd "${PROJECT_DIR}"

if [[ -n "${DATE_ARG}" ]]; then
    "${PYTHON}" daily_report.py "${DATE_ARG}"
else
    "${PYTHON}" daily_report.py
fi

EXIT_CODE=$?
if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo "[$(date -u +%FT%TZ)] Daily report completed successfully."
else
    echo "[$(date -u +%FT%TZ)] Daily report FAILED with exit code ${EXIT_CODE}." >&2
fi
exit ${EXIT_CODE}
