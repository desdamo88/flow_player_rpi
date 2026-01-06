# Installation Flow Player sur Raspberry Pi 5

> Guide complet pour créer une carte SD prête à l'emploi

## Matériel requis

- **Raspberry Pi 5** (4GB ou 8GB RAM recommandé)
- **Carte microSD** (32GB minimum, classe A2 recommandée pour les performances)
- **Alimentation officielle** Raspberry Pi 5 (27W USB-C)
- **Câble HDMI** vers écran/projecteur
- **Connexion réseau** (Ethernet recommandé pour la stabilité)
- **Optionnel:** Interface DMX USB (Enttec Open/Pro, DMXKing)

## Étape 1: Préparer la carte SD

### 1.1 Télécharger Raspberry Pi Imager

Télécharger depuis: https://www.raspberrypi.com/software/

### 1.2 Flasher l'OS

1. Lancer **Raspberry Pi Imager**
2. Cliquer sur **"Choisir l'appareil"** → **Raspberry Pi 5**
3. Cliquer sur **"Choisir l'OS"** → **Raspberry Pi OS (64-bit)** (version Lite recommandée)
4. Cliquer sur **"Choisir le stockage"** → Sélectionner la carte SD
5. Cliquer sur **l'engrenage ⚙️** pour les paramètres avancés:

```
✅ Définir le nom d'hôte: flowplayer-01
✅ Activer SSH (authentification par mot de passe)
✅ Définir le nom d'utilisateur et mot de passe:
   - Utilisateur: flow
   - Mot de passe: [votre mot de passe]
✅ Configurer le Wi-Fi (optionnel si Ethernet)
✅ Définir les paramètres régionaux:
   - Fuseau horaire: Europe/Paris
   - Disposition clavier: fr
```

6. Cliquer sur **"Écrire"** et attendre la fin du processus

## Étape 2: Premier démarrage et configuration système

### 2.1 Connexion SSH

Insérer la carte SD dans le RPi5, brancher l'alimentation et attendre ~2 minutes.

```bash
# Trouver l'IP du RPi (depuis votre PC)
ping flowplayer-01.local

# Se connecter en SSH
ssh flow@flowplayer-01.local
```

### 2.2 Mise à jour du système

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### 2.3 Configuration du système

```bash
sudo raspi-config
```

Configurer:
- **System Options → Boot / Auto Login** → Console Autologin
- **Display Options → VNC Resolution** → 1920x1080 (ou résolution de votre écran)
- **Interface Options → VNC** → Enable (optionnel, pour debug)
- **Performance Options → GPU Memory** → 256
- **Advanced Options → Expand Filesystem**

```bash
sudo reboot
```

## Étape 3: Installation des dépendances

### 3.1 Paquets système

```bash
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    mpv \
    libmpv-dev \
    libasound2-dev \
    libatlas-base-dev \
    fonts-dejavu \
    htop \
    tmux
```

### 3.2 Paquets pour DMX (optionnel)

```bash
# Pour Art-Net (réseau)
# Rien à installer, utilise le réseau standard

# Pour DMX USB (Enttec, etc.)
sudo apt install -y libftdi1-dev
sudo usermod -a -G dialout flow
```

## Étape 4: Installation de Flow Player

### 4.1 Cloner le projet

```bash
cd /opt
sudo mkdir flow-player
sudo chown flow:flow flow-player
git clone https://github.com/VOTRE_REPO/flow_light_player_rpi.git flow-player
cd flow-player
```

Ou copier depuis votre machine de développement:
```bash
# Depuis votre PC
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
    /chemin/vers/flow_light_player_rpi/ \
    flow@flowplayer-01.local:/opt/flow-player/
```

### 4.2 Créer l'environnement Python

```bash
cd /opt/flow-player
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.3 Créer les répertoires

```bash
mkdir -p /opt/flow-player/shows
mkdir -p /opt/flow-player/config
mkdir -p /opt/flow-player/logs
```

### 4.4 Configuration initiale

Créer `/opt/flow-player/config/config.json`:

```bash
cat > /opt/flow-player/config/config.json << 'EOF'
{
  "network": {
    "hostname": "flowplayer-01",
    "dhcp": true
  },
  "video": {
    "output": "HDMI-1",
    "resolution": "1920x1080",
    "refresh_rate": 60
  },
  "audio": {
    "output": "hdmi",
    "volume": 100
  },
  "dmx": {
    "mode": "artnet",
    "enabled": true,
    "ip": "255.255.255.255",
    "port": 6454,
    "universe": 0,
    "fps": 40
  },
  "monitoring": {
    "heartbeat_enabled": false,
    "api_enabled": true,
    "api_key": ""
  },
  "autoplay": true,
  "loop": true,
  "web_host": "0.0.0.0",
  "web_port": 5000,
  "log_level": "WARNING"
}
EOF
```

## Étape 5: Configuration du démarrage automatique

### 5.1 Créer le service systemd

```bash
sudo cat > /etc/systemd/system/flow-player.service << 'EOF'
[Unit]
Description=Flow Player - Video/Audio/DMX Player
After=network.target graphical.target
Wants=graphical.target

[Service]
Type=simple
User=flow
Group=flow
WorkingDirectory=/opt/flow-player
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/1000
ExecStart=/opt/flow-player/venv/bin/python -m src.main
Restart=always
RestartSec=5
StandardOutput=append:/opt/flow-player/logs/flow-player.log
StandardError=append:/opt/flow-player/logs/flow-player.log

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2 Activer le service

```bash
sudo systemctl daemon-reload
sudo systemctl enable flow-player.service
sudo systemctl start flow-player.service

# Vérifier le statut
sudo systemctl status flow-player.service
```

### 5.3 Commandes utiles

