"""
Tests unitaires pour la fonctionnalité d'export de maillages
Tests de la conversion de format et de l'endpoint /export
"""

import pytest
from pathlib import Path
import trimesh
from src.converter import convert_mesh_format


@pytest.mark.unit
class TestConvertMeshFormat:
    """Tests unitaires pour la fonction convert_mesh_format"""

    def test_convert_obj_to_stl(self, sample_cube_obj, temp_output_dir):
        """Test conversion OBJ vers STL"""
        output_path = temp_output_dir / "cube.stl"

        result = convert_mesh_format(
            input_path=sample_cube_obj,
            output_path=output_path,
            output_format="stl"
        )

        # Vérifier le succès
        assert result['success'] is True
        assert output_path.exists()
        assert result['vertices'] > 0
        assert result['triangles'] > 0

        # Vérifier que le fichier STL est valide
        mesh = trimesh.load(str(output_path))
        assert hasattr(mesh, 'vertices')
        assert len(mesh.vertices) > 0

    def test_convert_obj_to_ply(self, sample_cube_obj, temp_output_dir):
        """Test conversion OBJ vers PLY"""
        output_path = temp_output_dir / "cube.ply"

        result = convert_mesh_format(
            input_path=sample_cube_obj,
            output_path=output_path,
            output_format="ply"
        )

        assert result['success'] is True
        assert output_path.exists()
        assert result['output_size'] > 0

        # Vérifier que le fichier PLY est valide
        mesh = trimesh.load(str(output_path))
        assert hasattr(mesh, 'faces')
        assert len(mesh.faces) > 0

    def test_convert_obj_to_glb(self, sample_cube_obj, temp_output_dir):
        """Test conversion OBJ vers GLB"""
        output_path = temp_output_dir / "cube.glb"

        result = convert_mesh_format(
            input_path=sample_cube_obj,
            output_path=output_path,
            output_format="glb"
        )

        assert result['success'] is True
        assert output_path.exists()
        assert result['conversion_time_ms'] > 0

        # Vérifier que le fichier GLB est valide
        loaded = trimesh.load(str(output_path))
        # GLB peut charger comme Scene, extraire le mesh
        if hasattr(loaded, 'geometry'):
            # C'est une Scene
            assert len(loaded.geometry) > 0
        else:
            # C'est directement un Mesh
            assert hasattr(loaded, 'vertices')

    def test_convert_stl_to_obj(self, sample_sphere_stl, temp_output_dir):
        """Test conversion STL vers OBJ"""
        output_path = temp_output_dir / "sphere.obj"

        result = convert_mesh_format(
            input_path=sample_sphere_stl,
            output_path=output_path,
            output_format="obj"
        )

        assert result['success'] is True
        assert output_path.exists()

        # Vérifier les statistiques
        assert 'vertices' in result
        assert 'triangles' in result
        assert result['vertices'] > 0
        assert result['triangles'] > 0

    def test_convert_ply_to_stl(self, sample_bunny_ply, temp_output_dir):
        """Test conversion PLY vers STL"""
        output_path = temp_output_dir / "bunny.stl"

        result = convert_mesh_format(
            input_path=sample_bunny_ply,
            output_path=output_path,
            output_format="stl"
        )

        assert result['success'] is True
        assert output_path.exists()

    def test_convert_invalid_file(self, sample_invalid_file, temp_output_dir):
        """Test conversion d'un fichier invalide"""
        output_path = temp_output_dir / "invalid.stl"

        result = convert_mesh_format(
            input_path=sample_invalid_file,
            output_path=output_path,
            output_format="stl"
        )

        # La conversion doit échouer proprement
        assert result['success'] is False
        assert 'error' in result

    def test_convert_nonexistent_file(self, temp_output_dir):
        """Test conversion d'un fichier qui n'existe pas"""
        input_path = temp_output_dir / "nonexistent.obj"
        output_path = temp_output_dir / "output.stl"

        result = convert_mesh_format(
            input_path=input_path,
            output_path=output_path,
            output_format="stl"
        )

        assert result['success'] is False
        assert 'error' in result

    def test_convert_all_formats(self, sample_cube_obj, temp_output_dir):
        """Test conversion vers tous les formats supportés"""
        formats = ['obj', 'stl', 'ply', 'glb']

        for fmt in formats:
            output_path = temp_output_dir / f"cube.{fmt}"

            result = convert_mesh_format(
                input_path=sample_cube_obj,
                output_path=output_path,
                output_format=fmt
            )

            assert result['success'] is True, f"Conversion to {fmt} failed"
            assert output_path.exists(), f"Output file {fmt} not created"


