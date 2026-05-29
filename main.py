#!/usr/bin/env python3
"""
Point d'entrée principal.
Lance le scraper EGL puis envoie vers Home Assistant.

Usage :
    python main.py                  # récupère les 7 derniers jours
    python main.py --days 30        # récupère les 30 derniers jours
    python main.py --month 2026-05  # récupère un mois précis
    python main.py --import-stats   # importe les points datés via Statistics API
    python main.py --dry-run        # affiche sans envoyer vers HA
"""

import argparse
import os
from datetime import date
from dotenv import load_dotenv
from egl_scraper import get_daily_consumption
from ha_sender import send_to_ha, send_month_total_to_ha, import_statistics_to_ha

load_dotenv("config.env")

def main():
    parser = argparse.ArgumentParser(description="EGL → Home Assistant water scraper")
    parser.add_argument("--days", type=int, default=7, help="Nombre de jours à récupérer")
    parser.add_argument(
        "--month",
        type=str,
        help="Mois à récupérer au format YYYY-MM (prioritaire sur --days)",
    )
    parser.add_argument(
        "--import-stats",
        action="store_true",
        help="Importe aussi les données dans l'API Statistics (dates réelles).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Pas d'envoi vers HA")
    args = parser.parse_args()

    email    = os.environ["EGL_EMAIL"]
    password = os.environ["EGL_PASSWORD"]
    ha_url   = os.environ["HA_URL"]
    ha_token = os.environ["HA_TOKEN"]
    sensor   = os.environ.get("HA_SENSOR", "sensor.eau_grand_lyon_daily")
    sensor_monthly = os.environ.get("HA_SENSOR_MONTHLY", "sensor.eau_grand_lyon_monthly_current")
    statistic_id = os.environ.get("HA_STATISTIC_ID", "sensor.eau_grand_lyon_daily_import")

    print("=== EGL Water Scraper ===")
    if args.month:
        print(f"Récupération du mois {args.month}...")
    else:
        print(f"Récupération des {args.days} derniers jours...")

    try:
        data = get_daily_consumption(
            email,
            password,
            days_back=args.days,
            target_month=args.month,
        )
    except ValueError as exc:
        print(f"ERREUR : {exc}")
        return 1

    if not data:
        print("ERREUR : aucune donnée récupérée.")
        return 1

    print(f"\nDonnées récupérées ({len(data)} jours) :")
    for entry in sorted(data, key=lambda x: x["date"]):
        print(f"  {entry['date']} : {entry['volume_liters']} L")

    if args.dry_run:
        print("\n[dry-run] Pas d'envoi vers Home Assistant.")
        if args.import_stats:
            import_statistics_to_ha(ha_url, ha_token, statistic_id, data)
    else:
        send_to_ha(ha_url, ha_token, sensor, data)
        month_label = args.month or date.today().strftime("%Y-%m")
        month_data = data
        if not args.month:
            # Pour un cumul mensuel fiable, on recharge explicitement le mois en cours.
            try:
                month_data = get_daily_consumption(
                    email,
                    password,
                    days_back=args.days,
                    target_month=month_label,
                )
            except ValueError:
                month_data = data
        send_month_total_to_ha(ha_url, ha_token, sensor_monthly, month_data, month_label)
        if args.import_stats:
            import_statistics_to_ha(ha_url, ha_token, statistic_id, data)

    return 0

if __name__ == "__main__":
    exit(main())