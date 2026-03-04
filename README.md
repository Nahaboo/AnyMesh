# AnyMesh — Pipeline 3D post-génération IA

Application web pour transformer des sorties brutes de modèles IA génératifs en assets 3D utilisables en production.

---

## Démonstration

> **[→ Démo live](https://your-vps-url)**
> Les opérations lourdes (génération, retopologie) sont déportées sur GPU RunPod — le serveur principal reste léger.

---

## Pourquoi ce projet

Les modèles IA génératifs produisent des résultats impressionnants visuellement, mais rarement utilisables directement. Les sorties arrivent souvent avec des centaines de composantes géométriques disconnectées, des trous dans le mesh, une topologie chaotique, et un nombre de polygones largement excessif pour une utilisation en temps réel.

AnyMesh traite ces sorties brutes : nettoyage, retopologie, transfert de texture, génération de LODs — le tout depuis une interface web interactive, sans avoir à ouvrir Blender.

---

## Workflow général

```
Image(s) → Génération IA → Analyse → Retopologie → Texture Baking → LODs → Export
```

---

## Fonctionnalités

### Génération 3D — 4 providers

**Contexte matériel :** les modèles de génération 3D nécessitent un GPU puissant (A40, A100). Ne disposant pas d'un tel matériel en local, l'intégration de plusieurs providers a permis d'explorer différentes approches selon les contraintes d'accès : API cloud facturée à l'usage, modèle open-source sur GPU loué à la demande, ou worker auto-hébergé sur une machine avec GPU modeste.

| Provider | Mode d'accès | Caractéristiques |
|----------|-------------|-----------------|
| **TRELLIS** (Microsoft) | RunPod Serverless | Meilleure qualité visuelle. Génère une scène multi-géométries, supporte plusieurs images en entrée pour capturer différentes vues du même objet |
| **TripoSR** (Stability/Tripo) | Modèle open-source, exécuté en local | Rapide (~30s sur GPU modeste), bon point de départ sans coût par génération |
| **Stability AI SF3D** | API cloud payante | Résultat propre et watertight en une seule image, ~10 crédits par génération |
| **Unique3D** | Worker Docker auto-hébergé | Plus lourd à déployer, mais entièrement sous contrôle |

**Mode multi-image TRELLIS :** TRELLIS accepte plusieurs images du même objet prises sous différents angles. En pratique, envoyer 3 à 4 vues (face, dos, profil) améliore significativement la reconstruction des zones non visibles sur une seule image. Le backend encode chaque image en base64 et les envoie dans un seul job RunPod.

Les 4 providers partagent la même interface API interne. Un script de benchmark (`benchmark_providers.py`) les compare objectivement sur les mêmes images : temps, taille de fichier, face count, watertight, aspect ratio des triangles, résolution texture.

---

### Simplification de mesh

**Ce qu'on fait :** réduire le nombre de triangles d'un mesh en préservant au mieux la forme. L'algorithme utilisé est le Quadric Error Metric (QEM) via Trimesh — pour chaque vertex supprimé, il minimise l'erreur géométrique introduite.

L'interface propose trois niveaux : Basse (garde 70%), Moyenne (garde 50%), Forte (garde 20%), avec une option pour préserver les bords du maillage.

**Limites et cas problématiques :**
- Les textures sont perdues après simplification — les UVs deviennent incohérents quand les vertices sont fusionnés. C'est une limitation fondamentale du QEM, pas un bug.
- Sur les meshes TRELLIS (scènes multi-géométries), les composantes sont fusionnées avant simplification, ce qui peut produire des artefacts aux jonctions.
- Sur des meshes très denses (2M+ triangles), la simplification peut être lente côté backend.

> **Point de débat :** le QEM est l'algorithme standard depuis 1997 (Garland & Heckbert). La vraie valeur ajoutée serait de conserver les textures après simplification. À noter que le re-baking post-retopologie est implémenté (voir section Texture Baking) — la même logique pourrait être appliquée après simplification, mais ce n'est pas encore branché sur ce chemin.

---

### Retopologie

**Pourquoi :** un mesh généré par IA a souvent 50 000 à 200 000 triangles positionnés de façon aléatoire, sans logique de flux géométrique. Pour l'animation, la subdivision ou simplement pour avoir un mesh propre et léger, il faut recréer la topologie depuis zéro.

**Ce qu'on fait :** on utilise Instant Meshes, un outil de remaillage field-aligned qui recrée le mesh avec des triangles isotropes bien orientés — le résultat ressemble à ce qu'un artiste 3D ferait manuellement, mais automatiquement. Le slider permet de viser entre 5% et 50% des faces originales.

**Contraintes importantes :**

Instant Meshes fonctionne bien sur des meshes propres et fermés. Les sorties IA posent deux problèmes spécifiques :

Premièrement, les meshes TRELLIS sont composés de centaines de géométries séparées non-fermées par design (c'est l'algorithme interne de TRELLIS qui génère des patches géométriques indépendants). Instant Meshes produit des trous sur ces meshes — problème connu et non résolu à ce jour.

Deuxièmement, une tentative de "sanitization" a été envisagée : avant la retopo, réparer le mesh pour le rendre watertight (fermé, sans trous) afin qu'Instant Meshes travaille sur une surface propre. L'outil testé (pymeshfix) ferme bien les trous, mais en reconstruisant la géométrie autour — ce qui déforme ou détruit la forme originale. La sanitization est donc désactivée automatiquement quand le mesh a trop de composantes ouvertes.

- Sur un mesh OBJ simple et propre, la retopo fonctionne très bien.
- Sur une sortie TRELLIS complexe, les résultats sont variables : bonne topologie sur les zones plates, trous possibles aux jonctions entre composantes.

> **Point de débat :** l'intégration d'Instant Meshes en subprocess est pragmatique mais fragile — dépendance externe non contrôlée, comportement légèrement différent Windows/Linux. Une alternative serait un remaillage isotrope en Python pur, mais la qualité d'Instant Meshes (développé par des chercheurs de Disney Research) serait difficile à égaler sans un investissement significatif.

---

### Texture Baking

**Pourquoi :** la retopologie recrée un mesh avec une bonne topologie, mais sans texture — la géométrie est refaite de zéro, donc les coordonnées UV originales ne correspondent plus à rien. Le mesh original (high poly) a une belle texture 1024×1024. Le baking transfère visuellement cette texture sur le nouveau mesh low poly propre.

**Comment ça fonctionne :**

Le mesh low poly n'a pas d'UVs — on commence par en générer via LSCM (voir section UV ci-dessous). Ensuite, pour chaque vertex du low poly, on cherche le vertex le plus proche sur le high poly via un KDTree spatial. Ce vertex high poly a des coordonnées UV connues, qui pointent vers une couleur dans la texture originale. On récupère cette couleur et on la projette dans la nouvelle texture, triangle par triangle, en interpolant les couleurs aux pixels par coordonnées barycentriques.

En résumé : chaque pixel de la nouvelle texture reçoit la couleur du point géométriquement le plus proche sur le mesh original.

**Limites :**
- L'approche KDTree vertex-to-vertex est une approximation. Un raycasting (lancer un rayon depuis chaque pixel de la nouvelle texture perpendiculairement à la surface) serait plus précis aux bords et dans les zones de fort détail, mais aussi bien plus lent.
- Disponible uniquement sur les meshes générés qui ont une texture source. Pas applicable sur un OBJ importé sans texture.

> **Point de débat :** Blender ou xNormal font un meilleur baking (raycasting, cage mesh, dilation des bords pour éviter les artifacts). La valeur d'AnyMesh est d'avoir ce pipeline automatisé en un clic sans quitter l'interface web — pas de concurrencer des outils dédiés.

---

### UV Unwrapping

**Ce qu'est le LSCM :** Least Squares Conformal Maps — un algorithme qui "déplie" un mesh 3D en 2D. L'idée est de couper le mesh le long de certaines arêtes, puis de l'étaler à plat en minimisant la distorsion angulaire (les angles sont préservés, pas les surfaces). Le résultat est un "patron" 2D du mesh, comme une peau d'orange dépliée.

**Pourquoi en avoir besoin :** pour appliquer une texture sur un mesh, il faut des coordonnées UV — une correspondance entre chaque point du mesh 3D et un pixel dans une image 2D. Les meshes générés par IA ont souvent des UVs absents ou de mauvaise qualité. L'unwrap LSCM en génère de nouveaux automatiquement.

**Ce qu'on propose :** un unwrap automatique via Trimesh, avec visualisation dans le viewer (mode UV checker — un damier qui permet de voir si les UVs sont bien proportionnés : si les carreaux ont tous la même taille, il n'y a pas de distorsion problématique).

