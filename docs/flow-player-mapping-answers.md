# Réponses Techniques - Video Mapping pour Flow Player RPi

> **Version du document : 1.0.0**
> Date : 2026-01-05
> Basé sur l'analyse du code Flow Studio

---

## 1. Structure des données de mapping

### Réponses :

**Q1** : Les coordonnées `x` et `y` sont-elles toujours normalisées (0.0 à 1.0) ?
- [x] **Oui, toujours 0.0-1.0**

```typescript
// Définition dans src/shared/types/index.ts (lignes 1541-1544)
interface Point2D {
  x: number;  // 0 = gauche, 1 = droite
  y: number;  // 0 = haut, 1 = bas (NORMALISÉ 0-1)
}
```

**Q2** : L'origine (0,0) est-elle toujours en haut à gauche ?
- [x] **Oui**

L'origine (0,0) est en **haut à gauche**. Le système de coordonnées est :
- X : 0 = bord gauche, 1 = bord droit
- Y : 0 = bord haut, 1 = bord bas

**Q3** : Le mapping est-il par scène ou global au projet ?
- [x] **Les deux sont possibles**

Le mapping peut être configuré :
- **Par écran individuel** : dans `displayConfig[].videoMapping`
- **Par écran dans un groupe** : dans `displayGroups[].screens[].videoMapping`
- Chaque scène affichée sur un écran hérite du mapping de cet écran

---

## 2. Modes de mapping supportés

**Q4** : Quels modes de mapping existent dans Flow ?
- [x] `perspective` (4 coins uniquement)
- [x] `mesh` (grille NxM)
- [ ] Autres modes - **Non, seulement ces 2 modes**

```typescript
// src/shared/types/index.ts (lignes 1507-1514)
interface VideoMappingConfig {
  enabled: boolean;
  mode: 'perspective' | 'mesh';  // SEULEMENT CES 2 MODES
  backgroundColor: string;
  perspectivePoints?: PerspectivePoints;
  meshGrid?: MeshGrid;
  targetResolution?: { width: number; height: number };
}
```

**Q5** : Pour le mode `mesh`, la grille est-elle toujours régulière au départ ?
- [x] **Oui**

La grille est initialisée avec des points uniformément répartis :
- Grille par défaut : 3×3 cellules = 4×4 points
- Extensible de 2×2 à 20×20 cellules
- Chaque point peut ensuite être déplacé individuellement

```typescript
// Initialisation d'une grille régulière
// Pour une grille rows×cols, on a (rows+1)×(cols+1) points
// Point initial (r,c) = { x: c/cols, y: r/rows }
```

---

## 3. Interpolation et rendu

**Q6** : Quelle méthode d'interpolation est utilisée pour déformer l'image ?
- [x] **Bilinéaire** (avec filtrage anisotropique optionnel)
- [ ] Bicubique

```typescript
// src/renderer/components/WebGLWarper.tsx (lignes 227-237)
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

// Extension anisotropique si disponible (meilleure qualité à angles obliques)
const ext = gl.getExtension('EXT_texture_filter_anisotropic');
if (ext) {
  const max = gl.getParameter(ext.MAX_TEXTURE_MAX_ANISOTROPY_EXT);
  gl.texParameterf(gl.TEXTURE_2D, ext.TEXTURE_MAX_ANISOTROPY_EXT, max);
}
```

**Q7** : Comment sont gérés les pixels en dehors de la zone mappée ?
- [x] **Noir** (`backgroundColor`)

```typescript
// backgroundColor par défaut : '#000000'
// Les zones hors du quadrilatère mappé sont remplies avec cette couleur
```

---

## 4. Résolutions

**Q8** : `targetResolution` représente quoi exactement ?
- [x] **La résolution de sortie (écran/projecteur)**

```typescript
// targetResolution = dimensions physiques de l'écran de sortie
targetResolution: {
  width: screen.bounds.width,   // ex: 1920
  height: screen.bounds.height  // ex: 1080
}
```

Utilisé pour :
- Calcul des largeurs de soft edge en pourcentage
- Mise à l'échelle haute résolution (devicePixelRatio)

**Q9** : Faut-il une `sourceResolution` (résolution de la vidéo source) ?
- [x] **Non, on utilise la résolution native de la vidéo**

La source est capturée dynamiquement. Le player RPi doit simplement utiliser la résolution native de la vidéo/média chargé.

---

## 5. Fonctionnalités avancées

**Q10** : Y a-t-il du edge blending (fusion de bords pour multi-projecteurs) ?
- [x] **Oui** - Voir structure ci-dessous

```typescript
// src/shared/types/index.ts (lignes 1444-1466)
interface SoftEdgeConfig {
  enabled: boolean;
  blendWidth: number;           // Largeur en pixels (100-300 typique)
  blendWidthPercent: number;    // Alternative en % (5-15%)
  gamma: number;                // Correction gamma (1.0-2.5, défaut: 2.2)
  blendCurve: 'linear' | 'quadratic' | 'cubic' | 'sine';
  blackLevelCompensation: number; // 0-255
  brightnessBalance: boolean;

  individualBlendWidths?: {     // Contrôle par bord
    left: number;
    right: number;
    top: number;
    bottom: number;
  };

  calibrationMode?: boolean;    // Mode calibration visuelle
}
```

