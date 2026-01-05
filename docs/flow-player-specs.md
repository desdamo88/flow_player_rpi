# Flow Player

**Lecteur autonome de séquences audiovisuelles avec mapping vidéo, DMX et son pour Raspberry Pi 5**

---

## Vue d'ensemble

Flow Player est un runtime léger conçu pour lire des packages exportés depuis Flow (application Electron de création). Il permet de déployer des installations audiovisuelles autonomes sur Raspberry Pi 5, avec synchronisation vidéo/DMX/audio, planification horaire et monitoring à distance.

### Cas d'usage

- Installations muséales et expositions
- Vitrines et retail
- Mapping architectural permanent
- Événements récurrents avec programmation horaire
- Installations artistiques autonomes

---

## Fonctionnalités

### Playback

| Fonctionnalité | Description |
|----------------|-------------|
| Lecture vidéo | Décodage hardware H.264/H.265 jusqu'en 4K30 ou 1080p60 |
| Mapping vidéo | Corner pinning 4 points avec correction en temps réel |
| Sortie DMX | Art-Net et sACN, 1 univers (512 canaux), 40fps |
| Audio | Sortie HDMI ou jack 3.5mm, synchronisé à la vidéo |
| Boucle | Lecture en boucle infinie ou single shot |
| Blackout | Extinction automatique DMX en fin de séquence |

### Planification

| Fonctionnalité | Description |
|----------------|-------------|
| Planning journalier | Définition d'horaires par jour de la semaine |
| Plages horaires | Activation/désactivation sur période (ex: 9h-18h) |
| Dates spéciales | Exceptions pour jours fériés ou événements |
| Mode manuel | Déclenchement via interface web ou API |
| Mode continu | Boucle permanente sans planification |

### Interface Web

| Fonctionnalité | Description |
|----------------|-------------|
| Dashboard | Status en temps réel (lecture, position, prochain trigger) |
| Upload show | Chargement d'un nouveau package .zip via navigateur |
| Gestion shows | Liste des shows disponibles, sélection du show actif |
| Planification | Édition du planning horaire via interface graphique |
| Configuration | Réglages réseau, DMX, sortie vidéo |
| Logs | Consultation des logs système et erreurs |
| Contrôle | Play/Stop/Restart manuels |

### Monitoring & API

| Fonctionnalité | Description |
|----------------|-------------|
| Status endpoint | GET /api/status - état complet du player |
| Heartbeat | Envoi périodique du status vers serveur distant |
| Webhook | Notification sur événements (start, stop, error) |
| Contrôle distant | Endpoints API pour play/stop/load |
| Métriques | CPU, RAM, température, uptime |
| Identification | Device ID unique basé sur numéro série Pi |

### Système

| Fonctionnalité | Description |
|----------------|-------------|
| Auto-start | Démarrage automatique au boot |
| USB auto-detect | Détection et chargement automatique depuis clé USB |
| Watchdog | Redémarrage automatique en cas de crash |
| OTA update | Mise à jour du player via interface web |
| Backup config | Sauvegarde/restauration de la configuration |
| LED status | Indication visuelle via GPIO (optionnel) |

---

## Stack technique

### Hardware cible

```
Raspberry Pi 5 (4GB ou 8GB)
├── SoC: Broadcom BCM2712 (Cortex-A76 quad-core @ 2.4GHz)
├── GPU: VideoCore VII (OpenGL ES 3.1, Vulkan 1.2)
├── RAM: 4GB ou 8GB LPDDR4X
├── Stockage: microSD ou SSD NVMe (via HAT)
├── Vidéo: micro-HDMI x2 (4Kp60)
├── Audio: Jack 3.5mm ou HDMI
├── USB: 2x USB 3.0, 2x USB 2.0
└── Réseau: Gigabit Ethernet, WiFi 5
```

### Système d'exploitation

