"""
Backend FastAPI pour MeshSimplifier
Fournit les endpoints pour l'upload et le traitement de maillages 3D
"""

import os
import re
import shutil
import time
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Q2: Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import trimesh

from .task_manager import task_manager, Task
from .simplify import simplify_mesh, adaptive_simplify_mesh, simplify_mesh_glb
from .converter import convert_mesh_format, convert_any_to_glb
from .stability_client import generate_mesh_from_image_sf3d
from .mamouth_client import generate_image_from_prompt, generate_texture_from_prompt, infer_physics_from_prompt
from .retopology import retopologize_mesh, retopologize_mesh_glb
from .segmentation import segment_mesh, segment_mesh_glb
from .temp_utils import cleanup_temp_directory, safe_delete

# Charger les variables d'environnement depuis .env
load_dotenv()


# Q1: Lifespan context manager (remplace @app.on_event deprecated)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion du cycle de vie de l'application.
    Remplace les @app.on_event("startup") et @app.on_event("shutdown") dépréciés.
    """
    # === STARTUP ===
    logger.info("=== MeshSimplifier Backend Starting ===")

    # Valider la clé API Stability
    api_key = os.getenv('STABILITY_API_KEY')
    if not api_key:
        logger.warning("STABILITY_API_KEY not set - mesh generation will fail")
        logger.warning("Create .env file and add: STABILITY_API_KEY=sk-your-key-here")
    elif not api_key.startswith('sk-'):
        logger.warning("STABILITY_API_KEY may be invalid (should start with 'sk-')")
    else:
        logger.info(f"Stability API key loaded: {api_key[:10]}...")

    # Valider la cle API Mamouth
    mamouth_key = os.getenv('MAMOUTH_API_KEY')
    if mamouth_key:
        logger.info(f"Mamouth API key loaded: {mamouth_key[:10]}...")
    else:
        logger.warning("MAMOUTH_API_KEY not set - prompt generation disabled")

    # Enregistrer les handlers de tâches
    task_manager.register_handler("simplify", simplify_task_handler)
    task_manager.register_handler("simplify_adaptive", adaptive_simplify_task_handler)
    task_manager.register_handler("generate_mesh", generate_mesh_task_handler)
    task_manager.register_handler("retopologize", retopologize_task_handler)
    task_manager.register_handler("segment", segment_task_handler)
    task_manager.register_handler("generate_image", generate_image_task_handler)
    task_manager.register_handler("generate_texture", generate_texture_task_handler)
    task_manager.register_handler("generate_material", generate_material_task_handler)
    task_manager.register_handler("sanitize", sanitize_task_handler)
    task_manager.start()

    # GLB-First: Nettoyer les fichiers temporaires au démarrage
    logger.info("Nettoyage des fichiers temporaires...")
    cleanup_temp_directory(DATA_TEMP, max_age_hours=1)

    logger.info("Backend started successfully")

    yield  # L'application tourne ici

    # === SHUTDOWN ===
    logger.info("=== MeshSimplifier Backend Stopping ===")
    task_manager.stop()
    logger.info("Backend stopped")


app = FastAPI(
    title="MeshSimplifier API",
    description="API pour la simplification et réparation de maillages 3D",
    version="0.2.0",
    lifespan=lifespan  # Q1: Utilisation du nouveau système lifespan
)

# Configuration CORS - Lecture depuis variable d'environnement
# En dev: ALLOWED_ORIGINS=* (défaut)
# En prod: ALLOWED_ORIGINS=https://votre-frontend.vercel.app
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if allowed_origins_env == "*" else [o.strip() for o in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,  # Doit être False si allow_origins contient "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dossiers de données
DATA_INPUT = Path("data/input")
DATA_OUTPUT = Path("data/output")
DATA_INPUT_IMAGES = Path("data/input_images")
DATA_GENERATED_MESHES = Path("data/generated_meshes")
DATA_RETOPO = Path("data/retopo")
DATA_SEGMENTED = Path("data/segmented")
DATA_GENERATED_TEXTURES = Path("data/generated_textures")
DATA_TEMP = Path("data/temp")  # GLB-First: Fichiers temporaires pour conversions
DATA_SAVED = Path("data/saved")  # GLB-First: Meshes sauvegardés par l'utilisateur
DATA_INPUT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
DATA_INPUT_IMAGES.mkdir(parents=True, exist_ok=True)
DATA_GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
DATA_RETOPO.mkdir(parents=True, exist_ok=True)
DATA_SEGMENTED.mkdir(parents=True, exist_ok=True)
DATA_GENERATED_TEXTURES.mkdir(parents=True, exist_ok=True)
DATA_TEMP.mkdir(parents=True, exist_ok=True)

# Formats de fichiers supportés
SUPPORTED_FORMATS = {".obj", ".stl", ".ply", ".off", ".gltf", ".glb"}
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png"}

# Limite de taille de fichier (95 MB)
MAX_UPLOAD_SIZE = 95 * 1024 * 1024  # 95 MB en bytes


def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier pour éviter les path traversal attacks.

    Sécurité:
    - Retire tout chemin (garde seulement le nom de fichier)
    - Retire les séquences ".." dangereuses
    - Limite aux caractères alphanumériques, points, tirets et underscores
    """
    if not filename:
        raise ValueError("Nom de fichier vide")

    # Retirer tout chemin (garde seulement le nom de fichier)
    filename = os.path.basename(filename)

    # Retirer les caractères dangereux de path traversal
    filename = filename.replace("..", "")

    # Limiter aux caractères sûrs: alphanumériques, point, tiret, underscore
    # Préserver l'extension en traitant séparément
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()

    # Nettoyer le stem (nom sans extension)
    clean_stem = re.sub(r'[^\w\-]', '_', stem)

    # Reconstruire le filename
    clean_filename = f"{clean_stem}{ext}" if ext else clean_stem

    if not clean_filename or clean_filename in ('.', '..'):
        raise ValueError("Nom de fichier invalide apres nettoyage")

    return clean_filename

# Modèles Pydantic
class SimplifyRequest(BaseModel):
    """Paramètres de simplification"""
    filename: str
    target_triangles: Optional[int] = None
    reduction_ratio: Optional[float] = None
    preserve_boundary: bool = True
    is_generated: bool = False  # Si True, cherche dans data/generated_meshes

class AdaptiveSimplifyRequest(BaseModel):
    """Paramètres de simplification adaptative"""
    filename: str
    target_ratio: float = 0.5  # Ratio de reduction de base (0.0 - 1.0)
    flat_multiplier: float = 2.0  # Multiplicateur pour zones plates (1.0 - 3.0)
    curvature_threshold: Optional[float] = None  # Seuil auto si None
    is_generated: bool = False  # Si True, cherche dans data/generated_meshes

class GenerateMeshRequest(BaseModel):
    """Paramètres de génération de maillage à partir d'images
    GLB-First: Le format de sortie est toujours GLB (natif de l'API Stability ou TripoSR)
    """
    session_id: str
    resolution: str = "medium"  # 'low', 'medium', 'high'
    remesh_option: str = "quad"  # 'none', 'triangle', 'quad' - Topologie du mesh généré (Stability only)
    provider: str = "stability"  # 'stability' (API cloud) ou 'triposr' (local, gratuit)

class GenerateImageRequest(BaseModel):
    """Parametres de generation d'image a partir d'un prompt textuel via Mamouth.ai"""
    prompt: str
    resolution: str = "medium"  # 'low', 'medium', 'high'

class GenerateTextureRequest(BaseModel):
    """Parametres de generation de texture via Mamouth.ai"""
    prompt: str
    resolution: str = "medium"  # 'low', 'medium', 'high'

class GenerateMaterialRequest(BaseModel):
    """Parametres de generation de materiau IA (texture + physique)"""
    prompt: str

