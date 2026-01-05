"""Video Mapping - Warping transformations for perspective and mesh modes

Implements video mapping/warping as specified in Flow Studio exports:
- Perspective mode: 4-corner homography transformation
- Mesh mode: Grid-based triangulated warping
- Soft edge blending for multi-projector setups

Based on specifications from docs/flow-player-mapping-answers.md
"""

import logging
import math
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Point2D:
    """2D point with normalized coordinates (0.0-1.0)"""
    x: float = 0.0
    y: float = 0.0

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_pixel(self, width: int, height: int) -> Tuple[int, int]:
        """Convert normalized coords to pixel coords"""
        return (int(self.x * width), int(self.y * height))

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'Point2D':
        return cls(x=d.get('x', 0.0), y=d.get('y', 0.0))


@dataclass
class SoftEdgeConfig:
    """Soft edge blending configuration for multi-projector setups"""
    enabled: bool = False
    blend_width: int = 100  # pixels
    blend_width_percent: float = 5.0  # percentage
    gamma: float = 2.2  # gamma correction
    blend_curve: str = 'quadratic'  # linear, quadratic, cubic, sine
    black_level_compensation: int = 0  # 0-255
    brightness_balance: bool = False

    # Per-edge blend widths (in pixels)
    blend_left: int = 0
    blend_right: int = 0
    blend_top: int = 0
    blend_bottom: int = 0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SoftEdgeConfig':
        individual = d.get('individualBlendWidths', {})
        return cls(
            enabled=d.get('enabled', False),
            blend_width=d.get('blendWidth', 100),
            blend_width_percent=d.get('blendWidthPercent', 5.0),
            gamma=d.get('gamma', 2.2),
            blend_curve=d.get('blendCurve', 'quadratic'),
            black_level_compensation=d.get('blackLevelCompensation', 0),
            brightness_balance=d.get('brightnessBalance', False),
            blend_left=individual.get('left', 0),
            blend_right=individual.get('right', 0),
            blend_top=individual.get('top', 0),
            blend_bottom=individual.get('bottom', 0),
        )


@dataclass
class PerspectivePoints:
    """4 corner points for perspective transformation"""
    top_left: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))
    top_right: Point2D = field(default_factory=lambda: Point2D(1.0, 0.0))
    bottom_left: Point2D = field(default_factory=lambda: Point2D(0.0, 1.0))
    bottom_right: Point2D = field(default_factory=lambda: Point2D(1.0, 1.0))

    def is_deformed(self) -> bool:
        """Check if corners are moved from default positions"""
        eps = 0.001
        return (
            abs(self.top_left.x) > eps or abs(self.top_left.y) > eps or
            abs(self.top_right.x - 1.0) > eps or abs(self.top_right.y) > eps or
            abs(self.bottom_left.x) > eps or abs(self.bottom_left.y - 1.0) > eps or
            abs(self.bottom_right.x - 1.0) > eps or abs(self.bottom_right.y - 1.0) > eps
        )

    def to_list(self) -> List[Tuple[float, float]]:
        """Return corners as list: [TL, TR, BL, BR]"""
        return [
            self.top_left.to_tuple(),
            self.top_right.to_tuple(),
            self.bottom_left.to_tuple(),
            self.bottom_right.to_tuple(),
        ]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'PerspectivePoints':
        return cls(
            top_left=Point2D.from_dict(d.get('topLeft', {'x': 0, 'y': 0})),
            top_right=Point2D.from_dict(d.get('topRight', {'x': 1, 'y': 0})),
            bottom_left=Point2D.from_dict(d.get('bottomLeft', {'x': 0, 'y': 1})),
            bottom_right=Point2D.from_dict(d.get('bottomRight', {'x': 1, 'y': 1})),
        )


