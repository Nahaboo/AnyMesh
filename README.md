# MeshSimplifier

**Application web de simplification et reparation de maillages 3D**

Backend Python (FastAPI + Open3D) avec file d'attente de taches asynchrones + Frontend React Three Fiber.

## Statut du Projet

### Backend (Option A - API REST avec File d'Attente)
- [x] FastAPI server avec CORS configure
- [x] Upload de fichiers 3D (OBJ, STL, PLY, OFF, GLTF, GLB)
- [x] Analyse des proprietes geometriques et topologiques
- [x] Systeme de file d'attente de taches avec workers threads
- [x] Simplification de maillages (algorithme Quadric Error Metric)
- [x] Suivi de progression des taches en temps reel
- [x] Telechargement des fichiers traites
- [x] API complete testee et fonctionnelle
- [ ] Reparation de maillages (a venir)

### Frontend
- [ ] Interface React avec Three.js / React Three Fiber
- [ ] Visualisation 3D interactive
- [ ] Upload avec drag & drop
- [ ] Controles de simplification
- [ ] Comparaison avant/apres

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│                   React Three Fiber (3D)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP REST API
┌──────────────────────┴──────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Task Manager (Queue)                     │  │
│  │  ┌─────────────┐  ┌─────────────┐                    │  │
│  │  │  Worker 1   │  │  Worker 2   │                    │  │
│  │  └─────────────┘  └─────────────┘                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            Open3D                                    │  │
│  │                                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                       │
                  ┌────┴────┐
                  │  Files  │
            ┌─────┴─────────┴─────┐
            │ data/input/         │
            │ data/output/        │
            └─────────────────────┘
```

## Technologies Utilisees

### Backend
- **Python 3.12.10** (IMPORTANT: Open3D ne supporte pas Python 3.13+)
- **FastAPI** - Framework web asynchrone
- **Uvicorn** - Serveur ASGI
- **Open3D** - Traitement de maillages 3D
- **Threading + Queue** - Gestion de taches asynchrones

### Frontend (a venir)
- **React** - Framework UI
- **Three.js / React Three Fiber** - Visualisation 3D
- **Vite** - Build tool

## Installation

### Prerequis
- Python 3.12.10 (exactement cette version, Open3D ne supporte pas 3.13+)
- Git

### Etapes

1. **Cloner le repository**
```bash
git clone <repo-url>
cd MeshSimplifier
```

2. **Creer le virtual environment**
```bash
python -m venv venv
```

3. **Activer le venv**
```bash
# Windows CMD
venv\Scripts\activate.bat

# Windows PowerShell
venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate
```

4. **Installer les dependances**
```bash
pip install -r requirement.txt
```

5. **Verifier l'installation**
```bash
python --version  # Doit afficher 3.12.10
python test_open3d.py  # Test Open3D avec spheres
```

## Demarrage Rapide

### Demarrer le Backend

```bash
# Avec reload automatique
uvicorn src.main:app --reload --port 8000

# Ou directement avec Python
python -m uvicorn src.main:app --reload --port 8000
```

Le backend sera accessible sur :
- **API** : http://localhost:8000
- **Documentation interactive** : http://localhost:8000/docs
- **Health check** : http://localhost:8000/health

### Tester l'API

#### Script de test automatique
```bash
python test_api.py
```

#### Tests manuels avec curl
```bash
# 1. Verifier l'API
curl http://localhost:8000/

# 2. Lister les maillages disponibles
curl http://localhost:8000/meshes

# 3. Upload d'un fichier
curl -X POST "http://localhost:8000/upload" -F "file=@data/input/bunny.obj"

# 4. Lancer une simplification (reduction de 50%)
curl -X POST "http://localhost:8000/simplify" \
  -H "Content-Type: application/json" \
  -d '{"filename":"bunny.obj","reduction_ratio":0.5}'

# Response: {"task_id":"xxx-xxx-xxx","message":"...","output_filename":"..."}

# 5. Verifier le statut de la tache
curl http://localhost:8000/tasks/xxx-xxx-xxx

# 6. Telecharger le resultat
curl -O http://localhost:8000/download/bunny_simplified.obj
```

## API Endpoints

### Upload et Gestion de Fichiers

- **GET /** - Information API
- **GET /health** - Health check
- **POST /upload** - Upload un fichier 3D
- **GET /meshes** - Liste des maillages disponibles
- **GET /download/{filename}** - Telecharge un fichier traite

### Simplification de Maillages

- **POST /simplify** - Lance une tache de simplification
  ```json
  {
    "filename": "bunny.obj",
    "reduction_ratio": 0.5,
    "target_triangles": 1000,
    "preserve_boundary": true
  }
  ```

### Gestion de Taches

- **GET /tasks** - Liste toutes les taches
- **GET /tasks/{task_id}** - Statut d'une tache specifique

### Statuts de Tache

- `pending` - Tache en attente
- `processing` - Tache en cours de traitement
- `completed` - Tache terminee avec succes
- `failed` - Tache echouee

## Exemple d'Utilisation

```python
import requests
import time

