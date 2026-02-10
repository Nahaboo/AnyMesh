uniform sampler2D uColorMap;
uniform sampler2D uNormalMap;
uniform sampler2D uRoughnessMap;
uniform float uTextureScale;
uniform float uBlendSharpness;
uniform vec3 uLightDir;

varying vec3 vWorldPosition;
varying vec3 vWorldNormal;
varying vec3 vViewDir;

// Tri-planar blend weights from surface normal
vec3 getBlendWeights(vec3 normal) {
  vec3 blend = pow(abs(normal), vec3(uBlendSharpness));
  return blend / (blend.x + blend.y + blend.z);
}

// Sample a texture tri-planarly
vec4 triplanarSample(sampler2D tex, vec3 pos, vec3 blend) {
  vec4 xProj = texture2D(tex, pos.yz);
  vec4 yProj = texture2D(tex, pos.xz);
  vec4 zProj = texture2D(tex, pos.xy);
  return xProj * blend.x + yProj * blend.y + zProj * blend.z;
}

// Tri-planar normal mapping: tangent-space normals blended into world space
vec3 triplanarNormal(vec3 pos, vec3 blend, vec3 surfaceNormal) {
  vec3 nX = texture2D(uNormalMap, pos.yz).rgb * 2.0 - 1.0;
  vec3 nY = texture2D(uNormalMap, pos.xz).rgb * 2.0 - 1.0;
  vec3 nZ = texture2D(uNormalMap, pos.xy).rgb * 2.0 - 1.0;

  vec3 worldNX = vec3(nX.z, nX.y, nX.x) * sign(surfaceNormal.x);
  vec3 worldNY = vec3(nY.x, nY.z, nY.y) * sign(surfaceNormal.y);
  vec3 worldNZ = vec3(nZ.x, nZ.y, nZ.z) * sign(surfaceNormal.z);

  return normalize(
    surfaceNormal +
    worldNX * blend.x +
    worldNY * blend.y +
    worldNZ * blend.z
  );
}

void main() {
  vec3 N = normalize(vWorldNormal);
  vec3 V = normalize(vViewDir);
  vec3 L = normalize(uLightDir);

  vec3 pos = vWorldPosition * uTextureScale;
  vec3 blend = getBlendWeights(N);

  // Sample PBR textures via tri-planar projection
  vec3 albedo = triplanarSample(uColorMap, pos, blend).rgb;
  vec3 Np = triplanarNormal(pos, blend, N);
  float roughness = triplanarSample(uRoughnessMap, pos, blend).r;

  // --- Hemisphere ambient: sky (warm white) / ground (cool dark) ---
  vec3 skyColor = vec3(0.45, 0.45, 0.5);
  vec3 groundColor = vec3(0.15, 0.13, 0.12);
  float hemiBlend = dot(Np, vec3(0.0, 1.0, 0.0)) * 0.5 + 0.5;
  vec3 ambient = mix(groundColor, skyColor, hemiBlend);

  // --- Key light (main directional) ---
  float NdotL = max(dot(Np, L), 0.0);
  vec3 keyColor = vec3(1.0, 0.98, 0.95) * 0.6;

  // --- Fill light (opposite side, cooler) ---
  vec3 fillDir = normalize(vec3(-0.5, 0.3, -0.8));
  float NdotFill = max(dot(Np, fillDir), 0.0);
  vec3 fillColor = vec3(0.7, 0.75, 0.85) * 0.25;

  // --- Specular (Blinn-Phong, modulated by roughness) ---
  vec3 H = normalize(L + V);
  float NdotH = max(dot(Np, H), 0.0);
  float shininess = mix(256.0, 4.0, roughness);
  float spec = pow(NdotH, shininess);
  // Reduce specular intensity for rough surfaces
  float specIntensity = mix(0.5, 0.02, roughness);
  vec3 specular = vec3(1.0, 0.98, 0.95) * spec * specIntensity;

  // --- Combine ---
  vec3 color = albedo * (ambient + keyColor * NdotL + fillColor * NdotFill) + specular;

  // --- Fresnel rim ---
  float NdotV = max(dot(Np, V), 0.0);
  float fresnel = pow(1.0 - NdotV, 4.0);
  color += fresnel * vec3(0.08, 0.08, 0.1);

  gl_FragColor = vec4(color, 1.0);
}