@dataclass
class MeshGridData:
    """Mesh grid for advanced warping - NxM grid of control points"""
    rows: int = 1  # Number of cells vertically
    cols: int = 1  # Number of cells horizontally
    points: List[List[Point2D]] = field(default_factory=list)

    def __post_init__(self):
        # Initialize default grid if empty
        if not self.points:
            self.points = self._create_default_grid()

    def _create_default_grid(self) -> List[List[Point2D]]:
        """Create uniformly distributed grid points"""
        grid = []
        for r in range(self.rows + 1):
            row = []
            for c in range(self.cols + 1):
                row.append(Point2D(
                    x=c / self.cols if self.cols > 0 else 0,
                    y=r / self.rows if self.rows > 0 else 0
                ))
            grid.append(row)
        return grid

    def get_point(self, row: int, col: int) -> Point2D:
        """Get point at (row, col)"""
        if 0 <= row < len(self.points) and 0 <= col < len(self.points[row]):
            return self.points[row][col]
        # Return expected default position
        return Point2D(
            x=col / self.cols if self.cols > 0 else 0,
            y=row / self.rows if self.rows > 0 else 0
        )

    def is_deformed(self) -> bool:
        """Check if any point is moved from default position"""
        eps = 0.001
        for r, row in enumerate(self.points):
            for c, point in enumerate(row):
                expected_x = c / self.cols if self.cols > 0 else 0
                expected_y = r / self.rows if self.rows > 0 else 0
                if abs(point.x - expected_x) > eps or abs(point.y - expected_y) > eps:
                    return True
        return False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'MeshGridData':
        rows = d.get('rows', 1)
        cols = d.get('cols', 1)

        # Parse points from nested list
        points_data = d.get('points', [])
        points = []
        for row_data in points_data:
            row = []
            for point_data in row_data:
                if isinstance(point_data, dict):
                    row.append(Point2D.from_dict(point_data))
                else:
                    row.append(Point2D())
            points.append(row)

        mesh = cls(rows=rows, cols=cols, points=points if points else [])
        return mesh


class HomographyCalculator:
    """Calculate homography matrix for perspective transformation

    Uses Direct Linear Transform (DLT) algorithm to compute
    the 3x3 homography matrix from 4 point correspondences.
    """

    @staticmethod
    def calculate(src_points: List[Tuple[float, float]],
                  dst_points: List[Tuple[float, float]]) -> List[List[float]]:
        """Calculate homography matrix from source to destination points

        Args:
            src_points: 4 source points [(x,y), ...] - typically unit square corners
            dst_points: 4 destination points [(x,y), ...] - warped positions

        Returns:
            3x3 homography matrix as nested list
        """
        # Build the 8x9 matrix A for Ah = 0
        A = []
        for (sx, sy), (dx, dy) in zip(src_points, dst_points):
            A.append([-sx, -sy, -1, 0, 0, 0, sx*dx, sy*dx, dx])
            A.append([0, 0, 0, -sx, -sy, -1, sx*dy, sy*dy, dy])

        # Solve using pseudo-inverse (simple implementation without numpy)
        # For production, use numpy.linalg.svd
        try:
            H = HomographyCalculator._solve_homography(A)
            return H
        except Exception as e:
            logger.warning(f"Homography calculation failed: {e}, using identity")
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    @staticmethod
    def _solve_homography(A: List[List[float]]) -> List[List[float]]:
        """Solve homography using SVD (simplified for small matrices)

        For robust implementation, use numpy:
            _, _, V = np.linalg.svd(A)
            H = V[-1].reshape(3, 3)
            return H / H[2, 2]
        """
        # Simple implementation using Gaussian elimination
        # This is a simplified solver for the 8x9 system
        # In production, use numpy or scipy

        try:
            import numpy as np
            A_np = np.array(A)
            _, _, V = np.linalg.svd(A_np)
            H = V[-1].reshape(3, 3)
            H = H / H[2, 2]  # Normalize
            return H.tolist()
        except ImportError:
            # Fallback: return identity matrix
            logger.warning("numpy not available for homography calculation")
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


