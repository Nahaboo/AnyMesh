# Tests MeshSimplifier

Structure des tests pour le projet MeshSimplifier.

## Structure

```
tests/
├── conftest.py              # Configuration pytest et fixtures communes
├── fixtures/                # Fichiers 3D de test (générés automatiquement)
├── unit/                    # Tests unitaires
│   ├── test_converter.py    # Tests du module converter.py
│   └── test_simplify.py     # Tests du module simplify.py
└── integration/             # Tests d'intégration
    └── test_api.py          # Tests de l'API FastAPI complète
```

## Installation des Dépendances

Assurez-vous que pytest est installé:

```bash
pip install pytest pytest-cov
```

Pour les tests d'API, installez aussi:

```bash
pip install httpx  # Requis par TestClient de FastAPI
```

## Lancer les Tests

### Tous les tests

```bash
pytest
```

### Tests unitaires uniquement

```bash
pytest tests/unit/
```

### Tests d'intégration uniquement

```bash
pytest tests/integration/
```

### Test d'un module spécifique

```bash
pytest tests/unit/test_converter.py
```

### Avec couverture de code

```bash
pytest --cov=src --cov-report=html
```

Le rapport HTML sera généré dans `htmlcov/index.html`.

### Mode verbose

```bash
pytest -v
```

### Afficher les print statements

```bash
pytest -s
```

## Fixtures Disponibles

Les fixtures sont définies dans `conftest.py`:

- **`fixtures_dir`**: Chemin du dossier fixtures
- **`sample_cube_obj`**: Fichier OBJ de test (cube)
- **`sample_sphere_stl`**: Fichier STL de test (sphère)
- **`sample_bunny_ply`**: Fichier PLY de test (icosphère)
- **`sample_invalid_file`**: Fichier invalide pour tester la gestion d'erreurs
- **`temp_output_dir`**: Dossier temporaire nettoyé après chaque test
- **`api_client`**: Client de test FastAPI

## Écrire de Nouveaux Tests

### Test Unitaire

```python
import pytest
from src.converter import convert_to_glb

def test_my_feature(sample_cube_obj, temp_output_dir):
    """Description du test"""
    output_path = temp_output_dir / "output.glb"
    result = convert_to_glb(sample_cube_obj, output_path)

    assert result['success'] is True
    assert output_path.exists()
```

### Test d'Intégration API

```python
def test_my_endpoint(api_client, sample_cube_obj):
    """Test d'un endpoint API"""
    with open(sample_cube_obj, 'rb') as f:
        files = {'file': ('cube.obj', f, 'model/obj')}
        response = api_client.post('/upload', files=files)

    assert response.status_code == 200
    data = response.json()
    assert 'mesh_info' in data
```

## Notes Importantes

### Tests de Compression Draco

Les tests de compression Draco (`test_compress_glb_with_draco`) sont conçus pour fonctionner même si `gltf-pipeline` n'est pas installé. Ils vérifieront simplement que le message d'erreur approprié est retourné.

Pour tester la compression Draco complètement:

```bash
npm install -g gltf-pipeline
```

### Fichiers de Test

Les fichiers 3D de test (fixtures) sont générés automatiquement par pytest lors de la première exécution. Ils sont stockés dans `tests/fixtures/` et réutilisés pour les tests suivants.

Pour régénérer les fixtures, supprimez le dossier:

```bash
rm -rf tests/fixtures/
```

### Tests Asynchrones

L'API FastAPI utilise des tâches asynchrones (TaskManager). Les tests d'intégration peuvent nécessiter d'attendre que les tâches se terminent:

```python
import time

# Lancer la tâche
response = api_client.post('/simplify', json={...})
task_id = response.json()['task_id']

# Attendre la complétion
max_wait = 10  # secondes
for _ in range(max_wait):
    status = api_client.get(f'/tasks/{task_id}').json()
    if status['status'] in ['completed', 'failed']:
        break
    time.sleep(1)
```

## CI/CD

Pour intégrer ces tests dans un pipeline CI/CD (GitHub Actions, GitLab CI, etc.):

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirement.txt
      - run: pip install pytest pytest-cov httpx
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Erreur "ModuleNotFoundError: No module named 'src'"

Assurez-vous d'exécuter pytest depuis la racine du projet:

```bash
cd /path/to/MeshSimplifier
pytest
```

Ou ajoutez le projet au PYTHONPATH:

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/MeshSimplifier"
pytest
```

### Erreur "fixture 'api_client' not found"

Installez httpx:

```bash
pip install httpx
```

### Tests de Draco échouent

C'est normal si `gltf-pipeline` n'est pas installé. Les tests vérifient que l'erreur appropriée est retournée. Pour activer la compression Draco:

```bash
npm install -g gltf-pipeline
```
