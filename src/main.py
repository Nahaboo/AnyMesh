"""
Backend FastAPI pour MeshSimplifier
Fournit les endpoints pour l'upload et le traitement de maillages 3D
"""

import os
import shutil
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import trimesh

from .task_manager import task_manager, Task
from .simplify import simplify_mesh, adaptive_simplify_mesh
from .converter import convert_and_compress, convert_mesh_format
from .glb_cache import (
    invalidate_glb_cache,
    should_convert_to_glb,
    cleanup_orphaned_glb_files,
    get_cache_stats,
    is_glb_file
)
from .stability_client import generate_mesh_from_image_sf3d
from .retopology import retopologize_mesh

# Charger les variables d'environnement depuis .env
load_dotenv()

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
DATA_INPUT_IMAGES = Path("data/input_images")
DATA_GENERATED_MESHES = Path("data/generated_meshes")
DATA_RETOPO = Path("data/retopo")
DATA_INPUT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
DATA_INPUT_IMAGES.mkdir(parents=True, exist_ok=True)
DATA_GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
DATA_RETOPO.mkdir(parents=True, exist_ok=True)

# Formats de fichiers supportés
SUPPORTED_FORMATS = {".obj", ".stl", ".ply", ".off", ".gltf", ".glb"}
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png"}

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
    """Paramètres de génération de maillage à partir d'images"""
    session_id: str
    resolution: str = "medium"  # 'low', 'medium', 'high'
    output_format: str = "obj"  # 'obj', 'stl', 'ply'
    remesh_option: str = "quad"  # 'none', 'triangle', 'quad' - Topologie du mesh généré

class RetopologyRequest(BaseModel):
    """Paramètres de retopologie avec Instant Meshes"""
    filename: str
    target_face_count: int = 10000
    original_face_count: int  # Nombre de faces du mesh original (envoyé par le frontend)
    deterministic: bool = True
    preserve_boundaries: bool = True
    is_generated: bool = False  # Si True, cherche dans data/generated_meshes

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
    print(f"\n [UPLOAD-FAST] Upload started: {file.filename}")

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
    print(f"   File save: {save_duration:.2f}ms ({file_size / 1024 / 1024:.2f} MB)")

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

        #  NORMALISATION DU MESH: Centrer à l'origine
        # Cela garantit que tous les modèles sont centrés pour une visualisation cohérente
        original_centroid = mesh.centroid.copy()
        original_scale = mesh.scale

        # Translater les vertices pour centrer le mesh à l'origine
        mesh.vertices -= mesh.centroid

        # Sauvegarder le mesh normalisé (écrase le fichier original)
        mesh.export(str(file_path))

        print(f"   Mesh normalized:")
        print(f"     Original centroid: [{original_centroid[0]:.2f}, {original_centroid[1]:.2f}, {original_centroid[2]:.2f}]")
        print(f"     Original scale: {original_scale:.2f}")
        print(f"     New centroid: [0.00, 0.00, 0.00]")

        bounds = mesh.bounds
        bounding_box = {
            "min": [float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])],
            "max": [float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])],
            "center": [float(mesh.centroid[0]), float(mesh.centroid[1]), float(mesh.centroid[2])],
            "diagonal": float(mesh.scale)
        }

        # Calculer les statistiques du mesh
        vertices_count = int(len(mesh.vertices))
        faces_count = int(len(mesh.faces))
        print(f"   Mesh stats: {vertices_count:,} vertices, {faces_count:,} faces")

    except Exception as e:
        print(f"   Could not compute bounding box: {e}")
        # Bounding box par défaut si le calcul échoue
        bounding_box = {
            "min": [-1.0, -1.0, -1.0],
            "max": [1.0, 1.0, 1.0],
            "center": [0.0, 0.0, 0.0],
            "diagonal": 1.732
        }
        vertices_count = 0
        faces_count = 0

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
            # Générer un nom unique pour éviter les conflits de cache
            timestamp = int(time.time() * 1000)  # timestamp en millisecondes
            glb_filename = f"{file_path.stem}_{timestamp}.glb"
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
    print(f" [UPLOAD-FAST] Completed: {total_duration:.2f}ms\n")

    return {
        "message": "Fichier uploadé avec succès",
        "filename": file.filename,
        "glb_filename": glb_filename,
        "original_filename": file.filename if glb_filename != file.filename else None,
        "file_size": file_size,
        "format": file_ext,
        "bounding_box": bounding_box,
        "vertices_count": vertices_count,
        "faces_count": faces_count,
        "upload_time_ms": round(total_duration, 2)
    }