class MeshTriangulator:
    """Generate triangles from mesh grid for rendering

    Converts a grid of control points into triangles for
    GPU-based texture mapping with proper UV coordinates.
    """

    @staticmethod
    def triangulate(mesh: MeshGridData) -> List[Dict[str, Any]]:
        """Convert mesh grid to triangle list

        Each cell becomes 2 triangles:
        p00 ---- p10     Triangle 1: p00 -> p01 -> p10
        |  \      |      Triangle 2: p10 -> p01 -> p11
        |    \    |
        p01 ---- p11

        Returns:
            List of triangles, each with 'vertices' and 'uvs'
        """
        triangles = []

        for r in range(mesh.rows):
            for c in range(mesh.cols):
                # Get 4 corners of the cell
                p00 = mesh.get_point(r, c)
                p10 = mesh.get_point(r, c + 1)
                p01 = mesh.get_point(r + 1, c)
                p11 = mesh.get_point(r + 1, c + 1)

                # Calculate UV coordinates (normalized to cell)
                u0 = c / mesh.cols
                u1 = (c + 1) / mesh.cols
                v0 = r / mesh.rows
                v1 = (r + 1) / mesh.rows

                # Triangle 1: p00 -> p01 -> p10
                triangles.append({
                    'vertices': [p00.to_tuple(), p01.to_tuple(), p10.to_tuple()],
                    'uvs': [(u0, v0), (u0, v1), (u1, v0)],
                })

                # Triangle 2: p10 -> p01 -> p11
                triangles.append({
                    'vertices': [p10.to_tuple(), p01.to_tuple(), p11.to_tuple()],
                    'uvs': [(u1, v0), (u0, v1), (u1, v1)],
                })

        return triangles


