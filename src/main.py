"""
FastAPI backend for AnyMesh. Provides endpoints for uploading and processing 3D meshes.
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

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import trimesh

from .task_manager import task_manager, Task
from .simplify import simplify_mesh_glb
from .converter import convert_mesh_format, convert_any_to_glb
from .mamouth_client import generate_image_from_prompt, generate_texture_from_prompt, infer_physics_from_prompt
from .retopology import retopologize_mesh, retopologize_mesh_glb
from .segmentation import segment_mesh, segment_mesh_glb
from .temp_utils import cleanup_temp_directory, safe_delete

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    logger.info("=== MeshSimplifier Backend Starting ===")

    api_key = os.getenv('STABILITY_API_KEY')
    if not api_key:
        logger.warning("STABILITY_API_KEY not set - mesh generation will fail")
        logger.warning("Create .env file and add: STABILITY_API_KEY=sk-your-key-here")
    elif not api_key.startswith('sk-'):
        logger.warning("STABILITY_API_KEY may be invalid (should start with 'sk-')")
    else:
        logger.info(f"Stability API key loaded: {api_key[:10]}...")

    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        logger.info(f"Gemini API key loaded: {gemini_key[:10]}...")
    else:
        logger.warning("GEMINI_API_KEY not set - prompt generation disabled")

    task_manager.register_handler("simplify", simplify_task_handler)
    task_manager.register_handler("generate_mesh", generate_mesh_task_handler)
    task_manager.register_handler("retopologize", retopologize_task_handler)
    task_manager.register_handler("segment", segment_task_handler)
    task_manager.register_handler("generate_image", generate_image_task_handler)
    task_manager.register_handler("generate_texture", generate_texture_task_handler)
    task_manager.register_handler("generate_material", generate_material_task_handler)
    task_manager.register_handler("compare", compare_task_handler)
    task_manager.register_handler("unwrap_uv", unwrap_uv_task_handler)
    task_manager.register_handler("bake_texture", bake_texture_task_handler)
    task_manager.register_handler("generate_lod", generate_lod_task_handler)
    task_manager.start()

    logger.info("Cleaning up temp files...")
    cleanup_temp_directory(DATA_TEMP, max_age_hours=1)

    logger.info("Backend started successfully")

    yield

    # === SHUTDOWN ===
    logger.info("=== MeshSimplifier Backend Stopping ===")
    task_manager.stop()
    logger.info("Backend stopped")


app = FastAPI(
    title="MeshSimplifier API",
    description="API for 3D mesh simplification and processing",
    version="0.2.0",
    lifespan=lifespan
)

# CORS: read origins from ALLOWED_ORIGINS env var. Use "*" for dev, explicit origins for prod.
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if allowed_origins_env == "*" else [o.strip() for o in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,  # Must be False when allow_origins contains "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directories
DATA_INPUT = Path("data/input")
DATA_OUTPUT = Path("data/output")
DATA_INPUT_IMAGES = Path("data/input_images")
DATA_GENERATED_MESHES = Path("data/generated_meshes")
DATA_RETOPO = Path("data/retopo")
DATA_SEGMENTED = Path("data/segmented")
DATA_GENERATED_TEXTURES = Path("data/generated_textures")
DATA_TEMP = Path("data/temp")   # Temp files for format conversions
DATA_SAVED = Path("data/saved")  # User-saved meshes
DATA_COMPARED = Path("data/compared")
DATA_UNWRAPPED = Path("data/unwrapped")
DATA_BAKED = Path("data/baked")
DATA_INPUT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
DATA_INPUT_IMAGES.mkdir(parents=True, exist_ok=True)
DATA_GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
DATA_RETOPO.mkdir(parents=True, exist_ok=True)
DATA_SEGMENTED.mkdir(parents=True, exist_ok=True)
DATA_GENERATED_TEXTURES.mkdir(parents=True, exist_ok=True)
DATA_TEMP.mkdir(parents=True, exist_ok=True)
DATA_COMPARED.mkdir(parents=True, exist_ok=True)
DATA_UNWRAPPED.mkdir(parents=True, exist_ok=True)
DATA_BAKED.mkdir(parents=True, exist_ok=True)

# Supported file formats
SUPPORTED_FORMATS = {".obj", ".stl", ".ply", ".off", ".gltf", ".glb"}
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png"}

# File size limit: 95 MB
MAX_UPLOAD_SIZE = 95 * 1024 * 1024  # 95 MB en bytes


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.

    Strips any directory component, removes ".." sequences,
    and limits characters to alphanumeric, dot, dash, and underscore.
    """
    if not filename:
        raise ValueError("Empty filename")

    filename = os.path.basename(filename)
    filename = filename.replace("..", "")

    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()

    clean_stem = re.sub(r'[^\w\-]', '_', stem)
    clean_filename = f"{clean_stem}{ext}" if ext else clean_stem

    if not clean_filename or clean_filename in ('.', '..'):
        raise ValueError("Invalid filename after sanitization")

    return clean_filename

class SimplifyRequest(BaseModel):
    """Simplification parameters."""
    filename: str
    target_triangles: Optional[int] = None
    reduction_ratio: Optional[float] = None
    is_generated: bool = False  # If True, looks in data/generated_meshes
    preserve_texture: bool = False  # If True, transfers UVs via KDTree after simplification

class GenerateMeshRequest(BaseModel):
    """Mesh generation parameters. Output format is always GLB."""
    session_id: str
    resolution: str = "medium"  # 'low', 'medium', 'high'
    remesh_option: str = "quad"  # 'none', 'triangle', 'quad' (Stability AI only)
    provider: str = "unique3d"  # 'unique3d', 'triposr', 'stability', 'trellis', 'trellis2'

class GenerateImageRequest(BaseModel):
    """Image generation parameters for Mamouth.ai text-to-image."""
    prompt: str
    resolution: str = "medium"  # 'low', 'medium', 'high'

class GenerateTextureRequest(BaseModel):
    """Texture generation parameters for Mamouth.ai."""
    prompt: str
    resolution: str = "medium"  # 'low', 'medium', 'high'