```
Raspberry Pi OS Lite (64-bit, Bookworm)
├── Kernel: 6.6+ avec support DRM/KMS
├── Boot: ~10 secondes jusqu'au player
├── Empreinte: < 2GB sur SD
└── RAM utilisée: < 150MB (hors vidéo)
```

### Stack logicielle

```
┌─────────────────────────────────────────────────────────────┐
│                      FLOW PLAYER                            │
├─────────────────────────────────────────────────────────────┤
│  Interface Web          │  API REST                         │
│  (Flask + HTML/JS)      │  (Flask)                          │
├─────────────────────────────────────────────────────────────┤
│  Core Engine (Python 3.11+)                                 │
│  ├── Project Loader     - Parse packages .zip               │
│  ├── Scheduler          - Planification horaire             │
│  ├── Timeline           - Synchronisation master            │
│  └── Monitor            - Status & heartbeat                │
├─────────────────────────────────────────────────────────────┤
│  Playback Layer                                             │
│  ├── Video Player       - libmpv (hardware decode)          │
│  ├── DMX Player         - Art-Net/sACN output               │
│  └── Mapping Engine     - GLSL shaders (corner pin)         │
├─────────────────────────────────────────────────────────────┤
│  System Layer                                               │
│  ├── systemd            - Service management                │
│  ├── udev               - USB auto-mount                    │
│  └── watchdog           - Hardware watchdog                 │
└─────────────────────────────────────────────────────────────┘
```

### Dépendances Python

```
# requirements.txt
flask==3.0.0              # Web server & API
python-mpv==1.0.6         # Video playback
stupidArtnet==1.4.0       # Art-Net DMX output
sacn==1.9.0               # sACN DMX output (alternative)
pyserial==3.5             # USB-DMX serial communication (ENTTEC, DMXKing)
apscheduler==3.10.4       # Job scheduling
requests==2.31.0          # HTTP client (monitoring)
psutil==5.9.0             # System metrics
python-dotenv==1.0.0      # Configuration
```

### Dépendances système

```bash
# Packages APT
python3-venv              # Python virtual environment
python3-pip               # Package manager
mpv                       # Media player
libmpv-dev                # MPV development libraries
git                       # Version control
```

---

## Format de package (.zip)

Le package exporté depuis Flow contient toutes les données nécessaires au playback autonome. Le format correspond à la structure native des projets Flow.

### Structure

```
show_package.zip
├── project.json            # Configuration principale du projet
├── scenes/
│   └── [scene-id].json     # Fichiers de scène individuels
├── media/
│   ├── images/             # Images (.jpg, .png, .webp)
│   ├── videos/             # Vidéos (.mp4, .webm)
│   ├── audio/              # Audio (.mp3, .wav, .ogg)
│   └── effects/            # Effets AR (.zip)
└── thumbnails/             # Vignettes générées
    └── [media-id].jpg
```

### project.json

Structure principale du projet Flow :