class RetopologyRequest(BaseModel):
    """Paramètres de retopologie avec Instant Meshes"""
    filename: str
    target_face_count: int = 10000
    original_face_count: int  # Nombre de faces du mesh original (envoyé par le frontend)
    deterministic: bool = True
    preserve_boundaries: bool = True
    is_generated: bool = False  # Si True, cherche dans data/generated_meshes
    is_simplified: bool = False  # Si True, cherche dans data/output

class SegmentRequest(BaseModel):
    """Paramètres de segmentation de mesh"""
    filename: str
    method: str = "connectivity"  # 'connectivity', 'sharp_edges', 'curvature', 'planes'
    angle_threshold: Optional[float] = None  # Pour sharp_edges (degrés)
    num_clusters: Optional[int] = None  # Pour curvature
    num_planes: Optional[int] = None  # Pour planes
    is_generated: bool = False  # Si True, cherche dans data/generated_meshes
    is_simplified: bool = False  # Si True, cherche dans data/output
    is_retopo: bool = False  # Si True, cherche dans data/retopo


class SaveMeshRequest(BaseModel):
    """GLB-First: Paramètres pour sauvegarder un mesh"""
    source_filename: str  # Nom du fichier source (dans n'importe quel dossier)
    save_name: str  # Nom de la sauvegarde (sans extension)


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
    """
    U6: Health check détaillé avec infos système.
    Retourne le statut de l'API, les tâches en cours et l'espace disque.
    """
    # Espace disque disponible
    disk = shutil.disk_usage(DATA_INPUT)
    disk_free_gb = disk.free / (1024 ** 3)

    # Tâches en cours
    all_tasks = task_manager.get_all_tasks()
    pending_count = sum(1 for t in all_tasks.values() if t.status.value == "pending")
    processing_count = sum(1 for t in all_tasks.values() if t.status.value == "processing")

    return {
        "status": "healthy",
        "version": "0.2.0",
        "tasks": {
            "pending": pending_count,
            "processing": processing_count,
            "total": len(all_tasks)
        },
        "disk": {
            "free_gb": round(disk_free_gb, 2),
            "warning": disk_free_gb < 1.0
        }
    }

