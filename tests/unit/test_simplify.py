"""
Tests unitaires pour le module simplify.py
Teste la simplification de maillages
"""

import pytest
from pathlib import Path
from src.simplify import simplify_mesh


class TestSimplifyMesh:
    """Tests pour la fonction simplify_mesh"""

    def test_simplify_with_target_triangles(self, sample_sphere_stl, temp_output_dir):
        """Test de simplification avec un nombre cible de triangles"""
        output_path = temp_output_dir / "sphere_simplified.stl"

        result = simplify_mesh(
            input_path=sample_sphere_stl,
            output_path=output_path,
            target_triangles=50,  # Réduire à 50 triangles
            preserve_boundary=True
        )

        assert result['success'] is True
        assert output_path.exists()
        assert result['simplified_triangles'] <= 70  # ~50 triangles (+/- marge plus large)
        assert result['simplified_triangles'] < result['original_triangles']

    def test_simplify_with_reduction_ratio(self, sample_bunny_ply, temp_output_dir):
        """Test de simplification avec un ratio de réduction"""
        output_path = temp_output_dir / "bunny_simplified.ply"

        result = simplify_mesh(
            input_path=sample_bunny_ply,
            output_path=output_path,
            reduction_ratio=0.5,  # Réduire de 50%
            preserve_boundary=True
        )

        assert result['success'] is True
        assert output_path.exists()
        assert result['simplified_triangles'] < result['original_triangles']
        # Vérifier que la réduction est approximativement 50%
        ratio = result['simplified_triangles'] / result['original_triangles']
        assert 0.3 <= ratio <= 0.7  # Marge de 20% (algorithme peut varier)

    def test_simplify_preserve_boundary(self, sample_cube_obj, temp_output_dir):
        """Test de simplification avec préservation des bords"""
        output_path = temp_output_dir / "cube_simplified.obj"

        result = simplify_mesh(
            input_path=sample_cube_obj,
            output_path=output_path,
            reduction_ratio=0.3,
            preserve_boundary=True
        )

        assert result['success'] is True
        assert output_path.exists()

    def test_simplify_nonexistent_file(self, temp_output_dir):
        """Test de simplification d'un fichier qui n'existe pas"""
        input_path = Path("nonexistent.obj")
        output_path = temp_output_dir / "output.obj"

        result = simplify_mesh(
            input_path=input_path,
            output_path=output_path,
            reduction_ratio=0.5
        )

        assert result['success'] is False
        assert 'error' in result

    def test_simplify_invalid_parameters(self, sample_cube_obj, temp_output_dir):
        """Test de simplification avec des paramètres invalides"""
        output_path = temp_output_dir / "cube_invalid.obj"

        # Ni target_triangles ni reduction_ratio fournis
        result = simplify_mesh(
            input_path=sample_cube_obj,
            output_path=output_path
        )

        assert result['success'] is False
        assert 'error' in result