**Q11** : Y a-t-il des masques (zones à rendre transparentes/noires) ?
- [x] **Oui** - Masquage implicite par le WebGL

Le masquage est implicite : tout contenu hors de la zone mappée (quadrilatère perspective ou mesh) est automatiquement clippé par le rasterizer WebGL. Pas de système de masques arbitraires.

**Q12** : Y a-t-il du soft edge / feathering (adoucissement des bords) ?
- [x] **Oui** - Intégré dans SoftEdgeConfig

Le soft edge est appliqué via un fragment shader avec correction gamma :

```glsl
// Fragment shader simplifié
if (u_softEdgeEnabled) {
  float alpha = 1.0;

  // Bord gauche : fondu de 0 à blendLeft
  if (u_blendLeft > 0.0 && uv.x < u_blendLeft) {
    float t = uv.x / u_blendLeft;
    alpha *= pow(t, u_gamma);  // Correction gamma
  }
  // Idem pour right, top, bottom...

  color.rgb *= alpha;
  color.a *= alpha;
}
```

---

## 6. Structure de données complète pour l'export Player

Voici la structure **complète** que le player RPi doit supporter :

```json
{
  "displayConfig": [
    {
      "screenId": "123456",
      "sceneId": "scene-uuid",
      "rotation": 0,
      "videoMapping": {
        "enabled": true,
        "mode": "perspective",
        "backgroundColor": "#000000",

        "perspectivePoints": {
          "topLeft": { "x": 0.0, "y": 0.0 },
          "topRight": { "x": 1.0, "y": 0.0 },
          "bottomLeft": { "x": 0.0, "y": 1.0 },
          "bottomRight": { "x": 1.0, "y": 1.0 }
        },

        "meshGrid": null,

        "targetResolution": {
          "width": 1920,
          "height": 1080
        }
      },

      "softEdge": {
        "enabled": false,
        "blendWidth": 100,
        "blendWidthPercent": 5,
        "gamma": 2.2,
        "blendCurve": "quadratic",
        "blackLevelCompensation": 0,
        "brightnessBalance": false,
        "individualBlendWidths": {
          "left": 0,
          "right": 0,
          "top": 0,
          "bottom": 0
        }
      }
    }
  ],

  "displayGroups": [
    {
      "id": "group-uuid",
      "name": "Video Wall 2x2",
      "enabled": true,
      "layout": {
        "rows": 2,
        "cols": 2,
        "totalResolution": { "width": 3840, "height": 2160 }
      },
      "screens": [
        {
          "screenId": "screen-1",
          "position": { "row": 0, "col": 0 },
          "viewport": { "x": 0, "y": 0, "width": 0.5, "height": 0.5 },
          "videoMapping": {
            "enabled": true,
            "mode": "perspective",
            "perspectivePoints": { ... }
          },
          "softEdge": {
            "enabled": true,
            "blendRight": 100,
            "blendBottom": 100
          }
        }
      ]
    }
  ]
}
```

---

## 7. Exemple de mapping déformé

### Mode Perspective (4 coins)

**Entrée** : Rectangle source 1920×1080, coins déplacés

```
Source (normalisé)         Destination (déformé)
┌─────────────────┐        ┌───────────────────┐
│(0,0)       (1,0)│        │(0.05,0.02) (0.98,0.03)│
│                 │   →    │                       │
│                 │        │                       │
│(0,1)       (1,1)│        │(0.02,0.97) (0.95,0.99)│
└─────────────────┘        └───────────────────────┘
```

**Données** :
```json
{
  "perspectivePoints": {
    "topLeft": { "x": 0.05, "y": 0.02 },
    "topRight": { "x": 0.98, "y": 0.03 },
    "bottomLeft": { "x": 0.02, "y": 0.97 },
    "bottomRight": { "x": 0.95, "y": 0.99 }
  }
}
```

### Mode Mesh (grille 2×2)

**Entrée** : Grille 2×2 = 3×3 points, point central déplacé

```
Points initiaux (3×3)      Points déformés
┌───┬───┐                  ┌───┬───┐
│   │   │                  │   │   │
├───┼───┤         →        ├───•───┤  (point central déplacé)
│   │   │                  │  ╱ ╲  │
└───┴───┘                  └─╱───╲─┘
```

**Données** :
```json
{
  "meshGrid": {
    "rows": 2,
    "cols": 2,
    "points": [
      [{"x": 0.0, "y": 0.0}, {"x": 0.5, "y": 0.0}, {"x": 1.0, "y": 0.0}],
      [{"x": 0.0, "y": 0.5}, {"x": 0.6, "y": 0.4}, {"x": 1.0, "y": 0.5}],
      [{"x": 0.0, "y": 1.0}, {"x": 0.5, "y": 1.0}, {"x": 1.0, "y": 1.0}]
    ]
  }
}
```