```json
{
  "id": "f6df1017-de52-4fa7-a7fe-a2d11edbc1a1",
  "name": "Installation Musée XYZ",
  "version": "1.0.0",
  "created": "2025-01-05T10:30:00Z",
  "modified": "2025-01-05T14:00:00Z",
  "author": "Studio ABC",
  "description": "Mapping vidéo hall d'entrée",

  "settings": {
    "resolution": { "width": 1920, "height": 1080 },
    "framerate": 60,
    "autoSave": true,
    "autoSaveInterval": 60,
    "backgroundColor": "#000000",
    "preloadAllScenes": true,
    "enableConsoleLogging": true
  },

  "scenes": [
    {
      "id": "scene-uuid",
      "name": "Scène principale",
      "file": "scenes/scene-uuid.json",
      "thumbnail": "thumbnails/scene-uuid.jpg",
      "duration": 180000,
      "order": 0
    }
  ],

  "media": [
    {
      "id": "media-uuid",
      "name": "main_video.mp4",
      "type": "video",
      "path": "media/videos/media-uuid-main_video.mp4",
      "fileSize": 245000000,
      "duration": 180,
      "dimensions": { "width": 1920, "height": 1080 },
      "imported": "2025-01-04T14:30:00Z"
    }
  ],

  "startSceneId": "scene-uuid",

  "metadata": {
    "totalScenes": 1,
    "totalMedia": 1,
    "totalDuration": 180,
    "tags": []
  },

  "artnetConfig": {
    "enabled": true,
    "ip": "255.255.255.255",
    "port": 6454,
    "universe": 0,
    "fps": 40
  },

  "lightingSequences": [
    {
      "id": "seq-uuid",
      "name": "Séquence DMX principale",
      "duration": 180,
      "fixtures": ["fixture-1"],
      "loop": false,
      "speed": 1,
      "interpolation": "linear",
      "keyframes": [
        {
          "id": "kf-1",
          "time": 0,
          "fixtureId": "fixture-1",
          "values": [255, 128, 0, 0, 0, 0]
        },
        {
          "id": "kf-2",
          "time": 5,
          "fixtureId": "fixture-1",
          "values": [0, 255, 128, 0, 0, 0]
        }
      ]
    }
  ],

  "displayGroups": [
    {
      "id": "group-uuid",
      "name": "Projection principale",
      "enabled": true,
      "displayType": "projectors",
      "screens": [
        {
          "screenId": "screen-1",
          "position": { "row": 0, "col": 0 },
          "viewport": { "x": 0, "y": 0, "width": 1, "height": 1 },
          "videoMapping": {
            "enabled": true,
            "mode": "perspective",
            "perspectivePoints": {
              "topLeft": { "x": 0.02, "y": 0.01 },
              "topRight": { "x": 0.98, "y": 0.03 },
              "bottomLeft": { "x": 0.01, "y": 0.99 },
              "bottomRight": { "x": 0.97, "y": 0.98 }
            }
          }
        }
      ],
      "sceneId": "scene-uuid"
    }
  ],

  "schedules": [],
  "groupSchedules": []
}
```

### Structure d'une scène (scenes/[id].json)

```json
{
  "id": "scene-uuid",
  "name": "Scène principale",
  "projectId": "project-uuid",
  "created": "2025-01-05T10:30:00Z",
  "modified": "2025-01-05T14:00:00Z",

  "settings": {
    "backgroundColor": "#000000",
    "dimensions": { "width": 1920, "height": 1080 },
    "duration": 180000,
    "loop": true,
    "preloadMedia": true
  },

  "elements": [
    {
      "id": "elem-uuid",
      "type": "video",
      "name": "Vidéo principale",
      "position": { "x": 0, "y": 0, "unit": "px" },
      "size": { "width": 1920, "height": 1080, "unit": "px" },
      "rotation": 0,
      "opacity": 1,
      "visible": true,
      "locked": false,
      "zIndex": 0,
      "properties": {
        "src": "media-uuid",
        "autoplay": true,
        "loop": true,
        "muted": false,
        "volume": 1,
        "playbackRate": 1,
        "objectFit": "cover"
      }
    }
  ],

  "transitions": {
    "enter": { "type": "fade", "duration": 500, "easing": "ease-in-out" },
    "exit": { "type": "fade", "duration": 500, "easing": "ease-in-out" }
  },

  "metadata": {
    "elementCount": 1
  }
}
```

### Types d'éléments supportés par le player

| Type | Description | Propriétés clés |
|------|-------------|-----------------|
| `video` | Lecteur vidéo | src, autoplay, loop, volume, objectFit |
| `image` | Image statique | src, objectFit |
| `audio` | Piste audio | src, autoplay, loop, volume |
| `text` | Texte | content, fontFamily, fontSize, color |

### Configuration DMX/Art-Net

Le DMX utilise des séquences JSON avec keyframes interpolés :

