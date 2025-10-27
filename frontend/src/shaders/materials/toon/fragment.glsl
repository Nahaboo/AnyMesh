// Toon Shader - Fragment Shader
// Cel-shading avec quantification de la lumière

uniform vec3 uColor;
uniform int uLevels;
uniform float uOutlineThickness;
uniform vec3 uLightDirection;

varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;

void main() {
  // Normalize vectors
  vec3 normal = normalize(vNormal);
  vec3 viewDir = normalize(vViewPosition);
  vec3 lightDir = normalize(uLightDirection);

  // Calculate diffuse lighting
  float diffuse = max(dot(normal, lightDir), 0.0);

  // Quantize lighting into discrete levels (cel-shading effect)
  float levelStep = 1.0 / float(uLevels);
  float quantizedDiffuse = floor(diffuse / levelStep) * levelStep;

  // Add small offset to avoid pure black
  quantizedDiffuse = max(quantizedDiffuse, 0.2);

  // Calculate outline using fresnel-like effect
  float fresnel = 1.0 - abs(dot(viewDir, normal));
  float outline = smoothstep(uOutlineThickness - 0.01, uOutlineThickness, fresnel);

  // Mix color with lighting and outline
  vec3 finalColor = uColor * quantizedDiffuse;
  finalColor = mix(finalColor, vec3(0.0), outline);

  gl_FragColor = vec4(finalColor, 1.0);
}
