# InteractStudio Monitoring API - Documentation Technique

> **Version du document : 1.1.0**
> Date : 2026-01-05
> Version API : 1.1.0

## Vue d'ensemble

L'API REST de monitoring d'InteractStudio permet de surveiller et contrôler en temps réel l'état de l'application, les écrans actifs, les scènes en cours d'exécution, les plannings horaires, et les séquences DMX. Elle supporte également les WebSocket pour les mises à jour temps réel.

### Informations de Base

- **URL de Base (API principale)**: `http://localhost:3100`
- **URL de Base (API legacy)**: `http://localhost:3333/api`
- **WebSocket**: `ws://localhost:3100?apiKey={apiKey}`
- **Format**: JSON
- **Authentification**: API Key (header `X-API-Key`)
- **Version**: 1.1.0

### Configuration par Défaut

```json
{
  "host": "0.0.0.0",
  "port": 3100,
  "legacyPort": 3333,
  "apiKeyHeader": "X-API-Key",
  "cors": {
    "allowedOrigins": ["*"],
    "note": "Accepte toutes les origines par défaut"
  },
  "rateLimit": {
    "windowMs": 60000,
    "maxRequests": 100
  },
  "websocket": {
    "enabled": true,
    "heartbeatInterval": 30000
  }
}
```

**Note CORS**: Par défaut, l'API accepte les requêtes de **toutes les origines** (`*`). Vous pourrez restreindre les origines autorisées plus tard dans la configuration une fois que vous connaîtrez l'IP du PC de monitoring.

---

## 🔐 Authentification

Toutes les requêtes (sauf `/health` et `/docs`) nécessitent une clé API.

### Header requis

```http
X-API-Key: your-api-key-here
```

### Obtenir une API Key

1. Ouvrir InteractStudio
2. Aller dans Settings → API Monitoring
3. Activer l'API
4. Copier la clé générée automatiquement

### Exemple de requête avec authentification

```bash
curl -X GET http://localhost:3333/api/project \
  -H "X-API-Key: a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

```javascript
fetch('http://localhost:3333/api/project', {
  headers: {
    'X-API-Key': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
  }
})
```

---

## 📡 Endpoints

### 1. Health Check

Vérifier si l'application est fonctionnelle.

**Endpoint**: `GET /api/health`
**Authentification**: Non requise
**Rate Limit**: Aucun

#### Réponse Success (200)

```json
{
  "status": "running",
  "uptime": 123456,
  "version": "1.0.0",
  "timestamp": "2025-11-11T10:30:00.000Z",
  "apiVersion": "1.0.0"
}
```

#### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `status` | string | État de l'app: `"running"`, `"error"`, `"stopped"` |
| `uptime` | number | Temps depuis démarrage (secondes) |
| `version` | string | Version d'InteractStudio |
| `timestamp` | string | Date/heure actuelle (ISO 8601) |
| `apiVersion` | string | Version de l'API |

#### Exemple d'utilisation

```javascript
async function checkHealth() {
  const response = await fetch('http://localhost:3333/api/health');
  const data = await response.json();

  if (data.status === 'running') {
    console.log(`App is running for ${data.uptime}s`);
  }
}
```

---

### 2. Informations Projet

Récupérer les informations du projet actuellement ouvert.

**Endpoint**: `GET /api/project`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Mon Projet Interactive",
  "path": "/Users/username/Projects/MonProjet",
  "createdAt": "2025-01-15T09:00:00.000Z",
  "lastModified": "2025-11-11T10:00:00.000Z",
  "scenesCount": 15,
  "elementsCount": 45,
  "mediaCount": 23,
  "autoStart": {
    "enabled": true,
    "displayMappingsCount": 3
  }
}
```

#### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `id` | string | UUID du projet |
| `name` | string | Nom du projet |
| `path` | string | Chemin fichier projet |
| `createdAt` | string | Date de création (ISO 8601) |
| `lastModified` | string | Dernière modification (ISO 8601) |
| `scenesCount` | number | Nombre total de scènes |
| `elementsCount` | number | Nombre total d'éléments |
| `mediaCount` | number | Nombre de médias |
| `autoStart.enabled` | boolean | Auto-start activé |
| `autoStart.displayMappingsCount` | number | Nombre d'écrans configurés |

#### Erreur: Pas de projet ouvert (404)

```json
{
  "error": "No project currently opened",
  "code": "NO_PROJECT"
}
```

---

### 3. Liste des Scènes