---

## 8. Algorithme de rendu recommandé pour RPi

### Mode Perspective

1. **Calculer la matrice d'homographie 3×3** avec l'algorithme DLT (Direct Linear Transform)
2. **Appliquer via shader GPU** ou transformation matricielle

```python
# Pseudo-code Python pour homographie
import numpy as np

def calculate_homography(src_points, dst_points):
    """
    src_points: [(0,0), (1,0), (0,1), (1,1)]  # Carré unité
    dst_points: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]  # Coins déformés
    """
    # Construire matrice A pour système Ah = 0
    A = []
    for (sx, sy), (dx, dy) in zip(src_points, dst_points):
        A.append([-sx, -sy, -1, 0, 0, 0, sx*dx, sy*dx, dx])
        A.append([0, 0, 0, -sx, -sy, -1, sx*dy, sy*dy, dy])

    A = np.array(A)
    _, _, V = np.linalg.svd(A)
    H = V[-1].reshape(3, 3)
    return H / H[2, 2]  # Normaliser
```

### Mode Mesh

1. **Triangulariser la grille** : chaque cellule = 2 triangles
2. **Interpoler les UV** pour chaque triangle
3. **Rasteriser** avec interpolation bilinéaire

```python
# Pour une grille rows×cols
for r in range(rows):
    for c in range(cols):
        # 4 coins de la cellule
        p00 = points[r][c]
        p10 = points[r][c+1]
        p01 = points[r+1][c]
        p11 = points[r+1][c+1]

        # UV correspondants (normalisés à la cellule)
        u0, v0 = c/cols, r/rows
        u1, v1 = (c+1)/cols, (r+1)/rows

        # Triangle 1: p00 → p01 → p10
        draw_triangle(
            [(p00.x, p00.y), (p01.x, p01.y), (p10.x, p10.y)],
            [(u0, v0), (u0, v1), (u1, v0)]
        )

        # Triangle 2: p10 → p01 → p11
        draw_triangle(
            [(p10.x, p10.y), (p01.x, p01.y), (p11.x, p11.y)],
            [(u1, v0), (u0, v1), (u1, v1)]
        )
```

---

## 9. Soft Edge - Implémentation

Pour le blending multi-projecteurs :

```python
def apply_soft_edge(pixel_x, pixel_y, width, height, config):
    """
    Retourne le facteur alpha (0-1) pour un pixel donné
    """
    if not config['enabled']:
        return 1.0

    alpha = 1.0
    gamma = config.get('gamma', 2.2)

    # Normaliser la position
    nx = pixel_x / width
    ny = pixel_y / height

    # Bord gauche
    blend_left = config.get('individualBlendWidths', {}).get('left', 0) / width
    if blend_left > 0 and nx < blend_left:
        t = nx / blend_left
        alpha *= pow(t, gamma)

    # Bord droit
    blend_right = config.get('individualBlendWidths', {}).get('right', 0) / width
    if blend_right > 0 and nx > (1 - blend_right):
        t = (1 - nx) / blend_right
        alpha *= pow(t, gamma)

    # Idem pour top/bottom...

    return alpha
```

---

## 10. Résumé des informations critiques

| Information | Valeur | Statut |
|-------------|--------|--------|
| Coordonnées | **Normalisées 0-1** | ✅ Confirmé |
| Origine | **Top-left (0,0)** | ✅ Confirmé |
| Modes | **perspective + mesh** | ✅ Confirmé |
| Interpolation | **Bilinéaire** | ✅ Confirmé |
| targetResolution | **Résolution écran sortie** | ✅ Confirmé |
| sourceResolution | **Non nécessaire** | ✅ Confirmé |
| Edge blending | **Oui, avec gamma** | ✅ Confirmé |
| Masques arbitraires | **Non** (clipping implicite) | ✅ Confirmé |
| Soft edge | **Oui, par bord** | ✅ Confirmé |

---

## 11. Recommandations pour Flow Player RPi

### Priorité Haute
1. Implémenter le mode **perspective** avec homographie (90% des cas d'usage)
2. Utiliser **OpenGL ES** ou **DRM/KMS** pour le rendu GPU
3. Supporter les coordonnées **normalisées 0-1**

### Priorité Moyenne
4. Implémenter le mode **mesh** pour surfaces courbes
5. Ajouter le **soft edge** avec correction gamma

### Priorité Basse
6. Calibration grid overlay (debug)
7. Black level compensation

### Stack technique recommandée pour RPi 5

```
┌─────────────────────────────────────┐
│  Flow Player (Python)               │
├─────────────────────────────────────┤
│  mpv (vidéo) + OpenGL ES (warping)  │
├─────────────────────────────────────┤
│  DRM/KMS (sortie directe)           │
├─────────────────────────────────────┤
│  VideoCore VII GPU                  │
└─────────────────────────────────────┘
```

---

*Document généré automatiquement depuis l'analyse du code Flow Studio*
