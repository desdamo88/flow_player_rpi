# Flow Player RPi - Roadmap

> **Dernière mise à jour**: 2026-01-05

## Statut Actuel: v0.9.0 - Beta

Le player est fonctionnel pour la plupart des cas d'usage. Quelques fonctionnalités avancées sont en cours de finalisation.

---

## Fonctionnalités Implémentées

### Core Player
- [x] Chargement des projets Flow Studio (.zip)
- [x] Parsing complet du format project.json
- [x] Gestion des scènes avec éléments multiples
- [x] Lecture vidéo via MPV (GPU acceleré)
- [x] Lecture audio (intégré vidéo ou séparé)
- [x] Boucle et seek
- [x] Persistance de l'état (show actif, scène courante)

### DMX/Art-Net
- [x] Sortie Art-Net (UDP broadcast)
- [x] Sortie sACN (E1.31)
- [x] Support USB-DMX (Enttec Pro/Open)
- [x] Interpolation keyframes à 40fps
- [x] Liaison scène → séquence DMX
- [x] Blackout automatique

### Interface Web
- [x] Dashboard avec statut temps réel
- [x] Gestion des shows (upload, delete, activate)
- [x] Sélection et lecture de scènes
- [x] Visualisation du mapping vidéo (perspective + mesh)
- [x] Contrôles de lecture (play/stop/pause/seek)
- [x] Configuration DMX et audio
- [x] Timestamps d'import des shows
- [x] Logs en temps réel

### Video Mapping
- [x] Mode perspective (4 coins)
- [x] Mode mesh (grille NxM)
- [x] Détection de déformation
- [x] Visualisation SVG interactive
- [x] FFmpeg perspective filter fallback
- [x] GLSL shader generation (GPU)
- [x] Soft edge blending (multi-projecteur)

### Système
- [x] Service systemd
- [x] Découverte mDNS (flowplayer.local)
- [x] Scripts d'installation
- [x] Mode développement (Ubuntu/Linux)
- [x] Heartbeat monitoring

---

## En Cours de Test

### Video Mapping GPU
- [ ] Tests sur RPi 5 avec VideoCore VII
- [ ] Validation performance mesh complexes
- [ ] Calibration temps réel

### DMX
- [ ] Tests avec fixtures réels
- [ ] Validation timing précis

---

## Fonctionnalités Planifiées

### v1.0.0 - Release Stable
- [ ] Tests complets sur Raspberry Pi 5
- [ ] Documentation utilisateur complète
- [ ] Images RPi pré-configurées
- [ ] Optimisation mémoire/CPU

### v1.1.0 - Améliorations
- [ ] Multi-écrans (display groups)
- [ ] Synchronisation multi-players
- [ ] Timeline avec marqueurs
- [ ] Transitions entre scènes

### v1.2.0 - Fonctionnalités Avancées
- [ ] Masques arbitraires
- [ ] Black level compensation
- [ ] Calibration automatique
- [ ] Support NDI (entrée vidéo réseau)

---

## Compatibilité Matérielle

| Matériel | Status | Notes |
|----------|--------|-------|
| Raspberry Pi 5 | Testé | Recommandé |
| Raspberry Pi 4 | Compatible | Performance réduite |
| Raspberry Pi 3 | Non recommandé | Trop lent |
| Ubuntu/Linux x64 | Testé | Mode développement |

### Interfaces DMX Testées
| Interface | Status |
|-----------|--------|
| Art-Net (réseau) | Fonctionnel |
| sACN/E1.31 | Fonctionnel |
| Enttec USB Pro | À tester |
| Enttec Open DMX | À tester |

---

## Prérequis pour Déploiement Production

### Matériel
- Raspberry Pi 5 (4GB+ RAM)
- Carte SD 32GB+ (Class 10)
- Alimentation 5V/5A officielle
- Câble HDMI vers projecteur/écran

### Logiciel (installé automatiquement)
- Raspberry Pi OS Bookworm (64-bit Lite)
- Python 3.11+
- MPV avec support DRM/KMS
- Flask, python-mpv

### Configuration Réseau
- IP fixe ou DHCP
- Port 5000 (interface web)
- Port 6454 (Art-Net si utilisé)

---

## Commandes de Test

```bash
# Vérifier la syntaxe Python
python3 -m py_compile src/flow_player.py

# Lancer les tests (si disponibles)
python3 -m pytest tests/

# Vérifier les imports
python3 -c "from src.core.video_mapping import VideoMappingEngine; print('OK')"

# Test MPV
mpv --vo=gpu --hwdec=auto test_video.mp4
```

---

## Contribuer

1. Fork le repository
2. Créer une branche feature
3. Commiter les changements
4. Ouvrir une Pull Request

---

## Changelog

### v0.9.0 (2026-01-05)
- Implémentation complète du video mapping (perspective + mesh)
- GLSL shaders pour GPU warping
- Soft edge blending multi-projecteur
- Fix suppression shows avec zip source
- Timestamps d'import des shows
- API mapping endpoints

### v0.8.0 (2026-01-05)
- Support mesh grid warping
- Visualisation mapping dans dashboard
- Scene-specific mapping

### v0.7.0 (2026-01-04)
- Sélection et lecture de scènes
- Persistence scène courante
- Fix media serving (path references)

### v0.6.0 (2026-01-04)
- Interface web complète
- Upload/gestion des shows
- Contrôles de lecture