class VideoMappingEngine:
    """Main engine for video mapping transformations

    Supports:
    - Perspective mode (4-corner homography)
    - Mesh mode (grid-based triangulation)
    - Soft edge blending
    """

    def __init__(self):
        self.mode = 'perspective'
        self.perspective_points: Optional[PerspectivePoints] = None
        self.mesh_grid: Optional[MeshGridData] = None
        self.soft_edge: Optional[SoftEdgeConfig] = None
        self.background_color = '#000000'
        self.target_resolution = {'width': 1920, 'height': 1080}

    def configure_perspective(self, points: PerspectivePoints):
        """Configure perspective mode with corner points"""
        self.mode = 'perspective'
        self.perspective_points = points

    def configure_mesh(self, mesh: MeshGridData):
        """Configure mesh mode with grid"""
        self.mode = 'mesh'
        self.mesh_grid = mesh

    def configure_soft_edge(self, config: SoftEdgeConfig):
        """Configure soft edge blending"""
        self.soft_edge = config

    def is_deformed(self) -> bool:
        """Check if any warping is applied"""
        if self.mode == 'perspective' and self.perspective_points:
            return self.perspective_points.is_deformed()
        elif self.mode == 'mesh' and self.mesh_grid:
            return self.mesh_grid.is_deformed()
        return False

    def get_homography_matrix(self) -> Optional[List[List[float]]]:
        """Get homography matrix for perspective mode"""
        if self.mode != 'perspective' or not self.perspective_points:
            return None

        # Source: unit square corners
        src = [(0, 0), (1, 0), (0, 1), (1, 1)]
        dst = self.perspective_points.to_list()

        return HomographyCalculator.calculate(src, dst)

    def get_triangles(self) -> Optional[List[Dict[str, Any]]]:
        """Get triangles for mesh mode"""
        if self.mode != 'mesh' or not self.mesh_grid:
            return None

        return MeshTriangulator.triangulate(self.mesh_grid)

    def generate_mpv_vf(self, width: int, height: int) -> Optional[str]:
        """Generate MPV video filter string for transformation

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Video filter string for MPV's vf property
        """
        if self.mode == 'perspective' and self.perspective_points:
            return self._generate_perspective_vf(width, height)
        elif self.mode == 'mesh' and self.mesh_grid:
            return self._generate_mesh_vf(width, height)
        return None

    def _generate_perspective_vf(self, width: int, height: int) -> str:
        """Generate perspective transformation filter

        Uses FFmpeg's perspective filter via lavfi:
        perspective=x0:y0:x1:y1:x2:y2:x3:y3
        Points order: top-left, top-right, bottom-left, bottom-right
        """
        pp = self.perspective_points

        # Convert normalized coords to pixel expressions
        # Using W and H for source dimensions
        tl = f"{pp.top_left.x}*W:{pp.top_left.y}*H"
        tr = f"{pp.top_right.x}*W:{pp.top_right.y}*H"
        bl = f"{pp.bottom_left.x}*W:{pp.bottom_left.y}*H"
        br = f"{pp.bottom_right.x}*W:{pp.bottom_right.y}*H"

        # FFmpeg perspective filter
        vf = f"lavfi=[perspective={tl}:{tr}:{bl}:{br}:interpolation=linear]"

        return vf

    def _generate_mesh_vf(self, width: int, height: int) -> str:
        """Generate mesh warping filter

        For mesh warping, we need a more complex approach:
        1. Use FFmpeg's xbr/hqx filters (limited)
        2. Or generate a displacement map
        3. Or use custom OpenGL shader in MPV

        The cleanest approach is using MPV's OpenGL shaders.
        """
        # For complex mesh warping, generate a remap filter with displacement
        # This is a simplified version using multiple crop/pad operations
        # Full implementation requires custom shader

        if not self.mesh_grid or not self.mesh_grid.is_deformed():
            return ""

        # Generate displace filter using remap
        # This requires generating LUT images for X and Y displacement
        # For now, return a placeholder that logs a warning
        logger.warning("Mesh mode requires OpenGL shader - using fallback")

        # Fallback: use perspective with mesh corner points
        corners = [
            self.mesh_grid.get_point(0, 0),
            self.mesh_grid.get_point(0, self.mesh_grid.cols),
            self.mesh_grid.get_point(self.mesh_grid.rows, 0),
            self.mesh_grid.get_point(self.mesh_grid.rows, self.mesh_grid.cols),
        ]

        tl = f"{corners[0].x}*W:{corners[0].y}*H"
        tr = f"{corners[1].x}*W:{corners[1].y}*H"
        bl = f"{corners[2].x}*W:{corners[2].y}*H"
        br = f"{corners[3].x}*W:{corners[3].y}*H"

        return f"lavfi=[perspective={tl}:{tr}:{bl}:{br}:interpolation=linear]"

    def generate_glsl_shader(self) -> str:
        """Generate OpenGL ES 2.0 fragment shader for warping

        This shader can be used with MPV's --vo=gpu and custom shaders.
        """
        if self.mode == 'perspective':
            return self._generate_perspective_shader()
        elif self.mode == 'mesh':
            return self._generate_mesh_shader()
        return ""

    def _generate_perspective_shader(self) -> str:
        """Generate GLSL shader for perspective transformation"""
        pp = self.perspective_points

        # Homography matrix calculation in shader
        shader = f"""
//!HOOK MAIN
//!BIND HOOKED
//!DESC Flow Perspective Warp

// Corner points (normalized 0-1)
const vec2 tl = vec2({pp.top_left.x}, {pp.top_left.y});
const vec2 tr = vec2({pp.top_right.x}, {pp.top_right.y});
const vec2 bl = vec2({pp.bottom_left.x}, {pp.bottom_left.y});
const vec2 br = vec2({pp.bottom_right.x}, {pp.bottom_right.y});

vec2 bilinear_interp(vec2 uv) {{
    // Bilinear interpolation of corner positions
    vec2 top = mix(tl, tr, uv.x);
    vec2 bottom = mix(bl, br, uv.x);
    return mix(top, bottom, uv.y);
}}

vec4 hook() {{
    vec2 pos = HOOKED_pos;

    // Inverse mapping: find source UV for this output position
    // This is an approximation - true inverse requires solving
    vec2 src_uv = bilinear_interp(pos);

    // Check bounds
    if (src_uv.x < 0.0 || src_uv.x > 1.0 || src_uv.y < 0.0 || src_uv.y > 1.0) {{
        return vec4(0.0, 0.0, 0.0, 1.0);  // Background color
    }}

    return HOOKED_tex(src_uv);
}}
"""
        return shader

    def _generate_mesh_shader(self) -> str:
        """Generate GLSL shader for mesh warping

        This creates a shader that does bilinear interpolation
        within each mesh cell to warp the texture.
        """
        if not self.mesh_grid:
            return ""

        mesh = self.mesh_grid

        # Generate uniform array for mesh points
        points_str = ""
        for r in range(mesh.rows + 1):
            for c in range(mesh.cols + 1):
                p = mesh.get_point(r, c)
                points_str += f"const vec2 p_{r}_{c} = vec2({p.x}, {p.y});\n"

        shader = f"""
//!HOOK MAIN
//!BIND HOOKED
//!DESC Flow Mesh Warp

const int ROWS = {mesh.rows};
const int COLS = {mesh.cols};

// Mesh control points
{points_str}

vec2 get_mesh_point(int r, int c) {{
    // This would be better as a uniform array
    // Simplified lookup for generated code
"""

        # Generate switch cases for point lookup
        for r in range(mesh.rows + 1):
            for c in range(mesh.cols + 1):
                shader += f"    if (r == {r} && c == {c}) return p_{r}_{c};\n"

        shader += """    return vec2(float(c) / float(COLS), float(r) / float(ROWS));
}

vec4 hook() {
    vec2 pos = HOOKED_pos;

    // Find which cell we're in
    float cell_x = pos.x * float(COLS);
    float cell_y = pos.y * float(ROWS);

    int c = int(floor(cell_x));
    int r = int(floor(cell_y));

    // Clamp to valid range
    c = clamp(c, 0, COLS - 1);
    r = clamp(r, 0, ROWS - 1);

    // Local coordinates within cell (0-1)
    float u = fract(cell_x);
    float v = fract(cell_y);

    // Get 4 corners of this cell
    vec2 p00 = get_mesh_point(r, c);
    vec2 p10 = get_mesh_point(r, c + 1);
    vec2 p01 = get_mesh_point(r + 1, c);
    vec2 p11 = get_mesh_point(r + 1, c + 1);

    // Bilinear interpolation
    vec2 top = mix(p00, p10, u);
    vec2 bottom = mix(p01, p11, u);
    vec2 src_uv = mix(top, bottom, v);

    // Check bounds
    if (src_uv.x < 0.0 || src_uv.x > 1.0 || src_uv.y < 0.0 || src_uv.y > 1.0) {
        return vec4(0.0, 0.0, 0.0, 1.0);
    }

    return HOOKED_tex(src_uv);
}
"""
        return shader

    def generate_soft_edge_shader(self) -> str:
        """Generate GLSL shader for soft edge blending"""
        if not self.soft_edge or not self.soft_edge.enabled:
            return ""

        se = self.soft_edge
        width = self.target_resolution.get('width', 1920)
        height = self.target_resolution.get('height', 1080)

        # Convert pixel blend widths to normalized
        blend_left = se.blend_left / width if se.blend_left > 0 else 0
        blend_right = se.blend_right / width if se.blend_right > 0 else 0
        blend_top = se.blend_top / height if se.blend_top > 0 else 0
        blend_bottom = se.blend_bottom / height if se.blend_bottom > 0 else 0

        # Blend curve function
        curve_func = {
            'linear': 't',
            'quadratic': 't * t',
            'cubic': 't * t * t',
            'sine': 'sin(t * 3.14159 / 2.0)',
        }.get(se.blend_curve, 't * t')

        shader = f"""
//!HOOK OUTPUT
//!BIND HOOKED
//!DESC Flow Soft Edge Blending

const float GAMMA = {se.gamma};
const float BLEND_LEFT = {blend_left};
const float BLEND_RIGHT = {blend_right};
const float BLEND_TOP = {blend_top};
const float BLEND_BOTTOM = {blend_bottom};

float blend_curve(float t) {{
    return {curve_func};
}}

vec4 hook() {{
    vec2 pos = HOOKED_pos;
    vec4 color = HOOKED_tex(pos);

    float alpha = 1.0;

    // Left edge
    if (BLEND_LEFT > 0.0 && pos.x < BLEND_LEFT) {{
        float t = pos.x / BLEND_LEFT;
        alpha *= pow(blend_curve(t), 1.0 / GAMMA);
    }}

    // Right edge
    if (BLEND_RIGHT > 0.0 && pos.x > (1.0 - BLEND_RIGHT)) {{
        float t = (1.0 - pos.x) / BLEND_RIGHT;
        alpha *= pow(blend_curve(t), 1.0 / GAMMA);
    }}

    // Top edge
    if (BLEND_TOP > 0.0 && pos.y < BLEND_TOP) {{
        float t = pos.y / BLEND_TOP;
        alpha *= pow(blend_curve(t), 1.0 / GAMMA);
    }}

    // Bottom edge
    if (BLEND_BOTTOM > 0.0 && pos.y > (1.0 - BLEND_BOTTOM)) {{
        float t = (1.0 - pos.y) / BLEND_BOTTOM;
        alpha *= pow(blend_curve(t), 1.0 / GAMMA);
    }}

    color.rgb *= alpha;
    color.a *= alpha;

    return color;
}}
"""
        return shader

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'VideoMappingEngine':
        """Create engine from VideoMappingConfig dict"""
        engine = cls()

        engine.mode = config.get('mode', 'perspective')
        engine.background_color = config.get('background_color', '#000000')

        if config.get('target_resolution'):
            engine.target_resolution = config['target_resolution']

        # Parse perspective points
        pp = config.get('perspective_points', {})
        if pp:
            engine.perspective_points = PerspectivePoints.from_dict(pp)
        else:
            # Try tuple format from VideoMappingConfig
            engine.perspective_points = PerspectivePoints(
                top_left=Point2D(*config.get('top_left', (0, 0))),
                top_right=Point2D(*config.get('top_right', (1, 0))),
                bottom_left=Point2D(*config.get('bottom_left', (0, 1))),
                bottom_right=Point2D(*config.get('bottom_right', (1, 1))),
            )

        # Parse mesh grid
        mg = config.get('mesh_grid', {})
        if mg and mg.get('points'):
            engine.mesh_grid = MeshGridData.from_dict(mg)

        # Parse soft edge
        se = config.get('soft_edge', {})
        if se:
            engine.soft_edge = SoftEdgeConfig.from_dict(se)

        return engine