@pytest.mark.integration
class TestExportEndpoint:
    """Tests d'intégration pour l'endpoint /export"""

    def test_export_same_format(self, api_client, sample_cube_obj):
        """Test export dans le même format (pas de conversion)"""
        # Copier le fichier dans data/input
        import shutil
        from src.main import DATA_INPUT
        DATA_INPUT.mkdir(parents=True, exist_ok=True)
        test_file = DATA_INPUT / "test_cube.obj"
        shutil.copy(sample_cube_obj, test_file)

        try:
            # Exporter en OBJ (même format)
            response = api_client.get("/export/test_cube.obj?format=obj&is_generated=false")

            assert response.status_code == 200
            assert len(response.content) > 0
            # Devrait retourner le fichier original sans conversion
        finally:
            # Nettoyage
            if test_file.exists():
                test_file.unlink()

    def test_export_with_conversion(self, api_client, sample_cube_obj):
        """Test export avec conversion de format"""
        import shutil
        from src.main import DATA_INPUT
        DATA_INPUT.mkdir(parents=True, exist_ok=True)
        test_file = DATA_INPUT / "test_cube_convert.obj"
        shutil.copy(sample_cube_obj, test_file)

        try:
            # Exporter en STL (conversion requise)
            response = api_client.get("/export/test_cube_convert.obj?format=stl&is_generated=false")

            assert response.status_code == 200
            assert len(response.content) > 0

            # Vérifier que le fichier converti est valide STL
            from src.main import DATA_OUTPUT
            converted_file = DATA_OUTPUT / "test_cube_convert.stl"
            assert converted_file.exists()

            # Charger le fichier STL pour vérifier qu'il est valide
            mesh = trimesh.load(str(converted_file))
            assert hasattr(mesh, 'vertices')
            assert len(mesh.vertices) > 0
        finally:
            # Nettoyage
            if test_file.exists():
                test_file.unlink()

    def test_export_nonexistent_file(self, api_client):
        """Test export d'un fichier qui n'existe pas"""
        response = api_client.get("/export/nonexistent.obj?format=stl&is_generated=false")

        assert response.status_code == 404
        assert "non trouvé" in response.json()['detail'].lower()

    def test_export_all_formats(self, api_client, sample_cube_obj):
        """Test export vers tous les formats"""
        import shutil
        from src.main import DATA_INPUT
        DATA_INPUT.mkdir(parents=True, exist_ok=True)
        test_file = DATA_INPUT / "test_cube_all.obj"
        shutil.copy(sample_cube_obj, test_file)

        formats = ['obj', 'stl', 'ply', 'glb']

        try:
            for fmt in formats:
                response = api_client.get(
                    f"/export/test_cube_all.obj?format={fmt}&is_generated=false"
                )

                assert response.status_code == 200, f"Export to {fmt} failed"
                assert len(response.content) > 0, f"Export to {fmt} returned empty file"
        finally:
            # Nettoyage
            if test_file.exists():
                test_file.unlink()

    def test_export_generated_mesh(self, api_client, sample_cube_obj):
        """Test export d'un maillage généré"""
        import shutil
        from src.main import DATA_GENERATED_MESHES
        DATA_GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
        test_file = DATA_GENERATED_MESHES / "generated_test.obj"
        shutil.copy(sample_cube_obj, test_file)

        try:
            # Exporter avec is_generated=true
            response = api_client.get("/export/generated_test.obj?format=stl&is_generated=true")

            assert response.status_code == 200
            assert len(response.content) > 0
        finally:
            # Nettoyage
            if test_file.exists():
                test_file.unlink()

    def test_export_with_special_characters(self, api_client, sample_cube_obj):
        """Test export avec caractères spéciaux dans le nom (devrait échouer proprement)"""
        response = api_client.get("/export/invalid<>name.obj?format=stl&is_generated=false")

        # Devrait retourner 404 car le fichier n'existe pas
        assert response.status_code == 404


@pytest.mark.unit
class TestFormatPreservation:
    """Tests pour vérifier que les données du mesh sont préservées lors de la conversion"""

    def test_vertex_count_preservation(self, sample_cube_obj, temp_output_dir):
        """Vérifier que le nombre de vertices est préservé"""
        # Charger le mesh original
        original_mesh = trimesh.load(str(sample_cube_obj))
        original_vertices = len(original_mesh.vertices)

        # Convertir vers STL
        output_path = temp_output_dir / "cube_vertex_test.stl"
        result = convert_mesh_format(sample_cube_obj, output_path, "stl")

        assert result['success'] is True
        assert result['vertices'] == original_vertices

        # Vérifier en chargeant le fichier converti
        converted_mesh = trimesh.load(str(output_path))
        assert len(converted_mesh.vertices) == original_vertices

    def test_face_count_preservation(self, sample_cube_obj, temp_output_dir):
        """Vérifier que le nombre de faces est préservé"""
        original_mesh = trimesh.load(str(sample_cube_obj))
        original_faces = len(original_mesh.faces)

        output_path = temp_output_dir / "cube_face_test.ply"
        result = convert_mesh_format(sample_cube_obj, output_path, "ply")

        assert result['success'] is True
        assert result['triangles'] == original_faces

        converted_mesh = trimesh.load(str(output_path))
        assert len(converted_mesh.faces) == original_faces

    def test_geometry_preservation(self, sample_sphere_stl, temp_output_dir):
        """Vérifier que la géométrie est approximativement préservée"""
        original_mesh = trimesh.load(str(sample_sphere_stl))
        original_bounds = original_mesh.bounds

        output_path = temp_output_dir / "sphere_geometry_test.obj"
        result = convert_mesh_format(sample_sphere_stl, output_path, "obj")

        assert result['success'] is True

        converted_mesh = trimesh.load(str(output_path))
        converted_bounds = converted_mesh.bounds

        # Les bornes doivent être approximativement identiques
        import numpy as np
        assert np.allclose(original_bounds, converted_bounds, rtol=1e-5)