**Limites :**
- Les seams (coutures où le mesh est coupé) sont placés automatiquement, pas nécessairement aux endroits les plus judicieux visuellement.
- Sur des meshes non-manifold, l'unwrap peut échouer ou produire des îles UV qui se chevauchent.
- LSCM minimise la distorsion angulaire mais pas la distorsion de surface — des zones peuvent être sur- ou sous-représentées dans l'espace UV.

---

### Comparaison de meshes (Hausdorff)

**Ce que ça fait :** calcule la distance géométrique entre deux meshes et l'affiche sous forme de heatmap colorée directement sur le mesh — rouge = zones très différentes, vert = zones proches. Utile pour vérifier qu'une simplification ou une retopologie n'a pas trop déformé le mesh original.

> **Point de débat — à toi de décider :** la feature est techniquement correcte et pertinente dans un contexte professionnel (validation qualité de pipeline). Si l'objectif est de garder l'interface simple, elle peut partir. Si l'objectif est de montrer la maîtrise d'un pipeline 3D complet à un CTO, c'est exactement le genre d'outil qu'un ingénieur 3D est censé comprendre et utiliser.

---

### Segmentation

**Ce que ça fait :** découpe un mesh en régions distinctes selon 4 méthodes — connectivité, arêtes vives, courbure, plans géométriques.