@app.post("/upload")
async def upload_mesh(file: UploadFile = File(...)):
    """
    Upload un fichier de maillage 3D avec conversion automatique vers GLB.

    GLB-First Architecture:
    - Tous les fichiers sont convertis en GLB (format master)
    - Le fichier original est sauvegardé temporairement puis supprimé
    - Seul le GLB reste dans data/input/

    Formats supportés: OBJ, STL, PLY, OFF, GLTF, GLB
    """
    import uuid
    start_total = time.time()
    logger.info(f"[UPLOAD] Started: {file.filename}")

    # S1: Sécuriser le nom de fichier (path traversal protection)
    try:
        safe_filename = sanitize_filename(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.debug(f"Filename sanitized: {file.filename} -> {safe_filename}")

    # S2: Vérifier la taille du fichier AVANT d'écrire
    file.file.seek(0, 2)  # Aller à la fin
    file_size = file.file.tell()
    file.file.seek(0)  # Revenir au début

    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,  # Payload Too Large
            detail=f"Fichier trop volumineux ({file_size / 1024 / 1024:.1f} MB). Maximum: {MAX_UPLOAD_SIZE // (1024*1024)} MB"
        )

    # Vérification de l'extension
    file_ext = Path(safe_filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats acceptés: {', '.join(SUPPORTED_FORMATS)}"
        )

    # GLB-First: Sauvegarder d'abord dans temp/
    start_save = time.time()
    temp_path = DATA_TEMP / f"upload_{uuid.uuid4().hex[:8]}{file_ext}"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la sauvegarde: {str(e)}"
        ) from e

    save_duration = (time.time() - start_save) * 1000
    original_size = temp_path.stat().st_size
    logger.debug(f"Temp save: {save_duration:.2f}ms ({original_size / 1024 / 1024:.2f} MB)")

    # GLB-First: Définir le chemin GLB avant le try pour le cleanup
    # S1: Utiliser le filename sécurisé
    glb_filename = f"{Path(safe_filename).stem}.glb"
    glb_path = DATA_INPUT / glb_filename

    try:
        # GLB-First: Convertir vers GLB
        start_convert = time.time()

        conversion_result = convert_any_to_glb(temp_path, glb_path)
        convert_duration = (time.time() - start_convert) * 1000

        if not conversion_result['success']:
            raise HTTPException(
                status_code=400,
                detail=f"Conversion GLB echouee: {conversion_result.get('error')}"
            )

        logger.debug(f"GLB conversion: {convert_duration:.2f}ms")
        logger.debug(f"Original format: {conversion_result['original_format']}, Has textures: {conversion_result['has_textures']}")

        # Charger le GLB pour analyse
        start_load = time.time()
        loaded = trimesh.load(str(glb_path))

        # Gérer les Scenes
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                raise HTTPException(status_code=400, detail="La scene ne contient aucune geometrie")
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        load_duration = (time.time() - start_load) * 1000
        logger.debug(f"GLB load: {load_duration:.2f}ms")

        # Validation
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise HTTPException(status_code=400, detail="Le fichier ne contient pas de vertices valides")
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            raise HTTPException(status_code=400, detail="Le fichier ne contient pas de faces")

        # Analyse du mesh
        start_analyze = time.time()

        is_watertight = bool(mesh.is_watertight) if hasattr(mesh, 'is_watertight') else False
        is_winding_consistent = bool(mesh.is_winding_consistent) if hasattr(mesh, 'is_winding_consistent') else None

        volume = None
        if is_watertight:
            try:
                volume = float(mesh.volume)
            except Exception:
                pass

        bounds = mesh.bounds
        bounding_box = {
            "min": [float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])],
            "max": [float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])],
            "size": [float(bounds[1][0] - bounds[0][0]),
                     float(bounds[1][1] - bounds[0][1]),
                     float(bounds[1][2] - bounds[0][2])],
            "center": [float(mesh.centroid[0]), float(mesh.centroid[1]), float(mesh.centroid[2])],
            "diagonal": float(mesh.scale)
        }

        mesh_info = {
            "filename": glb_filename,  # GLB-First: filename est toujours le GLB
            "original_filename": file.filename,  # Nom original pour référence
            "original_format": conversion_result['original_format'],
            "file_size": glb_path.stat().st_size,
            "format": ".glb",  # GLB-First: format est toujours .glb
            "vertices_count": int(len(mesh.vertices)),
            "triangles_count": int(len(mesh.faces)),
            "has_normals": hasattr(mesh, 'vertex_normals') and mesh.vertex_normals is not None,
            "has_colors": bool(hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None),
            "has_textures": conversion_result['has_textures'],
            "is_watertight": is_watertight,
            "is_orientable": is_winding_consistent,
            "is_manifold": None,
            "euler_number": int(mesh.euler_number) if hasattr(mesh, 'euler_number') else None,
            "volume": volume,
            "bounding_box": bounding_box
        }

        analyze_duration = (time.time() - start_analyze) * 1000
        logger.debug(f"Analysis: {analyze_duration:.2f}ms - {mesh_info['vertices_count']:,} vertices, {mesh_info['triangles_count']:,} triangles")

        total_duration = (time.time() - start_total) * 1000
        logger.info(f"[UPLOAD] Completed: {total_duration:.2f}ms - {safe_filename}")

        backend_timings = {
            "file_save_ms": round(save_duration, 2),
            "glb_conversion_ms": round(convert_duration, 2),
            "trimesh_load_ms": round(load_duration, 2),
            "analysis_ms": round(analyze_duration, 2),
            "total_ms": round(total_duration, 2)
        }

        return {
            "message": "Fichier uploade et converti en GLB avec succes",
            "mesh_info": mesh_info,
            "backend_timings": backend_timings,
            "conversion": {
                "success": True,
                "original_format": conversion_result['original_format'],
                "has_textures": conversion_result['has_textures'],
                "glb_filename": glb_filename
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        # Supprimer le GLB si créé
        if glb_path.exists():
            glb_path.unlink()
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors du chargement du maillage: {str(e)}"
        ) from e
    finally:
        # GLB-First: Toujours supprimer le fichier temporaire
        safe_delete(temp_path)

@app.get("/analyze/{filename}")
async def analyze_mesh(filename: str):
    """
    Analyse détaillée d'un fichier de maillage déjà uploadé
    Retourne les statistiques complètes (vertices, triangles, propriétés)
    """
    start_analyze = time.time()
    logger.info(f"[ANALYZE] Starting: {filename}")

    file_path = DATA_INPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    try:
        loaded = trimesh.load(str(file_path))

        # Si c'est une Scene, extraire et fusionner les géométries
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                raise HTTPException(status_code=400, detail="La scène ne contient aucune géométrie")
            elif len(meshes) == 1:
                mesh = meshes[0]
            else:
                mesh = trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise HTTPException(status_code=400, detail="Le fichier ne contient pas de vertices valides")

        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            raise HTTPException(status_code=400, detail="Le fichier ne contient pas de faces")

        # Extraction des propriétés du maillage
        is_watertight = bool(mesh.is_watertight) if hasattr(mesh, 'is_watertight') else False
        is_winding_consistent = bool(mesh.is_winding_consistent) if hasattr(mesh, 'is_winding_consistent') else None

        # Volume - calcul sécurisé uniquement si watertight
        volume = None
        if is_watertight:
            try:
                volume = float(mesh.volume)
            except Exception:
                pass

        mesh_stats = {
            "filename": filename,
            "vertices_count": int(len(mesh.vertices)),
            "triangles_count": int(len(mesh.faces)),
            "has_normals": hasattr(mesh, 'vertex_normals') and mesh.vertex_normals is not None,
            "has_colors": bool(hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None),
            "is_watertight": is_watertight,
            "is_orientable": is_winding_consistent,
            "is_manifold": None,
            "euler_number": int(mesh.euler_number) if hasattr(mesh, 'euler_number') else None,
            "volume": volume
        }

        analyze_duration = (time.time() - start_analyze) * 1000
        logger.info(f"[ANALYZE] Completed: {analyze_duration:.2f}ms - {mesh_stats['vertices_count']:,} vertices, {mesh_stats['triangles_count']:,} triangles")

        return {
            "success": True,
            "mesh_stats": mesh_stats,
            "analysis_time_ms": round(analyze_duration, 2)
        }

    except Exception as e:
        logger.error(f"[ANALYZE] Failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'analyse: {str(e)}"
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


# ============================================================================
# GLB-First: Endpoints de sauvegarde à la demande (M6)
# ============================================================================

def _find_mesh_in_directories(filename: str) -> Optional[Path]:
    """
    GLB-First: Recherche un mesh dans tous les dossiers de données.

    Ordre de recherche: input → output → retopo → segmented → generated_meshes
    """
    search_dirs = [
        DATA_INPUT,
        DATA_OUTPUT,
        DATA_RETOPO,
        DATA_SEGMENTED,
        DATA_GENERATED_MESHES
    ]
    for directory in search_dirs:
        file_path = directory / filename
        if file_path.exists():
            return file_path
    return None


@app.post("/save")
async def save_mesh(request: SaveMeshRequest):
    """
    GLB-First: Sauvegarde un mesh avec un nom personnalisé.

    Permet à l'utilisateur de sauvegarder le résultat d'une opération
    avant de procéder à une autre opération.
    """
    # Trouver le fichier source
    source_path = _find_mesh_in_directories(request.source_filename)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"Fichier non trouve: {request.source_filename}"
        )

    # Valider le nom de sauvegarde
    save_name = request.save_name.strip()
    if not save_name:
        raise HTTPException(status_code=400, detail="Nom de sauvegarde requis")

    # Nettoyer le nom (enlever caractères spéciaux)
    import re
    save_name = re.sub(r'[^\w\-]', '_', save_name)

    # Créer le dossier si nécessaire
    DATA_SAVED.mkdir(parents=True, exist_ok=True)

    # Copier le fichier
    save_path = DATA_SAVED / f"{save_name}.glb"
    shutil.copy2(source_path, save_path)

    logger.info(f"[SAVE] {source_path.name} -> {save_path.name}")

    return {
        "success": True,
        "saved_filename": save_path.name,
        "saved_size": save_path.stat().st_size,
        "source_filename": request.source_filename
    }


@app.get("/saved")
async def list_saved_meshes():
    """GLB-First: Liste tous les meshes sauvegardés par l'utilisateur."""
    if not DATA_SAVED.exists():
        return {"saved_meshes": [], "count": 0}

    saved = []
    for file_path in DATA_SAVED.glob("*.glb"):
        saved.append({
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "saved_at": file_path.stat().st_mtime
        })

    # Trier par date (plus récent en premier)
    saved.sort(key=lambda x: x["saved_at"], reverse=True)

    return {"saved_meshes": saved, "count": len(saved)}


@app.delete("/saved/{filename}")
async def delete_saved_mesh(filename: str):
    """GLB-First: Supprime un mesh sauvegardé."""
    file_path = DATA_SAVED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouve")

    file_path.unlink()
    logger.info(f"[DELETE] Saved mesh deleted: {filename}")

    return {"success": True, "deleted_filename": filename}


@app.get("/mesh/saved/{filename}")
async def get_saved_mesh(filename: str):
    """GLB-First: Stream un mesh sauvegardé pour visualisation."""
    file_path = DATA_SAVED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouve")

    return FileResponse(
        path=file_path,
        media_type="model/gltf-binary",
        filename=filename
    )


# Handler pour les tâches de simplification
def simplify_task_handler(task: Task):
    params = task.params
    input_path = Path(params["input_file"])
    output_path = Path(params["output_file"])
    reduction_ratio = params.get("reduction_ratio", 0.5)

    try:
        from .geometry_engine import to_pyvista, MeshSanitizer
        from .simplify import simplify_mesh_pyvista

        # 1. Chargement universel (GLB, OBJ, STL, PLY -> PolyData)
        pv_mesh = to_pyvista(input_path)
        original_faces = pv_mesh.n_cells
        original_vertices = pv_mesh.n_points

        # 2. Sanitization si mesh IA (sorties non-manifold de TripoSR)
        if params.get("is_generated", False):
            sanitizer = MeshSanitizer()
            cloud = sanitizer.sample_mesh_to_cloud(
                trimesh.Trimesh(vertices=pv_mesh.points, faces=pv_mesh.faces.reshape(-1, 4)[:, 1:])
            )
            surface = sanitizer.reconstruct_surface(cloud)
            pv_mesh = surface

        # 3. Decimation VTK
        simplified = simplify_mesh_pyvista(pv_mesh, reduction_ratio=reduction_ratio)

        # 4. Export GLB via Trimesh
        faces_back = simplified.faces.reshape(-1, 4)[:, 1:]
        final = trimesh.Trimesh(vertices=simplified.points, faces=faces_back)
        final.export(str(output_path), file_type='glb')

        simplified_faces = simplified.n_cells
        simplified_vertices = simplified.n_points

        # 5. Contrat API frontend
        return {
            'success': True,
            'output_filename': output_path.name,
            'output_file': str(output_path),
            'output_size': output_path.stat().st_size,
            'vertices_count': simplified_vertices,
            'faces_count': simplified_faces,
            'original': {
                'vertices': original_vertices,
                'triangles': original_faces
            },
            'simplified': {
                'vertices': simplified_vertices,
                'triangles': simplified_faces
            },
            'reduction': {
                'vertices_ratio': 1 - (simplified_vertices / original_vertices) if original_vertices > 0 else 0,
                'triangles_ratio': 1 - (simplified_faces / original_faces) if original_faces > 0 else 0
            }
        }

    except Exception as e:
        logger.error(f"[SIMPLIFY] Failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'output_filename': output_path.name,
            'faces_count': 0,
            'vertices_count': 0
        }


def adaptive_simplify_task_handler(task: Task):
    """Handler qui exécute la simplification adaptative d'un maillage"""
    params = task.params
    input_file = params["input_file"]
    output_file = params["output_file"]
    target_ratio = params.get("target_ratio", 0.5)
    flat_multiplier = params.get("flat_multiplier", 2.0)
    curvature_threshold = params.get("curvature_threshold")
    is_generated = params.get("is_generated", False)

    logger.info(f"[ADAPTIVE SIMPLIFY] Starting: {Path(input_file).name} (ratio={target_ratio}, flat_mult={flat_multiplier}x)")

    # Si le fichier est un GLB, le convertir en OBJ pour la simplification
    input_path = Path(input_file)
    if input_path.suffix.lower() == '.glb':
        logger.debug("Converting GLB to OBJ for simplification...")
        temp_obj_filename = f"{input_path.stem}_temp.obj"
        temp_obj_file = input_path.parent / temp_obj_filename

        from .converter import convert_mesh_format
        conversion_result = convert_mesh_format(
            input_path=input_path,
            output_path=temp_obj_file,
            output_format='obj'
        )

        if not conversion_result['success']:
            return {
                'success': False,
                'error': f"Conversion GLB→OBJ échouée: {conversion_result.get('error')}"
            }

        # Utiliser le fichier OBJ temporaire comme input
        input_file = str(temp_obj_file)
        logger.debug(f"Using temporary OBJ: {temp_obj_filename}")

    # Exécute la simplification adaptative
    # TEMPORAIRE: Utiliser Trimesh en mode standard (pas de vraie adaptation)
    # car Open3D donne de mauvais résultats sur les gros modèles
    result = simplify_mesh(
        input_path=Path(input_file),
        output_path=Path(output_file),
        reduction_ratio=target_ratio,
        preserve_boundary=True,
        use_trimesh=True  # Utiliser Trimesh
    )

    if result.get('success'):
        logger.info("[ADAPTIVE SIMPLIFY] Completed successfully")

        # Afficher les stats adaptatives
        adaptive_stats = result.get('adaptive_stats', {})
        logger.debug(f"Flat regions: {adaptive_stats.get('flat_percentage', 0):.1f}% of mesh")
        logger.debug(f"Flat triangles: {adaptive_stats.get('flat_triangles_original', 0)} -> {adaptive_stats.get('flat_triangles_final', 0)}")
        logger.debug(f"Curved triangles: {adaptive_stats.get('curved_triangles_original', 0)} -> {adaptive_stats.get('curved_triangles_final', 0)}")

        # Transformer le résultat pour le frontend
        output_path = Path(output_file)
        result_data = {
            'success': True,
            'output_filename': output_path.name,
            'output_file': str(output_path),
            'output_size': result.get('output_size', 0),
            'vertices_count': result.get('simplified_vertices', 0),
            'faces_count': result.get('simplified_triangles', 0),
            'original': {
                'vertices': result.get('original_vertices', 0),
                'triangles': result.get('original_triangles', 0)
            },
            'simplified': {
                'vertices': result.get('simplified_vertices', 0),
                'triangles': result.get('simplified_triangles', 0)
            },
            'reduction': {
                'vertices_ratio': result.get('vertices_ratio', 0),
                'triangles_ratio': result.get('triangles_ratio', 0)
            },
            'adaptive_stats': adaptive_stats
        }

        # Nettoyer le fichier OBJ temporaire si on a converti depuis GLB
        if '_temp.obj' in str(input_file) and Path(input_file).exists():
            logger.debug("Removing temporary OBJ file")
            Path(input_file).unlink()

        return result_data

    # En cas d'échec, nettoyer quand même le fichier temporaire
    if '_temp.obj' in str(input_file) and Path(input_file).exists():
        logger.debug("Removing temporary OBJ file")
        Path(input_file).unlink()

    return result

@app.post("/simplify")
async def simplify_mesh_async(request: SimplifyRequest):
    """
    GLB-First: Lance une tâche de simplification de maillage en arrière-plan.

    Avec l'architecture GLB-First, tous les fichiers sont en GLB.
    Le task handler utilise simplify_mesh_glb pour traiter directement les GLB.
    """
    # Déterminer le dossier source selon is_generated
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
    input_path = source_dir / request.filename

    # Vérification que le fichier existe
    if not input_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier non trouve: {request.filename}")

    # GLB-First: Le fichier est déjà en GLB, sortie aussi en GLB
    output_filename = f"{input_path.stem}_simplified.glb"
    output_path = DATA_OUTPUT / output_filename

    # Création de la tâche
    task_id = task_manager.create_task(
        task_type="simplify",
        params={
            "input_file": str(input_path),
            "output_file": str(output_path),
            "target_triangles": request.target_triangles,
            "reduction_ratio": request.reduction_ratio,
            "preserve_boundary": request.preserve_boundary,
            "is_generated": request.is_generated
        }
    )

    return {
        "task_id": task_id,
        "message": "Tâche de simplification créée",
        "output_filename": output_filename
    }

@app.post("/simplify-adaptive")
async def simplify_mesh_adaptive_async(request: AdaptiveSimplifyRequest):
    """
    GLB-First: Lance une tâche de simplification adaptative en arrière-plan.

    Détecte les zones plates et les simplifie plus agressivement.
    Note: Cette fonctionnalité n'a pas encore de version GLB-native.
    """
    # Déterminer le dossier source selon is_generated
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
    input_path = source_dir / request.filename

    # Vérification que le fichier existe
    if not input_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier non trouve: {request.filename}")

    # GLB-First: Sortie en GLB
    output_filename = f"{input_path.stem}_adaptive.glb"
    output_path = DATA_OUTPUT / output_filename

    # Création de la tâche
    task_id = task_manager.create_task(
        task_type="simplify_adaptive",
        params={
            "input_file": str(input_path),
            "output_file": str(output_path),
            "target_ratio": request.target_ratio,
            "flat_multiplier": request.flat_multiplier,
            "curvature_threshold": request.curvature_threshold,
            "is_generated": request.is_generated
        }
    )

    return {
        "task_id": task_id,
        "message": "Tâche de simplification adaptative créée",
        "output_filename": output_filename
    }

def sanitize_task_handler(task: Task):
    params = task.params
    input_path = Path(params["input_file"])
    output_path = Path(params["output_file"])

    from .geometry_engine import MeshSanitizer
    sanitizer = MeshSanitizer()
    return sanitizer.sanitize_pipeline(input_path, output_path)

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
    """
    GLB-First: Sert un fichier de maillage depuis data/input pour la visualisation.

    Avec l'architecture GLB-First, tous les fichiers uploadés sont convertis en GLB
    et stockés directement dans data/input.
    """
    file_path = DATA_INPUT / filename
    file_ext = Path(filename).suffix.lower()

    # GLB-First: Le fichier devrait exister directement dans data/input
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier non trouve: {filename}")

    # Déterminer le media_type
    media_type_mapping = {
        ".obj": "model/obj",
        ".stl": "model/stl",
        ".ply": "application/ply",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
        ".off": "application/octet-stream"
    }
    media_type = media_type_mapping.get(file_ext, "application/octet-stream")

    # Streamer le fichier avec des chunks optimisés (1MB par chunk)
    CHUNK_SIZE = 1024 * 1024  # 1 MB chunks pour de meilleures performances

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            while chunk := file_like.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
            "Content-Length": str(file_path.stat().st_size)  # Important pour la barre de progression
        }
    )

