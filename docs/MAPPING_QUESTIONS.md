# Questions Techniques - Video Mapping pour Flow Player RPi

Ce document liste les informations nécessaires pour implémenter le video mapping/warping sur Raspberry Pi.

---

## 1. Structure des données de mapping

### Actuellement reçu dans l'export :

```json
{
  "displayConfig": [{
    "sceneId": "xxx",
    "videoMapping": {
      "enabled": true,
      "mode": "mesh",
      "perspectivePoints": {
        "topLeft": {"x": 0, "y": 0},
        "topRight": {"x": 1, "y": 0},
        "bottomLeft": {"x": 0, "y": 1},
        "bottomRight": {"x": 1, "y": 1}
      },
      "meshGrid": {
        "rows": 3,
        "cols": 3,
        "points": [[{x, y}, ...], ...]
      },
      "targetResolution": {"width": 2560, "height": 1600}
    }
  }]
}
```

### Questions :

**Q1** : Les coordonnées `x` et `y` sont-elles toujours normalisées (0.0 à 1.0) ?
- [ ] Oui, toujours 0.0-1.0
- [ ] Non, elles sont en pixels

**Q2** : L'origine (0,0) est-elle toujours en haut à gauche ?
- [ ] Oui
- [ ] Non (préciser)

**Q3** : Le mapping est-il par scène ou global au projet ?
- [ ] Par scène (chaque scène peut avoir son propre mapping)
- [ ] Global (un seul mapping pour tout le projet)
- [ ] Les deux sont possibles

---

## 2. Modes de mapping supportés

**Q4** : Quels modes de mapping existent dans Flow ?
- [ ] `perspective` (4 coins uniquement)
- [ ] `mesh` (grille NxM)
- [ ] Autres modes ? (lesquels)

**Q5** : Pour le mode `mesh`, la grille est-elle toujours régulière au départ ?
- Exemple : 3x3 cellules = 4x4 points uniformément répartis avant déformation
- [ ] Oui
- [ ] Non

---

## 3. Interpolation et rendu

**Q6** : Quelle méthode d'interpolation est utilisée pour déformer l'image ?
- [ ] Bilinéaire
- [ ] Bicubique
- [ ] Autre (préciser)

**Q7** : Comment sont gérés les pixels en dehors de la zone mappée ?
- [ ] Noir (`backgroundColor`)
- [ ] Transparent
- [ ] Autre

---

## 4. Résolutions

**Q8** : `targetResolution` représente quoi exactement ?
- [ ] La résolution de sortie (écran/projecteur)
- [ ] La résolution du canvas de rendu interne
- [ ] Autre

**Q9** : Faut-il une `sourceResolution` (résolution de la vidéo source) ?
- [ ] Oui, elle devrait être dans l'export
- [ ] Non, on utilise la résolution native de la vidéo

---

## 5. Fonctionnalités avancées

**Q10** : Y a-t-il du edge blending (fusion de bords pour multi-projecteurs) ?
- [ ] Oui - fournir le format des données
- [ ] Non

**Q11** : Y a-t-il des masques (zones à rendre transparentes/noires) ?
- [ ] Oui - fournir le format des données
- [ ] Non

**Q12** : Y a-t-il du soft edge / feathering (adoucissement des bords) ?
- [ ] Oui - fournir les paramètres
- [ ] Non

---

## 6. Informations additionnelles à ajouter à l'export

Si possible, ajouter ces champs à l'export pour le player RPi :

```json
{
  "videoMapping": {
    // Champs existants...

    // Nouveaux champs souhaités :
    "interpolation": "bilinear",     // ou "bicubic"
    "sourceResolution": {
      "width": 1920,
      "height": 1080
    },
    "edgeBlending": null,            // ou { zones: [...] }
    "masks": [],                      // zones à masquer
    "softEdge": {
      "enabled": false,
      "width": 0
    }
  }
}
```

---

## 7. Exemple de mapping déformé attendu

Pour valider l'implémentation, un exemple concret serait utile :

**Entrée** : Vidéo 1920x1080, grille 2x2 avec un point déplacé
**Sortie attendue** : Screenshot ou description de la déformation

---

## Résumé des informations critiques

| Information | Statut | Priorité |
|-------------|--------|----------|
| Coordonnées normalisées (0-1) | À confirmer | Haute |
| Mode d'interpolation | À confirmer | Haute |
| Résolution cible | Présent | OK |
| Edge blending | À confirmer | Moyenne |
| Masques | À confirmer | Basse |

---

*Document généré pour communication entre Flow Studio et Flow Player RPi*
