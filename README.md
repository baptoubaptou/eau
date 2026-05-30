# Eau du Grand Lyon -> Home Assistant

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Compatible-41BDF5.svg)](https://www.home-assistant.io/)
[![Playwright](https://img.shields.io/badge/Playwright-Scraping-green.svg)](https://playwright.dev/python/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](#licence)

Automatisation Python pour récupérer la consommation d'eau depuis l'espace client **Eau du Grand Lyon** puis l'envoyer dans Home Assistant.

## Apercu

- Recupere les consommations **journalieres** via l'API interne EGL (apres login Playwright)
- Met a jour un capteur journalier HA
- Met a jour un capteur de **cumul du mois en cours**
- Permet un backfill avec dates reelles via l'API **Statistics** de Home Assistant

## Demo rapide

```bash
# Run quotidien
python3 main.py

# Mois complet + import Statistics date
python3 main.py --month 2026-05 --import-stats
```

## Installation

```bash
git clone https://github.com/baptoubaptou/eau.git
cd eau
python3 -m pip install -r requirements.txt
```

## Mise en prod sur Raspberry Pi

Le repo contient tout le necessaire pour un run quotidien robuste (retry + lock + logs + systemd timer).

### 1) Setup machine

```bash
cd /home/pi/eau
./scripts/setup_raspberry.sh
```

### 2) Configurer les secrets

```bash
cp -n config.env.example config.env
nano config.env
```

### 3) Installer le service systemd

```bash
sudo cp deploy/systemd/eau-scraper.service /etc/systemd/system/
sudo cp deploy/systemd/eau-scraper.timer /etc/systemd/system/
```

Verifie et adapte les chemins dans le service si besoin :

- `User=pi`
- `WorkingDirectory=/home/pi/eau`
- `ExecStart=/home/pi/eau/scripts/run_eau.sh`

### 4) Activer et lancer le timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eau-scraper.timer
sudo systemctl status eau-scraper.timer
```

### 5) Logs et debug

```bash
# logs app (retry details)
tail -f /home/pi/eau/logs/eau.log

# logs systemd
journalctl -u eau-scraper.service -f
```

## Configuration

```bash
cp config.env.example config.env
```

Variables principales dans `config.env` :

- `EGL_EMAIL`
- `EGL_PASSWORD`
- `HA_URL`
- `HA_TOKEN`
- `HA_SENSOR` (optionnel, defaut: `sensor.eau_grand_lyon_daily`)
- `HA_SENSOR_MONTHLY` (optionnel, defaut: `sensor.eau_grand_lyon_monthly_current`)
- `HA_STATISTIC_ID` (optionnel, defaut: `sensor.eau_grand_lyon_daily_import`)

> `config.env` est ignore par git pour ne jamais pousser de secrets.

## Utilisation

```bash
# Derniers jours (defaut 7)
python3 main.py
python3 main.py --days 30

# Mois cible (YYYY-MM)
python3 main.py --month 2026-05

# Dry run (sans ecriture HA)
python3 main.py --dry-run

# Import Statistics (dates reelles)
python3 main.py --month 2026-05 --import-stats
```

## Entites HA produites

- `sensor.eau_grand_lyon_daily` : derniere conso journaliere dispo
- `sensor.eau_grand_lyon_monthly_current` : cumul du mois en cours
- `sensor.eau_grand_lyon_daily_import` : serie statistics importee (si `--import-stats`)

## Dashboard Lovelace (exemple)

```yaml
type: entities
title: Eau Grand Lyon
entities:
  - entity: sensor.eau_grand_lyon_daily
    name: Conso journaliere (derniere valeur)
  - entity: sensor.eau_grand_lyon_monthly_current
    name: Cumul mois en cours
```

## Limitations connues

- `api/states` dans HA ne permet pas de backdater un etat brut
- Les derniers jours peuvent manquer cote EGL (publication J+1/J+2)
- Le script privilegie l'API journaliere; fallback UI uniquement si necessaire

## Roadmap

- [x] Recuperation journaliere fiable via API interne EGL
- [x] Cumul mensuel dans HA
- [x] Import Statistics date
- [ ] Carte Lovelace prete a copier/coller (ApexCharts)
- [ ] Workflow GitHub Actions planifie (cron quotidien)
- [ ] Option de logs silencieux (`--quiet`)

## Structure du projet

- `main.py` : CLI et orchestration
- `egl_scraper.py` : login + extraction donnees EGL
- `ha_sender.py` : envois HA (states + monthly + statistics WS)
- `config.env.example` : modele de configuration
- `requirements.txt` : dependances Python

## Securite

- Ne jamais committer `config.env`
- Regenerer les tokens HA en cas de doute
- Utiliser un token HA dedie a cette integration

## Licence

MIT
