// Simplex Noise 3D function is injected from common/simplexNoise3D.glsl

// Uniforms
uniform float uTime;
uniform float uAmplitude;
uniform float uSpeed;
uniform float uFrequency;
uniform float uMeshScale;
uniform vec3 uMousePosition;
uniform float uMouseInfluence;
uniform float uMouseRadius;

// Varyings
varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;
varying float vMouseInfluenceFactor; // How much this vertex is affected by mouse

void main() {
  // Calculate world position for size-independent noise
  vec4 worldPos = modelMatrix * vec4(position, 1.0);

  // Normalize by mesh scale to make the effect truly scale-independent
  // This way, the same frequency/amplitude values work for all mesh sizes
  vec3 normalizedPos = worldPos.xyz / uMeshScale;
  vec3 noiseInput = normalizedPos * uFrequency;

  // Create multiple octaves of noise for more organic movement
  float noiseValue = 0.0;

  // Main wave - travels through space
  noiseValue += snoise(noiseInput + vec3(uTime * uSpeed, 0.0, 0.0)) * 0.5;

  // Secondary wave - travels in different direction for complexity
  noiseValue += snoise(noiseInput + vec3(0.0, uTime * uSpeed * 0.7, uTime * uSpeed * 0.5)) * 0.3;

  // Fine detail - faster, smaller waves
  noiseValue += snoise(noiseInput * 2.0 + vec3(uTime * uSpeed * 1.5)) * 0.2;

  // Scale amplitude by mesh scale so displacement is proportional to mesh size
  float scaledAmplitude = uAmplitude * uMeshScale;

  // Apply smooth clamping to prevent triangle flipping at high amplitudes
  // Use tanh for soft limiting: prevents extreme displacements while keeping smooth motion
  float displacement = noiseValue * scaledAmplitude;
  float maxDisplacement = 0.15; // Max safe displacement as ratio of mesh scale
  displacement = tanh(displacement / maxDisplacement) * maxDisplacement;

  // Displace vertex along normal with clamped displacement
  vec3 displacedPosition = position + normal * displacement;

  // Apply mouse interaction - push vertices along their normal (not towards cursor)
  vec4 displacedWorldPos = modelMatrix * vec4(displacedPosition, 1.0);

  // Initialize mouse influence factor (0 = no influence, 1 = full influence)
  vMouseInfluenceFactor = 0.0;

  // Check if mouse is actually hovering (position != [0,0,0])
  float mouseActive = step(0.001, length(uMousePosition));

  if (mouseActive > 0.5) {
    float distToMouse = distance(displacedWorldPos.xyz, uMousePosition);

    // Scale radius by mesh size for consistent behavior across different mesh sizes
    float scaledRadius = uMouseRadius * uMeshScale;

    // Only affect vertices within the radius (very local effect)
    if (distToMouse < scaledRadius) {
      // Smooth falloff - stronger near cursor, weaker at edges
      float mouseFactor = smoothstep(scaledRadius, 0.0, distToMouse);

      // Moderate exponential curve for organic but visible effect
      mouseFactor = pow(mouseFactor, 2.0);

      // Store the influence factor for fragment shader coloring
      vMouseInfluenceFactor = mouseFactor;

      // Push vertices along their normal direction (not towards cursor!)
      // This creates a smooth "bump" effect without distorting triangles
      vec3 worldNormal = normalize(mat3(modelMatrix) * normal);

      // Scale influence by mesh size as well
      float scaledInfluence = uMouseInfluence * uMeshScale;
      displacedPosition += worldNormal * mouseFactor * scaledInfluence;

      // Recalculate world position after normal displacement
      displacedWorldPos = modelMatrix * vec4(displacedPosition, 1.0);
    }
  }

  // Pass varyings to fragment shader (use interpolated normals for smooth shading)
  vWorldPosition = displacedWorldPos.xyz;
  vNormal = normalize(normalMatrix * normal);

  // Calculate view position for lighting
  vec4 mvPosition = viewMatrix * displacedWorldPos;
  vViewPosition = -mvPosition.xyz;

  // Final position
  gl_Position = projectionMatrix * mvPosition;
}