```json
{
  "artnetConfig": {
    "enabled": true,
    "ip": "255.255.255.255",
    "port": 6454,
    "universe": 0,
    "fps": 40
  },
  "lightingSequences": [
    {
      "id": "seq-uuid",
      "name": "Séquence",
      "duration": 180,
      "loop": false,
      "speed": 1,
      "interpolation": "linear",
      "keyframes": [
        {
          "time": 0,
          "fixtureId": "fixture-1",
          "values": [255, 0, 0, 0, 0, 0]
        }
      ]
    }
  ]
}
```

**Interpolation** : Le player doit interpoler les valeurs DMX entre les keyframes selon le mode choisi (linear, ease-in, ease-out, ease-in-out).

### Modes de connexion DMX

Le player supporte 3 modes de sortie DMX :

#### 1. Art-Net (réseau)
Protocole standard sur Ethernet/WiFi. Broadcast ou unicast vers nodes Art-Net.

```json
{
  "dmx": {
    "mode": "artnet",
    "ip": "255.255.255.255",
    "port": 6454,
    "universe": 0
  }
}
```

#### 2. sACN / E1.31 (réseau)
Alternative à Art-Net, souvent utilisé en broadcast multicast.

```json
{
  "dmx": {
    "mode": "sacn",
    "universe": 1,
    "multicast": true
  }
}
```

#### 3. USB-DMX (connexion directe)
Adaptateurs USB vers DMX512 (ENTTEC Open DMX, ENTTEC Pro, DMXKing ultraDMX, etc.)

```json
{
  "dmx": {
    "mode": "usb",
    "port": "/dev/ttyUSB0",
    "driver": "enttec_pro",
    "baudrate": 250000
  }
}
```

**Drivers USB supportés :**
| Driver | Adaptateurs compatibles |
|--------|------------------------|
| `enttec_open` | ENTTEC Open DMX USB, clones FTDI |
| `enttec_pro` | ENTTEC DMX USB Pro, Pro Mk2 |
| `dmxking` | DMXKing ultraDMX Micro, ultraDMX Pro |

**Détection automatique :** Le player peut scanner `/dev/ttyUSB*` et `/dev/ttyACM*` pour détecter automatiquement les adaptateurs compatibles.

### Mapping vidéo (Corner Pin)

Configuration dans `displayGroups[].screens[].videoMapping` ou directement sur les éléments :

```json
{
  "videoMapping": {
    "enabled": true,
    "mode": "perspective",
    "backgroundColor": "#000000",
    "perspectivePoints": {
      "topLeft": { "x": 0.02, "y": 0.01 },
      "topRight": { "x": 0.98, "y": 0.03 },
      "bottomLeft": { "x": 0.01, "y": 0.99 },
      "bottomRight": { "x": 0.97, "y": 0.98 }
    }
  }
}
```

Les coordonnées sont normalisées (0-1) par rapport à la résolution de sortie.

---

## API REST

### Endpoints

#### Status

```
GET /api/status
```

Réponse :
```json
{
  "device": {
    "id": "10000000abcd1234",
    "hostname": "flowplayer-01",
    "ip": "192.168.1.50",
    "mac": "dc:a6:32:xx:xx:xx"
  },
  "system": {
    "uptime": 86400,
    "cpu_percent": 15.2,
    "memory_percent": 22.5,
    "temperature": 52.3,
    "disk_free_gb": 24.5
  },
  "player": {
    "state": "playing",
    "current_show": "Installation Musée XYZ",
    "position_ms": 45000,
    "duration_ms": 180000,
    "loop_count": 3
  },
  "schedule": {
    "enabled": true,
    "next_trigger": "2025-01-05T12:00:00Z",
    "triggers_today": ["09:00", "12:00", "15:00", "18:00"]
  },
  "dmx": {
    "protocol": "artnet",
    "universe": 0,
    "target_ip": "255.255.255.255",
    "fps": 40
  },
  "timestamp": "2025-01-05T10:45:30Z"
}
```

#### Contrôle playback

```
POST /api/control/play
POST /api/control/stop
POST /api/control/restart
```

