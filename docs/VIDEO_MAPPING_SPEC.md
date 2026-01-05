# Spécifications Techniques - Video Mapping / Warping

## Objectif

Appliquer les déformations de mapping vidéo définies dans Flow Studio lors de la diffusion sur le Raspberry Pi (vidéoprojecteur).

---

## Données actuellement disponibles dans l'export

### Structure `displayConfig[].videoMapping`

```json
{
  "enabled": true,
  "mode": "mesh",                    // "perspective" ou "mesh"
  "backgroundColor": "#000000",
  "perspectivePoints": {             // Mode perspective (4 coins)
    "topLeft": { "x": 0, "y": 0 },
    "topRight": { "x": 1, "y": 0 },
    "bottomLeft": { "x": 0, "y": 1 },
    "bottomRight": { "x": 1, "y": 1 }
  },
  "meshGrid": {                      // Mode mesh (grille déformable)
    "rows": 3,
    "cols": 3,
    "points": [                      // Grille (rows+1) x (cols+1) = 4x4 points
      [
        {"x": 0, "y": 0},
        {"x": 0.333, "y": 0},
        {"x": 0.666, "y": 0},
        {"x": 1, "y": 0}
      ],
      [
        {"x": 0, "y": 0.333},
        {"x": 0.16, "y": 0.178},     // Point déplacé !
        {"x": 0.666, "y": 0.333},
        {"x": 1, "y": 0.333}
      ],
      // ... autres lignes
    ]
  },
  "targetResolution": {
    "width": 2560,
    "height": 1600
  }
}
```

### Coordonnées

- Les coordonnées `x` et `y` sont **normalisées** (0.0 à 1.0)
- `(0, 0)` = coin haut-gauche
- `(1, 1)` = coin bas-droit
- Les points intermédiaires définissent la déformation de chaque cellule

---

## Questions / Informations manquantes

### 1. Mapping par scène ou global ?

**Question** : Le mapping est-il :
- [ ] Global (même mapping pour toutes les scènes)
- [ ] Par scène (chaque scène peut avoir son propre mapping)
- [ ] Par élément vidéo (chaque vidéo dans une scène peut avoir son mapping)

**Actuellement** : Le mapping est dans `displayConfig` qui est lié à une `sceneId`, suggérant un mapping par écran/scène.

### 2. Interpolation des cellules mesh

**Question** : Comment les pixels sont-ils interpolés dans chaque cellule ?
- [ ] Bilinéaire (standard)
- [ ] Bicubique (plus lisse)
- [ ] Autre méthode

### 3. Résolution de sortie

**Question** : La `targetResolution` (2560x1600) représente :
- [ ] La résolution de l'écran/projecteur de sortie
- [ ] La résolution du canvas de rendu
- [ ] Autre

### 4. Blending / Edge blending

**Question** : Y a-t-il un edge blending pour multi-projecteurs ?
- [ ] Oui - fournir les zones de blend et courbes de luminosité
- [ ] Non

### 5. Masques et zones noires

**Question** : Est-il possible de masquer des zones (projeter du noir) ?
- [ ] Oui - fournir le format des masques
- [ ] Non, uniquement via les points mesh

### 6. Soft edge / Feathering

**Question** : Y a-t-il un adoucissement des bords ?
- [ ] Oui - fournir les paramètres
- [ ] Non

---

## Implémentation proposée

### Option A : Transformation côté GPU avec MPV (recommandé pour RPi)

MPV supporte les shaders GLSL personnalisés. On peut créer un shader de mesh warping :

```glsl
// Pseudo-code shader
uniform sampler2D video;
uniform vec2 meshPoints[16];  // Grille 4x4

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 warpedUV = applyMeshWarp(uv, meshPoints);
    gl_FragColor = texture2D(video, warpedUV);
}
```

**Avantages** :
- Performances GPU natives
- Pas de re-encodage vidéo
- Temps réel

**Inconvénients** :
- Complexité du shader mesh warp
- Dépend des capacités GPU du RPi

### Option B : Pré-traitement avec FFmpeg

Générer une vidéo pré-déformée :

```bash
ffmpeg -i input.mp4 -vf "perspective=..." output_warped.mp4
```

**Avantages** :
- Simple à implémenter
- Fonctionne partout

**Inconvénients** :
- Temps de traitement initial
- Espace disque supplémentaire
- Le mode mesh n'est pas nativement supporté par FFmpeg

### Option C : Rendu WebGL (pour preview dans dashboard)

Utiliser Three.js ou WebGL natif pour déformer la texture vidéo en temps réel dans le navigateur.

```javascript
// Créer une géométrie mesh à partir des points
const geometry = new THREE.PlaneGeometry(1, 1, cols, rows);
// Déplacer les vertices selon meshGrid.points
geometry.vertices.forEach((v, i) => {
    const row = Math.floor(i / (cols + 1));
    const col = i % (cols + 1);
    v.x = meshPoints[row][col].x;
    v.y = meshPoints[row][col].y;
});
```

---

## Format de données souhaité pour l'export

Pour une implémentation optimale, voici le format idéal :

```json
{
  "videoMapping": {
    "enabled": true,
    "mode": "mesh",

    // Configuration de la grille
    "meshGrid": {
      "rows": 3,
      "cols": 3,
      "points": [...]
    },

    // OU mode perspective simple
    "perspectivePoints": {
      "topLeft": { "x": 0, "y": 0 },
      "topRight": { "x": 1, "y": 0 },
      "bottomLeft": { "x": 0, "y": 1 },
      "bottomRight": { "x": 1, "y": 1 }
    },

    // Résolution
    "sourceResolution": { "width": 1920, "height": 1080 },
    "targetResolution": { "width": 2560, "height": 1600 },

    // Options additionnelles (si disponibles)
    "interpolation": "bilinear",      // bilinear, bicubic
    "backgroundColor": "#000000",
    "edgeBlending": null,             // ou { zones: [...], gamma: 2.2 }
    "masks": []                       // Zones à masquer
  }
}
```

---

## Prochaines étapes

1. **Confirmer** les réponses aux questions ci-dessus
2. **Implémenter** le rendu mesh warp pour :
   - Preview dashboard (WebGL/Canvas)
   - Sortie MPV (shader GLSL ou pipeline GStreamer)
3. **Tester** avec différentes configurations de grille

---

## Contact

Pour extraire les informations additionnelles de Flow Studio, utiliser les outils de debug ou l'export JSON étendu.
