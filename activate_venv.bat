@echo off
REM Script d'activation rapide du virtual environment
REM Usage: Double-cliquez sur ce fichier ou executez "activate_venv.bat" dans le terminal

echo ================================================
echo Activation du virtual environment MeshSimplifier
echo ================================================
echo.

REM Verifier si le venv existe
if not exist "venv\Scripts\activate.bat" (
    echo [ERREUR] Le virtual environment n'existe pas!
    echo Executez d'abord: python -m venv venv
    echo Puis: pip install -r requirement.txt
    pause
    exit /b 1
)

REM Activer le venv
call venv\Scripts\activate.bat

echo.
echo [OK] Virtual environment active!
echo.
echo Commandes disponibles:
echo   - python --version        : Verifier la version Python
echo   - pip list                : Lister les packages installes
echo   - uvicorn src.main:app --reload : Demarrer le backend
echo   - python test_open3d.py   : Tester Open3D
echo   - deactivate              : Desactiver le venv
echo.
echo ================================================
