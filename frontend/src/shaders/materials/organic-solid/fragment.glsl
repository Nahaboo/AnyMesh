// Uniforms
uniform vec3 uColor;
uniform vec3 uMouseHighlightColor;
uniform vec3 uLightDirection;

// Varyings
varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;
varying float vMouseInfluenceFactor;

void main() {
  // Smooth shading - use interpolated vertex normals (not face normals)
  vec3 normal = normalize(vNormal);

  // Normalize light direction
  vec3 lightDir = normalize(uLightDirection);

  // Diffuse lighting (Lambertian)
  float diffuse = max(dot(normal, lightDir), 0.0);

  // Specular lighting (Blinn-Phong)
  vec3 viewDir = normalize(vViewPosition);
  vec3 halfDir = normalize(lightDir + viewDir);
  float specular = pow(max(dot(normal, halfDir), 0.0), 32.0) * 0.3;

  // Ambient light
  float ambient = 0.3;

  // Combine lighting
  float lighting = ambient + diffuse * 0.7 + specular;

  // Mix base color with highlight color based on mouse influence
  vec3 baseColor = mix(uColor, uMouseHighlightColor, vMouseInfluenceFactor);

  // Apply lighting to color
  vec3 finalColor = baseColor * lighting;

  gl_FragColor = vec4(finalColor, 1.0);
}
