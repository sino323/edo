"""Procedural low-poly head (pure Python). Returns vertices, triangles and ring info
for the HUD. Model space: +z = face front, +y = up, head centre near y = 0."""
import math

# (y, half-width, half-depth)
RINGS = [(1.02, 0.0, 0.0), (0.98, .30, .34), (0.90, .52, .58), (0.78, .66, .74), (0.62, .74, .84),
         (0.45, .78, .88), (0.28, .79, .88), (0.10, .78, .86), (-0.08, .76, .86), (-0.25, .72, .82),
         (-0.42, .66, .76), (-0.58, .58, .68), (-0.72, .46, .54), (-0.80, .36, .40), (-0.88, .33, .34),
         (-1.10, .36, .36), (-1.30, .50, .44)]
ANGLES_DEG = [0, 8, 16, 24, 32, 40, 52, 66, 82, 100, 120, 140, 160, 180, 200, 220, 240, 260,
              278, 294, 308, 320, 328, 336, 344, 352]

def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi

def _radii(y):
    for i in range(len(RINGS) - 1):
        y0, a0, b0 = RINGS[i]
        y1, a1, b1 = RINGS[i + 1]
        if y1 <= y <= y0:
            t = (y0 - y) / (y0 - y1)
            return a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
    return RINGS[-1][1], RINGS[-1][2]

def _g(v, s):
    return math.exp(-(v / s) ** 2)

def _off(th, y):
    w = _wrap(th)
    o = 0.22 * math.exp(-((w / 0.17) ** 2 + ((y + 0.16) / 0.20) ** 2))           # nose
    o += 0.05 * _g(y - 0.22, 0.08) * _g(w, 0.6)                                    # brow
    for s in (-1, 1):
        o -= 0.07 * math.exp(-(((w - s * 0.42) / 0.16) ** 2 + ((y - 0.10) / 0.12) ** 2))  # eye sockets
    o += 0.03 * math.exp(-(((abs(w) - 0.7) / 0.2) ** 2 + ((y + 0.1) / 0.15) ** 2))  # cheeks
    o += 0.05 * math.exp(-((w / 0.22) ** 2 + ((y + 0.42) / 0.05) ** 2))             # lips
    o += 0.05 * math.exp(-((w / 0.2) ** 2 + ((y + 0.74) / 0.08) ** 2))              # chin
    o += 0.12 * math.exp(-(((abs(w) - 1.57) / 0.2) ** 2 + (y / 0.16) ** 2))         # ears
    return o

def vert(th, y):
    rx, rz = _radii(y)
    f = 1.0 + _off(th, y)
    return (rx * f * math.sin(th), y, rz * f * math.cos(th))

def build_head():
    angs = [math.radians(d) for d in ANGLES_DEG]
    n = len(angs)
    V = [vert(th, y) for (y, _, _) in RINGS for th in angs]
    T = []
    for k in range(len(RINGS) - 1):
        for j in range(n):
            j2 = (j + 1) % n
            a, b = k * n + j, k * n + j2
            c, d = (k + 1) * n + j, (k + 1) * n + j2
            for tri in ((a, c, b), (b, c, d)):
                p0, p1, p2 = (V[i] for i in tri)
                ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
                vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
                nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
                ln = math.sqrt(nx*nx + ny*ny + nz*nz)
                if ln < 1e-7:
                    continue
                nx, ny, nz = nx/ln, ny/ln, nz/ln
                cx = (p0[0]+p1[0]+p2[0]) / 3
                cz = (p0[2]+p1[2]+p2[2]) / 3
                if nx*cx + nz*cz < 0:           # make normals point outward
                    tri = (tri[0], tri[2], tri[1]); nx, ny, nz = -nx, -ny, -nz
                T.append((tri[0], tri[1], tri[2], nx, ny, nz, ((len(T) * 37) % 100 - 50) / 900.0))
    # rings ordered by wrapped angle (front in the middle) for contour lines
    order = sorted(range(n), key=lambda j: _wrap(angs[j]))
    return V, T, n, order

def eye_points():
    return [vert(-0.42, 0.10), vert(0.42, 0.10)]

def mouth_points(n=7, half=0.30, y=-0.42):
    return [vert(-half + 2 * half * i / (n - 1), y) for i in range(n)]