class GenerateMaterialRequest(BaseModel):
    """AI material generation parameters (texture + physics)."""
    prompt: str

class RetopologyRequest(BaseModel):
    """Retopology parameters for Instant Meshes."""
    filename: str
    target_face_count: int = 10000
    original_face_count: int  # Original mesh face count, sent by frontend
    deterministic: bool = True
    preserve_boundaries: bool = True
    is_generated: bool = False
    is_simplified: bool = False
    bake_textures: bool = False  # If True, bake high-poly texture onto retopo result

class SegmentRequest(BaseModel):
    """Mesh segmentation parameters."""
    filename: str
    method: str = "connectivity"  # 'connectivity', 'sharp_edges', 'curvature', 'planes'
    angle_threshold: Optional[float] = None  # For sharp_edges (degrees)
    num_clusters: Optional[int] = None  # For curvature
    num_planes: Optional[int] = None  # For planes
    is_generated: bool = False
    is_simplified: bool = False
    is_retopo: bool = False


class CompareRequest(BaseModel):
    """Mesh comparison parameters."""
    filename_ref: str
    filename_comp: str
    is_generated_ref: bool = False
    is_simplified_ref: bool = False
    is_retopo_ref: bool = False
    is_generated_comp: bool = False
    is_simplified_comp: bool = False
    is_retopo_comp: bool = False


class UnwrapUVRequest(BaseModel):
    """UV unwrap parameters."""
    filename: str
    is_generated: bool = False
    is_simplified: bool = False
    is_retopologized: bool = False


class BakeTextureRequest(BaseModel):
    """Texture baking parameters."""
    filename: str
    texture_id: str
    is_generated: bool = False
    is_simplified: bool = False
    is_retopologized: bool = False
    is_uv_unwrapped: bool = False


class SaveMeshRequest(BaseModel):
    """Mesh save parameters."""
    source_filename: str  # Source filename (searched across all data folders)
    save_name: str  # Save name (without extension)


class GenerateLodRequest(BaseModel):
    """Auto-LOD generation parameters."""
    filename: str
    is_generated: bool = False


