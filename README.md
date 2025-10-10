Projet de simplification et réparation de maillage en python et en utilisant la lib open3d.
Le traitement 3D sera fait en back end tandis que l'affichage se fera dans une app web a l'aide de React Three Fiber.

Les étapes du développement :

Architecture :
Etape a: mettre en place le backEnd
Backend : 
    - python avec FastAPI + Open3D
    - test les routes pour voir que les fichiers sont bien traités.

Etape b: mettre en place le frontEnd
FrontEnd : 
    - Web avec Three.js (React Three Fiber) pour l'affichage.
    - Intègre des appel a l'API pour charger les modèles dynamiquement.

Fonctionnalités:
Etape 1: 
    - Fonction de base : 
        *Upload de fichier (obj, stl, gltf, glb)
        *Visualisation des propriétés géométrique et topologique.
    
Etape 2:
    - Simplification du maillage (simplify.py): Simplifier le maillage avec open3d simplify_quadric_decimation. 
    - Ajout de l'option de simplification du maillage a l'interface utilisateur, avoir le paramètre de simplification en tant qu'option dans l'interface, avoir la possibilité de relancer la simplification.
    - Ajout dans l'interface une option de comparaison de maillage. Open3D permet de comparer visuellement des maillages avant et apres. Ajoute une fonction de comparaison.

Etape 3:
    - Script principal (mail.py) : crée un script pour tester la simplification avec une réduction de 70%. Un fichier obj est présent dans data/input

Etape 4: 
    - Ajoute un test pour vérifier que la simplification fonctionne c'est a dire que le nombre de triangle a diminué.