#!/usr/bin/env python3
"""
Point d'entrée principal.
Lance le scraper EGL puis envoie vers Home Assistant.

Usage :
    python main.py                  # récupère les 7 derniers jours
    python main.py --days 30        # récupère les 30 derniers jours
    python main.py --month 2026-05  # récupère un mois précis
    python main.py --dry-run        # affiche sans envoyer vers HA
"""

import argparse
import os
from datetime import date, timedelta
from typing import Optional
from dotenv import load_dotenv
from egl_scraper import get_daily_consumption
from ha_sender import (
    send_to_ha,
    send_month_total_to_ha,
    import_statistics_to_ha,
    send_live_state,
)

load_dotenv("config.env")

def main():
    parser = argparse.ArgumentParser(description="EGL → Home Assistant water scraper")
    parser.add_argument("--days", type=int, default=7, help="Nombre de jours à récupérer")
    parser.add_argument(
        "--month",
        type=str,
        help="Mois à récupérer au format YYYY-MM (prioritaire sur --days)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Pas d'envoi vers HA")
    args = parser.parse_args()

    email    = os.environ["EGL_EMAIL"]
    password = os.environ["EGL_PASSWORD"]
    ha_url   = os.environ["HA_URL"]
    ha_token = os.environ["HA_TOKEN"]
    sensor   = os.environ.get("HA_SENSOR", "sensor.eau_grand_lyon_daily")
    sensor_live = os.environ.get("HA_SENSOR_LIVE")
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
    else:
        send_to_ha(ha_url, ha_token, sensor, data)
        if sensor_live:
            if sensor_live == sensor:
                print(
                    "[HA] HA_SENSOR_LIVE est identique à HA_SENSOR, "
                    "mise à jour live ignorée pour éviter l'écrasement."
                )
            else:
                latest = sorted(data, key=lambda x: x["date"], reverse=True)[0]
                send_live_state(ha_url, ha_token, sensor_live, latest["volume_liters"])
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
        months_to_import = _months_to_import(args.month)
        month_cache = {month_label: month_data}
        for label in months_to_import:
            dataset = month_cache.get(label)
            if dataset is None:
                try:
                    dataset = get_daily_consumption(
                        email,
                        password,
                        days_back=args.days,
                        target_month=label,
                    )
                except ValueError:
                    dataset = []
                month_cache[label] = dataset
            import_statistics_to_ha(ha_url, ha_token, statistic_id, dataset)

    return 0


def _previous_month_label(today: date) -> str:
    first_day_current = today.replace(day=1)
    prev_month_day = first_day_current - timedelta(days=1)
    return prev_month_day.strftime("%Y-%m")


def _months_to_import(target_month: Optional[str]) -> list[str]:
    """
    Règle demandée:
    - Si un mois est explicitement demandé: importer ce mois seulement.
    - Sinon, jours 1-2: importer le mois précédent.
    - Jour 3: importer le mois précédent ET le mois courant.
    - À partir du 4: importer le mois courant.
    """
    if target_month:
        return [target_month]

    today = date.today()
    current = today.strftime("%Y-%m")
    previous = _previous_month_label(today)

    if today.day <= 2:
        return [previous]
    if today.day == 3:
        return [previous, current]
    return [current]


if __name__ == "__main__":
    exit(main())