@app.get("/")
async def root():
    """Root endpoint. Confirms the API is running."""
    return {
        "message": "MeshSimplifier API",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Detailed health check. Returns API status, active tasks, and disk space."""
    disk = shutil.disk_usage(DATA_INPUT)
    disk_free_gb = disk.free / (1024 ** 3)

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

@app.get("/config")
async def get_config():
    """Feature flags based on environment variables."""
    return {
        "trellis2_enabled": bool(os.getenv("RUNPOD_TRELLIS2_ENDPOINT_ID"))
    }

@app.post("/upload")
async def upload_mesh(file: UploadFile = File(...)):
    """
    Upload a 3D mesh file and convert it to GLB.

    GLB-First: all uploads are converted to GLB and stored in data/input/.
    Supported formats: OBJ, STL, PLY, OFF, GLTF, GLB.
    """
    import uuid
    start_total = time.time()
    logger.info(f"[UPLOAD] Started: {file.filename}")

    try:
        safe_filename = sanitize_filename(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.debug(f"Filename sanitized: {file.filename} -> {safe_filename}")

    file.file.seek(0, 2)  # Seek to end to get size
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,  # Payload Too Large
            detail=f"File too large ({file_size / 1024 / 1024:.1f} MB). Maximum: {MAX_UPLOAD_SIZE // (1024*1024)} MB"
        )

    file_ext = Path(safe_filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Accepted: {', '.join(SUPPORTED_FORMATS)}"
        )

    start_save = time.time()
    temp_path = DATA_TEMP / f"upload_{uuid.uuid4().hex[:8]}{file_ext}"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        ) from e

    save_duration = (time.time() - start_save) * 1000
    original_size = temp_path.stat().st_size
    logger.debug(f"Temp save: {save_duration:.2f}ms ({original_size / 1024 / 1024:.2f} MB)")

    glb_filename = f"{Path(safe_filename).stem}.glb"
    glb_path = DATA_INPUT / glb_filename

    try:
        start_convert = time.time()
        conversion_result = convert_any_to_glb(temp_path, glb_path)
        convert_duration = (time.time() - start_convert) * 1000

        if not conversion_result['success']:
            raise HTTPException(
                status_code=400,
                detail=f"GLB conversion failed: {conversion_result.get('error')}"
            )

        logger.debug(f"GLB conversion: {convert_duration:.2f}ms")
        logger.debug(f"Original format: {conversion_result['original_format']}, Has textures: {conversion_result['has_textures']}")

        start_load = time.time()
        loaded = trimesh.load(str(glb_path))

        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                raise HTTPException(status_code=400, detail="Scene contains no geometry")
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        load_duration = (time.time() - start_load) * 1000
        logger.debug(f"GLB load: {load_duration:.2f}ms")

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise HTTPException(status_code=400, detail="File contains no valid vertices")
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            raise HTTPException(status_code=400, detail="File contains no faces")

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
            "filename": glb_filename,
            "original_filename": file.filename,
            "original_format": conversion_result['original_format'],
            "file_size": glb_path.stat().st_size,
            "format": ".glb",
            "vertices_count": int(len(mesh.vertices)),
            "triangles_count": int(len(mesh.faces)),
            "has_normals": hasattr(mesh, 'vertex_normals') and mesh.vertex_normals is not None,
            "has_colors": bool(hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None),
            "has_textures": conversion_result['has_textures'],
            "is_watertight": is_watertight,
            "is_orientable": is_winding_consistent,
            "is_manifold": None,
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
            "message": "File uploaded and converted to GLB successfully",
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
        if glb_path.exists():
            glb_path.unlink()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load mesh: {str(e)}"
        ) from e
    finally:
        safe_delete(temp_path)

@app.get("/analyze/{filename}")
async def analyze_mesh(filename: str):
    """Detailed analysis of an uploaded mesh. Returns full stats."""
    start_analyze = time.time()
    logger.info(f"[ANALYZE] Starting: {filename}")

    file_path = DATA_INPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        loaded = trimesh.load(str(file_path))

        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                raise HTTPException(status_code=400, detail="Scene contains no geometry")
            elif len(meshes) == 1:
                mesh = meshes[0]
            else:
                mesh = trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise HTTPException(status_code=400, detail="File contains no valid vertices")

        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            raise HTTPException(status_code=400, detail="File contains no faces")

        is_watertight = bool(mesh.is_watertight) if hasattr(mesh, 'is_watertight') else False
        is_winding_consistent = bool(mesh.is_winding_consistent) if hasattr(mesh, 'is_winding_consistent') else None

        # Volume is only valid for watertight meshes
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
            detail=f"Analysis failed: {str(e)}"
        ) from e

@app.get("/meshes")
async def list_meshes():
    """List all available mesh files."""
    meshes = []
    for file_path in DATA_INPUT.iterdir():
        if file_path.suffix.lower() in SUPPORTED_FORMATS:
            meshes.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "format": file_path.suffix.lower()
            })
    return {"meshes": meshes, "count": len(meshes)}


def _find_mesh_in_directories(filename: str) -> Optional[Path]:
    """Search for a mesh across all data directories. Order: input, output, retopo, segmented, generated_meshes."""
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
    """Save a mesh with a custom name."""
    source_path = _find_mesh_in_directories(request.source_filename)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {request.source_filename}"
        )

    save_name = request.save_name.strip()
    if not save_name:
        raise HTTPException(status_code=400, detail="Save name is required")

    import re
    save_name = re.sub(r'[^\w\-]', '_', save_name)

    DATA_SAVED.mkdir(parents=True, exist_ok=True)

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
    """List all user-saved meshes."""
    if not DATA_SAVED.exists():
        return {"saved_meshes": [], "count": 0}

    saved = []
    for file_path in DATA_SAVED.glob("*.glb"):
        saved.append({
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "saved_at": file_path.stat().st_mtime
        })

    saved.sort(key=lambda x: x["saved_at"], reverse=True)  # Most recent first

    return {"saved_meshes": saved, "count": len(saved)}


@app.delete("/saved/{filename}")
async def delete_saved_mesh(filename: str):
    """Delete a saved mesh."""
    file_path = DATA_SAVED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    logger.info(f"[DELETE] Saved mesh deleted: {filename}")

    return {"success": True, "deleted_filename": filename}


@app.get("/mesh/saved/{filename}")
async def get_saved_mesh(filename: str):
    """Stream a saved mesh for visualization."""
    file_path = DATA_SAVED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type="model/gltf-binary",
        filename=filename
    )


def simplify_task_handler(task: Task):
    params = task.params
    input_path = Path(params["input_file"])
    output_path = Path(params["output_file"])

    result = simplify_mesh_glb(
        input_path=input_path,
        output_path=output_path,
        target_triangles=params.get("target_triangles"),
        reduction_ratio=params.get("reduction_ratio", 0.5),
        preserve_texture=params.get("preserve_texture", False),
        temp_dir=DATA_TEMP
    )

    if result.get('success'):
        result['output_filename'] = output_path.name
        result['vertices_count'] = result['simplified_vertices']
        result['faces_count'] = result['simplified_triangles']
        result['original'] = {
            'vertices': result['original_vertices'],
            'triangles': result['original_triangles']
        }
        result['simplified'] = {
            'vertices': result['simplified_vertices'],
            'triangles': result['simplified_triangles']
        }
        result['reduction'] = {
            'vertices_ratio': result['vertices_ratio'],
            'triangles_ratio': result['triangles_ratio']
        }
    else:
        logger.error(f"[SIMPLIFY] Failed: {result.get('error')}")
        result['output_filename'] = output_path.name
        result['faces_count'] = 0
        result['vertices_count'] = 0

    return result


@app.post("/simplify")
async def simplify_mesh_async(request: SimplifyRequest):
    """Start an async mesh simplification task. Returns task_id."""
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
    input_path = source_dir / request.filename

    if not input_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    output_filename = f"{input_path.stem}_simplified.glb"
    output_path = DATA_OUTPUT / output_filename

    task_id = task_manager.create_task(
        task_type="simplify",
        params={
            "input_file": str(input_path),
            "output_file": str(output_path),
            "target_triangles": request.target_triangles,
            "reduction_ratio": request.reduction_ratio,
            "is_generated": request.is_generated,
            "preserve_texture": request.preserve_texture
        }
    )

    return {
        "task_id": task_id,
        "message": "Simplification task created",
        "output_filename": output_filename
    }


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Return the status of a task."""
    task = task_manager.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()

@app.get("/tasks")
async def list_tasks():
    """List all tasks."""
    tasks = task_manager.get_all_tasks()
    return {
        "tasks": [task.to_dict() for task in tasks.values()],
        "count": len(tasks),
        "queue_size": task_manager.get_queue_size()
    }

@app.get("/mesh/input/{filename}")
async def get_input_mesh(filename: str):
    """Stream a mesh from data/input for visualization."""
    file_path = DATA_INPUT / filename
    file_ext = Path(filename).suffix.lower()

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    media_type_mapping = {
        ".obj": "model/obj",
        ".stl": "model/stl",
        ".ply": "application/ply",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
        ".off": "application/octet-stream"
    }
    media_type = media_type_mapping.get(file_ext, "application/octet-stream")

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

@app.get("/mesh/output/{filename}")
async def get_output_mesh(filename: str):
    """Stream a simplified mesh from data/output for visualization."""
    file_path = DATA_OUTPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

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
    """Download a simplified mesh from data/output."""
    file_path = DATA_OUTPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/export/{subpath:path}")
async def export_mesh(subpath: str, format: str = "obj"):
    """
    Export a mesh file in the requested format.
    subpath is relative to data/ (e.g. 'baked/bunny.glb', 'input/bunny.glb').
    GLB-First: source files are always GLB. Converts to the target format on the fly.
    """
    if ".." in subpath:
        raise HTTPException(status_code=400, detail="Invalid path")

    source_path = Path("data") / subpath
    filename = source_path.name

    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {subpath}")

    source_ext = source_path.suffix.lower().lstrip('.')
    target_format = format.lower()

    if source_ext == target_format:
        return FileResponse(
            path=str(source_path),
            filename=filename,
            media_type="application/octet-stream"
        )

    output_filename = f"{source_path.stem}.{target_format}"
    output_path = DATA_OUTPUT / output_filename

    logger.info(f"[EXPORT] Converting {subpath} to {target_format.upper()}")

    result = convert_mesh_format(source_path, output_path, target_format)

    if not result['success']:
        raise HTTPException(
            status_code=500,
            detail=f"Conversion failed: {result.get('error', 'Unknown error')}"
        )

    logger.info(f"[EXPORT] Success: {output_filename}")

    return FileResponse(
        path=str(output_path),
        filename=output_filename,
        media_type="application/octet-stream"
    )

@app.post("/upload-glb-result")
async def upload_glb_result(file: UploadFile = File(...), job_id: str = Form(...)):
    """Receive a GLB from RunPod worker, save it, return absolute download URL."""
    filename = f"trellis2_{job_id}.glb"
    path = DATA_GENERATED_MESHES / filename
    path.write_bytes(await file.read())
    logger.info(f"[TRELLIS2] GLB received from worker: {filename} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
    base_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    return {"url": f"{base_url}/mesh/generated/{filename}"}


@app.post("/upload-images")
async def upload_images(files: list[UploadFile] = File(...)):
    """
    Upload one or more images for 3D mesh generation.

    Creates a session and saves the images. Returns session_id and image list.
    """
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No images provided")

    session_id = f"session_{int(time.time() * 1000)}"
    session_path = DATA_INPUT_IMAGES / session_id
    session_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"[UPLOAD-IMAGES] Session: {session_id} ({len(files)} images)")

    uploaded_images = []

    for idx, file in enumerate(files):
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {file.filename}. Accepted: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )

        file_path = session_path / f"image_{idx:03d}{file_ext}"
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save {file.filename}: {str(e)}"
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
        "message": "Images uploaded successfully",
        "session_id": session_id,
        "images": uploaded_images,
        "images_count": len(uploaded_images)
    }

