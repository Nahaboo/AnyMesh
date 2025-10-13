# DEBUG.md - Performance Tracing & Analysis

Ce document explique le système de traçage des performances de MeshSimplifier pour identifier les goulots d'étranglement lors du chargement de fichiers 3D.

## Vue d'ensemble

Le chargement d'un fichier 3D passe par plusieurs étapes, réparties entre le **backend (Python/FastAPI/Trimesh)** et le **frontend (React/Three.js)**. Chaque étape est mesurée individuellement pour identifier où le temps est dépensé.

## Architecture du système de tracing

```
[User Upload]
    ↓
┌─────────────────────────────────────────────────┐
│ BACKEND (Python + Trimesh)                      │
│ ------------------------------------------------│
│ 1. HTTP_UPLOAD - Réception du fichier          │
│ 2. FILE_SAVE - Écriture sur disque             │
│ 3. TRIMESH_LOAD - trimesh.load()               │
│ 4. ANALYSIS - Calcul vertices/triangles        │
└─────────────────────────────────────────────────┘
    ↓ (Response avec timings)
┌─────────────────────────────────────────────────┐
│ FRONTEND (React/Three.js)                       │
│ ------------------------------------------------│
│ 5. FETCH - Téléchargement du fichier           │
│ 6. PARSE - Parsing Three.js (OBJLoader, etc.)  │
│ 7. RENDER - Création material + normals        │
└─────────────────────────────────────────────────┘
    ↓
[3D Model Displayed]
```

## Étapes mesurées en détail

### BACKEND (src/main.py)

#### 1. HTTP_UPLOAD
- **Quoi** : Temps total de réception du fichier uploadé par FastAPI
- **Méthode** : `@app.post("/upload")` avec `UploadFile`
- **Inclut** : Parsing multipart/form-data, buffering
- **Commence** : Entrée dans la fonction `upload_mesh()`
- **Termine** : Avant l'appel à `file_path.open()`

#### 2. FILE_SAVE
- **Quoi** : Écriture du fichier sur le disque
- **Méthode** : `shutil.copyfileobj(file.file, buffer)`
- **Inclut** : I/O disque, buffering système
- **Commence** : `start_save = time.time()`
- **Termine** : Après fermeture du fichier

#### 3. TRIMESH_LOAD ⭐
- **Quoi** : **Parsing et chargement du mesh par Trimesh**
- **Méthode** : `trimesh.load(str(file_path))`
- **Inclut** :
  - Lecture du fichier depuis le disque
  - Parsing du format (OBJ, STL, PLY, GLTF, GLB, OFF, etc.)
  - Construction des structures Trimesh (vertices, faces, normals)
  - Calcul automatique des propriétés topologiques
