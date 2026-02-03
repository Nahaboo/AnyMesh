# AnyMesh

Application web pour manipuler des modèles 3D : simplification, retopologie, segmentation et génération depuis images.

## Stack

**Backend:** Python 3.12 + FastAPI + Trimesh
**Frontend:** React + Three.js
**Outils:** Instant Meshes, Stability AI

## Démarrage

```bash
# Backend
pip install -r requirement.txt
uvicorn src.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

→ http://localhost:5173

## Fonctionnalités

- Upload : OBJ, STL, PLY, GLB, GLTF
- Simplification : réduction du nombre de triangles
- Retopologie : remaillage optimisé
- Segmentation : découpage par connectivity, arêtes, courbure
- Génération 3D : création depuis une image (Stability AI)
- Export : OBJ, STL, PLY, GLB

## Déploiement

```bash
docker-compose up -d --build
```

## License

MIT