@app.get("/mesh/output/{filename}")
async def get_output_mesh(filename: str):
    """
    Sert un fichier de maillage depuis data/output pour la visualisation
    Utilisé pour visualiser les meshes simplifiés
    Convertit automatiquement en GLB pour de meilleures performances
    """
    file_path = DATA_OUTPUT / filename

    # GLB-First: Le fichier devrait exister directement en GLB
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier non trouve: {filename}")

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
    CHUNK_SIZE = 1024 * 1024

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            while chunk := file_like.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
            "Content-Length": str(file_path.stat().st_size)
        }
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

@app.get("/export/{filename}")
async def export_mesh(filename: str, format: str = "obj", is_generated: bool = False, is_simplified: bool = False, is_retopologized: bool = False, is_segmented: bool = False):
    """
    GLB-First: Exporte un fichier de maillage dans le format demandé.

    Avec l'architecture GLB-First, tous les fichiers source sont en GLB.
    L'export convertit depuis GLB vers le format demandé.

    Args:
        filename: Nom du fichier source (GLB)
        format: Format de sortie ('obj', 'stl', 'ply', 'glb')
        is_generated: Si True, cherche dans data/generated_meshes
        is_simplified: Si True, cherche dans data/output (meshes simplifiés)
        is_retopologized: Si True, cherche dans data/retopo (meshes retopologisés)
        is_segmented: Si True, cherche dans data/segmented (meshes segmentés)

    Returns:
        Le fichier converti au format demandé
    """
    # Déterminer le dossier source
    if is_segmented:
        source_dir = DATA_SEGMENTED
    elif is_retopologized:
        source_dir = DATA_RETOPO
    elif is_simplified:
        source_dir = DATA_OUTPUT
    elif is_generated:
        source_dir = DATA_GENERATED_MESHES
    else:
        source_dir = DATA_INPUT

    source_path = source_dir / filename

    # GLB-First: Le fichier source est toujours en GLB
    # Vérifier que le fichier existe
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier non trouve: {filename}")

    # Si le format demandé est le même que le fichier source, le renvoyer directement
    source_ext = source_path.suffix.lower().lstrip('.')
    target_format = format.lower()

    if source_ext == target_format:
        return FileResponse(
            path=str(source_path),
            filename=filename,
            media_type="application/octet-stream"
        )

    # Sinon, convertir vers le format demandé
    output_filename = f"{source_path.stem}.{target_format}"
    output_path = DATA_OUTPUT / output_filename

    logger.info(f"[EXPORT] Converting {filename} to {target_format.upper()}")

    # Convertir le fichier
    result = convert_mesh_format(source_path, output_path, target_format)

    if not result['success']:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la conversion: {result.get('error', 'Unknown error')}"
        )

    logger.info(f"[EXPORT] Success: {output_filename}")

    # Retourner le fichier converti
    return FileResponse(
        path=str(output_path),
        filename=output_filename,
        media_type="application/octet-stream"
    )