Récupérer toutes les scènes du projet.

**Endpoint**: `GET /api/project/scenes`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "scenes": [
    {
      "id": "scene-001",
      "name": "Scène d'Accueil",
      "order": 0,
      "elementsCount": 5,
      "duration": 30000,
      "isActive": true,
      "activeOnDisplays": ["display-1", "display-2"]
    },
    {
      "id": "scene-002",
      "name": "Scène Quiz",
      "order": 1,
      "elementsCount": 8,
      "duration": null,
      "isActive": false,
      "activeOnDisplays": []
    }
  ],
  "total": 2
}
```

#### Champs Scene

| Champ | Type | Description |
|-------|------|-------------|
| `id` | string | ID unique de la scène |
| `name` | string | Nom de la scène |
| `order` | number | Ordre dans la liste |
| `elementsCount` | number | Nombre d'éléments |
| `duration` | number\|null | Durée en ms (null si infinie) |
| `isActive` | boolean | Scène actuellement affichée |
| `activeOnDisplays` | string[] | IDs des écrans affichant cette scène |

---

### 4. Liste des Écrans

Récupérer tous les écrans configurés et leur état.

**Endpoint**: `GET /api/displays`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "displays": [
    {
      "id": "display-001",
      "screenId": "69733382",
      "name": "Écran Principal",
      "enabled": true,
      "resolution": {
        "width": 1920,
        "height": 1080
      },
      "position": {
        "x": 0,
        "y": 0
      },
      "currentScene": {
        "id": "scene-001",
        "name": "Scène d'Accueil",
        "startedAt": "2025-11-11T10:00:00.000Z",
        "duration": 30000,
        "elapsedTime": 15234
      },
      "windowStatus": "open",
      "lastUpdate": "2025-11-11T10:15:34.000Z"
    },
    {
      "id": "display-002",
      "screenId": "69733383",
      "name": "Écran Secondaire",
      "enabled": true,
      "resolution": {
        "width": 1920,
        "height": 1080
      },
      "position": {
        "x": 1920,
        "y": 0
      },
      "currentScene": null,
      "windowStatus": "closed",
      "lastUpdate": "2025-11-11T09:30:00.000Z"
    }
  ],
  "total": 2,
  "activeCount": 1
}
```

#### Champs Display

| Champ | Type | Description |
|-------|------|-------------|
| `id` | string | ID unique du display |
| `screenId` | string | ID de l'écran physique |
| `name` | string | Nom personnalisé |
| `enabled` | boolean | Display activé |
| `resolution` | object | Résolution de l'écran |
| `position` | object | Position (x, y) |
| `currentScene` | object\|null | Scène actuellement affichée |
| `currentScene.startedAt` | string | Début d'affichage (ISO 8601) |
| `currentScene.elapsedTime` | number | Temps écoulé (ms) |
| `windowStatus` | string | `"open"`, `"closed"`, `"minimized"` |
| `lastUpdate` | string | Dernière mise à jour (ISO 8601) |

---

### 5. Détails d'un Écran

Récupérer les détails complets d'un écran spécifique.

**Endpoint**: `GET /api/displays/:id`
**Authentification**: Requise

#### Paramètres URL

| Paramètre | Type | Description |
|-----------|------|-------------|
| `id` | string | ID du display |

#### Réponse Success (200)

```json
{
  "id": "display-001",
  "screenId": "69733382",
  "name": "Écran Principal",
  "enabled": true,
  "resolution": {
    "width": 1920,
    "height": 1080
  },
  "position": {
    "x": 0,
    "y": 0
  },
  "currentScene": {
    "id": "scene-001",
    "name": "Scène d'Accueil",
    "startedAt": "2025-11-11T10:00:00.000Z",
    "duration": 30000,
    "elapsedTime": 15234,
    "elements": [
      {
        "id": "elem-001",
        "type": "text",
        "name": "Titre",
        "visible": true,
        "position": { "x": 100, "y": 50 },
        "size": { "width": 500, "height": 100 }
      },
      {
        "id": "elem-002",
        "type": "image",
        "name": "Logo",
        "visible": true,
        "position": { "x": 800, "y": 50 },
        "size": { "width": 200, "height": 200 },
        "src": "media/logo.png"
      }
    ]
  },
  "windowStatus": "open",
  "lastUpdate": "2025-11-11T10:15:34.000Z"
}
```

#### Erreur: Display non trouvé (404)

