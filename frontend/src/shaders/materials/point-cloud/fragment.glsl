// Uniforms
uniform vec3 uColor;
uniform bool uDepthFade;

// Varyings
varying float vDepth;
varying vec3 vColor;

void main() {
  // Create circular points (discard pixels outside circle)
  vec2 cxy = 2.0 * gl_PointCoord - 1.0;
  float dist = dot(cxy, cxy);

  // Discard fragments outside the circle
  if (dist > 1.0) {
    discard;
  }

  // Start with base color
  vec3 finalColor = uColor;

  // Optional: Apply depth-based fading
  if (uDepthFade) {
    // Fade points that are further away
    float depthFactor = 1.0 - clamp(vDepth * 0.5, 0.0, 0.8);
    finalColor *= depthFactor;
  }

  // Optional: Add soft edge to points (anti-aliasing)
  float alpha = 1.0 - smoothstep(0.7, 1.0, dist);

  // Output final color
  gl_FragColor = vec4(finalColor, alpha);
}