@app.post("/upload")
async def upload_mesh(file: UploadFile = File(...)):
    """
    Upload un fichier de maillage 3D avec analyse complète
    Formats supportés: OBJ, STL, PLY, OFF, GLTF, GLB
    """
    start_total = time.time()
    print(f"\n [PERF] Upload started: {file.filename}")

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
    print(f"   File save: {save_duration:.2f}ms ({file_path.stat().st_size / 1024 / 1024:.2f} MB)")

    # Utilisation de trimesh pour toutes les analyses
    start_load = time.time()
    try:
        loaded = trimesh.load(str(file_path))
        load_duration = (time.time() - start_load) * 1000
        print(f"   trimesh load: {load_duration:.2f}ms")

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
        print(f"   Analysis: {analyze_duration:.2f}ms")
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
                    print(f"   GLB conversion failed: {conversion_result.get('error')}")
                    # Continuer avec le fichier original
                    glb_filename = file.filename
            else:
                # Conversion non recommandée (fichier trop gros)
                print(f"   Skipping GLB conversion: {reason}")
                conversion_result = {
                    'skipped': True,
                    'reason': reason
                }
        else:
            # Fichier déjà GLB/GLTF, pas de conversion nécessaire
            print("   File is already GLB/GLTF, no conversion needed")
            conversion_result = {
                'skipped': True,
                'reason': 'File is already GLB/GLTF'
            }

        total_duration = (time.time() - start_total) * 1000
        print(f" [PERF] Upload completed: {total_duration:.2f}ms\n")

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
    print(f"\n [ANALYZE] Starting analysis: {filename}")

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
        print(f"   Analysis completed: {analyze_duration:.2f}ms")
        print(f"     Vertices: {mesh_stats['vertices_count']:,}")
        print(f"     Triangles: {mesh_stats['triangles_count']:,}")

        return {
            "success": True,
            "mesh_stats": mesh_stats,
            "analysis_time_ms": round(analyze_duration, 2)
        }

    except Exception as e:
        print(f"   Analysis failed: {e}")
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
    is_generated = params.get("is_generated", False)

    print(f"\n [SIMPLIFY] Starting simplification")
    print(f"  Input: {Path(input_file).name}")
    print(f"  Output: {Path(output_file).name}")

    # Si le fichier est un GLB, le convertir en OBJ pour la simplification
    input_path = Path(input_file)
    if input_path.suffix.lower() == '.glb':
        print(f"  [INFO] Converting GLB to OBJ for simplification...")
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
        print(f"  [INFO] Using temporary OBJ: {temp_obj_filename}")

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
        print(f"   Simplification completed successfully")

        # Note: On n'invalide PAS le cache du fichier d'entrée car il n'a pas changé
        # Le GLB du fichier d'entrée reste valide
        # Si l'utilisateur veut visualiser le résultat, il devra uploader le fichier de sortie
        # qui générera automatiquement son propre GLB

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
            }
        }

        # Nettoyer le fichier OBJ temporaire si on a converti depuis GLB
        if '_temp.obj' in str(input_file) and Path(input_file).exists():
            print(f"  [CLEANUP] Removing temporary OBJ file")
            Path(input_file).unlink()

        return result_data

    # En cas d'échec, nettoyer quand même le fichier temporaire
    if '_temp.obj' in str(input_file) and Path(input_file).exists():
        print(f"  [CLEANUP] Removing temporary OBJ file")
        Path(input_file).unlink()

    return result

