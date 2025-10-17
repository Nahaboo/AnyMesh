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
from .converter import convert_and_compress
from .glb_cache import (
    invalidate_glb_cache,
    should_convert_to_glb,
    cleanup_orphaned_glb_files,
    get_cache_stats,
    is_glb_file
)

app = FastAPI(
    title="MeshSimplifier API",
    description="API pour la simplification et réparation de maillages 3D",
    version="0.1.0"
)

# Configuration CORS - Permettre toutes les origines en développement
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les origines autorisées
    allow_credentials=False,  # Doit être False si allow_origins=["*"]
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

@app.post("/upload-fast")
async def upload_mesh_fast(file: UploadFile = File(...)):
    """
    Upload rapide d'un fichier de maillage 3D pour visualisation immédiate
    Sauvegarde le fichier et convertit en GLB sans analyse détaillée
    Formats supportés: OBJ, STL, PLY, OFF, GLTF, GLB
    """
    start_total = time.time()
    print(f"\n🔵 [UPLOAD-FAST] Upload started: {file.filename}")

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
    file_size = file_path.stat().st_size
    print(f"  📁 File save: {save_duration:.2f}ms ({file_size / 1024 / 1024:.2f} MB)")

    # Bounding box basique (rapide, juste pour la caméra)
    # On charge le mesh uniquement pour avoir la bounding box
    try:
        loaded = trimesh.load(str(file_path))
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) > 0:
                mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
            else:
                raise HTTPException(status_code=400, detail="La scène ne contient aucune géométrie")
        else:
            mesh = loaded

        bounds = mesh.bounds
        bounding_box = {
            "min": [float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])],
            "max": [float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])],
            "center": [float(mesh.centroid[0]), float(mesh.centroid[1]), float(mesh.centroid[2])],
            "diagonal": float(mesh.scale)
        }
    except Exception as e:
        print(f"  ⚠️ Could not compute bounding box: {e}")
        # Bounding box par défaut si le calcul échoue
        bounding_box = {
            "min": [-1.0, -1.0, -1.0],
            "max": [1.0, 1.0, 1.0],
            "center": [0.0, 0.0, 0.0],
            "diagonal": 1.732
        }

    # Conversion automatique vers GLB si nécessaire
    glb_filename = file.filename
    conversion_result = None

    if not is_glb_file(file.filename):
        should_convert, reason = should_convert_to_glb(
            file.filename,
            file_size,
            max_size_mb=50
        )

        if should_convert:
            glb_filename = f"{file_path.stem}.glb"
            glb_path = DATA_INPUT / glb_filename

            invalidate_glb_cache(file.filename, DATA_INPUT)

            conversion_result = convert_and_compress(
                input_path=file_path,
                output_path=glb_path,
                enable_draco=False,
                compression_level=7
            )

            if conversion_result['success']:
                glb_filename = glb_filename
                print(f"  ✓ GLB generated: {glb_filename}")
            else:
                print(f"  ⚠️ GLB conversion failed: {conversion_result.get('error')}")
                glb_filename = file.filename
        else:
            print(f"  ⚠️ Skipping GLB conversion: {reason}")

    total_duration = (time.time() - start_total) * 1000
    print(f"🟢 [UPLOAD-FAST] Completed: {total_duration:.2f}ms\n")

    return {
        "message": "Fichier uploadé avec succès",
        "filename": file.filename,
        "glb_filename": glb_filename,
        "original_filename": file.filename if glb_filename != file.filename else None,
        "file_size": file_size,
        "format": file_ext,
        "bounding_box": bounding_box,
        "upload_time_ms": round(total_duration, 2)
    }

