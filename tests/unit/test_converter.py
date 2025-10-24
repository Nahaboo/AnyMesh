"""
Tests unitaires pour le module converter.py
Teste la conversion GLB et la compression Draco
"""

import pytest
from pathlib import Path
from src.converter import convert_to_glb, apply_draco_compression, convert_and_compress


class TestConvertToGLB:
    """Tests pour la fonction convert_to_glb"""

    def test_convert_obj_to_glb(self, sample_cube_obj, temp_output_dir):
        """Test de conversion OBJ vers GLB"""
        output_path = temp_output_dir / "cube.glb"

        result = convert_to_glb(sample_cube_obj, output_path)

        assert result['success'] is True
        assert output_path.exists()
        assert result['input_format'] == '.obj'
        assert result['vertices'] > 0
        assert result['triangles'] > 0
        assert result['output_size'] > 0

    def test_convert_stl_to_glb(self, sample_sphere_stl, temp_output_dir):
        """Test de conversion STL vers GLB"""
        output_path = temp_output_dir / "sphere.glb"

        result = convert_to_glb(sample_sphere_stl, output_path)

        assert result['success'] is True
        assert output_path.exists()
        assert result['input_format'] == '.stl'

    def test_convert_ply_to_glb(self, sample_bunny_ply, temp_output_dir):
        """Test de conversion PLY vers GLB"""
        output_path = temp_output_dir / "bunny.glb"

        result = convert_to_glb(sample_bunny_ply, output_path)

        assert result['success'] is True
        assert output_path.exists()
        assert result['input_format'] == '.ply'

    def test_convert_invalid_file(self, sample_invalid_file, temp_output_dir):
        """Test de conversion d'un fichier invalide (doit échouer)"""
        output_path = temp_output_dir / "invalid.glb"

        result = convert_to_glb(sample_invalid_file, output_path)

        assert result['success'] is False
        assert 'error' in result

    def test_convert_nonexistent_file(self, temp_output_dir):
        """Test de conversion d'un fichier qui n'existe pas"""
        input_path = Path("nonexistent.obj")
        output_path = temp_output_dir / "output.glb"

        result = convert_to_glb(input_path, output_path)

        assert result['success'] is False
        assert 'error' in result


class TestApplyDracoCompression:
    """Tests pour la fonction apply_draco_compression"""

    def test_compress_glb_with_draco(self, sample_cube_obj, temp_output_dir):
        """Test de compression Draco sur un GLB"""
        # D'abord convertir en GLB
        glb_path = temp_output_dir / "cube.glb"
        convert_result = convert_to_glb(sample_cube_obj, glb_path)
        assert convert_result['success']

        original_size = glb_path.stat().st_size

        # Compresser avec Draco
        result = apply_draco_compression(glb_path, compression_level=7)

        # Note: Ce test peut échouer si gltf-pipeline n'est pas installé
        if result['success']:
            assert glb_path.exists()
            compressed_size = glb_path.stat().st_size
            assert compressed_size <= original_size
            assert result['compression_ratio'] <= 1.0
            assert result['method'] == 'gltf-pipeline'
        else:
            # Si Draco n'est pas disponible, vérifier le message d'erreur
            assert 'error' in result
            assert 'gltf-pipeline' in result['error'].lower() or 'draco' in result['error'].lower()

    def test_compress_nonexistent_glb(self, temp_output_dir):
        """Test de compression d'un fichier GLB qui n'existe pas"""
        glb_path = temp_output_dir / "nonexistent.glb"

        result = apply_draco_compression(glb_path)

        assert result['success'] is False
        assert 'error' in result


class TestConvertAndCompress:
    """Tests pour la fonction convert_and_compress (pipeline complet)"""

    def test_full_pipeline_with_draco(self, sample_cube_obj, temp_output_dir):
        """Test du pipeline complet: conversion + compression"""
        output_path = temp_output_dir / "cube_compressed.glb"

        result = convert_and_compress(
            input_path=sample_cube_obj,
            output_path=output_path,
            enable_draco=True,
            compression_level=7
        )

        assert result['success'] is True
        assert output_path.exists()
        assert result['conversion']['success'] is True
        assert result['final_size'] > 0

        # Si Draco est disponible, vérifier la compression
        if result['compression'] and result['compression']['success']:
            assert result['compression']['compression_ratio'] < 1.0

    def test_full_pipeline_without_draco(self, sample_cube_obj, temp_output_dir):
        """Test du pipeline sans compression Draco"""
        output_path = temp_output_dir / "cube_uncompressed.glb"

        result = convert_and_compress(
            input_path=sample_cube_obj,
            output_path=output_path,
            enable_draco=False
        )

        assert result['success'] is True
        assert output_path.exists()
        assert result['conversion']['success'] is True
        assert result['compression'] is None  # Pas de compression

    def test_pipeline_with_invalid_file(self, sample_invalid_file, temp_output_dir):
        """Test du pipeline avec un fichier invalide"""
        output_path = temp_output_dir / "invalid.glb"

        result = convert_and_compress(
            input_path=sample_invalid_file,
            output_path=output_path,
            enable_draco=True
        )

        assert result['success'] is False
        assert 'error' in result
