"""
Backend FastAPI pour MeshSimplifier
Fournit les endpoints pour l'upload et le traitement de maillages 3D
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import open3d as o3d

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
