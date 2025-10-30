// Simplex Noise 3D function is injected from common/simplexNoise3D.glsl

uniform float uTime;
uniform float uSizeStatic;
uniform float uSizeDynamic;
uniform vec3 uColorStatic;
uniform vec3 uColorDynamic;
uniform float uAmplitude;
uniform float uFrequency;
uniform float uSpeed;
uniform float uDepthOffset;
uniform float uMeshScale;
uniform float uIsStatic;
uniform int uMotionMode; // 0=Waves, 1=Pulse, 2=Turbulence, 3=Flow, 4=Breathe

varying vec3 vColor;
varying float vDepth;

// Helper function: calculate displacement based on motion mode
float calculateDisplacement(vec3 pos, vec3 normal) {
  float t = uTime * uSpeed;
  vec3 scaledPos = pos / uMeshScale;
  float displacement = 0.0;

  // Scale amplitude relative to mesh size for consistent visual effect
  float scaledAmplitude = uAmplitude * uMeshScale;

  if (uMotionMode == 0) {
    // MODE 0: WAVES - Multi-directional sine waves
    float wave1 = sin(scaledPos.y * uFrequency + t) * scaledAmplitude;
    float wave2 = sin(scaledPos.x * uFrequency * 0.7 + t * 0.8) * scaledAmplitude * 0.6;
    float wave3 = cos(scaledPos.z * uFrequency * 0.5 + t * 1.2) * scaledAmplitude * 0.4;

    // Add some noise variation
    vec3 noiseCoord = scaledPos * uFrequency * 0.3 + vec3(t * 0.2, 0.0, 0.0);
    float noiseVal = snoise(noiseCoord) * 0.3 + 0.7; // [0.4, 1.0]

    displacement = (wave1 + wave2 + wave3) * noiseVal;

  } else if (uMotionMode == 1) {
    // MODE 1: PULSE - Radial pulsation from center
    float distFromCenter = length(scaledPos);
    float pulse = sin(distFromCenter * uFrequency - t * 2.0) * scaledAmplitude;

    // Add breathing effect
    float breathe = sin(t * 0.5) * 0.3 + 0.7; // [0.4, 1.0]

    displacement = pulse * breathe;

  } else if (uMotionMode == 2) {
    // MODE 2: TURBULENCE - Chaotic multi-octave noise
    vec3 noiseCoord1 = scaledPos * uFrequency * 0.5 + vec3(t * 0.3, t * 0.2, 0.0);
    vec3 noiseCoord2 = scaledPos * uFrequency * 1.5 + vec3(0.0, t * 0.5, t * 0.4);
    vec3 noiseCoord3 = scaledPos * uFrequency * 3.0 + vec3(t * 0.7, 0.0, t * 0.6);

    float noise1 = snoise(noiseCoord1) * 0.5;
    float noise2 = snoise(noiseCoord2) * 0.3;
    float noise3 = snoise(noiseCoord3) * 0.2;

    displacement = (noise1 + noise2 + noise3) * scaledAmplitude;

  } else if (uMotionMode == 3) {
    // MODE 3: FLOW - Flowing fluid motion
    vec3 flowCoord = scaledPos * uFrequency * 0.4;

    // Create flowing pattern with offset noise samples
    float flow1 = snoise(flowCoord + vec3(t * 0.5, 0.0, 0.0));
    float flow2 = snoise(flowCoord + vec3(0.0, t * 0.3, t * 0.4));

    // Swirl effect
    float angle = atan(scaledPos.z, scaledPos.x);
    float swirl = sin(angle * 3.0 + t) * 0.3;

    displacement = (flow1 * 0.6 + flow2 * 0.4 + swirl) * scaledAmplitude;

  } else if (uMotionMode == 4) {
    // MODE 4: BREATHE - Organic breathing with local variations
    // Global breathing
    float globalBreathe = sin(t * 0.7) * 0.5 + 0.5; // [0, 1]

    // Local noise variations
    vec3 noiseCoord = scaledPos * uFrequency * 0.6 + vec3(t * 0.15, 0.0, 0.0);
    float localNoise = snoise(noiseCoord) * 0.5 + 0.5; // [0, 1]

    // Distance-based modulation
    float distFromCenter = length(scaledPos);
    float distModulation = sin(distFromCenter * uFrequency * 0.5 - t * 0.5) * 0.5 + 0.5;

    displacement = scaledAmplitude * globalBreathe * localNoise * distModulation;
  }

  return displacement;
}

void main() {
  vec3 pos = position;
  vec3 norm = normalize(normal);

  bool isStatic = uIsStatic > 0.5;

  // Scale depth offset relative to mesh size for consistent visual effect
  float scaledDepthOffset = uDepthOffset * uMeshScale;

  if (isStatic) {
    // === STATIC LAYER ===
    gl_PointSize = uSizeStatic;
    vColor = uColorStatic;

  } else {
    // === DYNAMIC LAYER ===

    // Calculate displacement based on selected motion mode
    float displacement = calculateDisplacement(pos, norm);

    // Apply displacement along normal + scaled depth offset
    pos += norm * (displacement + scaledDepthOffset);

    // Dynamic point appearance with color variation based on displacement
    gl_PointSize = uSizeDynamic;

    // Color variation: interpolate based on displacement intensity
    float intensity = abs(displacement) / (uAmplitude * uMeshScale);
    intensity = clamp(intensity, 0.0, 1.0);
    vColor = mix(uColorDynamic * 0.7, uColorDynamic * 1.3, intensity);
  }

  // Calculate depth for fade effect
  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  vDepth = -mvPosition.z;

  gl_Position = projectionMatrix * mvPosition;
}
