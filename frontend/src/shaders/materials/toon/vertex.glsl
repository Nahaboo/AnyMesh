// Toon Shader - Vertex Shader
// Calcule les normales et la position pour le fragment shader

varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;

void main() {
  // Transform normal to view space
  vNormal = normalize(normalMatrix * normal);

  // Calculate view position
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  vViewPosition = -mvPosition.xyz;

  // Calculate world position
  vWorldPosition = (modelMatrix * vec4(position, 1.0)).xyz;

  // Standard projection
  gl_Position = projectionMatrix * mvPosition;
}
