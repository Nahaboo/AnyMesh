varying vec3 vWorldPosition;
varying vec3 vWorldNormal;
varying vec3 vViewDir;

void main() {
  vec3 N = normalize(vWorldNormal);
  vec3 V = normalize(vViewDir);

  // Fresnel: strong reflection at grazing angles, transparent when facing
  float NdotV = max(dot(N, V), 0.0);
  float fresnel = pow(1.0 - NdotV, 3.0);

  // Glass tint color (subtle blue-white)
  vec3 glassColor = vec3(0.85, 0.9, 0.95);

  // Fake environment reflection (hemisphere: sky above, dark below)
  vec3 reflected = reflect(-V, N);
  float skyBlend = reflected.y * 0.5 + 0.5;
  vec3 envColor = mix(vec3(0.15, 0.15, 0.2), vec3(0.6, 0.65, 0.75), skyBlend);

  // Specular highlight from key light
  vec3 L = normalize(vec3(1.0, 1.0, 1.0));
  vec3 H = normalize(L + V);
  float spec = pow(max(dot(N, H), 0.0), 128.0);

  // Combine: glass body + fresnel reflection + specular
  float baseOpacity = 0.12;
  float opacity = baseOpacity + fresnel * 0.6;

  vec3 color = glassColor * 0.3 + envColor * fresnel + vec3(1.0) * spec * 0.8;

  gl_FragColor = vec4(color, opacity);
}