@app.get("/sessions/{session_id}/images")
async def list_session_images(session_id: str):
    """List images in a session."""
    session_path = DATA_INPUT_IMAGES / session_id

    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

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

def generate_mesh_task_handler(task: Task):
    """3D generation handler. Routes to the correct provider: unique3d, triposr, or stability."""
    params = task.params
    session_id = params["session_id"]
    resolution = params.get("resolution", "medium")
    provider = params.get("provider", "unique3d")

    if params.get("fake", False):  # Dev/test: fake task, already completed
        logger.debug("[GENERATE-MESH] Fake task detected, skipping API call")
        return task.result

    session_path = DATA_INPUT_IMAGES / session_id

    if not session_path.exists():
        return {
            'success': False,
            'error': 'Session not found'
        }

    logger.info(f"[GENERATE-MESH] Starting {provider} (session={session_id}, resolution={resolution})")

    image_paths = sorted([
        p for p in session_path.iterdir()
        if p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    ])

    if len(image_paths) == 0:
        return {
            'success': False,
            'error': 'No images found in session'
        }

    # All providers use only the first image (single-view)
    first_image = image_paths[0]
    if len(image_paths) > 1:
        logger.info(f"Using first image: {first_image.name} (single-view only)")

    output_filename = f"{session_id}_generated.glb"
    output_path = DATA_GENERATED_MESHES / output_filename

    if provider == "triposr":
        from .triposr_client import generate_mesh_from_image_triposr
        result = generate_mesh_from_image_triposr(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution
        )
    elif provider == "stability":
        from .stability_client import generate_mesh_from_image_sf3d
        api_key = os.getenv('STABILITY_API_KEY')
        if not api_key:
            return {
                'success': False,
                'error': 'STABILITY_API_KEY not configured in .env'
            }
        result = generate_mesh_from_image_sf3d(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution,
            remesh_option=params.get("remesh_option", "quad"),
            api_key=api_key
        )
    elif provider == "trellis":
        from .trellis_client import generate_mesh_from_image_trellis
        extra = image_paths[1:] if len(image_paths) > 1 else None
        result = generate_mesh_from_image_trellis(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution,
            extra_images=extra,
        )
    elif provider == "trellis2":
        from .trellis2_client import generate_mesh_from_image_trellis2
        result = generate_mesh_from_image_trellis2(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution,
        )
    else:
        # unique3d (default)
        from .unique3d_client import generate_mesh_from_image_unique3d
        result = generate_mesh_from_image_unique3d(
            image_path=first_image,
            output_path=output_path,
            resolution=resolution
        )

    if result.get('success'):
        # Mesh cleanup for TripoSR (TRELLIS handles its own cleanup in trellis_client.py)
        if provider == "triposr":
            try:
                import trimesh
                mesh = trimesh.load(str(output_path), force='mesh')
                before = len(mesh.faces)

                # Floater removal: keep largest connected component
                components = mesh.split()
                if len(components) > 1:
                    mesh = max(components, key=lambda m: len(m.faces))
                    logger.info(f"[GENERATE-MESH] Removed {len(components)-1} floater(s)")

                mesh.remove_degenerate_faces()
                mesh.remove_duplicate_faces()
                mesh.fix_normals()
                after = len(mesh.faces)
                mesh.export(str(output_path))
                if before != after:
                    logger.info(f"[GENERATE-MESH] Cleanup: {before} -> {after} faces")
                    result['faces_count'] = after
                    result['vertices_count'] = len(mesh.vertices)
            except Exception as e:
                logger.warning(f"[GENERATE-MESH] Cleanup skipped: {e}")

        logger.info(f"[GENERATE-MESH] Success: {output_filename}")
        result['output_filename'] = output_filename
        result['session_id'] = session_id
        result['images_used'] = 1
        result['provider'] = provider

    return result