# ===== ENDPOINTS GÉNÉRATION DE MAILLAGES À PARTIR D'IMAGES =====

@app.post("/upload-images")
async def upload_images(files: list[UploadFile] = File(...)):
    """
    Upload multiple d'images pour génération de maillage 3D
    Crée une session et sauvegarde les images

    Returns:
        session_id: Identifiant de session pour la génération
        images: Liste des images uploadées avec preview
    """
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="Aucune image fournie")

    # Créer un ID de session unique
    session_id = f"session_{int(time.time() * 1000)}"
    session_path = DATA_INPUT_IMAGES / session_id
    session_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"[UPLOAD-IMAGES] Session: {session_id} ({len(files)} images)")

    uploaded_images = []

    for idx, file in enumerate(files):
        # Vérification de l'extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Format non supporté: {file.filename}. Formats acceptés: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )

        # Sauvegarde du fichier
        file_path = session_path / f"image_{idx:03d}{file_ext}"
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la sauvegarde de {file.filename}: {str(e)}"
            ) from e

        uploaded_images.append({
            "filename": file.filename,
            "saved_as": file_path.name,
            "size": file_path.stat().st_size,
            "format": file_ext
        })

        logger.debug(f"Saved: {file.filename} -> {file_path.name}")

    logger.info(f"[UPLOAD-IMAGES] Completed: {len(uploaded_images)} images")

    return {
        "message": "Images uploadées avec succès",
        "session_id": session_id,
        "images": uploaded_images,
        "images_count": len(uploaded_images)
    }

@app.get("/sessions/{session_id}/images")
async def list_session_images(session_id: str):
    """
    Liste les images d'une session
    """
    session_path = DATA_INPUT_IMAGES / session_id

    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session non trouvée")

    images = []
    for file_path in session_path.iterdir():
        if file_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS:
            images.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "format": file_path.suffix.lower()
            })

    return {
        "session_id": session_id,
        "images": images,
        "count": len(images)
    }

# Handler pour les tâches de génération de maillages
def generate_mesh_task_handler(task: Task):
    """Handler qui exécute la génération de maillage avec Stability AI ou TripoSR
    GLB-First: Sauvegarde toujours en GLB
    Providers: 'stability' (API cloud) ou 'triposr' (local, gratuit)
    """
    params = task.params
    session_id = params["session_id"]
    resolution = params.get("resolution", "medium")
    remesh_option = params.get("remesh_option", "quad")
    provider = params.get("provider", "stability")

    # [DEV/TEST] Si c'est une tâche fake, elle est déjà complétée, ne rien faire
    if params.get("fake", False):
        logger.debug("[GENERATE-MESH] Fake task detected, skipping API call")
        return task.result  # Le résultat a déjà été défini dans l'endpoint

    session_path = DATA_INPUT_IMAGES / session_id

    if not session_path.exists():
        return {
            'success': False,
            'error': 'Session non trouvée'
        }

    logger.info(f"[GENERATE-MESH] Starting with {provider} (session={session_id}, resolution={resolution})")

    # Récupérer toutes les images de la session
    image_paths = sorted([
        p for p in session_path.iterdir()
        if p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    ])

    if len(image_paths) == 0:
        return {
            'success': False,
            'error': 'Aucune image trouvée dans la session'
        }

    # Les deux providers utilisent uniquement la première image
    first_image = image_paths[0]
    logger.debug(f"Images in session: {len(image_paths)}")
    if len(image_paths) > 1:
        logger.info(f"Using first image: {first_image.name} (single-view only)")

    # GLB-First: Format de sortie toujours GLB
    output_filename = f"{session_id}_generated.glb"
    output_path = DATA_GENERATED_MESHES / output_filename

    # Router vers le bon provider
    if provider == "triposr":
        # TripoSR: génération locale, gratuite
        from .triposr_client import generate_mesh_from_image_triposr
        result = generate_mesh_from_image_triposr(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution
        )
    else:
        # Stability AI: API cloud (défaut)
        api_key = os.getenv('STABILITY_API_KEY')
        if not api_key:
            return {
                'success': False,
                'error': 'STABILITY_API_KEY non configurée dans .env'
            }

        result = generate_mesh_from_image_sf3d(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution,
            remesh_option=remesh_option,
            api_key=api_key
        )

    if result.get('success'):
        logger.info(f"[GENERATE-MESH] Success: {output_filename}")
        result['output_filename'] = output_filename
        result['session_id'] = session_id
        result['images_used'] = 1
        result['provider'] = provider

    return result

def generate_image_task_handler(task: Task):
    """Handler qui genere une image a partir d'un prompt textuel via Mamouth.ai"""
    params = task.params
    prompt = params["prompt"]
    resolution = params.get("resolution", "medium")

    session_id = f"session_{int(time.time() * 1000)}"
    session_path = DATA_INPUT_IMAGES / session_id
    session_path.mkdir(parents=True, exist_ok=True)

    output_path = session_path / "prompt_generated.png"
    api_key = os.getenv('MAMOUTH_API_KEY')

    logger.info(f"[GENERATE-IMAGE] Starting (session={session_id}, resolution={resolution})")

    result = generate_image_from_prompt(
        prompt=prompt,
        output_path=output_path,
        resolution=resolution,
        api_key=api_key
    )

    if result.get('success'):
        logger.info(f"[GENERATE-IMAGE] Success: {session_id}/prompt_generated.png")
        result['session_id'] = session_id
        result['image_url'] = f"/session-images/{session_id}/prompt_generated.png"
    else:
        logger.error(f"[GENERATE-IMAGE] Failed: {result.get('error')}")

    return result