```json
{
  "error": "Display not found",
  "code": "DISPLAY_NOT_FOUND",
  "displayId": "display-999"
}
```

---

### 6. Scène Active d'un Écran

Récupérer uniquement la scène actuellement affichée sur un écran.

**Endpoint**: `GET /api/displays/:id/scene`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "displayId": "display-001",
  "displayName": "Écran Principal",
  "scene": {
    "id": "scene-001",
    "name": "Scène d'Accueil",
    "startedAt": "2025-11-11T10:00:00.000Z",
    "duration": 30000,
    "elapsedTime": 15234,
    "elementsCount": 5,
    "progress": 50.78
  }
}
```

#### Réponse: Aucune scène active (200)

```json
{
  "displayId": "display-001",
  "displayName": "Écran Principal",
  "scene": null
}
```

---

### 7. Plannings Horaires

Récupérer tous les plannings horaires configurés.

**Endpoint**: `GET /api/schedules`
**Authentification**: Requise

#### Query Parameters (optionnels)

| Paramètre | Type | Description |
|-----------|------|-------------|
| `enabled` | boolean | Filtrer par statut activé |
| `today` | boolean | Uniquement les schedules d'aujourd'hui |
| `upcoming` | number | Nombre de prochains schedules |

#### Réponse Success (200)

```json
{
  "schedules": [
    {
      "id": "schedule-001",
      "name": "Matin - Écran Principal",
      "groupId": "group-001",
      "groupName": "Écran Principal",
      "sceneId": "scene-001",
      "sceneName": "Scène Matin",
      "time": "08:00",
      "days": [1, 2, 3, 4, 5],
      "daysText": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"],
      "enabled": true,
      "nextExecution": "2025-11-12T08:00:00.000Z",
      "lastExecution": "2025-11-11T08:00:00.000Z"
    },
    {
      "id": "schedule-002",
      "name": "Midi - Écran Principal",
      "groupId": "group-001",
      "groupName": "Écran Principal",
      "sceneId": "scene-003",
      "sceneName": "Scène Pause",
      "time": "12:00",
      "days": [1, 2, 3, 4, 5, 6, 7],
      "daysText": ["Tous les jours"],
      "enabled": true,
      "nextExecution": "2025-11-11T12:00:00.000Z",
      "lastExecution": "2025-11-10T12:00:00.000Z"
    }
  ],
  "total": 2,
  "enabledCount": 2
}
```

#### Champs Schedule

| Champ | Type | Description |
|-------|------|-------------|
| `id` | string | ID unique du schedule |
| `name` | string | Nom du planning |
| `groupId` | string | ID du groupe d'écrans |
| `groupName` | string | Nom du groupe |
| `sceneId` | string | ID de la scène à afficher |
| `sceneName` | string | Nom de la scène |
| `time` | string | Heure d'exécution (HH:MM) |
| `days` | number[] | Jours de la semaine (0=dimanche, 1=lundi, ..., 6=samedi) |
| `daysText` | string[] | Jours en texte |
| `enabled` | boolean | Planning activé |
| `nextExecution` | string | Prochaine exécution (ISO 8601) |
| `lastExecution` | string\|null | Dernière exécution (ISO 8601) |

#### Exemple avec filtres

```bash
# Uniquement les schedules actifs
GET /api/schedules?enabled=true

# Schedules d'aujourd'hui
GET /api/schedules?today=true