def create_mapping_from_project_config(mapping_config) -> Optional[VideoMappingEngine]:
    """Create VideoMappingEngine from project's VideoMappingConfig

    Args:
        mapping_config: VideoMappingConfig from project_loader

    Returns:
        Configured VideoMappingEngine or None if not enabled
    """
    if not mapping_config or not mapping_config.enabled:
        return None

    engine = VideoMappingEngine()
    engine.mode = mapping_config.mode
    engine.background_color = mapping_config.background_color

    if mapping_config.target_resolution:
        engine.target_resolution = mapping_config.target_resolution

    # Configure perspective points
    engine.perspective_points = PerspectivePoints(
        top_left=Point2D(*mapping_config.top_left),
        top_right=Point2D(*mapping_config.top_right),
        bottom_left=Point2D(*mapping_config.bottom_left),
        bottom_right=Point2D(*mapping_config.bottom_right),
    )

    # Configure mesh grid if present
    if mapping_config.mesh_grid:
        points = []
        for row in mapping_config.mesh_grid.points:
            point_row = []
            for p in row:
                if isinstance(p, dict):
                    point_row.append(Point2D.from_dict(p))
                else:
                    point_row.append(Point2D())
            points.append(point_row)

        engine.mesh_grid = MeshGridData(
            rows=mapping_config.mesh_grid.rows,
            cols=mapping_config.mesh_grid.cols,
            points=points,
        )

    return engine