Réponse :
```json
{
  "success": true,
  "state": "playing"
}
```

#### Gestion des shows

```
GET /api/shows
```

Réponse :
```json
{
  "shows": [
    {
      "id": "abc123",
      "name": "Installation Musée XYZ",
      "filename": "musee_xyz.zip",
      "duration_ms": 180000,
      "size_mb": 245.5,
      "uploaded": "2025-01-04T14:30:00Z",
      "active": true
    }
  ],
  "active_show": "abc123"
}
```

```
POST /api/shows/upload
Content-Type: multipart/form-data
```

```
POST /api/shows/{id}/activate
```

```
DELETE /api/shows/{id}
```

#### Planification

```
GET /api/schedule
```

Réponse :
```json
{
  "enabled": true,
  "mode": "daily",
  "rules": [
    {
      "id": "rule1",
      "days": ["mon", "tue", "wed", "thu", "fri"],
      "times": ["09:00", "12:00", "15:00", "18:00"],
      "enabled": true
    },
    {
      "id": "rule2",
      "days": ["sat", "sun"],
      "times": ["10:00", "14:00", "17:00"],
      "enabled": true
    }
  ],
  "exceptions": [
    {
      "date": "2025-12-25",
      "times": [],
      "reason": "Noël"
    }
  ]
}
```

```
PUT /api/schedule
Content-Type: application/json
```

#### Configuration

```
GET /api/config
PUT /api/config
```

```json
{
  "network": {
    "hostname": "flowplayer-01",
    "dhcp": true,
    "static_ip": null
  },
  "video": {
    "output": "HDMI-1",
    "resolution": "1920x1080",
    "refresh_rate": 60
  },
  "dmx": {
    "protocol": "artnet",
    "universe": 0,
    "target_ip": "255.255.255.255"
  },
  "monitoring": {
    "heartbeat_enabled": true,
    "heartbeat_url": "https://monitor.example.com/api/status",
    "heartbeat_interval_sec": 30
  },
  "audio": {
    "output": "hdmi",
    "volume": 100
  }
}
```

#### Système

```
GET /api/logs?lines=100&level=error
POST /api/system/reboot
POST /api/system/shutdown
POST /api/system/update
```

---

## Interface Web

### Pages

#### Dashboard (/)

```
┌─────────────────────────────────────────────────────────────┐
│  FLOW PLAYER                          flowplayer-01         │
│                                       192.168.1.50          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │              [THUMBNAIL / PREVIEW]                  │   │
│  │                                                     │   │
│  │                     advancement bar                  │   │
│  │              00:45  advancement bar 03:00            │   │
│  │                                                     │   │
│  │         [  ⏹ STOP  ]    [  ▶ PLAY  ]               │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Show actif: Installation Musée XYZ                         │
│  Status: En lecture (boucle #3)                             │
│                                                             │
│  Prochain déclenchement: 12:00 (dans 1h15)                  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  CPU: 15%  │  RAM: 22%  │  Temp: 52°C  │  Uptime: 24h      │
└─────────────────────────────────────────────────────────────┘
```

#### Shows (/shows)