# 1. Upload d'un fichier
files = {'file': open('mesh.obj', 'rb')}
upload_res = requests.post('http://localhost:8000/upload', files=files)
print(upload_res.json())

# 2. Lancer simplification
simplify_data = {
    "filename": "mesh.obj",
    "reduction_ratio": 0.7  # Reduction de 70%
}
simplify_res = requests.post(
    'http://localhost:8000/simplify',
    json=simplify_data
)
task_id = simplify_res.json()['task_id']

# 3. Polling du statut
while True:
    task_res = requests.get(f'http://localhost:8000/tasks/{task_id}')
    task = task_res.json()

    print(f"Status: {task['status']}, Progress: {task['progress']}%")

    if task['status'] == 'completed':
        print("Resultats:", task['result'])
        break
    elif task['status'] == 'failed':
        print("Erreur:", task['error'])
        break

    time.sleep(1)

# 4. Telecharger le resultat
output_file = task['result']['output_file']
download_res = requests.get(f'http://localhost:8000/download/{output_file}')
with open('result.obj', 'wb') as f:
    f.write(download_res.content)
```

## Structure du Projet

```
MeshSimplifier/
├── .vscode/                         # Configuration VS Code
│   ├── settings.json               # Python/venv settings
│   └── launch.json                 # Debug configurations
├── src/
│   ├── __init__.py
│   ├── main.py                     # Backend FastAPI
│   ├── simplify.py                 # Module de simplification
│   └── task_manager.py             # Gestionnaire de taches
├── data/
│   ├── input/                      # Fichiers 3D a traiter
│   └── output/                     # Fichiers 3D traites
├── tests/                           # Tests unitaires
├── venv/                            # Virtual environment (git-ignored)
├── requirement.txt                  # Dependances Python
├── test_open3d.py                  # Test Open3D
├── test_api.py                     # Tests API
├── CLAUDE.md                       # Instructions pour Claude Code
├── BACKEND_EXPLAINED.md            # Documentation backend detaillee
├── OPTION_A_IMPLEMENTATION.md      # Documentation Option A
├── DEMARRAGE_RAPIDE.md             # Guide de demarrage rapide
└── README.md                       # Ce fichier
```

## Formats de Fichiers Supportes

- **OBJ** (.obj) - Wavefront Object
- **STL** (.stl) - Stereolithography
- **PLY** (.ply) - Polygon File Format
- **OFF** (.off) - Object File Format
- **GLTF** (.gltf) - GL Transmission Format
- **GLB** (.glb) - Binary GLTF

## Algorithme de Simplification

Le backend utilise l'algorithme **Quadric Error Metric Decimation** d'Open3D :

- Preserve au mieux la forme originale
- Minimise l'erreur quadratique
- Options de preservation des bords
- Rapide et efficace

**Parametres disponibles :**
- `target_triangles` : Nombre cible de triangles
- `reduction_ratio` : Ratio de reduction (0.0 - 1.0)
- `preserve_boundary` : Preserve les bords du maillage

## Documentation

- **[DEMARRAGE_RAPIDE.md](DEMARRAGE_RAPIDE.md)** - Guide de demarrage complet
- **[BACKEND_EXPLAINED.md](BACKEND_EXPLAINED.md)** - Explication detaillee du backend
- **[OPTION_A_IMPLEMENTATION.md](OPTION_A_IMPLEMENTATION.md)** - Implementation Option A
- **[CLAUDE.md](CLAUDE.md)** - Instructions pour Claude Code

## Tests

### Test Open3D
```bash
python test_open3d.py
```
Affiche deux spheres (originale et simplifiee) pour verifier Open3D.

### Test API
```bash
python test_api.py
```
Test automatique complet de tous les endpoints.

### Tests Unitaires (a venir)
```bash
pytest tests/
```

## Troubleshooting

### Port 8000 deja utilise
```bash
# Utiliser un autre port
uvicorn src.main:app --reload --port 8001
```

### Module not found errors
```bash
# Verifier que le venv est actif
which python  # Linux/Mac
where python  # Windows

# Reinstaller les dependances
pip install -r requirement.txt
```

### Python 3.13+ installe
Open3D ne supporte pas Python 3.13+. Desinstallez Python 3.13 et installez Python 3.12.10.

## Roadmap

### Phase 1 : Backend (COMPLETE)
- [x] FastAPI server
- [x] Upload de fichiers
- [x] Analyse de maillages
- [x] Systeme de file d'attente
- [x] Simplification de maillages
- [x] API complete et testee

### Phase 2 : Frontend (EN COURS)
- [ ] Setup React + Vite
- [ ] Integration React Three Fiber
- [ ] Visualisation 3D
- [ ] Interface d'upload
- [ ] Controles de simplification
- [ ] Comparaison avant/apres

### Phase 3 : Fonctionnalites Avancees
- [ ] Reparation de maillages
- [ ] Batch processing
- [ ] Export multi-formats
- [ ] Historique de taches
- [ ] Statistiques detaillees

## License

MIT

## Auteur

Kevin
