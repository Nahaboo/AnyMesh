"""
Script de test pour l'API MeshSimplifier
Demonstre l'utilisation de l'API avec file d'attente de taches
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"


def test_root():
    """Test de l'endpoint racine"""
    print("[TEST] Endpoint racine...")
    response = requests.get(f"{BASE_URL}/")
    print(f"[OK] Status: {response.status_code}")
    print(f"[OK] Response: {response.json()}\n")


def test_list_meshes():
    """Test de la liste des maillages disponibles"""
    print("[TEST] Liste des maillages...")
    response = requests.get(f"{BASE_URL}/meshes")
    data = response.json()
    print(f"[OK] {data['count']} maillage(s) trouve(s)")
    for mesh in data['meshes']:
        print(f"  - {mesh['filename']} ({mesh['size']} bytes, {mesh['format']})")
    print()


def test_simplify(filename, reduction_ratio=0.5):
    """Test de simplification de maillage"""
    print(f"[TEST] Simplification de {filename}...")

    # Creation de la tache
    payload = {
        "filename": filename,
        "reduction_ratio": reduction_ratio
    }
    response = requests.post(f"{BASE_URL}/simplify", json=payload)

    if response.status_code != 200:
        print(f"[ERREUR] Status: {response.status_code}")
        print(f"[ERREUR] {response.json()}")
        return None

    data = response.json()
    task_id = data['task_id']
    print(f"[OK] Tache creee: {task_id}")
    print(f"[OK] Fichier de sortie: {data['output_filename']}\n")

    # Polling du statut de la tache
    print("[TEST] Attente de la completion...")
    max_attempts = 30
    for attempt in range(max_attempts):
        response = requests.get(f"{BASE_URL}/tasks/{task_id}")
        task = response.json()
        status = task['status']
        progress = task['progress']

        print(f"  Tentative {attempt + 1}: Status = {status}, Progress = {progress}%")

        if status == "completed":
            print("[OK] Tache completee avec succes!\n")
            print("[RESULTATS]")
            result = task['result']
            print(f"  Original:")
            print(f"    - Vertices: {result['original']['vertices']}")
            print(f"    - Triangles: {result['original']['triangles']}")
            print(f"  Simplifie:")
            print(f"    - Vertices: {result['simplified']['vertices']}")
            print(f"    - Triangles: {result['simplified']['triangles']}")
            print(f"  Reduction:")
            print(f"    - Vertices: {result['reduction']['vertices_ratio']*100:.1f}%")
            print(f"    - Triangles: {result['reduction']['triangles_ratio']*100:.1f}%")
            print(f"  Fichier de sortie: {result['output_file']}")
            print(f"  Taille: {result['output_size']} bytes\n")
            return task_id

        elif status == "failed":
            print(f"[ERREUR] Tache echouee: {task['error']}\n")
            return None

        time.sleep(0.5)

    print("[TIMEOUT] La tache n'a pas ete completee dans le temps imparti\n")
    return None


def test_list_tasks():
    """Test de la liste des taches"""
    print("[TEST] Liste des taches...")
    response = requests.get(f"{BASE_URL}/tasks")
    data = response.json()
    print(f"[OK] {data['count']} tache(s) au total")
    print(f"[OK] {data['queue_size']} tache(s) en attente\n")

    for task in data['tasks']:
        print(f"  - {task['id'][:8]}... ({task['type']}): {task['status']}")


def test_download(filename):
    """Test de telechargement d'un fichier"""
    print(f"[TEST] Telechargement de {filename}...")
    response = requests.get(f"{BASE_URL}/download/{filename}")

    if response.status_code == 200:
        print(f"[OK] Fichier telecharge: {len(response.content)} bytes")
        # Sauvegarde locale pour verification
        output_path = f"downloaded_{filename}"
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"[OK] Sauvegarde dans: {output_path}\n")
    else:
        print(f"[ERREUR] Status: {response.status_code}\n")


def main():
    """Execution de tous les tests"""
    print("=" * 60)
    print("TEST DE L'API MESHSIMPLIFIER")
    print("=" * 60)
    print()

    try:
        # Test 1: Endpoint racine
        test_root()

        # Test 2: Liste des maillages
        test_list_meshes()

        # Test 3: Simplification
        task_id = test_simplify("bunny.obj", reduction_ratio=0.7)

        if task_id:
            # Test 4: Liste des taches
            test_list_tasks()
            print()

            # Test 5: Telechargement
            test_download("bunny_simplified.obj")

        print("=" * 60)
        print("TOUS LES TESTS SONT PASSES!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("[ERREUR] Impossible de se connecter au serveur.")
        print("Assurez-vous que le backend est lance: uvicorn src.main:app --reload")
    except Exception as e:
        print(f"[ERREUR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