def generate_texture_task_handler(task: Task):
    """Handler qui genere une texture seamless a partir d'un prompt via Mamouth.ai"""
    params = task.params
    prompt = params["prompt"]
    resolution = params.get("resolution", "medium")

    texture_id = f"tex_{int(time.time() * 1000)}"
    texture_dir = DATA_GENERATED_TEXTURES / texture_id
    texture_dir.mkdir(parents=True, exist_ok=True)

    output_path = texture_dir / "color.png"
    api_key = os.getenv('MAMOUTH_API_KEY')

    logger.info(f"[GENERATE-TEXTURE] Starting (texture_id={texture_id}, resolution={resolution})")

    result = generate_texture_from_prompt(
        prompt=prompt,
        output_path=output_path,
        resolution=resolution,
        api_key=api_key
    )

    if result.get('success'):
        logger.info(f"[GENERATE-TEXTURE] Success: {texture_id}/color.png")
        result['texture_id'] = texture_id
        result['texture_url'] = f"/texture/generated/{texture_id}/color.png"
    else:
        logger.error(f"[GENERATE-TEXTURE] Failed: {result.get('error')}")

    return result


def retopologize_task_handler(task: Task):
    """
    Handler qui exécute la retopologie avec Instant Meshes.

    GLB-First: Utilise retopologize_mesh_glb pour les fichiers GLB.
    """
    params = task.params
    filename = params["filename"]
    target_face_count = params.get("target_face_count", 10000)
    deterministic = params.get("deterministic", True)
    preserve_boundaries = params.get("preserve_boundaries", True)
    is_generated = params.get("is_generated", False)
    is_simplified = params.get("is_simplified", False)

    # Déterminer le dossier source selon le flag
    if is_simplified:
        input_file = DATA_OUTPUT / filename
    elif is_generated:
        input_file = DATA_GENERATED_MESHES / filename
    else:
        input_file = DATA_INPUT / filename

    if not input_file.exists():
        return {
            'success': False,
            'error': f'Fichier source non trouve: {filename}'
        }

    logger.info(f"[RETOPOLOGIZE] Starting: {filename} (target={target_face_count} faces)")

    # GLB-First: Utiliser retopologize_mesh_glb directement pour les GLB
    if input_file.suffix.lower() == '.glb':
        logger.debug("[GLB-First] Direct GLB retopology pipeline")

        # Sortie en GLB
        output_filename = f"{input_file.stem}_retopo.glb"
        output_file = DATA_RETOPO / output_filename

        # Supprimer l'ancien résultat s'il existe
        if output_file.exists():
            output_file.unlink()

        result = retopologize_mesh_glb(
            input_glb=input_file,
            output_glb=output_file,
            target_face_count=target_face_count,
            deterministic=deterministic,
            preserve_boundaries=preserve_boundaries,
            temp_dir=DATA_TEMP
        )

        if result.get('success'):
            logger.info("[RETOPOLOGIZE] Completed successfully")
            if result.get('textures_lost'):
                logger.warning("Textures were lost during retopology")

            return {
                'success': True,
                'output_filename': output_filename,
                'output_file': str(output_file),
                'vertices_count': result.get('retopo_vertices', 0),
                'faces_count': result.get('retopo_faces', 0),
                'output_size': output_file.stat().st_size if output_file.exists() else 0,
                'original_vertices': result.get('original_vertices', 0),
                'original_faces': result.get('original_faces', 0),
                'retopo_vertices': result.get('retopo_vertices', 0),
                'retopo_faces': result.get('retopo_faces', 0),
                'had_textures': result.get('had_textures', False),
                'textures_lost': result.get('textures_lost', False)
            }
        return result

    # GLB-First: Ce code ne devrait pas être atteint car tous les uploads sont GLB
    # Mais par sécurité, on produit quand même un GLB en sortie
    logger.warning(f"Non-GLB input detected ({input_file.suffix}), converting to GLB pipeline")

    output_filename = f"{Path(filename).stem}_retopo.glb"
    output_file = DATA_RETOPO / output_filename
    temp_ply = DATA_TEMP / f"{Path(filename).stem}_retopo_temp.ply"

    if output_file.exists():
        output_file.unlink()

    # Retopologie vers PLY temporaire
    result = retopologize_mesh(
        input_path=input_file,
        output_path=temp_ply,
        target_face_count=target_face_count,
        deterministic=deterministic,
        preserve_boundaries=preserve_boundaries
    )

    if result.get('success'):
        # Convertir le PLY résultant en GLB
        try:
            import trimesh
            mesh = trimesh.load(str(temp_ply), process=False)
            mesh.export(str(output_file), file_type='glb')
            logger.info("[RETOPOLOGIZE] Completed (converted to GLB)")
            result['output_filename'] = output_filename
            result['output_file'] = str(output_file)
            result['vertices_count'] = result.get('retopo_vertices', 0)
            result['faces_count'] = result.get('retopo_faces', 0)
            result['output_size'] = output_file.stat().st_size if output_file.exists() else 0
        except Exception as e:
            logger.error(f"GLB conversion failed: {e}")
            result['success'] = False
            result['error'] = f"GLB conversion failed: {e}"
        finally:
            safe_delete(temp_ply)
    else:
        logger.error(f"Retopology failed: {result.get('error', 'Unknown error')}")

    return result

def segment_task_handler(task: Task):
    """
    Handler pour la tâche de segmentation.

    GLB-First: Utilise segment_mesh_glb pour les fichiers GLB.
    """
    params = task.params
    filename = params.get("filename")
    method = params.get("method", "connectivity")
    is_generated = params.get("is_generated", False)
    is_simplified = params.get("is_simplified", False)
    is_retopo = params.get("is_retopo", False)

    # Déterminer le fichier source selon les flags
    if is_generated:
        input_path = DATA_GENERATED_MESHES / filename
        source_label = "generated"
    elif is_simplified:
        input_path = DATA_OUTPUT / filename
        source_label = "output"
    elif is_retopo:
        input_path = DATA_RETOPO / filename
        source_label = "retopo"
    else:
        input_path = DATA_INPUT / filename
        source_label = "input"

    logger.info(f"[SEGMENT] Starting: {filename} ({source_label}) method={method}")

    # Construire les kwargs
    kwargs = {}
    if params.get("angle_threshold") is not None:
        kwargs["angle_threshold"] = params["angle_threshold"]
    if params.get("num_clusters") is not None:
        kwargs["num_clusters"] = params["num_clusters"]
    if params.get("num_planes") is not None:
        kwargs["num_planes"] = params["num_planes"]

    try:
        # GLB-First: Utiliser segment_mesh_glb pour les GLB
        if input_path.suffix.lower() == '.glb':
            logger.debug("[GLB-First] Direct GLB segmentation pipeline")

            # Sortie en GLB
            output_filename = f"{input_path.stem}_segmented.glb"
            output_path = DATA_SEGMENTED / output_filename

            result = segment_mesh_glb(
                input_glb=input_path,
                output_glb=output_path,
                method=method,
                temp_dir=DATA_TEMP,
                **kwargs
            )

            if result.get('success'):
                logger.info(f"[SEGMENT] Completed: {result.get('num_segments', 0)} segments")
                if result.get('textures_lost'):
                    logger.warning("Textures were lost during segmentation")

                return {
                    "success": True,
                    "output_filename": output_filename,
                    "output_size": output_path.stat().st_size if output_path.exists() else 0,
                    "num_segments": result.get("num_segments", 0),
                    "method": method,
                    "vertices_count": result.get("vertices_count", 0),
                    "faces_count": result.get("faces_count", 0),
                    "had_textures": result.get("had_textures", False),
                    "textures_lost": result.get("textures_lost", False),
                    **{k: v for k, v in result.items() if k not in [
                        'success', 'output_filename', 'output_format',
                        'original_vertices', 'original_faces', 'vertices_count',
                        'faces_count', 'had_textures', 'textures_lost'
                    ]}
                }
            return result

        # GLB-First: Ce code ne devrait pas être atteint car tous les uploads sont GLB
        # Mais par sécurité, on produit quand même un GLB en sortie
        logger.warning(f"Non-GLB input detected ({input_path.suffix}), converting to GLB pipeline")

        base_name = Path(filename).stem
        temp_output = DATA_TEMP / f"{base_name}_segmented_temp{input_path.suffix}"
        output_filename = f"{base_name}_segmented.glb"
        output_path = DATA_SEGMENTED / output_filename

        result = segment_mesh(
            input_path=input_path,
            output_path=temp_output,
            method=method,
            **kwargs
        )

        if result.get("success"):
            # Convertir en GLB
            try:
                import trimesh
                mesh = trimesh.load(str(temp_output), process=False)
                mesh.export(str(output_path), file_type='glb')
                logger.info(f"[SEGMENT] Completed (converted to GLB): {result.get('num_segments', 0)} segments")
                return {
                    "success": True,
                    "output_filename": output_filename,
                    "output_size": output_path.stat().st_size if output_path.exists() else 0,
                    "num_segments": result.get("num_segments", 0),
                    "method": method,
                    **result
                }
            except Exception as e:
                logger.error(f"GLB conversion failed: {e}")
                return {"success": False, "error": f"GLB conversion failed: {e}"}
            finally:
                safe_delete(temp_output)
                # Aussi supprimer le .mtl si présent
                mtl_path = temp_output.with_suffix('.mtl')
                safe_delete(mtl_path)

        logger.error(f"Segmentation failed: {result.get('error')}")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Segmentation error: {str(e)}"
        }

