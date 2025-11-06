==============================================
INSTANT MESHES - Installation Instructions
==============================================

Location: tools/instant-meshes/
Executable: Instant Meshes.exe
Version: Latest from GitHub releases

==============================================
QUICK TEST
==============================================

Verify installation:
    "Instant Meshes.exe" --help

Test with dataset:
    "Instant Meshes.exe" -o test_output.obj -v 1000 datasets/bunny_botsch.ply

==============================================
BASIC USAGE
==============================================

Command structure:
    Instant Meshes.exe [options] input_file

Common examples:

1. Quad mesh with 5000 vertices:
    "Instant Meshes.exe" -o output.obj -v 5000 -D input.ply

2. Triangle mesh with 3000 vertices:
    "Instant Meshes.exe" -o output.obj -r 6 -v 3000 input.obj

3. Feature-aware retopology:
    "Instant Meshes.exe" -o output.obj -v 2000 -c 30 input.ply

==============================================
KEY FLAGS
==============================================

-o <file>      Output file (OBJ or PLY)
-v <count>     Target vertex count
-f <count>     Target face count
-D             Quad-dominant mode (mix of quads/tris/pentagons)
-r <2|4|6>     Rotation symmetry (4=quads, 6=triangles)
-c <degrees>   Crease angle threshold (default: 20)
-S <iter>      Smoothing iterations (default: 2)
-b             Align to boundaries (for open meshes)
-d             Deterministic mode (reproducible)

==============================================
SUPPORTED FORMATS
==============================================

Input:  OBJ, PLY, ALN
Output: OBJ, PLY

==============================================
DATASETS
==============================================

Test models available in datasets/:
- bunny_botsch.ply (55k vertices)
- bimba.ply
- botijo.ply
- carter.ply
- cube_twist.ply
- fandisk.ply
- And more...

==============================================
REFERENCES
==============================================

GitHub: https://github.com/wjakob/instant-meshes
Paper: "Instant Field-Aligned Meshes" (Jakob et al., 2015)
License: BSD 3-clause

==============================================
INTEGRATION WITH MESHSIMPLIFIER
==============================================

This tool will be integrated into the MeshSimplifier backend
for automated retopology via the web interface.

See: ../RETOPOLOGY_INTEGRATION_PLAN.md for details.

==============================================