# 5 prochains schedules
GET /api/schedules?upcoming=5
```

---

### 8. Prochains Plannings

Récupérer les prochains plannings à venir.

**Endpoint**: `GET /api/schedules/upcoming`
**Authentification**: Requise

#### Query Parameters (optionnels)

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `limit` | number | 10 | Nombre max de résultats |
| `hours` | number | 24 | Fenêtre temporelle (heures) |

#### Réponse Success (200)

```json
{
  "upcoming": [
    {
      "scheduleId": "schedule-002",
      "scheduleName": "Midi - Écran Principal",
      "executionTime": "2025-11-11T12:00:00.000Z",
      "timeUntil": 5400000,
      "timeUntilText": "1h 30m",
      "sceneId": "scene-003",
      "sceneName": "Scène Pause",
      "groupId": "group-001",
      "groupName": "Écran Principal",
      "day": "Mardi"
    },
    {
      "scheduleId": "schedule-003",
      "scheduleName": "Soir - Écran Principal",
      "executionTime": "2025-11-11T18:00:00.000Z",
      "timeUntil": 27000000,
      "timeUntilText": "7h 30m",
      "sceneId": "scene-004",
      "sceneName": "Scène Fermeture",
      "groupId": "group-001",
      "groupName": "Écran Principal",
      "day": "Mardi"
    }
  ],
  "total": 2,
  "windowHours": 24
}
```

---

### 9. Séquences d'Éclairage

Récupérer toutes les séquences d'éclairage disponibles.

**Endpoint**: `GET /api/sequences`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "sequences": [
    {
      "id": "seq-001",
      "name": "Séquence Jour",
      "duration": 60000,
      "stepsCount": 10,
      "loop": true,
      "enabled": true,
      "fixtures": [
        {
          "id": "fixture-1",
          "name": "Spot Principal",
          "universe": 0,
          "channel": 1
        }
      ]
    },
    {
      "id": "seq-002",
      "name": "Séquence Nuit",
      "duration": 45000,
      "stepsCount": 8,
      "loop": true,
      "enabled": true,
      "fixtures": [
        {
          "id": "fixture-1",
          "name": "Spot Principal",
          "universe": 0,
          "channel": 1
        },
        {
          "id": "fixture-2",
          "name": "Spot Secondaire",
          "universe": 0,
          "channel": 10
        }
      ]
    }
  ],
  "total": 2
}
```

---

### 10. Séquences en Cours d'Exécution

Récupérer les séquences d'éclairage actuellement en cours.

**Endpoint**: `GET /api/sequences/running`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "running": [
    {
      "sequenceId": "seq-001",
      "sequenceName": "Séquence Jour",
      "startedAt": "2025-11-11T10:00:00.000Z",
      "duration": 60000,
      "elapsedTime": 27345,
      "progress": 45.58,
      "currentStep": 5,
      "totalSteps": 10,
      "loop": true,
      "loopCount": 3
    }
  ],
  "total": 1
}
```

#### Réponse: Aucune séquence active (200)

```json
{
  "running": [],
  "total": 0
}
```

---

### 11. Effets d'Éclairage

Récupérer tous les effets d'éclairage disponibles.

**Endpoint**: `GET /api/effects`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "effects": [
    {
      "id": "effect-001",
      "name": "Fade Doux",
      "type": "fade",
      "duration": 2000,
      "fixtures": ["fixture-1", "fixture-2"]
    },
    {
      "id": "effect-002",
      "name": "Stroboscope",
      "type": "strobe",
      "speed": 10,
      "fixtures": ["fixture-1"]
    }
  ],
  "total": 2
}
```

---

### 12. Effets en Cours d'Exécution

Récupérer les effets d'éclairage actuellement actifs.

**Endpoint**: `GET /api/effects/running`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "running": [
    {
      "effectId": "effect-001",
      "effectName": "Fade Doux",
      "startedAt": "2025-11-11T10:05:00.000Z",
      "fixtures": ["fixture-1", "fixture-2"]
    }
  ],
  "total": 1
}
```

---

### 13. Statistiques Système

Récupérer les statistiques système de l'application.

**Endpoint**: `GET /api/stats`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "system": {
    "platform": "darwin",
    "arch": "arm64",
    "nodeVersion": "v18.17.0",
    "electronVersion": "25.3.1"
  },
  "process": {
    "uptime": 123456,
    "memoryUsage": {
      "rss": 156725248,
      "heapTotal": 89407488,
      "heapUsed": 67234816,
      "external": 2456789
    },
    "cpu": {
      "user": 123456,
      "system": 45678
    }
  },
  "application": {
    "projectOpened": true,
    "activeDisplays": 2,
    "activeScenes": 2,
    "runningSequences": 1,
    "runningEffects": 0
  },
  "timestamp": "2025-11-11T10:30:00.000Z"
}
```

---

### 14. Contrôle de Lecture (Flow Player RPi)

Ces endpoints sont conçus pour les players RPi qui exposent une API de contrôle.

#### 14.1 Lecture / Pause / Stop

**Endpoint**: `POST /api/control/play`
**Authentification**: Requise

```json
{
  "sceneId": "scene-001"
}
```

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "play",
  "sceneId": "scene-001"
}
```

**Endpoint**: `POST /api/control/pause`
**Authentification**: Requise

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "pause"
}
```