@app.post("/generate-mesh-fake")
async def generate_mesh_fake(request: GenerateMeshRequest):
    """
    [DEV/TEST] Génère un mesh fake en copiant un GLB existant
    Utile pour tester sans consommer de crédits API
    """
    session_path = DATA_INPUT_IMAGES / request.session_id

    # Vérification que la session existe
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session non trouvée")

    # Chercher un fichier GLB template dans data/input
    template_files = list(DATA_INPUT.glob("*.glb"))
    if not template_files:
        raise HTTPException(
            status_code=404,
            detail="Aucun fichier GLB template trouvé dans data/input. Uploadez un fichier GLB d'abord."
        )

    # Utiliser le premier fichier GLB trouvé comme template
    template_glb = template_files[0]
    logger.info(f"[FAKE-GENERATE] Using template: {template_glb.name}")

    # Générer le nom de fichier de sortie
    output_filename = f"{request.session_id}_generated.glb"
    output_path = DATA_GENERATED_MESHES / output_filename

    # Copier le fichier template
    import shutil
    shutil.copy2(template_glb, output_path)
    logger.debug(f"[FAKE-GENERATE] Copied to: {output_filename}")

    # Charger le mesh pour obtenir les stats
    import trimesh
    mesh = trimesh.load(str(output_path))
    if hasattr(mesh, 'geometry'):
        # Scene avec plusieurs maillages
        meshes = list(mesh.geometry.values())
        if len(meshes) > 0:
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)

    vertices_count = len(mesh.vertices)
    faces_count = len(mesh.faces)

    # GLB-First: Créer une tâche fake qui se termine immédiatement
    task_id = task_manager.create_task(
        task_type="generate_mesh",
        params={
            "session_id": request.session_id,
            "resolution": request.resolution,
            "remesh_option": request.remesh_option,
            "fake": True
        }
    )

    # Marquer la tâche comme complétée immédiatement
    task = task_manager.get_task(task_id)
    if task:
        task.status = "completed"
        task.result = {
            'success': True,
            'output_filename': output_filename,
            'vertices_count': vertices_count,
            'faces_count': faces_count,
            'resolution': request.resolution,
            'generation_time': 0.1,  # Fake time
            'method': 'fake_copy',
            'session_id': request.session_id,
            'images_used': 1
        }
        logger.info(f"[FAKE-GENERATE] Completed: {vertices_count} vertices, {faces_count} faces")

    return {
        "task_id": task_id,
        "message": "[FAKE] Mesh généré (copié depuis template)",
        "output_filename": output_filename
    }

@app.post("/generate-mesh")
async def generate_mesh_async(request: GenerateMeshRequest):
    """
    Lance une tâche de génération de maillage à partir d'images en arrière-plan
    Retourne un task_id pour suivre la progression
    """
    session_path = DATA_INPUT_IMAGES / request.session_id

    # Vérification que la session existe
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session non trouvée")

    # Vérifier qu'il y a des images dans la session
    image_count = len([
        p for p in session_path.iterdir()
        if p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    ])

    if image_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Aucune image trouvée dans la session"
        )

    # Validation de la résolution
    if request.resolution not in ['low', 'medium', 'high']:
        raise HTTPException(
            status_code=400,
            detail="Résolution invalide. Valeurs acceptées: 'low', 'medium', 'high'"
        )

    # GLB-First: Le format de sortie est toujours GLB (natif de l'API Stability)

    # Création de la tâche
    task_id = task_manager.create_task(
        task_type="generate_mesh",
        params={
            "session_id": request.session_id,
            "resolution": request.resolution,
            "remesh_option": request.remesh_option
        }
    )

    return {
        "task_id": task_id,
        "message": "Tâche de génération créée",
        "session_id": request.session_id,
        "images_count": image_count
    }

@app.post("/generate-image-from-prompt")
async def generate_image_from_prompt_endpoint(request: GenerateImageRequest):
    """
    Lance une tache de generation d'image a partir d'un prompt textuel via Mamouth.ai
    Retourne un task_id pour suivre la progression
    """
    if not os.getenv('MAMOUTH_API_KEY'):
        raise HTTPException(status_code=503, detail="MAMOUTH_API_KEY non configuree dans .env")

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Le prompt ne peut pas etre vide")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt trop long (max 1000 caracteres)")

    if request.resolution not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=400, detail="Resolution invalide. Valeurs acceptees: 'low', 'medium', 'high'")

    task_id = task_manager.create_task(
        task_type="generate_image",
        params={
            "prompt": request.prompt.strip(),
            "resolution": request.resolution
        }
    )

    logger.info(f"[API] Image generation task created: {task_id}")

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Generation d'image en cours"
    }


@app.post("/generate-texture")
async def generate_texture_endpoint(request: GenerateTextureRequest):
    """Lance une tache de generation de texture seamless via Mamouth.ai"""
    if not os.getenv('MAMOUTH_API_KEY'):
        raise HTTPException(status_code=503, detail="MAMOUTH_API_KEY non configuree dans .env")

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Le prompt ne peut pas etre vide")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt trop long (max 1000 caracteres)")

    if request.resolution not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=400, detail="Resolution invalide")

    task_id = task_manager.create_task(
        task_type="generate_texture",
        params={
            "prompt": request.prompt.strip(),
            "resolution": request.resolution
        }
    )

    logger.info(f"[API] Texture generation task created: {task_id}")

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Generation de texture en cours"
    }

@app.post("/sanitize")
async def sanitize_mesh_endpoint(filename: str):
    input_path = DATA_INPUT / filename # Ou DATA_GENERATED_MESHES
    output_filename = f"{Path(filename).stem}_clean.glb"
    output_path = DATA_OUTPUT / output_filename

    task_id = task_manager.create_task(
        "sanitize", 
        {"input_file": str(input_path), "output_file": str(output_path)}
    )
    return {"task_id": task_id, "output_filename": output_filename}