def generate_image_task_handler(task: Task):
    """Generate an image from a text prompt via Mamouth.ai."""
    params = task.params
    prompt = params["prompt"]
    resolution = params.get("resolution", "medium")

    session_id = f"session_{int(time.time() * 1000)}"
    session_path = DATA_INPUT_IMAGES / session_id
    session_path.mkdir(parents=True, exist_ok=True)

    output_path = session_path / "prompt_generated.png"
    api_key = os.getenv('GEMINI_API_KEY')

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
    """Generate a seamless texture from a prompt via Mamouth.ai."""
    params = task.params
    prompt = params["prompt"]
    resolution = params.get("resolution", "medium")

    texture_id = f"tex_{int(time.time() * 1000)}"
    texture_dir = DATA_GENERATED_TEXTURES / texture_id
    texture_dir.mkdir(parents=True, exist_ok=True)

    output_path = texture_dir / "color.png"
    api_key = os.getenv('GEMINI_API_KEY')

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
    """Execute retopology using Instant Meshes."""
    params = task.params
    filename = params["filename"]
    target_face_count = params.get("target_face_count", 10000)
    deterministic = params.get("deterministic", True)
    preserve_boundaries = params.get("preserve_boundaries", True)
    is_generated = params.get("is_generated", False)
    is_simplified = params.get("is_simplified", False)

    if is_simplified:
        input_file = DATA_OUTPUT / filename
    elif is_generated:
        input_file = DATA_GENERATED_MESHES / filename
    else:
        input_file = DATA_INPUT / filename

    if not input_file.exists():
        return {
            'success': False,
            'error': f'Source file not found: {filename}'
        }

    bake_textures = params.get("bake_textures", False)

    logger.info(f"[RETOPOLOGIZE] Starting: {filename} (target={target_face_count} faces, bake={bake_textures})")

    if input_file.suffix.lower() == '.glb':
        output_filename = f"{input_file.stem}_retopo.glb"
        output_file = DATA_RETOPO / output_filename

        if output_file.exists():
            output_file.unlink()

        result = retopologize_mesh_glb(
            input_glb=input_file,
            output_glb=output_file,
            target_face_count=target_face_count,
            deterministic=deterministic,
            preserve_boundaries=preserve_boundaries,
            temp_dir=DATA_TEMP,
            bake_textures=bake_textures
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
                'has_textures': result.get('has_textures', False),
                'textures_lost': result.get('textures_lost', False),
                'texture_baked': result.get('texture_baked', False),
                'baked_texture_filename': result.get('baked_texture_filename', None)
            }
        return result

    # Non-GLB fallback (all uploads should be GLB, but kept for safety)
    logger.warning(f"Non-GLB input detected ({input_file.suffix}), converting to GLB pipeline")

    output_filename = f"{Path(filename).stem}_retopo.glb"
    output_file = DATA_RETOPO / output_filename
    temp_ply = DATA_TEMP / f"{Path(filename).stem}_retopo_temp.ply"

    if output_file.exists():
        output_file.unlink()

    result = retopologize_mesh(
        input_path=input_file,
        output_path=temp_ply,
        target_face_count=target_face_count,
        deterministic=deterministic,
        preserve_boundaries=preserve_boundaries
    )

    if result.get('success'):
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
    """Execute mesh segmentation."""
    params = task.params
    filename = params.get("filename")
    method = params.get("method", "connectivity")
    is_generated = params.get("is_generated", False)
    is_simplified = params.get("is_simplified", False)
    is_retopo = params.get("is_retopo", False)

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

    kwargs = {}
    if params.get("angle_threshold") is not None:
        kwargs["angle_threshold"] = params["angle_threshold"]
    if params.get("num_clusters") is not None:
        kwargs["num_clusters"] = params["num_clusters"]
    if params.get("num_planes") is not None:
        kwargs["num_planes"] = params["num_planes"]

    try:
        if input_path.suffix.lower() == '.glb':
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
                    "has_textures": result.get("has_textures", False),
                    "textures_lost": result.get("textures_lost", False),
                    **{k: v for k, v in result.items() if k not in [
                        'success', 'output_filename', 'output_format',
                        'original_vertices', 'original_faces', 'vertices_count',
                        'faces_count', 'has_textures', 'textures_lost'
                    ]}
                }
            return result

        # Non-GLB fallback (all uploads should be GLB, but kept for safety)
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
                mtl_path = temp_output.with_suffix('.mtl')  # Also clean up .mtl if present
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

def compare_task_handler(task: Task):
    """Compare two meshes and generate a distance heatmap."""
    from .compare import compare_meshes

    params = task.params

    def _resolve_path(filename, is_generated, is_simplified, is_retopo):
        if is_generated:
            return DATA_GENERATED_MESHES / filename
        elif is_simplified:
            return DATA_OUTPUT / filename
        elif is_retopo:
            return DATA_RETOPO / filename
        return DATA_INPUT / filename

    ref_path = _resolve_path(
        params["filename_ref"],
        params.get("is_generated_ref", False),
        params.get("is_simplified_ref", False),
        params.get("is_retopo_ref", False)
    )
    comp_path = _resolve_path(
        params["filename_comp"],
        params.get("is_generated_comp", False),
        params.get("is_simplified_comp", False),
        params.get("is_retopo_comp", False)
    )

    base_name = Path(params["filename_comp"]).stem
    output_filename = f"{base_name}_compared.glb"
    output_path = DATA_COMPARED / output_filename

    logger.info(f"[COMPARE] Ref={ref_path.name} vs Comp={comp_path.name}")

    result = compare_meshes(ref_path, comp_path, output_path)
    if result.get("success"):
        result["output_filename"] = output_filename
    return result


def unwrap_uv_task_handler(task: Task):
    """Execute LSCM UV unwrapping."""
    from .uv_unwrap import unwrap_uv

    params = task.params
    mesh_path = _resolve_mesh_path(
        params["filename"],
        params.get("is_generated", False),
        params.get("is_simplified", False),
        params.get("is_retopologized", False)
    )

    if not mesh_path.exists():
        return {'success': False, 'error': f'File not found: {params["filename"]}'}

    output_filename = f"{mesh_path.stem}_unwrapped.glb"
    output_path = DATA_UNWRAPPED / output_filename

    logger.info(f"[UV_UNWRAP] Starting: {mesh_path.name}")

    result = unwrap_uv(mesh_path, output_path)
    if result.get('success'):
        result['output_filename'] = output_filename
    return result


