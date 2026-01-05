# Flow Player for Raspberry Pi

Lecteur autonome vidéo/audio/DMX pour Raspberry Pi 5, conçu pour lire les exports Flow Studio.

## Fonctionnalités

- **Lecture vidéo** via MPV avec support GPU
- **Sortie DMX** : Art-Net, sACN, USB-DMX (Enttec Pro/Open)
- **Scènes synchronisées** : vidéo + timeline DMX avec interpolation à 40fps
- **Interface web** : contrôle et monitoring depuis navigateur
- **Découverte réseau** : accessible via `flowplayer.local`
- **Persistance** : restauration automatique après redémarrage
- **Planification** : lecture programmée horaire/quotidienne

## Installation rapide

Sur un Raspberry Pi avec Raspberry Pi OS Lite (Bookworm) :

```bash
curl -sSL https://raw.githubusercontent.com/desdamo88/flow_player_rpi/main/scripts/quick-install.sh | sudo bash
```

## Installation manuelle

```bash
# Cloner le dépôt
sudo git clone https://github.com/desdamo88/flow_player_rpi.git /opt/flow-player

# Lancer l'installation
cd /opt/flow-player
sudo ./install.sh
```

## Mode développement (Ubuntu/Linux)

```bash
# Installer les dépendances
sudo apt install python3-venv python3-pip mpv libmpv-dev

# Créer l'environnement
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Lancer
python run_dev.py
```

Accès : http://127.0.0.1:5000

## Structure des projets Flow Studio

Placer les exports `.zip` de Flow Studio dans le dossier `datas/` (dev) ou `shows/` (prod).

Structure attendue :
```
project-name/
├── project.json          # Métadonnées du projet
├── scenes/               # Fichiers de scènes
│   └── scene-id.json
├── media/
│   └── videos/           # Fichiers vidéo
└── thumbnails/           # Miniatures
```

## API REST

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/status` | GET | État complet du player |
| `/api/shows` | GET | Liste des shows |
| `/api/shows/<id>/load` | POST | Charger un show |
| `/api/scenes` | GET | Scènes du show actif |
| `/api/scenes/<id>/play` | POST | Jouer une scène |
| `/api/control/play` | POST | Démarrer la lecture |
| `/api/control/stop` | POST | Arrêter |
| `/api/control/pause` | POST | Pause |
| `/api/config` | GET/POST | Configuration |

## Configuration DMX

### Art-Net
```json
{
  "dmx": {
    "mode": "artnet",
    "ip": "2.0.0.255",
    "port": 6454,
    "universe": 0,
    "fps": 40
  }
}
```

### USB-DMX (Enttec Pro)
```json
{
  "dmx": {
    "mode": "usb",
    "usb_port": "/dev/ttyUSB0",
    "usb_driver": "enttec_pro"
  }
}
```

## Création d'image RPi

Trois méthodes disponibles :

```bash
# 1. Cloud-init (recommandé pour déploiement)
./scripts/build-image.sh cloudinit

# 2. Cloner une SD configurée
./scripts/build-image.sh clone

# 3. Construire avec pi-gen (Docker requis)
./scripts/build-image.sh pigen
```

## Architecture

```
src/
├── core/
│   ├── config.py         # Gestion configuration
│   ├── project_loader.py # Chargement projets Flow
│   ├── scene_player.py   # Lecture synchronisée
│   ├── scheduler.py      # Planification
│   └── timeline.py       # Timeline DMX
├── players/
│   ├── video_player.py   # Lecteur MPV
│   └── dmx_player.py     # Sortie DMX
├── web/
│   ├── app.py            # Application Flask
│   ├── api.py            # Endpoints REST
│   └── templates/        # Interface web
└── flow_player.py        # Orchestration principale
```

## Commandes systemd

```bash
sudo systemctl start flow-player    # Démarrer
sudo systemctl stop flow-player     # Arrêter
sudo systemctl restart flow-player  # Redémarrer
sudo systemctl status flow-player   # État
journalctl -u flow-player -f        # Logs en direct
```

## Roadmap

Voir [ROADMAP.md](ROADMAP.md) pour le statut détaillé des fonctionnalités.

**Statut actuel**: v0.9.0 Beta - Prêt pour tests sur RPi 5

## Licence

MIT
