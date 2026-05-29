"""
Envoie les données vers Home Assistant via l'API REST.
Crée/met à jour un sensor avec les conso d'eau.
"""

import requests
import json
from datetime import date
from urllib.parse import urlparse, urlunparse

from websocket import create_connection


def send_to_ha(ha_url: str, token: str, sensor_name: str, consumption_data: list[dict]):
    """
    Met à jour un sensor Home Assistant avec la dernière consommation journalière.
    
    consumption_data : [{"date": "2025-05-28", "volume_liters": 142}, ...]
    
    Le sensor principal = conso du jour le plus récent.
    Les attributs contiennent l'historique des derniers jours.
    """
    if not consumption_data:
        print("[HA] Aucune donnée à envoyer.")
        return False

    # Trier par date décroissante
    sorted_data = sorted(consumption_data, key=lambda x: x["date"], reverse=True)
    latest = sorted_data[0]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    state_url = f"{ha_url.rstrip('/')}/api/states/{sensor_name}"

    # IMPORTANT:
    # Home Assistant timestamp les états au moment du POST.
    # Si on renvoie chaque jour la même "last_date", le point est déplacé visuellement à "aujourd'hui".
    # On évite donc de republier quand la date n'a pas changé.
    try:
        current = requests.get(state_url, headers=headers, timeout=10)
        if current.status_code == 200:
            current_payload = current.json()
            current_last_date = (
                current_payload.get("attributes", {}).get("last_date")
                if isinstance(current_payload, dict)
                else None
            )
            if current_last_date == latest["date"]:
                print(
                    f"[HA] Sensor '{sensor_name}' déjà à jour pour {latest['date']} "
                    "(pas de réécriture)."
                )
                return True
    except requests.RequestException:
        # Non bloquant: on tente quand même l'update si la lecture d'état échoue.
        pass

    # Payload du sensor principal (dernière valeur)
    payload = {
        "state": latest["volume_liters"],
        "attributes": {
            "unit_of_measurement": "L",
            "device_class": "water",
            "state_class": "measurement",
            "friendly_name": "Eau Grand Lyon - Consommation journalière",
            "last_date": latest["date"],
            "history": sorted_data[:30],  # 30 derniers jours
            "icon": "mdi:water",
        },
    }

    try:
        resp = requests.post(state_url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[HA] Sensor '{sensor_name}' mis à jour : {latest['volume_liters']} L le {latest['date']}")
        return True
    except requests.RequestException as e:
        print(f"[HA] Erreur envoi : {e}")
        return False


def send_month_total_to_ha(
    ha_url: str,
    token: str,
    sensor_name: str,
    consumption_data: list[dict],
    month_label: str,
):
    """
    Met à jour un capteur de cumul pour un mois donné.
    """
    if not consumption_data:
        print(f"[HA] Aucune donnée mensuelle à envoyer pour {month_label}.")
        return False

    # Ne garder que les entrées du mois demandé.
    month_data = [d for d in consumption_data if str(d.get("date", "")).startswith(month_label + "-")]
    if not month_data:
        print(f"[HA] Aucune donnée pour le mois {month_label}.")
        return False

    total_liters = sum(int(d.get("volume_liters", 0)) for d in month_data)
    last_date = max(d["date"] for d in month_data)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    state_url = f"{ha_url.rstrip('/')}/api/states/{sensor_name}"

    payload = {
        "state": total_liters,
        "attributes": {
            "unit_of_measurement": "L",
            "device_class": "water",
            "state_class": "total",
            "friendly_name": f"Eau Grand Lyon - Cumul {month_label}",
            "month": month_label,
            "days_count": len(month_data),
            "last_date": last_date,
            "history": sorted(month_data, key=lambda x: x["date"]),
            "icon": "mdi:water-check",
        },
    }

    try:
        resp = requests.post(state_url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(
            f"[HA] Sensor mensuel '{sensor_name}' mis à jour : "
            f"{total_liters} L sur {len(month_data)} jour(s) ({month_label})."
        )
        return True
    except requests.RequestException as e:
        print(f"[HA] Erreur envoi mensuel : {e}")
        return False


def send_history_statistics(ha_url: str, token: str, consumption_data: list[dict]):
    """
    (Optionnel) Envoie chaque jour comme sensor séparé pour l'Energy Dashboard.
    Utile si tu veux voir l'historique dans les graphiques HA.
    """
    for entry in consumption_data:
        sensor_id = f"sensor.eau_egl_{entry['date'].replace('-', '_')}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "state": entry["volume_liters"],
            "attributes": {
                "unit_of_measurement": "L",
                "device_class": "water",
                "friendly_name": f"Eau EGL {entry['date']}",
            },
        }
        requests.post(f"{ha_url.rstrip('/')}/api/states/{sensor_id}",
                      headers=headers, json=payload, timeout=5)


def send_live_state(ha_url, token, sensor_name, latest_value):
    """
    Crée/met à jour un sensor avec une valeur courante.
    Nécessaire pour que HA calcule les coûts dans le dashboard Énergie.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "state": latest_value,
        "attributes": {
            "unit_of_measurement": "L",
            "device_class": "water",
            "state_class": "total_increasing",
            "friendly_name": "Eau Grand Lyon - Journalier",
        },
    }
    requests.post(
        f"{ha_url}/api/states/{sensor_name}",
        headers=headers,
        json=payload,
        timeout=10,
    )


def import_statistics_to_ha(
    ha_url: str,
    token: str,
    statistic_id: str,
    consumption_data: list[dict],
    source: str = "recorder",
):
    """
    Importe des statistiques datées dans Home Assistant via WebSocket API.
    Chaque point journalier est importé avec sa date réelle.
    """
    if not consumption_data:
        print("[HA] Aucune donnée à importer dans Statistics.")
        return False

    ws_url = _to_ws_url(ha_url)
    sorted_data = sorted(consumption_data, key=lambda x: x["date"])

    cumulative = 0.0
    stats = []
    for entry in sorted_data:
        liters = float(entry["volume_liters"])
        cumulative += liters
        # Point journalier à 00:00 UTC.
        stats.append(
            {
                "start": f"{entry['date']}T00:00:00+00:00",
                "state": liters,
                "sum": cumulative,
            }
        )

    metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Eau Grand Lyon - Journalier (import)",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "L",
    }

    ws = None
    try:
        ws = create_connection(ws_url, timeout=20)
        hello = json.loads(ws.recv())
        if hello.get("type") != "auth_required":
            print(f"[HA] WebSocket inattendu: {hello}")
            return False

        ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_resp = json.loads(ws.recv())
        if auth_resp.get("type") != "auth_ok":
            print(f"[HA] Auth WebSocket échouée: {auth_resp}")
            return False

        msg_id = 1
        ws.send(
            json.dumps(
                {
                    "id": msg_id,
                    "type": "recorder/import_statistics",
                    "metadata": metadata,
                    "stats": stats,
                }
            )
        )
        resp = json.loads(ws.recv())
        if not resp.get("success"):
            print(f"[HA] Import Statistics échoué: {resp}")
            return False

        print(
            f"[HA] Statistics importées '{statistic_id}' : "
            f"{len(stats)} point(s), de {sorted_data[0]['date']} à {sorted_data[-1]['date']}."
        )
        return True
    except Exception as e:
        print(f"[HA] Erreur import Statistics: {e}")
        return False
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


def _to_ws_url(ha_url: str) -> str:
    parsed = urlparse(ha_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_path = "/api/websocket"
    return urlunparse((ws_scheme, parsed.netloc, ws_path, "", "", ""))