def bake_texture_task_handler(task: Task):
    """Embed an Imagen-generated texture PNG into a mesh GLB via UV coordinates."""
    import copy
    from PIL import Image as PILImage
    import numpy as np

    params = task.params
    filename = params["filename"]
    texture_id = params["texture_id"]
    is_uv_unwrapped = params.get("is_uv_unwrapped", False)

    # Resolve mesh path
    if is_uv_unwrapped:
        mesh_path = DATA_UNWRAPPED / filename
    else:
        mesh_path = _resolve_mesh_path(
            filename,
            params.get("is_generated", False),
            params.get("is_simplified", False),
            params.get("is_retopologized", False)
        )

    if not mesh_path.exists():
        return {'success': False, 'error': f'Mesh not found: {filename}'}

    texture_path = DATA_GENERATED_TEXTURES / texture_id / "color.png"
    if not texture_path.exists():
        return {'success': False, 'error': f'Texture not found: {texture_id}'}

    logger.info(f"[BAKE_TEXTURE] Starting: {mesh_path.name} + {texture_id}")

    try:
        scene = trimesh.load(str(mesh_path), force='scene')
        if isinstance(scene, trimesh.Trimesh):
            scene = trimesh.scene.scene.Scene(geometry={'mesh': scene})

        img = PILImage.open(str(texture_path)).convert('RGB')

        baked_geometries = {}
        for name, geom in scene.geometry.items():
            mesh = copy.deepcopy(geom)

            # Ensure UVs exist
            if not (hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None):
                try:
                    unwrapped = mesh.unwrap()
                    if unwrapped is not None and hasattr(unwrapped.visual, 'uv') and unwrapped.visual.uv is not None:
                        mesh = unwrapped
                    else:
                        logger.warning(f"[BAKE_TEXTURE] Cannot unwrap {name}, skipping")
                        baked_geometries[name] = mesh
                        continue
                except Exception as e:
                    logger.warning(f"[BAKE_TEXTURE] Unwrap failed for {name}: {e}")
                    baked_geometries[name] = mesh
                    continue

            material = trimesh.visual.material.PBRMaterial(
                baseColorTexture=img,
                metallicFactor=0.0,
                roughnessFactor=0.8
            )
            mesh.visual = trimesh.visual.TextureVisuals(uv=mesh.visual.uv, material=material)
            baked_geometries[name] = mesh

        baked_scene = trimesh.scene.scene.Scene(geometry=baked_geometries)

        stem = Path(filename).stem
        # Remove _unwrapped suffix if present to keep name clean
        if stem.endswith('_unwrapped'):
            stem = stem[:-len('_unwrapped')]
        output_filename = f"{stem}_baked.glb"
        output_path = DATA_BAKED / output_filename
        baked_scene.export(str(output_path), file_type='glb')

        logger.info(f"[BAKE_TEXTURE] Done: {output_filename}")
        return {
            'success': True,
            'output_filename': output_filename,
            'vertices_count': sum(len(g.vertices) for g in baked_geometries.values()),
            'faces_count': sum(len(g.faces) for g in baked_geometries.values()),
        }

    except Exception as e:
        logger.error(f"[BAKE_TEXTURE] Failed: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def _resolve_mesh_path(filename, is_generated, is_simplified, is_retopologized):
    """Resolve mesh file path based on flags."""
    if is_generated:
        return DATA_GENERATED_MESHES / filename
    elif is_simplified:
        return DATA_OUTPUT / filename
    elif is_retopologized:
        return DATA_RETOPO / filename
    return DATA_INPUT / filename


@app.post("/generate-mesh-fake")
async def generate_mesh_fake(request: GenerateMeshRequest):
    """[DEV/TEST] Generate a fake mesh by copying an existing GLB. No API credits consumed."""
    session_path = DATA_INPUT_IMAGES / request.session_id

    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    template_files = list(DATA_INPUT.glob("*.glb"))
    if not template_files:
        raise HTTPException(
            status_code=404,
            detail="No GLB template found in data/input. Upload a GLB file first."
        )

    template_glb = template_files[0]
    logger.info(f"[FAKE-GENERATE] Using template: {template_glb.name}")

    output_filename = f"{request.session_id}_generated.glb"
    output_path = DATA_GENERATED_MESHES / output_filename

    import shutil
    shutil.copy2(template_glb, output_path)
    logger.debug(f"[FAKE-GENERATE] Copied to: {output_filename}")

    import trimesh
    mesh = trimesh.load(str(output_path))
    if hasattr(mesh, 'geometry'):
        meshes = list(mesh.geometry.values())
        if len(meshes) > 0:
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)

    vertices_count = len(mesh.vertices)
    faces_count = len(mesh.faces)

    task_id = task_manager.create_task(
        task_type="generate_mesh",
        params={
            "session_id": request.session_id,
            "resolution": request.resolution,
            "remesh_option": request.remesh_option,
            "fake": True
        }
    )

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
    """Start an async 3D mesh generation task. Returns task_id."""
    session_path = DATA_INPUT_IMAGES / request.session_id

    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    image_count = len([
        p for p in session_path.iterdir()
        if p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    ])

    if image_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No images found in session"
        )

    if request.resolution not in ['low', 'medium', 'high']:
        raise HTTPException(
            status_code=400,
            detail="Invalid resolution. Use 'low', 'medium', or 'high'"
        )

    # Création de la tâche
    task_id = task_manager.create_task(
        task_type="generate_mesh",
        params={
            "session_id": request.session_id,
            "resolution": request.resolution,
            "provider": request.provider,
            "remesh_option": request.remesh_option
        }
    )

    return {
        "task_id": task_id,
        "message": "Generation task created",
        "session_id": request.session_id,
        "images_count": image_count,
        "provider": request.provider
    }

@app.post("/process")
async def process_worker_task(payload: dict):
    # Executed only by the unique3d-worker container
    from src.unique3d_client import generate_mesh_from_image_unique3d
    return generate_mesh_from_image_unique3d(
        image_path=Path(payload["image_path"]),
        output_path=Path(payload["output_path"]),
        resolution=payload.get("resolution", "medium")
    )

