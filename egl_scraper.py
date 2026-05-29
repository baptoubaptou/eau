"""
Scraper pour l'espace client Eau du Grand Lyon
Site : https://agence.eaudugrandlyon.com

IMPORTANT : Le site a été refait en janvier 2025.
  - Login maintenant par email (plus numéro abonné)
  - Les données de J sont disponibles à J+1 vers 6h

Méthode : Playwright headless (le site est SPA / JavaScript lourd)
"""

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from pathlib import Path

SESSION_FILE = Path("playwright_session.json")


def get_daily_consumption(
    email: str, password: str, days_back: int = 7, target_month: Optional[str] = None
) -> list[dict]:
    """
    Se connecte au site EGL et récupère les consommations journalières.
    
    Retourne une liste de dicts :
      [{"date": "2025-05-28", "volume_liters": 142}, ...]
    
    Stratégie :
      1. Login via le formulaire
      2. Naviguer vers "Mon suivi conso"
      3. Intercepter les requêtes XHR/fetch vers l'API interne
         (chercher des appels contenant "dataPoints" ou "consommation")
      4. Parser la réponse JSON
    """
    results = []
    range_start, range_end = _resolve_target_range(days_back, target_month)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # ---- Intercepter les appels API ----
        api_responses = []
        contract_reference = None
        contract_id_token = None

        def handle_response(response):
            nonlocal contract_reference, contract_id_token
            url = response.url
            # Le site fait des appels vers ses endpoints internes (à ajuster)
            if any(kw in url for kw in ["dataPoint", "consommation", "conso", "mesure", "graph"]):
                try:
                    data = response.json()
                    if "/contrats/rechercher" in url and isinstance(data, list):
                        for contract in data:
                            if isinstance(contract, dict) and contract.get("reference"):
                                contract_reference = str(contract["reference"])
                                break
                    m = re.search(r"/contrats/([^/]+)/consommationsMensuelles", url)
                    if m:
                        contract_id_token = m.group(1)
                    api_responses.append({"url": url, "data": data})
                    print(f"[intercept] {url}")
                except Exception:
                    pass

        page.on("response", handle_response)

        # ---- 1. Page de login ----
        print("[*] Navigation vers le site...")
        page.goto("https://agence.eaudugrandlyon.com/", wait_until="domcontentloaded", timeout=30000)

        # Chercher les champs email / password avec des sélecteurs robustes
        # (le markup change souvent sur ce site)
        try:
            if page.locator("input[type='password']").count() == 0:
                # Sur certaines versions, il faut ouvrir la vue de login d'abord.
                for open_login_selector in [
                    "a:has-text('Se connecter')",
                    "button:has-text('Se connecter')",
                    "a:has-text('Connexion')",
                    "button:has-text('Connexion')",
                    "a:has-text('Espace client')",
                    "button:has-text('Espace client')",
                    "a:has-text('Mon compte')",
                    "button:has-text('Mon compte')",
                ]:
                    try:
                        open_btn = page.locator(open_login_selector).first
                        if open_btn.count() > 0 and open_btn.is_visible():
                            open_btn.click(timeout=5000)
                            page.wait_for_timeout(1200)
                            if page.locator("input[type='password']").count() > 0:
                                break
                    except Exception:
                        pass

            page.wait_for_selector(
                "input[type='password'], input[type='email'], input[type='text']",
                timeout=20000,
            )

            # Bandeau cookies éventuel.
            for cookie_selector in [
                "button:has-text('Accepter')",
                "button:has-text('Tout accepter')",
                "button:has-text('Autoriser')",
            ]:
                try:
                    btn = page.locator(cookie_selector).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=2000)
                        break
                except Exception:
                    pass

            email_locator = page.locator(
                "input[type='email'], "
                "input[name*='email' i], input[id*='email' i], "
                "input[name*='ident' i], input[id*='ident' i], "
                "input[name*='user' i], input[id*='user' i]"
            ).first

            if email_locator.count() == 0:
                # Fallback si le champ n'est pas typé email.
                email_locator = page.locator("input[type='text']").first

            pwd_locator = page.locator(
                "input[type='password'], input[name*='pass' i], input[id*='pass' i]"
            ).first

            email_locator.fill(email, timeout=10000)
            pwd_locator.fill(password, timeout=10000)

            clicked_submit = False
            for submit_selector in [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Se connecter')",
                "button:has-text('Connexion')",
                "button:has-text('Me connecter')",
                "button:has-text('Valider')",
            ]:
                try:
                    submit_btn = page.locator(submit_selector).first
                    if submit_btn.count() > 0 and submit_btn.is_visible():
                        submit_btn.click(timeout=5000)
                        clicked_submit = True
                        break
                except Exception:
                    pass

            if not clicked_submit:
                # Dernier recours : touche Entrée sur le champ mot de passe.
                pwd_locator.press("Enter")

            page.wait_for_load_state("networkidle", timeout=20000)
            print("[*] Tentative de connexion terminée.")
        except (PWTimeout, Exception) as e:
            print(f"[!] Échec au login : {e}")
            browser.close()
            return []

        # ---- 2. Naviguer vers le suivi conso ----
        # Aller directement sur la page contrat quand la référence est connue.
        try:
            if contract_reference:
                page.goto(
                    f"https://agence.eaudugrandlyon.com/#/contrats/{contract_reference}/consommations",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            else:
                conso_link = page.locator(
                    "a:has-text('conso'), a:has-text('Consommation'), a:has-text('suivi')"
                )
                conso_link.first.click()
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception as e:
            print(f"[!] Impossible de naviguer vers suivi conso : {e}")
            # Fallback: on reste sur la page courante (l'API conso peut déjà avoir répondu).

        # Appel direct de l'endpoint journalier via le token contrat.
        try:
            if contract_id_token:
                date_debut = _to_egl_utc(datetime.combine(range_start, time.min, tzinfo=timezone.utc))
                end_dt = datetime.combine(range_end, time(23, 59, 59), tzinfo=timezone.utc)
                now_dt = datetime.now(timezone.utc)
                date_fin = _to_egl_utc(min(end_dt, now_dt))
                daily_url = (
                    "https://agence.eaudugrandlyon.com/application/rest/produits/contrats/"
                    f"{contract_id_token}/consommationsJournalieres?dateDebut={date_debut}&dateFin={date_fin}"
                )
                daily_payload = page.evaluate(
                    """async ({url}) => {
                        const token = localStorage.getItem('access_token');
                        const resp = await fetch(url, {
                            method: 'GET',
                            headers: {
                                'Authorization': `Bearer ${token}`,
                                'entreprise': 'EPGL',
                                'Accept': 'application/json, text/plain, */*'
                            },
                            credentials: 'include'
                        });
                        const text = await resp.text();
                        let data = null;
                        try { data = JSON.parse(text); } catch (e) {}
                        return { ok: resp.ok, status: resp.status, data };
                    }""",
                    {"url": daily_url},
                )
                if daily_payload.get("ok") and daily_payload.get("data"):
                    api_responses.append({"url": daily_url, "data": daily_payload["data"]})
                    print(f"[api] Journalier OK: {daily_url}")
                else:
                    print(f"[!] API journalière KO ({daily_payload.get('status')})")
        except Exception as e:
            print(f"[!] Appel API journalière impossible : {e}")

        # Fallback UI: forcer "Par jour" si l'appel direct n'a rien donné.
        try:
            if not any("consommationsJournalieres" in item["url"] for item in api_responses):
                page.wait_for_selector("ael-select[role='combobox']", timeout=10000)
                combo_candidates = page.locator("ael-select[role='combobox']")
                selected_combo = None
                for idx in range(combo_candidates.count()):
                    candidate = combo_candidates.nth(idx)
                    text = candidate.inner_text().strip().lower()
                    if "par " in text:
                        selected_combo = candidate
                        break

                if selected_combo is None and combo_candidates.count() > 0:
                    selected_combo = combo_candidates.first

                if selected_combo is not None:
                    selected_combo.click(force=True, timeout=5000)
                    page.locator("ael-option:has-text('Par jour')").first.click(
                        force=True, timeout=5000
                    )
                    page.wait_for_load_state("networkidle", timeout=20000)
                    print("[*] Mode 'Par jour' sélectionné (fallback UI).")
        except Exception as e:
            print(f"[!] Impossible de forcer le mode journalier : {e}")

        # Attendre un peu que les appels API se fassent
        page.wait_for_timeout(4000)

        # ---- 3. Parser les réponses interceptées ----
        if api_responses:
            print(f"[*] {len(api_responses)} réponse(s) API interceptée(s)")
            results = _parse_api_responses(api_responses)
            results = _filter_date_range(results, range_start, range_end)
        else:
            print("[!] Aucune réponse API interceptée.")
            print("    → Ouvre le site dans Chrome, onglet Network (XHR/Fetch),")
            print("      navigue vers 'Mon suivi conso' et note les URLs des appels.")
            print("      Mets à jour handle_response() avec les bons mots-clés.")

        browser.close()

    return results


def _parse_api_responses(api_responses: list[dict]) -> list[dict]:
    """
    Parse les réponses JSON de l'API EGL.
    
    La structure JSON varie selon les versions du site.
    Stratégie : chercher récursivement des patterns date+volume.
    
    Structure probable (basée sur ancienne version connue) :
      {"dataPoints": [{"date": "2025-05-27", "value": 0.142}, ...]}
    ou
      [{"startDate": "...", "volume": 142}, ...]
    """
    results = []

    # Priorité aux consommations journalières si présentes.
    prioritized = [
        item for item in api_responses if "consommationsJournalieres" in item.get("url", "")
    ]
    to_parse = prioritized if prioritized else api_responses

    for item in to_parse:
        data = item["data"]
        extracted = _extract_datapoints(data)
        if extracted:
            results.extend(extracted)
            print(f"  → {len(extracted)} points extraits de {item['url']}")

    # Dédupliquer par date
    seen = {}
    for r in results:
        seen[r["date"]] = r
    return list(seen.values())


def _extract_datapoints(data, depth=0) -> list[dict]:
    """Cherche récursivement des paires date/volume dans un objet JSON."""
    if depth > 5:
        return []

    results = []

    if isinstance(data, list):
        for item in data:
            results.extend(_extract_datapoints(item, depth + 1))

    elif isinstance(data, dict):
        # Pattern 1 : {"date": "...", "value": ...}  (valeur en m³)
        if "date" in data and "value" in data:
            try:
                vol_liters = int(float(data["value"]) * 1000)
                results.append({"date": str(data["date"])[:10], "volume_liters": vol_liters})
                return results
            except (ValueError, TypeError):
                pass

        # Pattern 2 : {"startDate": "...", "volume": ...}  (volume en L)
        if "startDate" in data and "volume" in data:
            try:
                results.append({"date": str(data["startDate"])[:10],
                                 "volume_liters": int(data["volume"])})
                return results
            except (ValueError, TypeError):
                pass

        # Pattern 3 : clé "dataPoints" connue de l'ancienne version
        if "dataPoints" in data:
            results.extend(_extract_datapoints(data["dataPoints"], depth + 1))

        # Pattern 4 : nouvelle API EGL
        # {"consommation": 2.0, "mois": 3, "annee": 2026}
        if "consommation" in data and "mois" in data and "annee" in data:
            # Cas journalier : {"jour": 31, "mois": 6, "annee": 2024, "consommation": 0.0}
            if "jour" in data:
                try:
                    day = int(data["jour"])
                    month = int(data["mois"]) + 1  # API 0-indexée (0=janvier)
                    year = int(data["annee"])
                    if 1 <= day <= 31 and 1 <= month <= 12:
                        results.append(
                            {
                                "date": f"{year:04d}-{month:02d}-{day:02d}",
                                "volume_liters": int(float(data["consommation"])),
                            }
                        )
                        return results
                except (ValueError, TypeError):
                    pass

            # Cas mensuel : mois indexé à 0.
            try:
                month = int(data["mois"]) + 1  # API 0-indexée (0=janvier)
                year = int(data["annee"])
                if 1 <= month <= 12:
                    vol_liters = int(float(data["consommation"]) * 1000)
                    results.append(
                        {"date": f"{year:04d}-{month:02d}-01", "volume_liters": vol_liters}
                    )
                    return results
            except (ValueError, TypeError):
                pass

        # Chercher récursivement dans toutes les valeurs
        for v in data.values():
            results.extend(_extract_datapoints(v, depth + 1))

    return results


def _filter_date_range(entries: list[dict], range_start: date, range_end: date) -> list[dict]:
    filtered = []
    for entry in entries:
        try:
            d = date.fromisoformat(entry["date"])
        except Exception:
            continue
        if range_start <= d <= range_end:
            filtered.append(entry)
    return filtered


def _to_egl_utc(dt: datetime) -> str:
    """Format datetime en ISO UTC attendu par l'API EGL."""
    dt_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _resolve_target_range(days_back: int, target_month: Optional[str] = None) -> tuple[date, date]:
    if target_month:
        try:
            year_str, month_str = target_month.split("-")
            year = int(year_str)
            month = int(month_str)
            if not (1 <= month <= 12):
                raise ValueError("month out of range")
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
            return start, end
        except Exception as exc:
            raise ValueError("target_month doit être au format YYYY-MM") from exc

    today = date.today()
    start = today - timedelta(days=max(days_back - 1, 0))
    return start, today