**Endpoint**: `POST /api/control/stop`
**Authentification**: Requise

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "stop"
}
```

#### 14.2 Navigation Scènes

**Endpoint**: `POST /api/control/next`
**Authentification**: Requise

```json
{
  "success": true,
  "action": "next",
  "newSceneId": "scene-002"
}
```

**Endpoint**: `POST /api/control/previous`
**Authentification**: Requise

```json
{
  "success": true,
  "action": "previous",
  "newSceneId": "scene-001"
}
```

#### 14.3 Chargement Direct de Scène

**Endpoint**: `POST /api/control/load-scene`
**Authentification**: Requise

**Corps de la requête**
```json
{
  "sceneId": "scene-003"
}
```

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "load-scene",
  "sceneId": "scene-003",
  "sceneName": "Scène Vidéo"
}
```

#### 14.4 Contrôle du Volume

**Endpoint**: `POST /api/control/volume`
**Authentification**: Requise

**Corps de la requête**
```json
{
  "volume": 75
}
```

**Réponse Success (200)**
```json
{
  "success": true,
  "volume": 75
}
```

---

### 15. Contrôle Système (Flow Player RPi)

#### 15.1 Redémarrage et Arrêt

**Endpoint**: `POST /api/system/reboot`
**Authentification**: Requise

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "reboot",
  "message": "System will reboot in 5 seconds"
}
```

**Endpoint**: `POST /api/system/shutdown`
**Authentification**: Requise

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "shutdown",
  "message": "System will shutdown in 5 seconds"
}
```

**Endpoint**: `POST /api/system/restart-player`
**Authentification**: Requise

**Réponse Success (200)**
```json
{
  "success": true,
  "action": "restart-player",
  "message": "Player service will restart"
}
```

---

### 16. Groupes d'Écrans

Récupérer tous les groupes d'écrans configurés.

**Endpoint**: `GET /api/display-groups`
**Authentification**: Requise

#### Réponse Success (200)

```json
{
  "groups": [
    {
      "id": "group-001",
      "name": "Écran Principal",
      "enabled": true,
      "displayType": "screens",
      "screensCount": 1,
      "screens": [
        {
          "screenId": "69733382",
          "position": { "row": 0, "col": 0 }
        }
      ],
      "currentScene": {
        "id": "scene-001",
        "name": "Scène d'Accueil"
      },
      "schedules": [
        {
          "id": "schedule-001",
          "time": "08:00",
          "sceneId": "scene-001"
        }
      ]
    }
  ],
  "total": 1
}
```

---

## ❌ Codes d'Erreur

### Erreurs HTTP Standard

| Code | Signification | Description |
|------|---------------|-------------|
| 200 | OK | Requête réussie |
| 400 | Bad Request | Paramètres invalides |
| 401 | Unauthorized | API Key manquante ou invalide |
| 404 | Not Found | Ressource non trouvée |
| 429 | Too Many Requests | Rate limit dépassé |
| 500 | Internal Server Error | Erreur serveur |

### Format des Erreurs

Toutes les erreurs suivent ce format :

```json
{
  "error": "Description de l'erreur",
  "code": "ERROR_CODE",
  "timestamp": "2025-11-11T10:30:00.000Z",
  "details": {}
}
```

### Exemples d'Erreurs

#### 401 - API Key Invalide

```json
{
  "error": "Invalid or missing API key",
  "code": "INVALID_API_KEY",
  "timestamp": "2025-11-11T10:30:00.000Z"
}
```

#### 404 - Projet Non Trouvé

```json
{
  "error": "No project currently opened",
  "code": "NO_PROJECT",
  "timestamp": "2025-11-11T10:30:00.000Z"
}
```

#### 429 - Rate Limit

```json
{
  "error": "Too many requests",
  "code": "RATE_LIMIT_EXCEEDED",
  "timestamp": "2025-11-11T10:30:00.000Z",
  "details": {
    "limit": 100,
    "windowMs": 60000,
    "retryAfter": 30
  }
}
```

---

## 📊 WebSocket

Pour les mises à jour temps réel, une connexion WebSocket est disponible.

**Endpoint**: `ws://localhost:3100?apiKey={apiKey}`

### Connexion