> **Point de débat — à toi de décider :** la segmentation telle qu'implémentée est basique. La méthode courbure utilise un KMeans (sklearn) sur les normales de surface, ce qui est fragile et produit des résultats incohérents sur des meshes complexes. La méthode connectivité est triviale — elle sépare juste les composantes déjà disconnectées. Dans l'état actuel, c'est une feature qui démontre une compréhension des concepts mais dont la qualité n'est pas au niveau du reste du pipeline.

---

### Texturing IA

**Ce qu'on fait :** l'utilisateur entre un prompt textuel ("rusty metal", "mossy stone"), le backend appelle l'API Mamouth.ai qui génère une texture seamless PNG, puis le frontend l'applique sur le mesh.

L'application de texture se fait par triplanar mapping : plutôt que d'utiliser des coordonnées UV, on projette la texture depuis les trois axes orthogonaux (X, Y, Z) et on blende les trois projections selon la normale de la surface à chaque point. Ça permet d'appliquer n'importe quelle texture sur n'importe quel mesh sans UVs et sans coutures visibles — au prix d'un résultat qui manque de précision sur les surfaces courbées.

**Limites :** le triplanar donne un résultat "générique" sans personnalisation par zone. C'est adapté pour des matériaux uniformes (pierre, métal, bois), pas pour des textures qui nécessitent un placement précis.

---

### Physique temps réel

**Ce qu'est Rapier :** un moteur physique écrit en Rust, compilé en WebAssembly et intégré via `@react-three/rapier`. Il tourne entièrement dans le navigateur à 60fps, sans aucun calcul côté serveur.

**Ce qu'on fait :** on extrait le convex hull du mesh (enveloppe convexe, simplifiée à 128 vertices pour rester performant dans le navigateur), on l'utilise comme collider physique, et on simule la chute et les rebonds de l'objet dans le viewer 3D. Les propriétés physiques — densité, friction, restitution — peuvent être générées depuis un prompt IA : "bois dense" et "caoutchouc souple" donnent des comportements différents.

**Utilité :** pertinente pour valider rapidement le comportement physique d'un asset avant de l'intégrer dans un moteur de jeu. La limite principale est le convex hull : un objet en forme de L ou de C aura un collider qui ne correspond pas à sa silhouette réelle. Une décomposition convexe (VHACD) serait plus précise mais beaucoup plus coûteuse à calculer dans le navigateur.

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

**Docker / VPS / RunPod — comment ça s'articule :**

Le VPS fait tourner le backend FastAPI et sert les fichiers statiques. Il n'a pas de GPU. Pour les opérations qui en nécessitent un (génération TRELLIS, TripoSR), deux approches :

- **RunPod Serverless** : le backend soumet un job via API REST, RunPod alloue un GPU A40 ou A100 à la demande, exécute la génération, retourne le GLB encodé en base64. On ne paie que le temps GPU réellement utilisé (~45 secondes par génération TRELLIS). C'est la solution retenue pour TRELLIS qui nécessite un GPU haut de gamme.

- **Docker worker** : Unique3D tourne dans un container Docker sur le même VPS (ou sur une machine locale avec GPU). Le backend lui envoie les requêtes en HTTP interne (`http://localhost:8001`). Plus de latence réseau, mais contrôle total et pas de coût variable.

Stability AI et TripoSR ne passent pas par RunPod : Stability est une API cloud directe, TripoSR tourne en local sur n'importe quel GPU, même modeste.

---

## Stack

| Couche | Technologie | Pourquoi |
|--------|-------------|----------|
| Backend | **FastAPI** | Framework Python async, génération automatique de la doc API, typage Pydantic |
| Géométrie 3D | **Trimesh** | Chargement natif GLB/GLTF, QEM, LSCM unwrap |
| Géométrie 3D | **PyMeshLab** | Triangulation des N-gons produits par Instant Meshes (Trimesh ne sait pas les lire) |
| Calcul numérique | **SciPy / NumPy** | KDTree spatial pour le texture baking, calculs matriciels |
| Images | **Pillow** | Lecture/écriture des textures PNG pour le baking |
| Segmentation | **Open3D + scikit-learn** | Calcul de normales et KMeans pour la segmentation par courbure |
| Remaillage | **Instant Meshes** | Field-aligned remeshing C++ — qualité difficile à égaler en Python pur |
| Rendu 3D | **React Three Fiber (RTF)** | Binding React de Three.js — composants 3D déclaratifs, intégration naturelle avec l'état React |
| Helpers 3D | **@react-three/drei** | Abstractions RTF (OrbitControls, Environment, ContactShadows) — évite de réimplémenter les éléments courants |
| Physique | **Rapier (WASM)** | Moteur physique Rust compilé WebAssembly — simulation temps réel dans le navigateur sans serveur |
| Build frontend | **Vite** | Bundler moderne, HMR instantané, beaucoup plus rapide que Webpack |
| Infra | **Docker** | Isolation du worker Unique3D et de ses dépendances CUDA |
| GPU à la demande | **RunPod Serverless** | GPU A40/A100 payés à l'usage, sans infrastructure fixe |

> **Note :** Open3D et PyVista sont présents dans le code mais leur usage est marginal (segmentation et un handler de simplification legacy). Le chemin principal utilise Trimesh.

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

## License

MIT