```bash
# Voir les logs en temps réel
sudo journalctl -u flow-player -f

# Redémarrer le service
sudo systemctl restart flow-player

# Arrêter le service
sudo systemctl stop flow-player
```

## Étape 6: Configuration réseau avancée (optionnel)

### 6.1 IP statique (recommandé pour production)

Éditer `/etc/dhcpcd.conf`:

```bash
sudo nano /etc/dhcpcd.conf
```

Ajouter à la fin:
```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

### 6.2 Hostname personnalisé

```bash
sudo hostnamectl set-hostname flowplayer-01
sudo nano /etc/hosts
# Remplacer raspberrypi par flowplayer-01
```

## Étape 7: Optimisations pour la production

### 7.1 Désactiver les services inutiles

```bash
# Désactiver le Bluetooth si non utilisé
sudo systemctl disable bluetooth
sudo systemctl disable hciuart

# Désactiver le Wi-Fi si Ethernet utilisé
# Ajouter dans /boot/config.txt: dtoverlay=disable-wifi
```

### 7.2 Configuration GPU pour vidéo fluide

Éditer `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Ajouter/modifier:
```ini
# GPU Memory
gpu_mem=256

# Forcer la sortie HDMI
hdmi_force_hotplug=1
hdmi_group=1
hdmi_mode=16

# Désactiver l'économiseur d'écran
disable_overscan=1

# Audio HDMI
hdmi_drive=2
```

### 7.3 Désactiver l'écran de veille

```bash
# Créer un script de désactivation
sudo nano /etc/xdg/lxsession/LXDE-pi/autostart
```

Ajouter:
```
@xset s off
@xset -dpms
@xset s noblank
```

### 7.4 Rotation des logs

```bash
sudo cat > /etc/logrotate.d/flow-player << 'EOF'
/opt/flow-player/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 644 flow flow
}
EOF
```

## Étape 8: Importer un show

### 8.1 Via l'interface web

1. Ouvrir `http://flowplayer-01.local:5000` dans un navigateur
2. Aller dans **Shows**
3. Cliquer sur **Importer** et sélectionner le fichier `.zip` exporté depuis Flow Studio

### 8.2 Via SCP/SFTP

```bash
# Depuis votre PC
scp mon-show.zip flow@flowplayer-01.local:/opt/flow-player/shows/
```

Puis extraire:
```bash
ssh flow@flowplayer-01.local
cd /opt/flow-player/shows
unzip mon-show.zip -d mon-show/
```

### 8.3 Via clé USB

```bash
# Monter la clé USB
sudo mount /dev/sda1 /mnt

# Copier le show
cp /mnt/mon-show.zip /opt/flow-player/shows/
unzip /opt/flow-player/shows/mon-show.zip -d /opt/flow-player/shows/mon-show/

# Démonter
sudo umount /mnt
```

## Étape 9: Test final

### 9.1 Vérifier les services

```bash
# Vérifier que le service tourne
sudo systemctl status flow-player

# Vérifier les logs
tail -50 /opt/flow-player/logs/flow-player.log

# Tester l'API
curl http://localhost:5000/api/health
```

### 9.2 Vérifier l'accès web

Depuis un navigateur sur le même réseau:
- `http://flowplayer-01.local:5000`
- Ou `http://[IP_DU_RPI]:5000`

### 9.3 Tester la lecture

1. Ouvrir l'interface web
2. Aller dans **Shows** et activer un show
3. Aller dans **Dashboard** et lancer une scène
4. Vérifier que la vidéo s'affiche sur l'écran connecté au RPi

## Dépannage

### Pas de vidéo sur l'écran

```bash
# Vérifier que MPV peut afficher
DISPLAY=:0 mpv --vo=gpu /opt/flow-player/shows/*/media/videos/*.mp4

# Vérifier les permissions
ls -la /dev/dri/
groups flow  # Doit inclure 'video'
```

### Service qui ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u flow-player -n 100 --no-pager

# Tester manuellement
cd /opt/flow-player
source venv/bin/activate
python -m src.main
```

### Pas de DMX

```bash
# Vérifier la connexion USB
lsusb | grep -i ftdi

# Vérifier les permissions
ls -la /dev/ttyUSB*
# Si permission denied:
sudo usermod -a -G dialout flow
# Puis reboot
```

### Problèmes réseau

```bash
# Vérifier l'IP
ip addr show

# Tester la connectivité
ping google.com

# Vérifier le hostname
hostname -f
```

## Sauvegarde de la carte SD

Une fois tout configuré, créer une image de sauvegarde:

### Sur Linux/Mac

```bash
# Identifier la carte SD
lsblk

# Créer l'image (remplacer /dev/sdX par votre device)
sudo dd if=/dev/sdX of=flowplayer-image.img bs=4M status=progress

# Compresser l'image
gzip flowplayer-image.img
```

### Restaurer sur une nouvelle carte

```bash
gunzip -c flowplayer-image.img.gz | sudo dd of=/dev/sdX bs=4M status=progress
```

---

## Résumé des accès

| Service | URL/Commande |
|---------|--------------|
| Interface Web | `http://flowplayer-01.local:5000` |
| SSH | `ssh flow@flowplayer-01.local` |
| API Health | `curl http://flowplayer-01.local:5000/api/health` |
| Logs | `tail -f /opt/flow-player/logs/flow-player.log` |
| Service | `sudo systemctl status flow-player` |

## Ports utilisés

| Port | Service |
|------|---------|
| 5000 | Interface Web + API REST |
| 6454 | Art-Net DMX (UDP) |
| 5568 | sACN DMX (UDP) |
| 22 | SSH |

---

*Document créé le 2026-01-05 pour Flow Player v0.9.0*