```javascript
const ws = new WebSocket('ws://localhost:3100?apiKey=your-api-key-here');

ws.onopen = () => {
  console.log('Connected to Flow Studio/Player');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'scene:changed':
      console.log('Scene changed:', data.payload);
      break;
    case 'schedule:executed':
      console.log('Schedule executed:', data.payload);
      break;
    case 'sequence:started':
      console.log('Sequence started:', data.payload);
      break;
    case 'player:status':
      console.log('Player status:', data.payload);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

### Événements Temps Réel

| Type | Description |
|------|-------------|
| `scene:changed` | Une scène a changé sur un écran |
| `schedule:executed` | Un planning horaire a été exécuté |
| `sequence:started` | Une séquence DMX a démarré |
| `sequence:stopped` | Une séquence DMX s'est arrêtée |
| `player:status` | Changement de statut du player |
| `heartbeat` | Ping de connexion (toutes les 30s) |

### Format des Messages

```json
{
  "type": "scene:changed",
  "timestamp": "2026-01-05T10:30:00.000Z",
  "payload": {
    "displayId": "display-001",
    "previousSceneId": "scene-001",
    "newSceneId": "scene-002",
    "sceneName": "Nouvelle Scène"
  }
}
```

---

## 🔧 Configuration

### Activer l'API

1. Ouvrir InteractStudio
2. Menu → Settings → API Monitoring
3. Cocher "Activer l'API de monitoring"
4. Configurer le port (défaut: 3333)
5. Copier l'API Key générée

### Variables d'Environnement

```bash
# Port du serveur API
MONITORING_API_PORT=3333

# Activer/Désactiver
MONITORING_API_ENABLED=true

# Origines CORS autorisées (séparées par virgules)
# Par défaut: * (toutes les origines)
# Pour restreindre plus tard: http://localhost:8080,http://192.168.1.100
MONITORING_API_CORS_ORIGINS=*
```

### Fichier de Configuration

```json
{
  "monitoringAPI": {
    "enabled": true,
    "port": 3333,
    "apiKey": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "allowedOrigins": ["*"],
    "rateLimit": {
      "windowMs": 60000,
      "maxRequests": 100
    }
  }
}
```

---

## 💡 Exemples d'Utilisation

### JavaScript / Fetch API

```javascript
class InteractStudioAPI {
  constructor(baseURL, apiKey) {
    this.baseURL = baseURL;
    this.apiKey = apiKey;
  }

  async request(endpoint) {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      headers: {
        'X-API-Key': this.apiKey
      }
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }

  async getHealth() {
    return this.request('/health');
  }

  async getProject() {
    return this.request('/project');
  }

  async getDisplays() {
    return this.request('/displays');
  }

  async getSchedules() {
    return this.request('/schedules');
  }

  async getRunningSequences() {
    return this.request('/sequences/running');
  }
}

// Utilisation
const api = new InteractStudioAPI(
  'http://localhost:3333/api',
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
);

// Vérifier le statut
const health = await api.getHealth();
console.log('Status:', health.status);

// Récupérer les écrans
const displays = await api.getDisplays();
displays.displays.forEach(display => {
  console.log(`${display.name}: ${display.currentScene?.name || 'Aucune scène'}`);
});
```

### Python

```python
import requests

class InteractStudioAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            'X-API-Key': api_key
        }

    def get_health(self):
        response = requests.get(
            f'{self.base_url}/health'
        )
        return response.json()

    def get_project(self):
        response = requests.get(
            f'{self.base_url}/project',
            headers=self.headers
        )
        return response.json()

    def get_displays(self):
        response = requests.get(
            f'{self.base_url}/displays',
            headers=self.headers
        )
        return response.json()

    def get_schedules(self, enabled_only=None):
        params = {}
        if enabled_only is not None:
            params['enabled'] = enabled_only

        response = requests.get(
            f'{self.base_url}/schedules',
            headers=self.headers,
            params=params
        )
        return response.json()

# Utilisation
api = InteractStudioAPI(
    'http://localhost:3333/api',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
)

# Vérifier le statut
health = api.get_health()
print(f"Status: {health['status']}")

# Récupérer les écrans
displays = api.get_displays()
for display in displays['displays']:
    scene_name = display['currentScene']['name'] if display['currentScene'] else 'Aucune scène'
    print(f"{display['name']}: {scene_name}")
```

### cURL

```bash
# Health check
curl http://localhost:3333/api/health

# Get project info
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:3333/api/project

# Get displays
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:3333/api/displays

# Get schedules (enabled only)
curl -H "X-API-Key: YOUR_API_KEY" \
  "http://localhost:3333/api/schedules?enabled=true"