def adaptive_simplify_task_handler(task: Task):
    """Handler qui exécute la simplification adaptative d'un maillage"""
    params = task.params
    input_file = params["input_file"]
    output_file = params["output_file"]
    target_ratio = params.get("target_ratio", 0.5)
    flat_multiplier = params.get("flat_multiplier", 2.0)
    curvature_threshold = params.get("curvature_threshold")
    is_generated = params.get("is_generated", False)

    print(f"\n [ADAPTIVE SIMPLIFY] Starting adaptive simplification")
    print(f"  Input: {Path(input_file).name}")
    print(f"  Output: {Path(output_file).name}")
    print(f"  Target ratio: {target_ratio}")
    print(f"  Flat multiplier: {flat_multiplier}x")

    # Si le fichier est un GLB, le convertir en OBJ pour la simplification
    input_path = Path(input_file)
    if input_path.suffix.lower() == '.glb':
        print(f"  [INFO] Converting GLB to OBJ for simplification...")
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
        print(f"  [INFO] Using temporary OBJ: {temp_obj_filename}")

    # Exécute la simplification adaptative
    result = adaptive_simplify_mesh(
        input_path=Path(input_file),
        output_path=Path(output_file),
        target_ratio=target_ratio,
        flat_multiplier=flat_multiplier,
        curvature_threshold=curvature_threshold
    )

    if result.get('success'):
        print(f"   Adaptive simplification completed successfully")

        # Afficher les stats adaptatives
        adaptive_stats = result.get('adaptive_stats', {})
        print(f"  Flat regions: {adaptive_stats.get('flat_percentage', 0):.1f}% of mesh")
        print(f"  Flat triangles: {adaptive_stats.get('flat_triangles_original', 0)} → {adaptive_stats.get('flat_triangles_final', 0)}")
        print(f"  Curved triangles: {adaptive_stats.get('curved_triangles_original', 0)} → {adaptive_stats.get('curved_triangles_final', 0)}")

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
            print(f"  [CLEANUP] Removing temporary OBJ file")
            Path(input_file).unlink()

        return result_data

    # En cas d'échec, nettoyer quand même le fichier temporaire
    if '_temp.obj' in str(input_file) and Path(input_file).exists():
        print(f"  [CLEANUP] Removing temporary OBJ file")
        Path(input_file).unlink()

    return result

