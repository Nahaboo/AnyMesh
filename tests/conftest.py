"""
Configuration pytest pour les tests MeshSimplifier
Fournit des fixtures communes pour tous les tests
"""

import pytest
from pathlib import Path
import trimesh
import numpy as np


# Chemins des fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(exist_ok=True)


@pytest.fixture
def fixtures_dir():
    """Retourne le chemin du dossier fixtures"""
    return FIXTURES_DIR


@pytest.fixture
def sample_cube_obj(fixtures_dir):
    """
    Crée un fichier OBJ de test (cube simple)
    Retourne le chemin du fichier
    """
    cube_path = fixtures_dir / "cube.obj"

    if not cube_path.exists():
        # Créer un cube avec trimesh
        cube = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
        cube.export(str(cube_path))

    return cube_path


@pytest.fixture
def sample_sphere_stl(fixtures_dir):
    """
    Crée un fichier STL de test (sphère simple)
    Retourne le chemin du fichier
    """
    sphere_path = fixtures_dir / "sphere.stl"

    if not sphere_path.exists():
        # Créer une sphère avec trimesh
        sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        sphere.export(str(sphere_path))

    return sphere_path


@pytest.fixture
def sample_bunny_ply(fixtures_dir):
    """
    Crée un fichier PLY de test (lapin simple)
    Retourne le chemin du fichier
    """
    bunny_path = fixtures_dir / "bunny.ply"

    if not bunny_path.exists():
        # Créer un mesh simple pour le test
        # (Le vrai Stanford Bunny est trop gros pour un fixture)
        mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        mesh.export(str(bunny_path))

    return bunny_path


@pytest.fixture
def sample_invalid_file(fixtures_dir):
    """
    Crée un fichier invalide pour tester la gestion d'erreurs
    """
    invalid_path = fixtures_dir / "invalid.obj"

    if not invalid_path.exists():
        with open(invalid_path, 'w') as f:
            f.write("This is not a valid OBJ file\n")
            f.write("Just random text\n")

    return invalid_path


@pytest.fixture
def temp_output_dir(tmp_path):
    """
    Crée un dossier temporaire pour les fichiers de sortie des tests
    Nettoyé automatiquement après chaque test
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def api_client():
    """
    Fixture pour tester l'API FastAPI
    Retourne un TestClient
    """
    from fastapi.testclient import TestClient
    from src.main import app

    return TestClient(app)