# Get running sequences
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:3333/api/sequences/running
```

---

## 🚀 Application de Monitoring - Exemple

### HTML + JavaScript Simple

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>InteractStudio Monitor</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: #1e1e1e;
      color: #ffffff;
      padding: 20px;
    }
    .container { max-width: 1400px; margin: 0 auto; }
    h1 { margin-bottom: 30px; color: #4CAF50; }

    .status-bar {
      background: #2d2d2d;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 20px;
      display: flex;
      gap: 30px;
      align-items: center;
    }
    .status-item { flex: 1; }
    .status-label { font-size: 12px; color: #999; margin-bottom: 5px; }
    .status-value { font-size: 24px; font-weight: bold; }
    .status-value.running { color: #4CAF50; }
    .status-value.error { color: #f44336; }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
      gap: 20px;
      margin-bottom: 20px;
    }

    .card {
      background: #2d2d2d;
      border-radius: 8px;
      padding: 20px;
    }
    .card-title {
      font-size: 18px;
      margin-bottom: 15px;
      color: #4CAF50;
      border-bottom: 1px solid #444;
      padding-bottom: 10px;
    }

    .display-item {
      background: #3d3d3d;
      padding: 15px;
      border-radius: 4px;
      margin-bottom: 10px;
    }
    .display-name { font-weight: bold; margin-bottom: 5px; }
    .display-scene { color: #999; font-size: 14px; }
    .display-scene.active { color: #4CAF50; }

    .schedule-item {
      background: #3d3d3d;
      padding: 15px;
      border-radius: 4px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .schedule-time {
      font-weight: bold;
      color: #4CAF50;
      font-size: 18px;
    }
    .schedule-scene { color: #999; }

    .sequence-item {
      background: #3d3d3d;
      padding: 15px;
      border-radius: 4px;
      margin-bottom: 10px;
    }
    .sequence-name { font-weight: bold; margin-bottom: 5px; }
    .progress-bar {
      background: #555;
      height: 6px;
      border-radius: 3px;
      overflow: hidden;
      margin-top: 10px;
    }
    .progress-fill {
      background: #4CAF50;
      height: 100%;
      transition: width 0.3s ease;
    }

    .error-message {
      background: #f44336;
      padding: 15px;
      border-radius: 8px;
      margin-bottom: 20px;
    }

    .loading {
      text-align: center;
      padding: 40px;
      font-size: 18px;
      color: #999;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 InteractStudio Monitor</h1>

    <div id="error" class="error-message" style="display: none;"></div>
    <div id="loading" class="loading">Connexion à InteractStudio...</div>

    <div id="content" style="display: none;">
      <!-- Status Bar -->
      <div class="status-bar">
        <div class="status-item">
          <div class="status-label">Status</div>
          <div id="status" class="status-value">-</div>
        </div>
        <div class="status-item">
          <div class="status-label">Uptime</div>
          <div id="uptime" class="status-value">-</div>
        </div>
        <div class="status-item">
          <div class="status-label">Projet</div>
          <div id="project-name" class="status-value">-</div>
        </div>
        <div class="status-item">
          <div class="status-label">Écrans Actifs</div>
          <div id="active-displays" class="status-value">-</div>
        </div>
      </div>

      <!-- Grid -->
      <div class="grid">
        <!-- Displays -->
        <div class="card">
          <div class="card-title">🖥️ Écrans</div>
          <div id="displays-list"></div>
        </div>

        <!-- Schedules -->
        <div class="card">
          <div class="card-title">📅 Prochains Plannings</div>
          <div id="schedules-list"></div>
        </div>

        <!-- Sequences -->
        <div class="card">
          <div class="card-title">💡 Séquences d'Éclairage</div>
          <div id="sequences-list"></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    // Configuration
    const API_URL = 'http://localhost:3333/api';
    const API_KEY = 'YOUR_API_KEY_HERE'; // À remplacer
    const REFRESH_INTERVAL = 5000; // 5 secondes

    // Helper pour les requêtes API
    async function fetchAPI(endpoint) {
      const response = await fetch(`${API_URL}${endpoint}`, {
        headers: endpoint === '/health' ? {} : { 'X-API-Key': API_KEY }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    }

    // Formater le temps d'uptime
    function formatUptime(seconds) {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }

    // Formater le temps jusqu'à
    function formatTimeUntil(ms) {
      const hours = Math.floor(ms / 3600000);
      const minutes = Math.floor((ms % 3600000) / 60000);
      if (hours > 0) return `dans ${hours}h ${minutes}m`;
      return `dans ${minutes}m`;
    }

    // Mettre à jour l'interface
    async function updateUI() {
      try {
        // Health check
        const health = await fetchAPI('/health');
        document.getElementById('status').textContent = health.status;
        document.getElementById('status').className =
          `status-value ${health.status}`;
        document.getElementById('uptime').textContent =
          formatUptime(health.uptime);

        // Project
        const project = await fetchAPI('/project');
        document.getElementById('project-name').textContent = project.name;

        // Displays
        const displays = await fetchAPI('/displays');
        document.getElementById('active-displays').textContent =
          displays.activeCount;

        const displaysHTML = displays.displays.map(d => `
          <div class="display-item">
            <div class="display-name">${d.name}</div>
            <div class="display-scene ${d.currentScene ? 'active' : ''}">
              ${d.currentScene ?
                `▶️ ${d.currentScene.name}` :
                '⏸️ Aucune scène'}
            </div>
          </div>
        `).join('');
        document.getElementById('displays-list').innerHTML =
          displaysHTML || '<div style="color: #999;">Aucun écran configuré</div>';

        // Schedules
        const schedules = await fetchAPI('/schedules/upcoming?limit=5');
        const schedulesHTML = schedules.upcoming.map(s => `
          <div class="schedule-item">
            <div>
              <div class="schedule-time">${s.timeUntilText}</div>
              <div class="schedule-scene">${s.sceneName}</div>
            </div>
            <div style="text-align: right; color: #999;">
              ${s.day}<br>
              ${s.executionTime.substring(11, 16)}
            </div>
          </div>
        `).join('');
        document.getElementById('schedules-list').innerHTML =
          schedulesHTML || '<div style="color: #999;">Aucun planning à venir</div>';

        // Sequences
        const sequences = await fetchAPI('/sequences/running');
        const sequencesHTML = sequences.running.map(s => `
          <div class="sequence-item">
            <div class="sequence-name">${s.sequenceName}</div>
            <div style="font-size: 12px; color: #999;">
              Étape ${s.currentStep}/${s.totalSteps} •
              ${s.progress.toFixed(1)}%
            </div>
            <div class="progress-bar">
              <div class="progress-fill" style="width: ${s.progress}%"></div>
            </div>
          </div>
        `).join('');
        document.getElementById('sequences-list').innerHTML =
          sequencesHTML || '<div style="color: #999;">Aucune séquence active</div>';

        // Tout est OK, afficher le contenu
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'none';
        document.getElementById('content').style.display = 'block';

      } catch (error) {
        console.error('Error updating UI:', error);
        document.getElementById('error').textContent =
          `Erreur: ${error.message}. Vérifiez que l'API est activée et que la clé est correcte.`;
        document.getElementById('error').style.display = 'block';
        document.getElementById('loading').style.display = 'none';
      }
    }

    // Démarrer les mises à jour
    updateUI();
    setInterval(updateUI, REFRESH_INTERVAL);
  </script>