@app.post("/upload")
async def upload_mesh(file: UploadFile = File(...)):
    """
    Upload un fichier de maillage 3D avec analyse complète
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
        loaded = trimesh.load(str(file_path))
        load_duration = (time.time() - start_load) * 1000
        print(f"  🔷 trimesh load: {load_duration:.2f}ms")

        # Si c'est une Scene, extraire et fusionner les géométries
        if hasattr(loaded, 'geometry'):
            # C'est une Scene avec potentiellement plusieurs meshes
            print(f"  🔍 Scene détectée avec {len(loaded.geometry)} géométrie(s)")
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="La scène ne contient aucune géométrie"
                )
            elif len(meshes) == 1:
                mesh = meshes[0]
            else:
                # Fusionner plusieurs meshes
                mesh = trimesh.util.concatenate(meshes)
                print(f"  🔗 {len(meshes)} meshes fusionnés")
        else:
            # C'est directement un Mesh
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise HTTPException(
                status_code=400,
                detail="Le fichier ne contient pas de vertices valides"
            )

        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            raise HTTPException(
                status_code=400,
                detail="Le fichier ne contient pas de faces (mesh vide ou nuage de points)"
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

        # Conversion automatique vers GLB pour la visualisation frontend
        # IMPORTANT: Le GLB sert UNIQUEMENT à la visualisation
        # Toutes les opérations (simplification, réparation) utilisent le fichier original
        glb_filename = file.filename
        conversion_result = None

        if not is_glb_file(file.filename):
            # Vérifier si la conversion est recommandée (limite de taille)
            should_convert, reason = should_convert_to_glb(
                file.filename,
                file_path.stat().st_size,
                max_size_mb=50
            )

            if should_convert:
                # Générer le nom du fichier GLB
                glb_filename = f"{file_path.stem}.glb"
                glb_path = DATA_INPUT / glb_filename

                # Invalider le cache GLB existant pour forcer la reconversion
                invalidate_glb_cache(file.filename, DATA_INPUT)

                # Convertir vers GLB
                conversion_result = convert_and_compress(
                    input_path=file_path,
                    output_path=glb_path,
                    enable_draco=False,
                    compression_level=7
                )

                if conversion_result['success']:
                    # Mettre à jour mesh_info avec le nouveau filename GLB
                    mesh_info['glb_filename'] = glb_filename
                    mesh_info['glb_size'] = conversion_result['final_size']
                    mesh_info['original_filename'] = file.filename
                    mesh_info['original_size'] = file_path.stat().st_size
                    print(f"  ✓ GLB generated for visualization: {glb_filename}")
                else:
                    print(f"  ⚠️ GLB conversion failed: {conversion_result.get('error')}")
                    # Continuer avec le fichier original
                    glb_filename = file.filename
            else:
                # Conversion non recommandée (fichier trop gros)
                print(f"  ⚠️ Skipping GLB conversion: {reason}")
                conversion_result = {
                    'skipped': True,
                    'reason': reason
                }
        else:
            # Fichier déjà GLB/GLTF, pas de conversion nécessaire
            print("  ⚡ File is already GLB/GLTF, no conversion needed")
            conversion_result = {
                'skipped': True,
                'reason': 'File is already GLB/GLTF'
            }

        total_duration = (time.time() - start_total) * 1000
        print(f"🟢 [PERF] Upload completed: {total_duration:.2f}ms\n")

        # Timings pour le frontend
        backend_timings = {
            "file_save_ms": round(save_duration, 2),
            "trimesh_load_ms": round(load_duration, 2),
            "analysis_ms": round(analyze_duration, 2),
            "total_ms": round(total_duration, 2)
        }

        # Ajouter les timings de conversion si disponibles
        if conversion_result and not conversion_result.get('skipped'):
            if conversion_result.get('conversion'):
                backend_timings['glb_conversion_ms'] = conversion_result['conversion'].get('conversion_time_ms', 0)
            if conversion_result.get('compression'):
                backend_timings['draco_compression_ms'] = conversion_result['compression'].get('compression_time_ms', 0)

        return {
            "message": "Fichier uploadé avec succès",
            "mesh_info": mesh_info,
            "backend_timings": backend_timings,
            "conversion": conversion_result  # Informations sur la conversion GLB
        }

    except Exception as e:
        # Supprimer le fichier si le chargement échoue
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors du chargement du maillage: {str(e)}"
        ) from e

@app.get("/analyze/{filename}")
async def analyze_mesh(filename: str):
    """
    Analyse détaillée d'un fichier de maillage déjà uploadé
    Retourne les statistiques complètes (vertices, triangles, propriétés)
    """
    start_analyze = time.time()
    print(f"\n🔵 [ANALYZE] Starting analysis: {filename}")

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
        print(f"  📊 Analysis completed: {analyze_duration:.2f}ms")
        print(f"     Vertices: {mesh_stats['vertices_count']:,}")
        print(f"     Triangles: {mesh_stats['triangles_count']:,}")

        return {
            "success": True,
            "mesh_stats": mesh_stats,
            "analysis_time_ms": round(analyze_duration, 2)
        }

    except Exception as e:
        print(f"  ❌ Analysis failed: {e}")
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

# Handler pour les tâches de simplification
def simplify_task_handler(task: Task):
    """Handler qui exécute la simplification d'un maillage"""
    params = task.params
    input_file = params["input_file"]
    output_file = params["output_file"]
    target_triangles = params.get("target_triangles")
    reduction_ratio = params.get("reduction_ratio")
    preserve_boundary = params.get("preserve_boundary", True)

    print(f"\n🔵 [SIMPLIFY] Starting simplification")
    print(f"  Input: {Path(input_file).name}")
    print(f"  Output: {Path(output_file).name}")

    # Exécute la simplification
    result = simplify_mesh(
        input_path=Path(input_file),
        output_path=Path(output_file),
        target_triangles=target_triangles,
        reduction_ratio=reduction_ratio,
        preserve_boundary=preserve_boundary
    )

    # IMPORTANT: Après simplification, invalider le cache GLB du fichier SOURCE
    # Le fichier source n'a pas changé, mais on veut régénérer le GLB si l'utilisateur
    # re-upload le fichier simplifié pour remplacement
    if result.get('success'):
        print(f"  ✓ Simplification completed successfully")

        # Note: On n'invalide PAS le cache du fichier d'entrée car il n'a pas changé
        # Le GLB du fichier d'entrée reste valide
        # Si l'utilisateur veut visualiser le résultat, il devra uploader le fichier de sortie
        # qui générera automatiquement son propre GLB

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
    """
    Sert un fichier de maillage depuis data/input pour la visualisation
    Si un fichier GLB converti existe, il sera servi en priorité
    """
    file_path = DATA_INPUT / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Stratégie: Servir le GLB s'il existe, sinon le fichier original
    file_ext = file_path.suffix.lower()

    # Si le fichier demandé n'est pas GLB, vérifier si une version GLB existe
    if file_ext not in {".glb", ".gltf"}:
        glb_path = DATA_INPUT / f"{file_path.stem}.glb"
        if glb_path.exists():
            print(f"  ⚡ Serving GLB instead of {filename}: {glb_path.name}")
            file_path = glb_path
            file_ext = ".glb"

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

