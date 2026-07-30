import { useEffect, useRef, useState } from 'react'

const VERT = `
attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`

const FRAG = `
precision highp float;

uniform float u_time;
uniform vec2 u_res;
uniform float u_reduce;

varying vec2 v_uv;

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
  float n = hash21(p);
  return vec2(n, hash21(p + n));
}

/* Sharp star disc + soft bloom */
float starDisk(vec2 f, float size) {
  float d = length(f);
  float core = smoothstep(size, size * 0.15, d);
  float bloom = exp(-d * d * (18.0 / max(size, 0.01))) * 0.55;
  return core + bloom;
}

float starsAt(vec2 uv, float t, float reduce) {
  float sum = 0.0;

  // Dense far layer
  {
    float scale = 55.0;
    vec2 guv = uv * scale;
    vec2 id = floor(guv);
    vec2 f = fract(guv) - 0.5;
    for (int y = -1; y <= 1; y++) {
      for (int x = -1; x <= 1; x++) {
        vec2 cell = id + vec2(float(x), float(y));
        float n = hash21(cell);
        if (n > 0.955) {
          vec2 offs = (hash22(cell) - 0.5) * 0.7;
          float size = 0.018 + hash21(cell + 2.1) * 0.03;
          float tw = 0.7 + 0.3 * sin(t * (1.4 + n * 2.5) + n * 50.0);
          if (reduce > 0.5) tw = 0.9;
          sum += starDisk(f - offs - vec2(float(x), float(y)), size) * tw * (0.5 + n * 0.5);
        }
      }
    }
  }

  // Brighter sparse layer
  {
    float scale = 22.0;
    vec2 guv = uv * scale;
    vec2 id = floor(guv);
    vec2 f = fract(guv) - 0.5;
    for (int y = -1; y <= 1; y++) {
      for (int x = -1; x <= 1; x++) {
        vec2 cell = id + vec2(float(x), float(y));
        float n = hash21(cell + 9.7);
        if (n > 0.975) {
          vec2 offs = (hash22(cell + 3.3) - 0.5) * 0.55;
          float size = 0.03 + hash21(cell + 4.4) * 0.05;
          float tw = 0.75 + 0.25 * sin(t * (0.9 + n) + n * 30.0);
          if (reduce > 0.5) tw = 0.95;
          sum += starDisk(f - offs - vec2(float(x), float(y)), size) * tw * 1.25;
        }
      }
    }
  }

  return clamp(sum, 0.0, 2.2);
}

/* Height field for calm close-up water */
float waterHeight(vec2 p, float t) {
  float h = 0.0;
  h += sin(p.x * 6.0 + t * 0.45) * cos(p.y * 4.5 + t * 0.38) * 0.55;
  h += sin(p.x * 11.0 - t * 0.52 + p.y * 3.0) * 0.28;
  h += cos(p.y * 9.5 + t * 0.41 - p.x * 2.0) * 0.24;
  h += sin((p.x + p.y) * 3.5 + t * 0.22) * 0.35;
  h += cos((p.x * 1.7 - p.y) * 5.0 - t * 0.33) * 0.18;
  return h;
}

void main() {
  vec2 uv = v_uv;
  float aspect = u_res.x / max(u_res.y, 1.0);
  vec2 p = (uv - 0.5) * vec2(aspect, 1.0);

  float t = u_time;
  if (u_reduce > 0.5) t = 1.2;

  // Analytic normals from height field (camera almost overhead)
  float e = 0.0025;
  float h = waterHeight(p, t);
  float hx = waterHeight(p + vec2(e, 0.0), t);
  float hy = waterHeight(p + vec2(0.0, e), t);
  vec3 normal = normalize(vec3((h - hx) / e, (h - hy) / e, 1.35));

  // Reflect view (looking down) into night sky
  vec3 viewDir = vec3(0.0, 0.0, 1.0);
  vec3 refl = reflect(-viewDir, normal);
  vec2 skyUv = refl.xy * 0.55 + vec2(0.5, 0.42);
  skyUv += p * 0.12;

  float star = starsAt(skyUv, t, u_reduce);

  // Deep night water body
  vec3 deep = vec3(0.015, 0.02, 0.035);
  vec3 shallow = vec3(0.04, 0.07, 0.1);
  float depthMix = clamp(0.55 + p.y * 0.35 + h * 0.04, 0.0, 1.0);
  vec3 water = mix(deep, shallow, depthMix);

  // Soft night horizon band in reflection
  float band = exp(-pow((skyUv.y - 0.4) * 5.0, 2.0));
  water += vec3(0.03, 0.06, 0.12) * band * 0.55;

  // Star reflections
  vec3 starCool = vec3(0.82, 0.9, 1.0);
  vec3 starMint = vec3(0.45, 0.95, 0.78);
  water += starCool * star * 0.95;
  water += starMint * star * 0.12;

  // Specular from overhead moonlight + Libro.UZ lime/teal
  vec3 lightDir = normalize(vec3(0.15, 0.35, 0.9));
  float ndl = max(dot(normal, lightDir), 0.0);
  float spec = pow(ndl, 64.0);
  float specWide = pow(ndl, 12.0);
  water += vec3(0.7, 0.85, 1.0) * spec * 0.45;
  water += vec3(0.84, 1.0, 0.27) * spec * 0.18;
  water += vec3(0.18, 0.82, 0.61) * specWide * 0.08;

  // Subtle caustic shimmer on surface
  float caustic = sin((p.x * 18.0 + h) + t * 0.6) * sin((p.y * 16.0 - h) + t * 0.5);
  water += vec3(0.2, 0.45, 0.4) * max(caustic, 0.0) * 0.03;

  // Fresnel: brighter glancing reflections near screen edges
  float fres = pow(1.0 - max(dot(normal, viewDir), 0.0), 2.2);
  water = mix(water, water + vec3(0.05, 0.08, 0.12), fres * 0.35);

  // Vignette — close camera over dark water
  float vig = smoothstep(1.25, 0.2, length((uv - 0.5) * vec2(1.15, 1.05)));
  water *= mix(0.5, 1.0, vig);

  // Micro grain
  float grain = (hash21(gl_FragCoord.xy + t * 40.0) - 0.5) * 0.018;
  if (u_reduce > 0.5) grain = 0.0;
  water += grain;

  gl_FragColor = vec4(water, 1.0);
}
`

function createShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type)
  if (!shader) throw new Error('shader create failed')
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader)
    gl.deleteShader(shader)
    throw new Error(info || 'shader compile failed')
  }
  return shader
}

function createProgram(gl: WebGLRenderingContext, vertSrc: string, fragSrc: string): WebGLProgram {
  const vs = createShader(gl, gl.VERTEX_SHADER, vertSrc)
  const fs = createShader(gl, gl.FRAGMENT_SHADER, fragSrc)
  const program = gl.createProgram()
  if (!program) throw new Error('program create failed')
  gl.attachShader(program, vs)
  gl.attachShader(program, fs)
  gl.linkProgram(program)
  gl.deleteShader(vs)
  gl.deleteShader(fs)
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program)
    gl.deleteProgram(program)
    throw new Error(info || 'program link failed')
  }
  return program
}

/**
 * Full-screen night water surface with reflected stars (WebGL).
 * Falls back to a static CSS layer if WebGL is unavailable.
 */
export default function NightWaterCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let gl: WebGLRenderingContext | null
    try {
      gl = canvas.getContext('webgl', {
        alpha: false,
        antialias: false,
        depth: false,
        stencil: false,
        powerPreference: 'high-performance',
      })
    } catch {
      gl = null
    }

    if (!gl) {
      setFailed(true)
      return undefined
    }

    const surface: HTMLCanvasElement = canvas
    const glCtx: WebGLRenderingContext = gl
    let program: WebGLProgram | undefined
    let buffer: WebGLBuffer | null = null
    let raf = 0
    let disposed = false

    try {
      program = createProgram(glCtx, VERT, FRAG)
    } catch (err) {
      console.warn('[NightWaterCanvas]', err)
      setFailed(true)
      return undefined
    }

    buffer = glCtx.createBuffer()
    glCtx.bindBuffer(glCtx.ARRAY_BUFFER, buffer)
    glCtx.bufferData(
      glCtx.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      glCtx.STATIC_DRAW
    )

    const aPos = glCtx.getAttribLocation(program, 'a_pos')
    const uTime = glCtx.getUniformLocation(program, 'u_time')
    const uRes = glCtx.getUniformLocation(program, 'u_res')
    const uReduce = glCtx.getUniformLocation(program, 'u_reduce')

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const w = window.innerWidth
      const h = window.innerHeight
      surface.width = Math.floor(w * dpr)
      surface.height = Math.floor(h * dpr)
      surface.style.width = `${w}px`
      surface.style.height = `${h}px`
      glCtx.viewport(0, 0, surface.width, surface.height)
    }

    function draw(now: number) {
      if (disposed) return
      glCtx.useProgram(program!)
      glCtx.bindBuffer(glCtx.ARRAY_BUFFER, buffer)
      glCtx.enableVertexAttribArray(aPos)
      glCtx.vertexAttribPointer(aPos, 2, glCtx.FLOAT, false, 0, 0)
      glCtx.uniform1f(uTime, now * 0.001)
      glCtx.uniform2f(uRes, surface.width, surface.height)
      glCtx.uniform1f(uReduce, reduceMotion ? 1.0 : 0.0)
      glCtx.drawArrays(glCtx.TRIANGLES, 0, 6)
      if (!reduceMotion) {
        raf = requestAnimationFrame(draw)
      }
    }

    resize()
    draw(performance.now())
    window.addEventListener('resize', resize)

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      if (buffer) glCtx.deleteBuffer(buffer)
      if (program) glCtx.deleteProgram(program)
    }
  }, [])

  if (failed) {
    return <div className="splash__water-fallback" aria-hidden="true" />
  }

  return (
    <canvas
      ref={canvasRef}
      className="splash__water"
      aria-hidden="true"
    />
  )
}