@app.post("/generate-image-from-prompt")
async def generate_image_from_prompt_endpoint(request: GenerateImageRequest):
    """Start an async image generation task from a text prompt via Mamouth.ai. Returns task_id."""
    if not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured in .env")

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 1000 characters)")

    if request.resolution not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'low', 'medium', or 'high'")

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
        "message": "Image generation in progress"
    }


@app.post("/generate-texture")
async def generate_texture_endpoint(request: GenerateTextureRequest):
    """Start an async seamless texture generation task via Mamouth.ai."""
    if not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured in .env")

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 1000 characters)")

    if request.resolution not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=400, detail="Invalid resolution")

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
        "message": "Texture generation in progress"
    }

def generate_material_task_handler(task: Task):
    """Generate a full material: texture + physics parameters, in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    params = task.params
    prompt = params["prompt"]

    texture_id = f"tex_{int(time.time() * 1000)}"
    texture_dir = DATA_GENERATED_TEXTURES / texture_id
    texture_dir.mkdir(parents=True, exist_ok=True)

    output_path = texture_dir / "color.png"
    api_key = os.getenv('GEMINI_API_KEY')

    logger.info(f"[GENERATE-MATERIAL] Starting (texture_id={texture_id})")

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:  # Texture + physics in parallel
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
    """Start an async AI material generation task (texture + physics) via Mamouth.ai."""
    if not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured in .env")

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 1000 characters)")

    task_id = task_manager.create_task(
        task_type="generate_material",
        params={"prompt": request.prompt.strip()}
    )

    logger.info(f"[API] Material generation task created: {task_id}")

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Material generation in progress"
    }


@app.get("/texture/generated/{texture_id}/{filename}")
async def get_generated_texture(texture_id: str, filename: str):
    """Serve a generated texture file."""
    texture_path = DATA_GENERATED_TEXTURES / sanitize_filename(texture_id) / sanitize_filename(filename)

    if not texture_path.exists():
        raise HTTPException(status_code=404, detail="Texture not found")

    return FileResponse(str(texture_path), media_type="image/png")


@app.get("/session-images/{session_id}/{filename}")
async def get_session_image(session_id: str, filename: str):
    """Serve a session image for frontend preview."""
    image_path = DATA_INPUT_IMAGES / sanitize_filename(session_id) / sanitize_filename(filename)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    suffix = image_path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    return FileResponse(str(image_path), media_type=f"image/{suffix[1:]}")


@app.get("/mesh/generated/{filename}")
async def get_generated_mesh(filename: str):
    """Stream a generated mesh from data/generated_meshes for visualization."""
    file_path = DATA_GENERATED_MESHES / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_ext = file_path.suffix.lower()

    media_type_mapping = {
        ".obj": "model/obj",
        ".stl": "model/stl",
        ".ply": "application/ply",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
    }
    media_type = media_type_mapping.get(file_ext, "application/octet-stream")

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
    """Start an async retopology task using Instant Meshes."""
    if request.is_simplified:
        source_dir = DATA_OUTPUT
    elif request.is_generated:
        source_dir = DATA_GENERATED_MESHES
    else:
        source_dir = DATA_INPUT

    input_file = source_dir / request.filename

    if not input_file.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    # Validate target_face_count range: [5% : 50%] of original, minimum 1000
    original_face_count = request.original_face_count
    min_faces = max(1000, int(original_face_count * 0.05))
    max_faces = max(5000, int(original_face_count * 0.5))

    if request.target_face_count < min_faces:
        raise HTTPException(
            status_code=400,
            detail=f"target_face_count too low: minimum {min_faces} faces (original: {original_face_count})"
        )

    if request.target_face_count > max_faces:
        raise HTTPException(
            status_code=400,
            detail=f"target_face_count too high: maximum {max_faces} faces (original: {original_face_count})"
        )

    task_id = task_manager.create_task(
        task_type="retopologize",
        params={
            "filename": request.filename,
            "target_face_count": request.target_face_count,
            "deterministic": request.deterministic,
            "preserve_boundaries": request.preserve_boundaries,
            "is_generated": request.is_generated,
            "is_simplified": request.is_simplified,
            "bake_textures": request.bake_textures
        }
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Retopology task created"
    }

@app.get("/mesh/retopo/{filename}")
async def get_retopo_mesh(filename: str):
    """Stream a retopologized mesh from data/retopo for visualization."""
    file_path = DATA_RETOPO / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_ext = file_path.suffix.lower()

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
    """Start an async mesh segmentation task."""
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

    if not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File {request.filename} not found in {source_label}"
        )

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
        "message": f"Segmentation started with method '{request.method}'"
    }

@app.get("/mesh/segmented/{filename}")
async def get_segmented_mesh(filename: str):
    """Download a segmented mesh from data/segmented/."""
    file_path = DATA_SEGMENTED / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Segmented file not found")

    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename
    )

@app.post("/compare")
async def compare_meshes_endpoint(request: CompareRequest):
    """Compare two meshes and generate a distance heatmap."""

    def _resolve(filename, is_gen, is_simp, is_retopo):
        if is_gen:
            return DATA_GENERATED_MESHES / filename
        elif is_simp:
            return DATA_OUTPUT / filename
        elif is_retopo:
            return DATA_RETOPO / filename
        return DATA_INPUT / filename

    ref_path = _resolve(request.filename_ref, request.is_generated_ref,
                        request.is_simplified_ref, request.is_retopo_ref)
    comp_path = _resolve(request.filename_comp, request.is_generated_comp,
                         request.is_simplified_comp, request.is_retopo_comp)

    if not ref_path.exists():
        raise HTTPException(status_code=404, detail=f"Reference file not found: {request.filename_ref}")
    if not comp_path.exists():
        raise HTTPException(status_code=404, detail=f"Comparison file not found: {request.filename_comp}")

    task_id = task_manager.create_task(
        task_type="compare",
        params={
            "filename_ref": request.filename_ref,
            "filename_comp": request.filename_comp,
            "is_generated_ref": request.is_generated_ref,
            "is_simplified_ref": request.is_simplified_ref,
            "is_retopo_ref": request.is_retopo_ref,
            "is_generated_comp": request.is_generated_comp,
            "is_simplified_comp": request.is_simplified_comp,
            "is_retopo_comp": request.is_retopo_comp,
        }
    )

    return {"task_id": task_id, "message": "Comparison started"}


@app.get("/mesh/compared/{filename}")
async def get_compared_mesh(filename: str):
    """Download a comparison mesh (heatmap) from data/compared/."""
    file_path = DATA_COMPARED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Comparison file not found")
    return FileResponse(path=str(file_path), media_type="application/octet-stream", filename=filename)


@app.get("/quality-stats/{filename}")
async def get_quality_stats(
    filename: str,
    is_generated: bool = False,
    is_simplified: bool = False,
    is_retopologized: bool = False
):
    """Compute mesh quality stats (synchronous, fast)."""
    from .mesh_quality import compute_quality_stats

    mesh_path = _resolve_mesh_path(filename, is_generated, is_simplified, is_retopologized)
    if not mesh_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return compute_quality_stats(mesh_path)


@app.post("/unwrap-uv")
async def unwrap_uv_endpoint(request: UnwrapUVRequest):
    """Start an async LSCM UV unwrapping task. Returns task_id."""
    mesh_path = _resolve_mesh_path(
        request.filename,
        request.is_generated,
        request.is_simplified,
        request.is_retopologized
    )
    if not mesh_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    task_id = task_manager.create_task(
        task_type="unwrap_uv",
        params={
            "filename": request.filename,
            "is_generated": request.is_generated,
            "is_simplified": request.is_simplified,
            "is_retopologized": request.is_retopologized,
        }
    )
    return {"task_id": task_id, "message": "UV unwrapping started"}


@app.get("/mesh/unwrapped/{filename}")
async def get_unwrapped_mesh(filename: str):
    """Serve a UV-unwrapped mesh from data/unwrapped/."""
    file_path = DATA_UNWRAPPED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Unwrapped file not found")
    return FileResponse(path=str(file_path), media_type="application/octet-stream", filename=filename)


@app.post("/bake-texture")
async def bake_texture_endpoint(request: BakeTextureRequest):
    """Start an async texture baking task. Embeds Imagen texture PNG into mesh GLB via UV coords."""
    if request.is_uv_unwrapped:
        mesh_path = DATA_UNWRAPPED / request.filename
    else:
        mesh_path = _resolve_mesh_path(
            request.filename, request.is_generated, request.is_simplified, request.is_retopologized
        )
    if not mesh_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    texture_path = DATA_GENERATED_TEXTURES / request.texture_id / "color.png"
    if not texture_path.exists():
        raise HTTPException(status_code=404, detail=f"Texture not found: {request.texture_id}")

    task_id = task_manager.create_task(
        task_type="bake_texture",
        params={
            "filename": request.filename,
            "texture_id": request.texture_id,
            "is_generated": request.is_generated,
            "is_simplified": request.is_simplified,
            "is_retopologized": request.is_retopologized,
            "is_uv_unwrapped": request.is_uv_unwrapped,
        }
    )
    return {"task_id": task_id, "message": "Texture baking started"}


@app.get("/mesh/baked/{filename}")
async def get_baked_mesh(filename: str):
    """Serve a baked mesh from data/baked/."""
    file_path = DATA_BAKED / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Baked file not found")
    return FileResponse(path=str(file_path), media_type="application/octet-stream", filename=filename)


# ── Auto-LOD ──────────────────────────────────────────────────────────────────

LOD_RATIOS = [1.0, 0.5, 0.25, 0.10]  # LOD0=original, LOD1=50%, LOD2=25%, LOD3=10%

def generate_lod_task_handler(task: Task):
    import zipfile
    params = task.params
    input_path = Path(params["input_file"])
    stem = input_path.stem

    lods = []

    # LOD0: copy of the original
    lod0_path = DATA_OUTPUT / f"{stem}_LOD0.glb"
    shutil.copy2(str(input_path), str(lod0_path))
    original_faces = _count_faces_glb(input_path)
    lods.append({"level": 0, "filename": lod0_path.name, "faces_count": original_faces})

    # LOD1, LOD2, LOD3
    for i, ratio in enumerate([0.5, 0.25, 0.10], start=1):
        lod_path = DATA_OUTPUT / f"{stem}_LOD{i}.glb"
        result = simplify_mesh_glb(
            input_path=input_path,
            output_path=lod_path,
            reduction_ratio=1.0 - ratio  # ratio = faces kept; reduction = faces removed
        )
        faces = result.get("simplified_triangles", 0) if result.get("success") else 0
        lods.append({"level": i, "filename": lod_path.name, "faces_count": faces})

    # Pack all 4 LOD files into a ZIP
    zip_filename = f"{stem}_LODs.zip"
    zip_path = DATA_OUTPUT / zip_filename
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for lod in lods:
            lod_file = DATA_OUTPUT / lod["filename"]
            if lod_file.exists():
                zf.write(str(lod_file), lod["filename"])

    return {
        "success": True,
        "lods": lods,
        "zip_filename": zip_filename,
        "original_faces": original_faces,
    }


def _count_faces_glb(path: Path) -> int:
    try:
        loaded = trimesh.load(str(path))
        if hasattr(loaded, "geometry"):
            meshes = list(loaded.geometry.values())
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded
        return int(len(mesh.faces))
    except Exception:
        return 0


@app.post("/generate-lod")
async def generate_lod(request: GenerateLodRequest):
    """Generate 4 LOD levels (LOD0-LOD3) from a GLB mesh and package them as a downloadable ZIP."""
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
    input_path = source_dir / request.filename
    if not input_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    task_id = task_manager.create_task(
        task_type="generate_lod",
        params={
            "input_file": str(input_path),
            "is_generated": request.is_generated,
        }
    )
    return {"task_id": task_id, "message": "LOD generation started"}


@app.get("/download-lod-zip/{filename}")
async def download_lod_zip(filename: str):
    """Download the ZIP containing all LOD levels."""
    file_path = DATA_OUTPUT / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="LOD ZIP not found")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/zip"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
