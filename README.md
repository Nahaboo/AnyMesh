# AnyMesh — Pipeline 3D post-génération IA

Application web pour traiter les sorties brutes de modèles IA génératifs et produire des assets 3D utilisables en production.

---

## Démonstration

> **[→ Démo live](https://your-vps-url)**
> Les opérations lourdes (génération, retopologie) sont déportées sur GPU RunPod — le serveur principal reste léger.

---

## Pourquoi ce projet

Les sorties des modèles de génération 3D arrivent souvent avec des centaines de composantes géométriques disconnectées, des trous dans le mesh, une topologie chaotique, et un nombre de polygones trop élevé pour une utilisation en temps réel.

AnyMesh traite ces sorties brutes : analyse topologique, simplification, retopologie, transfert de texture, génération de LODs — depuis une interface web.

---

## Workflow général

```
Image(s) → Génération IA → Analyse → Retopologie → Texture Baking → LODs → Export
```

---

## Fonctionnalités

### Génération 3D

Deux providers open-source sont intégrés en production.

**TRELLIS** (Microsoft) tourne sur RunPod Serverless (GPU A40/A100). Meilleure qualité visuelle, texture incluse. Génère une scène multi-géométries — la topologie est fragmentée par design, ce qui implique des contraintes sur les opérations de post-processing (voir section Retopologie).

**TripoSR** (Stability/Tripo) tourne en local sur n'importe quel GPU modeste (~30s par génération). Résultat watertight sans texture — topologie propre, directement compatible avec le pipeline de retopologie.

Deux autres providers ont été testés et écartés : Stability AI SF3D (API cloud payante, bons résultats mais coût par génération) et Unique3D (worker Docker auto-hébergé, lourd à déployer). Le code d'intégration est présent dans le repo.

Un script de benchmark (`benchmark_providers.py`) compare les providers sur les mêmes images : temps, taille de fichier, face count, watertight, aspect ratio des triangles, résolution texture.

---

### Simplification de mesh

Réduit le nombre de triangles d'un mesh en préservant la forme. L'algorithme est le Quadric Error Metric (QEM) — pour chaque vertex supprimé, il minimise l'erreur géométrique introduite. Trois niveaux : Basse (garde 70%), Moyenne (garde 50%), Forte (garde 20%), avec une option pour préserver les bords.

Deux limitations à noter. Les textures sont perdues après simplification : les UVs deviennent incohérents quand les vertices sont fusionnés — c'est une contrainte fondamentale du QEM, pas un bug. Sur les meshes TRELLIS avec texture, le taux de réduction atteint peut être inférieur à la cible à cause du grand nombre de boundary edges.

---

### Retopologie

Un mesh généré par IA compte souvent plusieurs centaines de milliers à quelques millions de triangles, positionnés sans structure. Pour l'animation, la subdivision ou simplement avoir un mesh propre et léger, il faut recréer la topologie depuis zéro.

L'outil utilisé est Instant Meshes (Disney Research), un remaillage field-aligned qui recrée le mesh avec des quads bien orientés. Le slider permet de viser entre 5% et 50% des faces originales.

Instant Meshes fonctionne bien sur des meshes propres et fermés. Les meshes TRELLIS posent un problème spécifique : ils sont composés de centaines de géométries séparées non-fermées par design. Instant Meshes produit des trous sur ces meshes — problème connu (issue #78) et non résolu à ce jour. La retopologie est donc désactivée automatiquement sur ces meshes.

Une tentative de réparation a été testée : réparer le mesh avant retopo via pymeshfix pour le rendre watertight. Résultat : pymeshfix ferme les trous en reconstruisant la géométrie autour, ce qui déforme la forme originale. Approche abandonnée.

---

### Texture Baking

La retopologie recrée un mesh avec une bonne topologie, mais sans texture — la géométrie est refaite de zéro, les coordonnées UV originales ne correspondent plus à rien. Le baking transfère la texture du mesh original (high poly) vers le nouveau mesh low poly.

Pipeline : génération d'UVs via LSCM (voir section UV Unwrapping) sur le low poly, puis pour chaque vertex du low poly, recherche du vertex le plus proche sur le high poly via un KDTree spatial — une structure de données qui organise les points dans l'espace pour accélérer les recherches de proximité. Ce vertex high poly pointe vers une couleur dans la texture originale. La couleur est projetée dans la nouvelle texture, triangle par triangle, par interpolation barycentrique.

L'approche KDTree vertex-to-vertex est une approximation. Un raycasting perpendiculaire à la surface serait plus précis aux bords et dans les zones de fort détail, mais bien plus lent. Pour une prévisualisation web à 60fps, la qualité est suffisante.

---

### UV Unwrapping

Génère des coordonnées UV sur un mesh qui n'en a pas, via LSCM (Least Squares Conformal Maps) — un algorithme qui déplie le mesh 3D en 2D en minimisant la distorsion angulaire. Le viewer propose un mode UV checker (damier) pour visualiser la qualité de l'unwrap.

Limitations : les seams sont placés automatiquement, pas nécessairement aux endroits les plus judicieux — sur un visage humain par exemple, une couture au milieu du front est techniquement valide mais visuellement problématique. Sur des meshes non-manifold, l'unwrap peut produire des îles UV qui se chevauchent, ce qui provoque des artefacts de texture (deux zones du mesh partagent les mêmes pixels). LSCM préserve les angles mais pas les surfaces — une zone très courbée comme un nez ou une oreille peut être sur-représentée dans l'espace UV et recevoir plus de résolution de texture qu'une zone plate.

---

### Segmentation

Découpe un mesh en régions distinctes selon 4 méthodes : connectivité, arêtes vives, courbure, plans géométriques. Feature en cours de développement — l'implémentation actuelle est basique et ne fonctionne pas sur les meshes TRELLIS (non-watertight). La méthode courbure utilise un KMeans sur les normales de surface, fragile sur des meshes complexes. La méthode connectivité sépare simplement les composantes déjà disconnectées.

---

### Texturing IA

L'utilisateur entre un prompt textuel ("rusty metal" par exemple), le backend appelle Gemini Imagen qui génère une image PNG représentant la texture, puis le frontend l'applique sur le mesh via triplanar mapping : la texture est projetée depuis les trois axes (X, Y, Z) et blendée selon la normale de la surface. Aucun UV nécessaire, aucune couture visible — au prix d'un résultat générique sur les surfaces courbées.

Pour un export production, un bake de texture transfère le résultat dans le GLB — cette étape nécessite un mesh watertight.

---

### Physique temps réel

Feature en cours de développement. Rapier (moteur physique Rust compilé en WebAssembly, via `@react-three/rapier`) tourne dans le navigateur à 60fps sans calcul serveur. Le convex hull du mesh est extrait (simplifié à 128 vertices), utilisé comme collider, et la chute et les rebonds de l'objet sont simulés dans le viewer. Les propriétés physiques (densité, friction, restitution) peuvent être générées depuis un prompt IA.

La limite principale est le convex hull : un objet en forme de L ou de C aura un collider qui ne correspond pas à sa silhouette réelle. Une décomposition convexe (VHACD) serait plus précise mais plus coûteuse dans le navigateur.

---

## Architecture

```
Navigateur (React + RTF)
        │ REST API
        ▼
    FastAPI (VPS)
    ├── File de tâches async (thread workers)
    ├── Trimesh / PyMeshLab / SciPy
    └── Instant Meshes (subprocess C++)
        │
        ├── RunPod Serverless GPU
        │   └── TRELLIS endpoint
        │
        └── Docker worker (même VPS)
            └── Unique3D
```

Le VPS fait tourner le backend FastAPI et sert les fichiers statiques, sans GPU. Pour TRELLIS, le backend soumet un job via API REST, RunPod alloue un GPU à la demande et retourne le GLB. On ne paie que le temps GPU réellement utilisé. TripoSR tourne en local sur n'importe quel GPU, sans passer par RunPod.

---

## Stack

| Couche | Technologie | Pourquoi |
|--------|-------------|----------|
| Backend | **FastAPI** | Python async, typage Pydantic, doc API auto-générée |
| Géométrie 3D | **Trimesh** | Chargement natif GLB/GLTF, QEM, LSCM unwrap |
| Géométrie 3D | **PyMeshLab** | Triangulation des N-gons produits par Instant Meshes |
| Calcul numérique | **SciPy / NumPy** | KDTree spatial pour le texture baking |
| Images | **Pillow** | Lecture/écriture des textures PNG |
| Segmentation | **Open3D + scikit-learn** | Normales de surface et KMeans pour la segmentation par courbure |
| Remaillage | **Instant Meshes** | Field-aligned remeshing C++ (Disney Research) |
| Rendu 3D | **React Three Fiber** | Binding React de Three.js |
| Helpers 3D | **@react-three/drei** | OrbitControls, Environment, ContactShadows |
| Physique | **Rapier (WASM)** | Moteur physique Rust compilé WebAssembly |
| Build frontend | **Vite** | HMR instantané, plus rapide que Webpack |
| Infra | **Docker** | Isolation du worker Unique3D et ses dépendances CUDA |
| GPU à la demande | **RunPod Serverless** | GPU payés à l'usage |

Open3D et PyVista sont présents dans le code mais leur usage est marginal (segmentation et un handler legacy). Le chemin principal utilise Trimesh.

---

## Lancement

```bash
# Backend
pip install -r requirement.txt
uvicorn src.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Variables d'environnement (`.env`) :
```
STABILITY_API_KEY=sk-...
RUNPOD_API_KEY=...
RUNPOD_TRELLIS_ENDPOINT_ID=...
```

---

## Formats supportés

**Import :** OBJ · STL · PLY · GLB · GLTF
**Export :** GLB · OBJ · PLY · ZIP (LODs)

---


