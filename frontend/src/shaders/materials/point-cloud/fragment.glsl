uniform bool uDepthFade;

varying vec3 vColor;
varying float vDepth;

void main() {
  // Create circular points
  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);

  // Discard pixels outside circle
  if (dist > 0.5) discard;

  // Soft edges with antialiasing
  float alpha = smoothstep(0.5, 0.3, dist);

  // Use the color from vertex shader (red=static, green=dynamic)
  vec3 finalColor = vColor;

  // Apply depth fade if enabled
  if (uDepthFade) {
    float depthFactor = clamp(1.0 - vDepth * 0.01, 0.3, 1.0);
    finalColor *= depthFactor;
  }

  gl_FragColor = vec4(finalColor, alpha);
}