```
┌─────────────────────────────────────────────────────────────┐
│  SHOWS                                    [ + Upload ]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ● Installation Musée XYZ                   [ACTIF]  │   │
│  │   Durée: 3:00 │ Taille: 245 MB                      │   │
│  │   Uploadé: 04/01/2025 14:30                         │   │
│  │                        [ Activer ] [ Supprimer ]    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Vitrine Noël                                      │   │
│  │   Durée: 1:30 │ Taille: 180 MB                      │   │
│  │   Uploadé: 01/12/2024 09:00                         │   │
│  │                        [ Activer ] [ Supprimer ]    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Schedule (/schedule)

```
┌─────────────────────────────────────────────────────────────┐
│  PLANIFICATION                        [ ] Activée           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Mode: ○ Manuel  ○ Boucle continue  ● Planifié             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Règle 1                                    [ ✓ ]    │   │
│  │ Jours: [✓]L [✓]M [✓]M [✓]J [✓]V [ ]S [ ]D          │   │
│  │ Horaires: 09:00, 12:00, 15:00, 18:00      [ + ]     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Règle 2                                    [ ✓ ]    │   │
│  │ Jours: [ ]L [ ]M [ ]M [ ]J [ ]V [✓]S [✓]D          │   │
│  │ Horaires: 10:00, 14:00, 17:00             [ + ]     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [ + Ajouter règle ]                                        │
│                                                             │
│  Exceptions:                                                │
│  • 25/12/2025 - Noël (aucun déclenchement)                 │
│  [ + Ajouter exception ]                                    │
│                                                             │
│                                    [ Enregistrer ]          │
└─────────────────────────────────────────────────────────────┘
```

#### Settings (/settings)

```
┌─────────────────────────────────────────────────────────────┐
│  CONFIGURATION                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RÉSEAU                                                     │
│  ├── Hostname:     [ flowplayer-01        ]                │
│  ├── IP actuelle:  192.168.1.50                            │
│  ├── MAC:          dc:a6:32:xx:xx:xx                       │
│  └── Mode:         ○ DHCP  ○ IP Statique                   │
│                                                             │
│  VIDÉO                                                      │
│  ├── Sortie:       [ HDMI-1 ▼ ]                            │
│  └── Résolution:   [ 1920x1080 @ 60Hz ▼ ]                  │
│                                                             │
│  AUDIO                                                      │
│  ├── Sortie:       [ HDMI ▼ ]                              │
│  └── Volume:       [=====●=====] 100%                      │
│                                                             │
│  DMX                                                        │
│  ├── Protocole:    ○ Art-Net  ○ sACN                       │
│  ├── Universe:     [ 0 ]                                   │
│  └── Target IP:    [ 255.255.255.255 ] (broadcast)         │
│                                                             │
│  MONITORING                                                 │
│  ├── Heartbeat:    [ ✓ ] Activé                            │
│  ├── URL:          [ https://monitor.example.com/status ]  │
│  └── Intervalle:   [ 30 ] secondes                         │
│                                                             │
│                        [ Annuler ] [ Enregistrer ]          │
├─────────────────────────────────────────────────────────────┤
│  SYSTÈME                                                    │
│  [ Redémarrer player ] [ Redémarrer Pi ] [ Mise à jour ]   │
└─────────────────────────────────────────────────────────────┘
```

#### Logs (/logs)

```
┌─────────────────────────────────────────────────────────────┐
│  LOGS                    Niveau: [ Tous ▼ ] [ Actualiser ] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  10:45:30 INFO  Playback started - Installation Musée XYZ  │
│  10:45:30 INFO  DMX output initialized - Art-Net universe 0│
│  10:45:31 DEBUG Video position: 1000ms                     │
│  10:45:32 DEBUG Video position: 2000ms                     │
│  10:48:30 INFO  Playback completed - loop count: 3         │
│  10:48:30 INFO  DMX blackout sent                          │
│  10:48:31 INFO  Waiting for next trigger: 12:00            │
│  ...                                                        │
│                                                             │
│                                        [ Télécharger logs ] │
└─────────────────────────────────────────────────────────────┘
```

---

## Monitoring distant

### Architecture

```
┌──────────────┐     HTTP POST      ┌──────────────────────┐
│ Flow Player  │ ────────────────▶  │ Serveur Monitoring   │
│ (Pi 5)       │   /api/heartbeat   │ (Flow ou standalone) │
│              │                    │                      │
│              │ ◀──────────────── │                      │
│              │   Commandes opt.   │                      │
└──────────────┘                    └──────────────────────┘
```

### Payload heartbeat

```json
{
  "device_id": "10000000abcd1234",
  "hostname": "flowplayer-01",
  "ip": "192.168.1.50",
  "timestamp": "2025-01-05T10:45:30Z",
  "player": {
    "state": "playing",
    "show": "Installation Musée XYZ",
    "position_ms": 45000,
    "duration_ms": 180000
  },
  "system": {
    "uptime": 86400,
    "cpu_percent": 15.2,
    "memory_percent": 22.5,
    "temperature": 52.3
  },
  "errors": []
}
```

### Alertes

Le serveur de monitoring peut déclencher des alertes sur :

- Player offline (pas de heartbeat depuis X minutes)
- Température critique (> 80°C)
- Erreur de lecture répétée
- Espace disque faible
- Crash et redémarrage

---

## Installation

### Prérequis

- Raspberry Pi 5 (4GB minimum, 8GB recommandé)
- Carte microSD 32GB+ (ou SSD NVMe)
- Alimentation officielle 27W USB-C
- Câble HDMI
- Connexion réseau (Ethernet recommandé)

### Installation automatique

```bash
curl -sSL https://flow-player.example.com/install.sh | bash
```

### Installation manuelle

```bash
# 1. Mise à jour système
sudo apt update && sudo apt upgrade -y

# 2. Installation dépendances
sudo apt install -y python3-venv python3-pip mpv libmpv-dev git

# 3. Clone du projet
sudo mkdir -p /opt/flow-player
sudo chown $USER:$USER /opt/flow-player
git clone https://github.com/example/flow-player.git /opt/flow-player

# 4. Environnement Python
cd /opt/flow-player
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Installation service
sudo cp systemd/flow-player.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable flow-player
sudo systemctl start flow-player
```

### Configuration USB auto-mount

```bash
# /etc/udev/rules.d/99-usb-automount.rules
SUBSYSTEM=="block", KERNEL=="sd[a-z]1", ACTION=="add", RUN+="/bin/mount -o uid=1000,gid=1000 /dev/%k /media/usb"
SUBSYSTEM=="block", KERNEL=="sd[a-z]1", ACTION=="remove", RUN+="/bin/umount /media/usb"
```

---

## Utilisation

### Workflow standard

1. **Création** : Créer le show dans Flow (PC/Mac)
2. **Export** : Menu "Export > Player Package"
3. **Transfert** : Copier le .zip sur clé USB
4. **Déploiement** : Brancher la clé sur le Pi
5. **Automatique** : Le Pi détecte et charge le show

### Via interface web

1. Accéder à `http://<ip-du-pi>:5000`
2. Onglet "Shows" > "Upload"
3. Sélectionner le fichier .zip
4. Activer le show uploadé
5. Configurer le planning si nécessaire

### Commandes CLI

```bash
# Status du service
sudo systemctl status flow-player

# Logs en temps réel
journalctl -u flow-player -f

# Redémarrage
sudo systemctl restart flow-player

# Arrêt
sudo systemctl stop flow-player
```

---

## Roadmap

### Version 1.0 (MVP)

- [x] Lecture vidéo avec décodage hardware
- [x] Mapping corner pin 4 points
- [x] Sortie DMX Art-Net
- [x] Audio synchronisé
- [x] Planification horaire basique
- [x] Interface web minimale
- [x] API REST status/control
- [x] Heartbeat monitoring

### Version 1.1

- [ ] Support sACN
- [ ] Multi-univers DMX (jusqu'à 4)
- [ ] Transitions entre shows
- [ ] Playlists
- [ ] GPIO triggers (boutons physiques)

### Version 1.2

- [ ] Edge blending basique
- [ ] Backup automatique configuration
- [ ] Mode kiosk navigateur
- [ ] Support multi-écrans

### Version 2.0

- [ ] Cluster de players synchronisés
- [ ] Timecode externe (LTC/MIDI)
- [ ] OSC input/output
- [ ] Plugin système pour extensions

---

## Licence

MIT License - Libre d'utilisation commerciale et modification.

---

## Support

- Documentation : https://flow-player.example.com/docs
- Issues : https://github.com/example/flow-player/issues
- Contact : support@example.com