</body>
</html>
```

---

## 📝 Notes Importantes

1. **Sécurité**: Gardez votre API Key secrète. Ne la partagez pas et ne la commitez pas dans un dépôt public.

2. **CORS**: Par défaut, l'API accepte les requêtes de **toutes les origines** (`*`) pour faciliter le développement. Vous pourrez restreindre les origines autorisées plus tard dans la configuration quand vous connaîtrez l'IP exacte du PC de monitoring.

3. **Rate Limiting**: Par défaut, l'API est limitée à 100 requêtes par minute. Pour un monitoring en temps réel, utilisez un intervalle de 5-10 secondes.

4. **Performance**: Les endpoints retournent seulement les données essentielles. Pour des détails complets, utilisez les endpoints spécifiques (ex: `/displays/:id`).

5. **Timestamps**: Tous les timestamps sont au format ISO 8601 UTC.

6. **IDs**: Tous les IDs sont des strings. Ne faites pas d'hypothèses sur leur format.

---

## 🔄 Changelog

### Version 1.1.0 (2026-01-05)
- Ajout des endpoints de contrôle de lecture (play, pause, stop, next, previous, load-scene, volume)
- Ajout des endpoints de contrôle système (reboot, shutdown, restart-player)
- WebSocket temps réel disponible sur port 3100
- Documentation des endpoints pour Flow Player RPi
- Ports clarifiés: 3100 (principal), 3333 (legacy)

### Version 1.0.0 (2025-11-11)
- Version initiale de l'API
- Endpoints de base: health, project, displays, schedules, sequences
- Authentification par API Key
- Rate limiting
- Documentation complète

---

**Documentation générée le**: 2026-01-05
**Version de l'API**: 1.1.0
**Statut**: Production