@app.post("/simplify")
async def simplify_mesh_async(request: SimplifyRequest):
    """
    Lance une tâche de simplification de maillage en arrière-plan
    Retourne un task_id pour suivre la progression
    """
    # Déterminer le dossier source selon is_generated
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
    input_path = source_dir / request.filename

    # Vérification que le fichier existe
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Vérification du format et conversion si nécessaire
    file_ext = input_path.suffix.lower()
    if file_ext in {".gltf", ".glb"}:
        # Pour les meshes générés (GLB), on va les convertir en OBJ automatiquement dans le task handler
        if not request.is_generated:
            raise HTTPException(
                status_code=400,
                detail="La simplification des fichiers GLTF/GLB uploadés n'est pas supportée. Utilisez OBJ, STL ou PLY."
            )
        # Si c'est un mesh généré (GLB), on laisse le task handler gérer la conversion

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
    Lance une tâche de simplification adaptative en arrière-plan
    Détecte les zones plates et les simplifie plus agressivement
    Retourne un task_id pour suivre la progression
    """
    # Déterminer le dossier source selon is_generated
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
    input_path = source_dir / request.filename

    # Vérification que le fichier existe
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Vérification du format et conversion si nécessaire
    file_ext = input_path.suffix.lower()
    if file_ext in {".gltf", ".glb"}:
        # Pour les meshes générés (GLB), on va les convertir en OBJ automatiquement dans le task handler
        if not request.is_generated:
            raise HTTPException(
                status_code=400,
                detail="La simplification des fichiers GLTF/GLB uploadés n'est pas supportée. Utilisez OBJ, STL ou PLY."
            )
        # Si c'est un mesh généré (GLB), on laisse le task handler gérer la conversion

    # Génération du nom de fichier de sortie
    output_filename = f"{input_path.stem}_adaptive{input_path.suffix}"
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

@app.get("/mesh/output/{filename}")
async def get_output_mesh(filename: str):
    """
    Sert un fichier de maillage depuis data/output pour la visualisation
    Utilisé pour visualiser les meshes simplifiés
    Convertit automatiquement en GLB pour de meilleures performances
    """
    file_path = DATA_OUTPUT / filename

    # Si on demande un fichier GLB qui n'existe pas, essayer de le convertir depuis le fichier source
    if not file_path.exists() and filename.endswith('.glb'):
        # Chercher le fichier source (OBJ, STL, PLY, etc.)
        stem = file_path.stem
        for ext in ['.obj', '.stl', '.ply', '.off']:
            source_path = DATA_OUTPUT / f"{stem}{ext}"
            if source_path.exists():
                print(f"   Converting {source_path.name} to GLB for visualization...")
                try:
                    result = convert_and_compress(
                        input_path=source_path,
                        output_path=file_path,
                        enable_draco=False,
                        compression_level=7
                    )
                    if result and result.get('success'):
                        print(f"   GLB created: {file_path.name}")
                        break
                    else:
                        print(f"   GLB conversion failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"   GLB conversion failed: {e}")

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
async def export_mesh(filename: str, format: str = "obj", is_generated: bool = False, is_simplified: bool = False, is_retopologized: bool = False):
    """
    Exporte un fichier de maillage dans le format demandé

    Args:
        filename: Nom du fichier source
        format: Format de sortie ('obj', 'stl', 'ply', 'glb')
        is_generated: Si True, cherche dans data/generated_meshes
        is_simplified: Si True, cherche dans data/output (meshes simplifiés)
        is_retopologized: Si True, cherche dans data/retopo (meshes retopologisés)

    Returns:
        Le fichier converti au format demandé
    """
    # Déterminer le dossier source
    if is_retopologized:
        source_dir = DATA_RETOPO
    elif is_simplified:
        source_dir = DATA_OUTPUT
    elif is_generated:
        source_dir = DATA_GENERATED_MESHES
    else:
        source_dir = DATA_INPUT

    source_path = source_dir / filename

    # Si on exporte un mesh simplifié et que le fichier est un GLB,
    # essayer de trouver le fichier source original (OBJ, STL, PLY)
    # pour une meilleure conversion
    if is_simplified and filename.endswith('.glb'):
        stem = source_path.stem
        for ext in ['.obj', '.stl', '.ply', '.off']:
            original_source = source_dir / f"{stem}{ext}"
            if original_source.exists():
                print(f"   Using original source {original_source.name} instead of GLB")
                source_path = original_source
                filename = original_source.name
                break

    # Vérifier que le fichier existe
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

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

    print(f"\n [EXPORT] Converting {filename} to {target_format.upper()}")

    # Convertir le fichier
    result = convert_mesh_format(source_path, output_path, target_format)

    if not result['success']:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la conversion: {result.get('error', 'Unknown error')}"
        )

    print(f"  ✓ Export successful: {output_filename}")

    # Retourner le fichier converti
    return FileResponse(
        path=str(output_path),
        filename=output_filename,
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

    print(f"\n [UPLOAD-IMAGES] Session: {session_id}")
    print(f"  Images count: {len(files)}")

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

        print(f"  ✓ Saved: {file.filename} → {file_path.name}")

    print(f" [UPLOAD-IMAGES] Completed: {len(uploaded_images)} images")

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
    """Handler qui exécute la génération de maillage avec Stability AI"""
    params = task.params
    session_id = params["session_id"]
    resolution = params.get("resolution", "medium")
    output_format = params.get("output_format", "obj")
    remesh_option = params.get("remesh_option", "quad")

    # [DEV/TEST] Si c'est une tâche fake, elle est déjà complétée, ne rien faire
    if params.get("fake", False):
        print(f"  [GENERATE-MESH] Fake task detected, skipping API call")
        return task.result  # Le résultat a déjà été défini dans l'endpoint

    session_path = DATA_INPUT_IMAGES / session_id

    if not session_path.exists():
        return {
            'success': False,
            'error': 'Session non trouvée'
        }

    print(f"\n [GENERATE-MESH] Starting Stability AI generation")
    print(f"  Session: {session_id}")
    print(f"  Resolution: {resolution}")

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

    # Stability Fast 3D : utilise uniquement la première image
    first_image = image_paths[0]
    print(f"  Images in session: {len(image_paths)}")
    if len(image_paths) > 1:
        print(f"  [INFO] Using first image: {first_image.name} (SF3D single-view only)")

    # Générer le nom de fichier de sortie
    output_filename = f"{session_id}_generated.{output_format}"
    output_path = DATA_GENERATED_MESHES / output_filename

    # Charger l'API key depuis .env
    api_key = os.getenv('STABILITY_API_KEY')
    if not api_key:
        return {
            'success': False,
            'error': 'STABILITY_API_KEY non configurée dans .env'
        }

    # Exécuter la génération avec Stability AI
    result = generate_mesh_from_image_sf3d(
        image_path=first_image,
        output_path=output_path,
        resolution=resolution,
        remesh_option=remesh_option,
        api_key=api_key
    )

    if result.get('success'):
        print(f"   [OK] Mesh generated: {output_filename}")
        result['output_filename'] = output_filename
        result['session_id'] = session_id
        result['images_used'] = 1  # SF3D uses only first image

    return result

def retopologize_task_handler(task: Task):
    """Handler qui exécute la retopologie avec Instant Meshes"""
    params = task.params
    filename = params["filename"]
    target_face_count = params.get("target_face_count", 10000)
    deterministic = params.get("deterministic", True)
    preserve_boundaries = params.get("preserve_boundaries", True)
    is_generated = params.get("is_generated", False)

    # Chercher le fichier dans plusieurs dossiers selon l'origine
    # 1. data/generated_meshes (meshes générés par API)
    # 2. data/output (fichiers simplifiés)
    # 3. data/input (fichiers originaux)
    if is_generated:
        input_file = DATA_GENERATED_MESHES / filename
    else:
        input_file = DATA_OUTPUT / filename
        if not input_file.exists():
            input_file = DATA_INPUT / filename

    # Si le fichier n'existe pas, erreur
    if not input_file.exists():
        return {
            'success': False,
            'error': f'Fichier source non trouvé: {filename}'
        }

    # Si le fichier est un GLB, le convertir en OBJ pour la retopologie
    # (Instant Meshes ne supporte que OBJ/PLY)
    if input_file.suffix.lower() == '.glb':
        print(f"  [INFO] Converting GLB to OBJ for retopology...")
        temp_obj_filename = f"{input_file.stem}_temp.obj"
        temp_obj_file = input_file.parent / temp_obj_filename

        from .converter import convert_mesh_format
        conversion_result = convert_mesh_format(
            input_path=input_file,
            output_path=temp_obj_file,
            output_format='obj'
        )

        if not conversion_result['success']:
            return {
                'success': False,
                'error': f"Conversion GLB→OBJ échouée: {conversion_result.get('error')}"
            }

        # Utiliser le fichier OBJ temporaire comme input
        input_file = temp_obj_file
        filename = temp_obj_filename

    # Générer le nom du fichier de sortie
    output_filename = f"{Path(filename).stem}_retopo{Path(filename).suffix}"
    output_file = DATA_RETOPO / output_filename

    # Supprimer les anciens fichiers de résultat s'ils existent (OBJ/STL/PLY et GLB)
    if output_file.exists():
        print(f"  Removing old result: {output_filename}")
        output_file.unlink()

    # Supprimer aussi le GLB correspondant s'il existe
    glb_filename = f"{Path(filename).stem}_retopo.glb"
    glb_file = DATA_RETOPO / glb_filename
    if glb_file.exists():
        print(f"  Removing old GLB: {glb_filename}")
        glb_file.unlink()

    print(f"\n[RETOPOLOGIZE] Starting retopology")
    print(f"  Input: {filename}")
    print(f"  Output: {output_filename}")
    print(f"  Target faces: {target_face_count}")

    # Exécuter la retopologie
    result = retopologize_mesh(
        input_path=input_file,
        output_path=output_file,
        target_face_count=target_face_count,
        deterministic=deterministic,
        preserve_boundaries=preserve_boundaries
    )

    if result.get('success'):
        print(f"  [OK] Retopology completed")
        result['output_filename'] = output_filename
        result['output_file'] = str(output_file)
        # Ajouter les stats pour le frontend (avec les noms attendus)
        result['vertices_count'] = result.get('retopo_vertices', 0)
        result['faces_count'] = result.get('retopo_faces', 0)
        result['output_size'] = output_file.stat().st_size if output_file.exists() else 0
    else:
        print(f"  [ERROR] Retopology failed: {result.get('error', 'Unknown error')}")

    # Nettoyer le fichier OBJ temporaire si on a converti depuis GLB
    if '_temp.obj' in str(input_file) and input_file.exists():
        print(f"  [CLEANUP] Removing temporary OBJ file")
        input_file.unlink()

    return result

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
    print(f"\n [FAKE-GENERATE] Using template: {template_glb.name}")

    # Générer le nom de fichier de sortie
    output_filename = f"{request.session_id}_generated.glb"
    output_path = DATA_GENERATED_MESHES / output_filename

    # Copier le fichier template
    import shutil
    shutil.copy2(template_glb, output_path)
    print(f"  [FAKE-GENERATE] Copied to: {output_filename}")

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

    # Créer une tâche fake qui se termine immédiatement
    task_id = task_manager.create_task(
        task_type="generate_mesh",
        params={
            "session_id": request.session_id,
            "resolution": request.resolution,
            "output_format": request.output_format,
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
        print(f"  [FAKE-GENERATE] Task completed immediately")
        print(f"  [FAKE-GENERATE] Vertices: {vertices_count}, Faces: {faces_count}")

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

    # Validation du format de sortie
    if request.output_format not in ['obj', 'stl', 'ply', 'glb']:
        raise HTTPException(
            status_code=400,
            detail="Format invalide. Valeurs acceptées: 'obj', 'stl', 'ply', 'glb'"
        )

    # Création de la tâche
    task_id = task_manager.create_task(
        task_type="generate_mesh",
        params={
            "session_id": request.session_id,
            "resolution": request.resolution,
            "output_format": request.output_format
        }
    )

    return {
        "task_id": task_id,
        "message": "Tâche de génération créée",
        "session_id": request.session_id,
        "images_count": image_count
    }

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
    # Déterminer le dossier source selon is_generated
    source_dir = DATA_GENERATED_MESHES if request.is_generated else DATA_INPUT
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
            "is_generated": request.is_generated
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
    Sert un fichier de maillage retopologisé depuis data/retopo pour la visualisation
    Convertit automatiquement en GLB pour de meilleures performances
    """
    file_path = DATA_RETOPO / filename

    # Si on demande un fichier GLB qui n'existe pas, essayer de le convertir depuis le fichier source
    if not file_path.exists() and filename.endswith('.glb'):
        # Chercher le fichier source (OBJ, STL, PLY, etc.)
        stem = file_path.stem
        for ext in ['.obj', '.stl', '.ply', '.off']:
            source_path = DATA_RETOPO / f"{stem}{ext}"
            if source_path.exists():
                print(f"  Converting {source_path.name} to GLB for visualization...")
                try:
                    result = convert_and_compress(
                        input_path=source_path,
                        output_path=file_path,
                        enable_draco=False,
                        compression_level=7
                    )
                    if result and result.get('success'):
                        print(f"  [OK] GLB created: {file_path.name}")
                        break
                    else:
                        print(f"  [WARNING] GLB conversion failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"  [WARNING] GLB conversion failed: {e}")

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

# Initialisation du gestionnaire de tâches
@app.on_event("startup")
async def startup_event():
    """Démarre le gestionnaire de tâches"""
    print("\n=== MeshSimplifier Backend Starting ===")

    # Valider la clé API Stability
    api_key = os.getenv('STABILITY_API_KEY')
    if not api_key:
        print("[!] WARNING: STABILITY_API_KEY not set - mesh generation will fail")
        print("    Create .env file and add: STABILITY_API_KEY=sk-your-key-here")
    elif not api_key.startswith('sk-'):
        print("[!] WARNING: STABILITY_API_KEY may be invalid (should start with 'sk-')")
    else:
        print(f"[OK] Stability API key loaded: {api_key[:10]}...")

    # Enregistrer les handlers de tâches
    task_manager.register_handler("simplify", simplify_task_handler)
    task_manager.register_handler("simplify_adaptive", adaptive_simplify_task_handler)
    task_manager.register_handler("generate_mesh", generate_mesh_task_handler)
    task_manager.register_handler("retopologize", retopologize_task_handler)
    task_manager.start()

    # Afficher les statistiques du cache GLB au démarrage
    print("\n [GLB CACHE] Statistics at startup:")
    stats = get_cache_stats(DATA_INPUT)
    print(f"  Total GLB files: {stats['total_glb_files']}")
    print(f"  Total size: {stats['total_size_mb']:.2f} MB")
    if stats['orphaned_count'] > 0:
        print(f"   Orphaned files: {stats['orphaned_count']}")
        print(f"     Use POST /cache/glb/cleanup to clean them up")

    print("=====================================\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Arrête proprement le gestionnaire de tâches"""
    task_manager.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
