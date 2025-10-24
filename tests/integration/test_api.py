"""
Tests d'intégration pour l'API FastAPI
Teste les endpoints complets avec conversion GLB
"""

import pytest
import io
from pathlib import Path


class TestUploadEndpoint:
    """Tests pour l'endpoint POST /upload"""

    def test_upload_obj_file(self, api_client, sample_cube_obj):
        """Test d'upload d'un fichier OBJ"""
        with open(sample_cube_obj, 'rb') as f:
            files = {'file': ('cube.obj', f, 'model/obj')}
            response = api_client.post('/upload', files=files)

        assert response.status_code == 200
        data = response.json()

        assert data['message'] == 'Fichier uploadé avec succès'
        assert 'mesh_info' in data
        assert data['mesh_info']['vertices_count'] > 0
        assert data['mesh_info']['triangles_count'] > 0

        # Vérifier que la conversion GLB a été effectuée
        assert 'conversion' in data
        if data['conversion'] and not data['conversion'].get('skipped'):
            assert 'glb_filename' in data['mesh_info']

    def test_upload_stl_file(self, api_client, sample_sphere_stl):
        """Test d'upload d'un fichier STL"""
        with open(sample_sphere_stl, 'rb') as f:
            files = {'file': ('sphere.stl', f, 'model/stl')}
            response = api_client.post('/upload', files=files)

        assert response.status_code == 200
        data = response.json()
        assert 'mesh_info' in data

    def test_upload_ply_file(self, api_client, sample_bunny_ply):
        """Test d'upload d'un fichier PLY"""
        with open(sample_bunny_ply, 'rb') as f:
            files = {'file': ('bunny.ply', f, 'application/ply')}
            response = api_client.post('/upload', files=files)

        assert response.status_code == 200
        data = response.json()
        assert 'mesh_info' in data

    def test_upload_invalid_format(self, api_client):
        """Test d'upload d'un format non supporté"""
        fake_file = io.BytesIO(b"fake content")
        files = {'file': ('test.txt', fake_file, 'text/plain')}
        response = api_client.post('/upload', files=files)

        assert response.status_code == 400
        assert 'non supporté' in response.json()['detail'].lower()

    def test_upload_invalid_file(self, api_client, sample_invalid_file):
        """Test d'upload d'un fichier invalide"""
        with open(sample_invalid_file, 'rb') as f:
            files = {'file': ('invalid.obj', f, 'model/obj')}
            response = api_client.post('/upload', files=files)

        assert response.status_code == 400


class TestMeshEndpoints:
    """Tests pour les endpoints de gestion des maillages"""

    def test_list_meshes(self, api_client):
        """Test de listage des maillages"""
        response = api_client.get('/meshes')

        assert response.status_code == 200
        data = response.json()
        assert 'meshes' in data
        assert 'count' in data

    def test_get_input_mesh(self, api_client, sample_cube_obj):
        """Test de récupération d'un fichier de maillage"""
        # D'abord uploader le fichier
        with open(sample_cube_obj, 'rb') as f:
            files = {'file': ('cube.obj', f, 'model/obj')}
            api_client.post('/upload', files=files)

        # Ensuite le récupérer
        response = api_client.get('/mesh/input/cube.obj')

        assert response.status_code == 200
        assert len(response.content) > 0

    def test_get_nonexistent_mesh(self, api_client):
        """Test de récupération d'un fichier qui n'existe pas"""
        response = api_client.get('/mesh/input/nonexistent.obj')

        assert response.status_code == 404


class TestSimplifyEndpoint:
    """Tests pour l'endpoint POST /simplify"""

    def test_simplify_with_reduction_ratio(self, api_client, sample_sphere_stl):
        """Test de simplification avec ratio de réduction"""
        # D'abord uploader le fichier
        with open(sample_sphere_stl, 'rb') as f:
            files = {'file': ('sphere.stl', f, 'model/stl')}
            api_client.post('/upload', files=files)

        # Lancer la simplification
        response = api_client.post('/simplify', json={
            'filename': 'sphere.stl',
            'reduction_ratio': 0.5,
            'preserve_boundary': True
        })

        assert response.status_code == 200
        data = response.json()
        assert 'task_id' in data
        assert 'output_filename' in data

        # Vérifier le statut de la tâche
        task_id = data['task_id']
        status_response = api_client.get(f'/tasks/{task_id}')
        assert status_response.status_code == 200

    def test_simplify_with_target_triangles(self, api_client, sample_cube_obj):
        """Test de simplification avec nombre cible de triangles"""
        # Uploader le fichier
        with open(sample_cube_obj, 'rb') as f:
            files = {'file': ('cube.obj', f, 'model/obj')}
            api_client.post('/upload', files=files)

        # Lancer la simplification
        response = api_client.post('/simplify', json={
            'filename': 'cube.obj',
            'target_triangles': 50
        })

        assert response.status_code == 200
        data = response.json()
        assert 'task_id' in data

    def test_simplify_nonexistent_file(self, api_client):
        """Test de simplification d'un fichier qui n'existe pas"""
        response = api_client.post('/simplify', json={
            'filename': 'nonexistent.obj',
            'reduction_ratio': 0.5
        })

        assert response.status_code == 404

    def test_simplify_glb_file_should_fail(self, api_client):
        """Test de simplification d'un fichier GLB (devrait échouer)"""
        # Note: Les fichiers GLB ne peuvent pas être simplifiés avec Trimesh
        response = api_client.post('/simplify', json={
            'filename': 'test.glb',
            'reduction_ratio': 0.5
        })

        # Devrait échouer car GLB n'est pas supporté pour la simplification
        assert response.status_code in [400, 404]


class TestHealthEndpoints:
    """Tests pour les endpoints de santé"""

    def test_root_endpoint(self, api_client):
        """Test de l'endpoint racine"""
        response = api_client.get('/')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'running'

    def test_health_check(self, api_client):
        """Test du health check"""
        response = api_client.get('/health')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'

    def test_list_tasks(self, api_client):
        """Test de listage des tâches"""
        response = api_client.get('/tasks')

        assert response.status_code == 200
        data = response.json()
        assert 'tasks' in data
        assert 'count' in data
        assert 'queue_size' in data