- **Avantages Trimesh** :
  - ✅ **Beaucoup plus rapide** : `is_watertight` <1s vs 5s avec Open3D
  - ✅ Support natif GLTF/GLB (important pour Three.js)
  - ✅ Structures de données optimisées (graphes d'adjacence cachés)
  - ✅ API pythonique et intuitive
- **Commence** : `start_load = time.time()`
- **Termine** : Après retour de `trimesh.load()`

#### 4. ANALYSIS
- **Quoi** : Extraction des statistiques du mesh
- **Méthode** : Propriétés Trimesh (`mesh.vertices`, `mesh.faces`, `mesh.is_watertight`, etc.)
- **Inclut** :
  - Comptage vertices/triangles
  - Vérification topologique (watertight, winding consistency)
  - Calcul du volume (si mesh fermé)
  - Caractéristique d'Euler
- **Conversion** : Types Python vers JSON (bool, int, float)
- **Commence** : `start_analyze = time.time()`
- **Termine** : Après création du dict `mesh_info`

### FRONTEND (frontend/src/)

#### 5. FETCH_AND_PARSE
- **Quoi** : Téléchargement réseau + Parsing Three.js (combiné)
- **Méthode** : `useLoader()` de React Three Fiber
- **Loaders selon format** :
  - **OBJ** : `OBJLoader` - Parse texte, crée BufferGeometry
  - **STL** : `STLLoader` - Parse binaire/ASCII, crée BufferGeometry
  - **PLY** : `PLYLoader` - Parse binaire/ASCII, gère vertex colors
  - **GLTF/GLB** : `GLTFLoader` - Parse JSON + binaires, gère scène complète
- **Inclut** :
  - Téléchargement depuis `http://localhost:8000/mesh/input/${filename}`
  - Parsing du format
  - Création du material (`MeshStandardMaterial`)
  - Calcul des normales (`computeVertexNormals()`)
- **Commence** : Montage du composant `MeshModel`
- **Termine** : Quand `useLoader()` retourne le modèle

#### 6. TOTAL_LOAD
- **Quoi** : Temps total frontend (FETCH_AND_PARSE + statistiques)
- **Commence** : Montage du composant `MeshModel`
- **Termine** : Affichage des statistiques du modèle + résumé

## Utilisation du système de tracing

### Activer les traces

Les traces sont **toujours actives** par défaut.

**Backend** : Les traces apparaissent automatiquement dans la console Python/Uvicorn
**Frontend** : Les traces apparaissent dans la console navigateur (F12)

### Lire les traces

#### Console Backend (Terminal Python)
```
🔵 [PERF] Upload started: bunny.obj

  📁 File save: 2.34ms (0.20 MB)
  🔷 Trimesh load: 45.67ms
  📊 Analysis: 3.12ms
     Vertices: 2,503
     Triangles: 4,968

🟢 [PERF] Upload completed: 51.13ms
```

#### Console Frontend (Navigateur)

**Étape 1 : Après l'upload (écran de confirmation visible)**
```
Upload reussi: {message: '...', mesh_info: {...}, backend_timings: {...}}

📊 [BACKEND PERF] Upload & Analysis completed:
============================================================
🟢 FILE_SAVE:       2.34ms
🟢 TRIMESH_LOAD:   45.67ms
🟢 ANALYSIS:        3.12ms
============================================================
🟢 BACKEND TOTAL:  51.13ms
```
⚠️ **Important** : Ces traces s'affichent **immédiatement après l'upload**, pendant que l'écran de confirmation est affiché. Cela permet de voir le temps passé dans Trimesh **avant** de charger le modèle 3D dans le navigateur.

**Étape 2 : Après confirmation (chargement 3D en cours)**
```
🔵 [PERF] TOTAL_LOAD_bunny.obj - START
🔵 [PERF] FETCH_AND_PARSE_OBJ_bunny.obj - START
Chargement du mesh depuis: http://localhost:8000/mesh/input/bunny.obj Format: obj
🟢 [PERF] FETCH_AND_PARSE_OBJ_bunny.obj - END: 134.56ms
📊 [MODEL] bunny.obj: { vertices: "2,503", triangles: "4,968" }
🟢 [PERF] TOTAL_LOAD_bunny.obj - END: 134.68ms

📊 [FRONTEND PERF] Performance Summary:
============================================================
  FETCH_AND_PARSE_OBJ_bunny.obj                  134.56ms
  TOTAL_LOAD_bunny.obj                           134.68ms
============================================================
  TOTAL                                          269.24ms
```

### Séparation Backend / Frontend

**Architecture propre** : Les traces backend et frontend sont **complètement séparées** pour respecter la séparation des préoccupations :

- ✅ **Backend traces** : Affichées dans FileUpload.jsx (console navigateur) immédiatement après l'upload
- ✅ **Frontend traces** : Affichées dans MeshModel.jsx (console navigateur) après le chargement 3D
- ✅ **Console Python** : Les traces détaillées backend restent dans la console Python/Uvicorn
- ❌ **Pas de transfert** : Les timings backend ne sont PAS transmis au système de performance frontend
- ❌ **Pas de couplage** : Les composants frontend ne dépendent pas des timings backend

Cette séparation permet de :
1. Maintenir une architecture propre avec séparation des préoccupations
2. Débugger indépendamment le backend et le frontend
3. Éviter le couplage inutile entre les deux couches
4. Faciliter la maintenance et l'évolution du système

## Interpréter les résultats

### Couleurs des traces
- 🔵 **Bleu** : Début d'une opération
- 🟢 **Vert** : Fin rapide (< 100ms)
- 🟡 **Jaune** : Moyen (100-1000ms)
- 🔴 **Rouge** : Lent (> 1000ms)

### Identifier les goulots d'étranglement

1. **TRIMESH_LOAD est lent** (> 500ms)
   - Fichier très volumineux (> 10 MB)
   - Format inefficace (PLY texte vs binaire)
   - Solution : Utiliser formats binaires, pré-simplifier le mesh

2. **FETCH est lent** (> 200ms sur localhost)
   - Fichier volumineux
   - Solution : Compression gzip, streaming chunks

3. **PARSE (Three.js) est lent** (> 500ms)
   - Parsing Three.js inefficace
   - Trop de vertices/triangles
   - Solution : Utiliser formats binaires (GLB vs GLTF), simplifier le mesh

4. **Comparaison Trimesh vs Three.js**
   - Si TRIMESH_LOAD >> FETCH_AND_PARSE : Backend plus lent (rare)
   - Si FETCH_AND_PARSE >> TRIMESH_LOAD : Frontend plus lent (fréquent pour gros meshes)

## Fichiers concernés

### Backend
- **src/main.py** : API principale avec Trimesh
- Fonction `upload_mesh()` (ligne ~70-150) : Traces de performance avec `time.time()`

### Frontend
- **frontend/src/utils/performance.js** : Classe `PerformanceTracker`
- **frontend/src/components/MeshModel.jsx** : Traces FETCH_AND_PARSE, TOTAL_LOAD
- **frontend/src/components/FileUpload.jsx** : Fonction `displayBackendTimings()`

## Pourquoi Trimesh ?

### Avantages de Trimesh sur Open3D

1. **Performance** : `is_watertight()` 5-10x plus rapide
2. **Formats** : Support natif GLTF/GLB (essentiel pour Three.js)
3. **API** : Plus pythonique, plus intuitive
4. **Écosystème** : Intégration avec NetworkX, Shapely, rtree
5. **Propriétés avancées** : `euler_number`, `volume`, `is_winding_consistent`

### Quand utiliser Open3D ?

Pour votre projet, Open3D peut être ajouté plus tard pour :
- Simplification avancée (Quadric Error Metric)
- Traitement de nuages de points avancés
- Algorithmes de reconstruction de surface (Poisson, Ball-Pivoting)
- Registration ICP

**Pour l'instant, Trimesh suffit largement pour vos besoins.**

## Formats et performance

| Format | Taille | TRIMESH_LOAD | PARSE (Three.js) | Recommandation |
|--------|--------|--------------|------------------|----------------|
| OBJ    | Grande (texte) | Moyen | Moyen | Bon pour debug |
| STL    | Grande | Rapide | Rapide | Standard industrie |
| PLY    | Moyenne | Moyen | Moyen | Supporte couleurs |
| GLTF   | Moyenne | Rapide ✅ | Lent (multi-fichiers) | Éviter |
| GLB    | Petite | Rapide ✅ | Rapide | **Meilleur pour web** |
| OFF    | Moyenne | Rapide | ❌ N/A (pas Three.js) | Usage scientifique |

**Note** : Trimesh supporte TOUS ces formats, contrairement à Open3D qui ne gère pas GLTF/GLB.

## Changelog

### 2025-01-13 - Transition vers Trimesh
- Migration complète vers Trimesh comme bibliothèque backend
- Suppression de la dépendance Open3D pour l'analyse
- Performance `is_watertight` : 5s → <1s
- Support GLTF/GLB natif
- Documentation mise à jour

### 2025-01-XX - Version initiale
- Système de tracing backend avec `time.time()`
- Système de tracing frontend avec `performance.now()`
- Documentation initiale des étapes mesurées
