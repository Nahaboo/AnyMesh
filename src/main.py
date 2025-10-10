"""
Backend FastAPI pour MeshSimplifier
Fournit les endpoints pour l'upload et le traitement de maillages 3D
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
import shutil
import open3d as o3d

from .task_manager import task_manager, Task
from .simplify import simplify_mesh

app = FastAPI(
    title="MeshSimplifier API",
    description="API pour la simplification et reparation de maillages 3D",
    version="0.1.0"
)

# Configuration CORS pour permettre les requetes depuis le frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dossiers de donnees
DATA_INPUT = Path("data/input")
DATA_OUTPUT = Path("data/output")
DATA_INPUT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT.mkdir(parents=True, exist_ok=True)

# Formats de fichiers supportes
SUPPORTED_FORMATS = {".obj", ".stl", ".ply", ".off", ".gltf", ".glb"}


# Modeles Pydantic pour les requetes
class SimplifyRequest(BaseModel):
    """Parametres de simplification"""
    filename: str
    target_triangles: Optional[int] = None
    reduction_ratio: Optional[float] = None
    preserve_boundary: bool = True


@app.get("/")
async def root():
    """Endpoint racine - verification que l'API fonctionne"""
    return {
        "message": "MeshSimplifier API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Verification de l'etat de l'API"""
    return {"status": "healthy"}


@app.post("/upload")
async def upload_mesh(file: UploadFile = File(...)):
    """
    Upload un fichier de maillage 3D
    Formats supportes: OBJ, STL, PLY, OFF, GLTF, GLB
    """
    # Verification de l'extension du fichier
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporte. Formats acceptes: {', '.join(SUPPORTED_FORMATS)}"
        )

    # Sauvegarde du fichier
    file_path = DATA_INPUT / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde: {str(e)}")

    # Chargement et verification du maillage avec Open3D
    try:
        mesh = o3d.io.read_triangle_mesh(str(file_path))

        if not mesh.has_vertices():
            raise HTTPException(status_code=400, detail="Le fichier ne contient pas de vertices valides")

        # Extraction des proprietes du maillage
        mesh_info = {
            "filename": file.filename,
            "file_size": file_path.stat().st_size,
            "format": file_ext,
            "vertices_count": len(mesh.vertices),
            "triangles_count": len(mesh.triangles),
            "has_normals": mesh.has_vertex_normals(),
            "has_colors": mesh.has_vertex_colors(),
            "is_watertight": mesh.is_watertight(),
            "is_orientable": mesh.is_orientable(),
            "is_manifold": mesh.is_vertex_manifold() and mesh.is_edge_manifold()
        }

        return {
            "message": "Fichier uploade avec succes",
            "mesh_info": mesh_info
        }

    except Exception as e:
        # Supprimer le fichier si le chargement echoue
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"Erreur lors du chargement du maillage: {str(e)}")


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


# Handler pour les taches de simplification
def simplify_task_handler(task: Task):
    """Handler qui execute la simplification d'un maillage"""
    params = task.params
    input_file = params["input_file"]
    output_file = params["output_file"]
    target_triangles = params.get("target_triangles")
    reduction_ratio = params.get("reduction_ratio")
    preserve_boundary = params.get("preserve_boundary", True)

    # Execute la simplification
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
    Lance une tache de simplification de maillage en arriere-plan

    Retourne un task_id pour suivre la progression
    """
    input_path = DATA_INPUT / request.filename

    # Verification que le fichier existe
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouve")

    # Generation du nom de fichier de sortie
    output_filename = f"{input_path.stem}_simplified{input_path.suffix}"
    output_path = DATA_OUTPUT / output_filename

    # Creation de la tache
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
        "message": "Tache de simplification creee",
        "output_filename": output_filename
    }


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Recupere le statut d'une tache"""
    task = task_manager.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Tache non trouvee")

    return task.to_dict()


@app.get("/tasks")
async def list_tasks():
    """Liste toutes les taches"""
    tasks = task_manager.get_all_tasks()
    return {
        "tasks": [task.to_dict() for task in tasks.values()],
        "count": len(tasks),
        "queue_size": task_manager.get_queue_size()
    }


@app.get("/download/{filename}")
async def download_mesh(filename: str):
    """Telecharge un fichier de maillage simplifie"""
    file_path = DATA_OUTPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouve")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )


# Initialisation du gestionnaire de taches au demarrage
@app.on_event("startup")
async def startup_event():
    """Demarre le gestionnaire de taches"""
    task_manager.register_handler("simplify", simplify_task_handler)
    task_manager.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Arrete proprement le gestionnaire de taches"""
    task_manager.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
