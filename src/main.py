"""
Backend FastAPI pour MeshSimplifier
Fournit les endpoints pour l'upload et le traitement de maillages 3D
"""

import os
import shutil
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import trimesh

from .task_manager import task_manager, Task
from .simplify import simplify_mesh

app = FastAPI(
    title="MeshSimplifier API",
    description="API pour la simplification et réparation de maillages 3D",
    version="0.1.0"
)

# Configuration CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dossiers de données
DATA_INPUT = Path("data/input")
DATA_OUTPUT = Path("data/output")
DATA_INPUT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT.mkdir(parents=True, exist_ok=True)

# Formats de fichiers supportés
SUPPORTED_FORMATS = {".obj", ".stl", ".ply", ".off", ".gltf", ".glb"}

# Modèles Pydantic
class SimplifyRequest(BaseModel):
    """Paramètres de simplification"""
    filename: str
    target_triangles: Optional[int] = None
    reduction_ratio: Optional[float] = None
    preserve_boundary: bool = True

@app.get("/")
async def root():
    """Endpoint racine - vérification que l'API fonctionne"""
    return {
        "message": "MeshSimplifier API",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    return {"status": "healthy"}

@app.post("/upload")
async def upload_mesh(file: UploadFile = File(...)):
    """
    Upload un fichier de maillage 3D
    Formats supportés: OBJ, STL, PLY, OFF, GLTF, GLB
    """
    start_total = time.time()
    print(f"\n🔵 [PERF] Upload started: {file.filename}")

    # Vérification de l'extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats acceptés: {', '.join(SUPPORTED_FORMATS)}"
        )

    # Sauvegarde du fichier
    start_save = time.time()
    file_path = DATA_INPUT / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la sauvegarde: {str(e)}"
        ) from e

    save_duration = (time.time() - start_save) * 1000
    print(f"  📁 File save: {save_duration:.2f}ms ({file_path.stat().st_size / 1024 / 1024:.2f} MB)")

    # Utilisation de trimesh pour toutes les analyses
    start_load = time.time()
    try:
        mesh = trimesh.load(str(file_path))
        load_duration = (time.time() - start_load) * 1000
        print(f"  🔷 trimesh load: {load_duration:.2f}ms")

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise HTTPException(
                status_code=400,
                detail="Le fichier ne contient pas de vertices valides"
            )

        # Extraction des propriétés du maillage
        start_analyze = time.time()

        # Convertir les propriétés trimesh en types JSON-sérialisables
        is_watertight = bool(mesh.is_watertight) if hasattr(mesh, 'is_watertight') else False
        is_winding_consistent = bool(mesh.is_winding_consistent) if hasattr(mesh, 'is_winding_consistent') else None

        # Volume - calcul sécurisé uniquement si watertight
        volume = None
        if is_watertight:
            try:
                volume = float(mesh.volume)
            except Exception:
                # Ignorer si le calcul échoue (mesh invalide)
                pass

        # Bounding box pour ajuster la caméra frontend
        bounds = mesh.bounds  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
        bounding_box = {
            "min": [float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])],
            "max": [float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])],
            "size": [float(bounds[1][0] - bounds[0][0]),
                     float(bounds[1][1] - bounds[0][1]),
                     float(bounds[1][2] - bounds[0][2])],
            "center": [float(mesh.centroid[0]), float(mesh.centroid[1]), float(mesh.centroid[2])],
            "diagonal": float(mesh.scale)  # Longueur de la diagonale de la bounding box
        }

        mesh_info = {
            "filename": file.filename,
            "file_size": file_path.stat().st_size,
            "format": file_ext,
            "vertices_count": int(len(mesh.vertices)),
            "triangles_count": int(len(mesh.faces)),
            "has_normals": hasattr(mesh, 'vertex_normals') and mesh.vertex_normals is not None,
            "has_colors": bool(hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None),
            "is_watertight": is_watertight,
            "is_orientable": is_winding_consistent,
            "is_manifold": None,  # Trimesh n'a pas d'équivalent direct simple
            # Propriétés supplémentaires trimesh
            "euler_number": int(mesh.euler_number) if hasattr(mesh, 'euler_number') else None,
            "volume": volume,
            "bounding_box": bounding_box  # Pour ajuster la caméra Three.js
        }
        analyze_duration = (time.time() - start_analyze) * 1000
        print(f"  📊 Analysis: {analyze_duration:.2f}ms")
        print(f"     Vertices: {mesh_info['vertices_count']:,}")
        print(f"     Triangles: {mesh_info['triangles_count']:,}")

        total_duration = (time.time() - start_total) * 1000
        print(f"🟢 [PERF] Upload completed: {total_duration:.2f}ms\n")

        # Timings pour le frontend
        backend_timings = {
            "file_save_ms": round(save_duration, 2),
            "trimesh_load_ms": round(load_duration, 2),
            "analysis_ms": round(analyze_duration, 2),
            "total_ms": round(total_duration, 2)
        }

        return {
            "message": "Fichier uploadé avec succès",
            "mesh_info": mesh_info,
            "backend_timings": backend_timings
        }

    except Exception as e:
        # Supprimer le fichier si le chargement échoue
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors du chargement du maillage: {str(e)}"
        ) from e