def generate_material_task_handler(task: Task):
    """Handler qui genere un materiau complet: texture + parametres physiques en parallele"""
    from concurrent.futures import ThreadPoolExecutor
    params = task.params
    prompt = params["prompt"]

    texture_id = f"tex_{int(time.time() * 1000)}"
    texture_dir = DATA_GENERATED_TEXTURES / texture_id
    texture_dir.mkdir(parents=True, exist_ok=True)

    output_path = texture_dir / "color.png"
    api_key = os.getenv('MAMOUTH_API_KEY')

    logger.info(f"[GENERATE-MATERIAL] Starting (texture_id={texture_id})")

    start_time = time.time()

    # Lancer texture + physics en parallele
    with ThreadPoolExecutor(max_workers=2) as executor:
        texture_future = executor.submit(
            generate_texture_from_prompt,
            prompt=prompt, output_path=output_path, resolution="medium", api_key=api_key
        )
        physics_future = executor.submit(
            infer_physics_from_prompt,
            prompt=prompt, api_key=api_key
        )

        texture_result = texture_future.result()
        physics_result = physics_future.result()

    generation_time = (time.time() - start_time) * 1000

    if not texture_result.get('success'):
        logger.error(f"[GENERATE-MATERIAL] Texture failed: {texture_result.get('error')}")
        return texture_result

    logger.info(f"[GENERATE-MATERIAL] Success in {generation_time:.0f}ms")

    return {
        'success': True,
        'texture_id': texture_id,
        'texture_url': f"/texture/generated/{texture_id}/color.png",
        'physics': physics_result,
        'prompt': prompt,
        'image_width': texture_result.get('image_width'),
        'image_height': texture_result.get('image_height'),
        'generation_time_ms': round(generation_time, 2)
    }

@app.post("/generate-material")
async def generate_material_endpoint(request: GenerateMaterialRequest):
    """Lance une tache de generation de materiau IA (texture + physique) via Mamouth.ai"""
    if not os.getenv('MAMOUTH_API_KEY'):
        raise HTTPException(status_code=503, detail="MAMOUTH_API_KEY non configuree dans .env")

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Le prompt ne peut pas etre vide")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt trop long (max 1000 caracteres)")

    task_id = task_manager.create_task(
        task_type="generate_material",
        params={"prompt": request.prompt.strip()}
    )

    logger.info(f"[API] Material generation task created: {task_id}")

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Generation de materiau en cours"
    }


@app.get("/texture/generated/{texture_id}/{filename}")
async def get_generated_texture(texture_id: str, filename: str):
    """Sert un fichier texture genere"""
    texture_path = DATA_GENERATED_TEXTURES / sanitize_filename(texture_id) / sanitize_filename(filename)

    if not texture_path.exists():
        raise HTTPException(status_code=404, detail="Texture non trouvee")

    return FileResponse(str(texture_path), media_type="image/png")


@app.get("/session-images/{session_id}/{filename}")
async def get_session_image(session_id: str, filename: str):
    """Sert une image generee depuis une session (pour preview dans le frontend)"""
    image_path = DATA_INPUT_IMAGES / sanitize_filename(session_id) / sanitize_filename(filename)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image non trouvee")

    suffix = image_path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Format d'image non supporte")

    return FileResponse(str(image_path), media_type=f"image/{suffix[1:]}")


@app.get("/mesh/generated/{filename}")
async def get_generated_mesh(filename: str):
    """
    Sert un fichier de maillage généré depuis data/generated_meshes pour la visualisation
    """
    file_path = DATA_GENERATED_MESHES / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    file_ext = file_path.suffix.lower()

    # Déterminer le media_type
    media_type_mapping = {
        ".obj": "model/obj",
        ".stl": "model/stl",
        ".ply": "application/ply",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
    }
    media_type = media_type_mapping.get(file_ext, "application/octet-stream")

    # Streamer le fichier
    CHUNK_SIZE = 1024 * 1024  # 1 MB chunks

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            while chunk := file_like.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
            "Content-Length": str(file_path.stat().st_size)
        }
    )

@app.post("/retopologize")
async def retopologize(request: RetopologyRequest):
    """
    Lance une tâche de retopologie avec Instant Meshes
    """
    # Déterminer le dossier source selon le flag
    if request.is_simplified:
        source_dir = DATA_OUTPUT
    elif request.is_generated:
        source_dir = DATA_GENERATED_MESHES
    else:
        source_dir = DATA_INPUT

    input_file = source_dir / request.filename

    if not input_file.exists():
        raise HTTPException(status_code=404, detail=f"Fichier non trouvé: {request.filename}")

    # Valider que target_face_count est dans le range acceptable
    # Range: [original * 2 : original * 5]
    # Note: original_face_count est fourni par le frontend (déjà calculé lors de l'upload)
    original_face_count = request.original_face_count
    min_faces = original_face_count * 2
    max_faces = original_face_count * 5

    if request.target_face_count < min_faces:
        raise HTTPException(
            status_code=400,
            detail=f"target_face_count trop bas: minimum {min_faces} faces (mesh original: {original_face_count} faces)"
        )

    if request.target_face_count > max_faces:
        raise HTTPException(
            status_code=400,
            detail=f"target_face_count trop élevé: maximum {max_faces} faces (mesh original: {original_face_count} faces)"
        )

    # Créer une tâche asynchrone
    task_id = task_manager.create_task(
        task_type="retopologize",
        params={
            "filename": request.filename,
            "target_face_count": request.target_face_count,
            "deterministic": request.deterministic,
            "preserve_boundaries": request.preserve_boundaries,
            "is_generated": request.is_generated,
            "is_simplified": request.is_simplified
        }
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Tâche de retopologie créée"
    }

@app.get("/mesh/retopo/{filename}")
async def get_retopo_mesh(filename: str):
    """
    GLB-First: Sert un fichier de maillage retopologisé depuis data/retopo.

    Avec l'architecture GLB-First, tous les fichiers retopologisés sont directement en GLB.
    """
    file_path = DATA_RETOPO / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    file_ext = file_path.suffix.lower()

    # Déterminer le media_type
    media_type_mapping = {
        ".obj": "model/obj",
        ".stl": "model/stl",
        ".ply": "application/ply",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
    }
    media_type = media_type_mapping.get(file_ext, "application/octet-stream")

    # Streamer le fichier
    CHUNK_SIZE = 1024 * 1024  # 1 MB chunks

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            while chunk := file_like.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
            "Content-Length": str(file_path.stat().st_size)
        }
    )

@app.post("/segment")
async def segment(request: SegmentRequest):
    """
    Crée une tâche de segmentation asynchrone

    La segmentation colore le mesh selon différentes méthodes géométriques.
    Formats supportés: OBJ, STL, PLY, OFF
    """
    # Déterminer le dossier source selon les flags
    if request.is_generated:
        input_dir = DATA_GENERATED_MESHES
        source_label = "generated"
    elif request.is_simplified:
        input_dir = DATA_OUTPUT
        source_label = "output"
    elif request.is_retopo:
        input_dir = DATA_RETOPO
        source_label = "retopo"
    else:
        input_dir = DATA_INPUT
        source_label = "input"

    input_path = input_dir / request.filename

    # Vérifier que le fichier existe
    if not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Fichier {request.filename} introuvable dans {source_label}"
        )

    # Créer la tâche asynchrone
    task_id = task_manager.create_task(
        task_type="segment",
        params={
            "filename": request.filename,
            "method": request.method,
            "angle_threshold": request.angle_threshold,
            "num_clusters": request.num_clusters,
            "num_planes": request.num_planes,
            "is_generated": request.is_generated,
            "is_simplified": request.is_simplified,
            "is_retopo": request.is_retopo
        }
    )

    return {
        "task_id": task_id,
        "message": f"Segmentation lancée avec méthode '{request.method}'"
    }

@app.get("/mesh/segmented/{filename}")
async def get_segmented_mesh(filename: str):
    """Télécharge un mesh segmenté depuis data/segmented/"""
    file_path = DATA_SEGMENTED / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier segmenté introuvable")

    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename
    )

# NOTE: Les @app.on_event("startup") et @app.on_event("shutdown")
# ont été migrés vers le système lifespan (voir ligne ~33)
# Cette migration suit les recommandations FastAPI 0.93+

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
