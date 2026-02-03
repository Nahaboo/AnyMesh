# AnyMesh

Application web pour manipuler des modèles 3D : simplification, retopologie, segmentation et génération depuis images.

## Démarrage

**Backend** (Python 3.12)
```bash
pip install -r requirement.txt
uvicorn src.main:app --reload --port 8000
```

**Frontend** (React)
```bash
cd frontend
npm install
npm run dev
```

Ouvre http://localhost:5173

## Fonctionnalités

- **Upload** : OBJ, STL, PLY, GLB, GLTF
- **Simplification** : Réduction du nombre de triangles
- **Retopologie** : Remaillage optimisé (Instant Meshes)
- **Segmentation** : Découpage par connectivity, arêtes, courbure
- **Génération 3D** : Création de mesh depuis une image (Stability AI)
- **Export** : OBJ, STL, PLY, GLB

## Stack

- Backend : FastAPI + Trimesh
- Frontend : React + Three.js
- Outils : Instant Meshes, Stability AI

## Déploiement

```bash
docker-compose up -d --build
```

## License

MIT