@app.get("/meshes")
async def list_meshes():
    """Liste tous les fichiers de maillage disponibles"""
    meshes = []
    for file_path in DATA_INPUT.iterdir():
        if file_path.suffix.lower() in SUPPORTED_FORMATS:
            meshes.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "format": file_path.suffix.lower()
            })
    return {"meshes": meshes, "count": len(meshes)}

# Handler pour les tâches de simplification
def simplify_task_handler(task: Task):
    """Handler qui exécute la simplification d'un maillage"""
    params = task.params
    input_file = params["input_file"]
    output_file = params["output_file"]
    target_triangles = params.get("target_triangles")
    reduction_ratio = params.get("reduction_ratio")
    preserve_boundary = params.get("preserve_boundary", True)

    # Exécute la simplification
    result = simplify_mesh(
        input_path=Path(input_file),
        output_path=Path(output_file),
        target_triangles=target_triangles,
        reduction_ratio=reduction_ratio,
        preserve_boundary=preserve_boundary
    )

    return result

@app.post("/simplify")
async def simplify_mesh_async(request: SimplifyRequest):
    """
    Lance une tâche de simplification de maillage en arrière-plan
    Retourne un task_id pour suivre la progression
    """
    input_path = DATA_INPUT / request.filename

    # Vérification que le fichier existe
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Vérification du format
    file_ext = input_path.suffix.lower()
    if file_ext in {".gltf", ".glb"}:
        raise HTTPException(
            status_code=400,
            detail="La simplification des fichiers GLTF/GLB n'est pas supportée avec trimesh."
        )

    # Génération du nom de fichier de sortie
    output_filename = f"{input_path.stem}_simplified{input_path.suffix}"
    output_path = DATA_OUTPUT / output_filename

    # Création de la tâche
    task_id = task_manager.create_task(
        task_type="simplify",
        params={
            "input_file": str(input_path),
            "output_file": str(output_path),
            "target_triangles": request.target_triangles,
            "reduction_ratio": request.reduction_ratio,
            "preserve_boundary": request.preserve_boundary
        }
    )

    return {
        "task_id": task_id,
        "message": "Tâche de simplification créée",
        "output_filename": output_filename
    }

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Récupère le statut d'une tâche"""
    task = task_manager.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    return task.to_dict()

@app.get("/tasks")
async def list_tasks():
    """Liste toutes les tâches"""
    tasks = task_manager.get_all_tasks()
    return {
        "tasks": [task.to_dict() for task in tasks.values()],
        "count": len(tasks),
        "queue_size": task_manager.get_queue_size()
    }

@app.get("/mesh/input/{filename}")
async def get_input_mesh(filename: str):
    """Sert un fichier de maillage depuis data/input pour la visualisation"""
    file_path = DATA_INPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Déterminer le media_type
    file_ext = file_path.suffix.lower()
    media_type_mapping = {
        ".obj": "model/obj",
        ".stl": "model/stl",
        ".ply": "application/ply",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
        ".off": "application/octet-stream"
    }
    media_type = media_type_mapping.get(file_ext, "application/octet-stream")

    # Streamer le fichier
    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

@app.get("/download/{filename}")
async def download_mesh(filename: str):
    """Télécharge un fichier de maillage simplifié depuis data/output"""
    file_path = DATA_OUTPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )

# Initialisation du gestionnaire de tâches
@app.on_event("startup")
async def startup_event():
    """Démarre le gestionnaire de tâches"""
    task_manager.register_handler("simplify", simplify_task_handler)
    task_manager.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Arrête proprement le gestionnaire de tâches"""
    task_manager.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