@app.get("/debug/download-glb/{original_filename}")
async def debug_download_glb(original_filename: str):
    """
    [DEBUG] Télécharge le fichier GLB converti depuis data/input
    Usage: /debug/download-glb/bunny.obj → télécharge bunny.glb
    """
    # Extraire le nom sans extension
    file_stem = Path(original_filename).stem
    glb_filename = f"{file_stem}.glb"
    glb_path = DATA_INPUT / glb_filename

    if not glb_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"GLB converti non trouvé: {glb_filename}. Uploadez d'abord le fichier."
        )

    return FileResponse(
        path=str(glb_path),
        filename=glb_filename,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f'attachment; filename="{glb_filename}"'}
    )

@app.get("/cache/glb/stats")
async def get_glb_cache_stats():
    """
    Retourne des statistiques sur le cache GLB

    Utile pour monitoring et debugging
    """
    stats = get_cache_stats(DATA_INPUT)
    return {
        "cache_stats": stats,
        "message": "GLB cache statistics"
    }

@app.post("/cache/glb/cleanup")
async def cleanup_glb_cache():
    """
    Nettoie les fichiers GLB orphelins (sans fichier source correspondant)

    Les fichiers GLB sont générés automatiquement pour la visualisation.
    Cet endpoint supprime les GLB dont le fichier source a été supprimé.
    """
    deleted = cleanup_orphaned_glb_files(DATA_INPUT)

    return {
        "deleted_files": deleted,
        "count": len(deleted),
        "message": f"Cleaned up {len(deleted)} orphaned GLB file(s)"
    }

@app.delete("/cache/glb/{original_filename}")
async def invalidate_glb_cache_endpoint(original_filename: str):
    """
    Invalide le cache GLB d'un fichier spécifique

    Force la régénération du GLB au prochain chargement.
    Utile après une modification manuelle du fichier source.

    Args:
        original_filename: Nom du fichier source (ex: bunny.obj)
    """
    was_deleted = invalidate_glb_cache(original_filename, DATA_INPUT)

    if was_deleted:
        return {
            "message": f"GLB cache invalidated for {original_filename}",
            "deleted": True
        }
    else:
        return {
            "message": f"No GLB cache found for {original_filename}",
            "deleted": False
        }

# Initialisation du gestionnaire de tâches
@app.on_event("startup")
async def startup_event():
    """Démarre le gestionnaire de tâches"""
    task_manager.register_handler("simplify", simplify_task_handler)
    task_manager.start()

    # Afficher les statistiques du cache GLB au démarrage
    print("\n📊 [GLB CACHE] Statistics at startup:")
    stats = get_cache_stats(DATA_INPUT)
    print(f"  Total GLB files: {stats['total_glb_files']}")
    print(f"  Total size: {stats['total_size_mb']:.2f} MB")
    if stats['orphaned_count'] > 0:
        print(f"  ⚠️ Orphaned files: {stats['orphaned_count']}")
        print(f"     Use POST /cache/glb/cleanup to clean them up")

@app.on_event("shutdown")
async def shutdown_event():
    """Arrête proprement le gestionnaire de tâches"""
    task_manager.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
