"""
core/document_parser.py
Handles extracting plain text from uploaded engineering documents.

Supported formats:
  Documents : PDF, DOCX, TXT, MD, RTF, CSV
  3D Models : STL, OBJ, GLTF, GLB, PLY, 3MF, STEP, STP
               → parsed with trimesh for full geometry analysis
               → GLTF/GLB also extract embedded JSON annotations

Multiple files are handled upstream (routes/api.py merges their texts).
"""

import io
import json
import struct

import PyPDF2
import docx


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_text(file) -> str:
    """
    Extract plain text from a werkzeug FileStorage object.
    Dispatches to the appropriate parser based on file extension.
    Raises ValueError if the file type is unsupported or the result is empty.
    """
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        text = _parse_pdf(file)
    elif filename.endswith(".docx"):
        text = _parse_docx(file)
    elif any(filename.endswith(ext) for ext in (".txt", ".md", ".text", ".markdown", ".rtf", ".csv")):
        text = _parse_plain(file)
    elif any(filename.endswith(ext) for ext in (".stl", ".obj", ".ply", ".3mf")):
        text = _parse_mesh_trimesh(file, filename)
    elif filename.endswith(".glb") or filename.endswith(".gltf"):
        text = _parse_gltf(file, filename)
    elif filename.endswith(".step") or filename.endswith(".stp"):
        text = _parse_step(file)
    else:
        # Best-effort UTF-8 decode for anything else
        text = _parse_plain(file, strict=False)

    if not text.strip():
        raise ValueError(
            "The document appears to be empty or contains no extractable text. "
            "Make sure it is a text-based file (not a scanned image PDF) or a "
            "supported 3D model format (STL, OBJ, GLTF, GLB, PLY, 3MF, STEP)."
        )

    return text


# ---------------------------------------------------------------------------
# Document parsers
# ---------------------------------------------------------------------------

def _parse_pdf(file) -> str:
    try:
        reader = PyPDF2.PdfReader(file)
        pages = []
        for page in reader.pages:
            raw = page.extract_text()
            if raw:
                pages.append(raw.strip())
        return "\n\n".join(pages)
    except Exception as exc:
        raise ValueError(f"PDF parsing failed: {exc}") from exc


def _parse_docx(file) -> str:
    try:
        doc = docx.Document(file)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as exc:
        raise ValueError(f"DOCX parsing failed: {exc}") from exc


def _parse_plain(file, strict: bool = True) -> str:
    try:
        raw = file.read()
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        if strict:
            raise ValueError("File is not valid UTF-8 text.")
        return raw.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# 3D model parsers
# ---------------------------------------------------------------------------

def _parse_mesh_trimesh(file, filename: str) -> str:
    """
    Use trimesh to load STL / OBJ / PLY / 3MF and extract:
      - File name and format
      - Vertex count, face count, edge count
      - Bounding box dimensions
      - Volume and surface area (if watertight)
      - Mesh health: watertight, winding consistency, degenerate faces
      - Object / component names (for multi-body files)
    """
    try:
        import trimesh
    except ImportError:
        raise ValueError(
            "trimesh is not installed. Run: pip install trimesh numpy"
        )

    try:
        raw_bytes = file.read()
        ext = filename.rsplit(".", 1)[-1].lower()
        mesh_or_scene = trimesh.load(
            io.BytesIO(raw_bytes),
            file_type=ext,
            force="mesh",
        )
    except Exception as exc:
        raise ValueError(f"3D model loading failed ({filename}): {exc}") from exc

    # Normalise to a list of (name, mesh) tuples
    import trimesh as _tm
    if isinstance(mesh_or_scene, _tm.Scene):
        meshes = list(mesh_or_scene.geometry.items())
        scene_name = filename
    elif isinstance(mesh_or_scene, _tm.Trimesh):
        meshes = [(filename, mesh_or_scene)]
        scene_name = filename
    else:
        meshes = [(filename, mesh_or_scene)]
        scene_name = filename

    lines = [
        f"=== 3D MODEL GEOMETRY REPORT ===",
        f"File       : {filename}",
        f"Format     : {filename.rsplit('.', 1)[-1].upper()}",
        f"Components : {len(meshes)}",
        "",
    ]

    total_verts = 0
    total_faces = 0

    for obj_name, mesh in meshes:
        lines.append(f"--- Component: {obj_name} ---")

        if not hasattr(mesh, "vertices"):
            lines.append("  (non-mesh geometry — skipped)")
            lines.append("")
            continue

        verts = len(mesh.vertices)
        faces = len(mesh.faces)
        total_verts += verts
        total_faces += faces

        bounds = mesh.bounds  # [[xmin,ymin,zmin],[xmax,ymax,zmax]]
        dims   = bounds[1] - bounds[0]

        lines.append(f"  Vertices          : {verts:,}")
        lines.append(f"  Faces             : {faces:,}")
        lines.append(f"  Edges (unique)    : {len(mesh.edges_unique):,}")
        lines.append(f"  Bounding box (mm) : {dims[0]:.3f} × {dims[1]:.3f} × {dims[2]:.3f}")

        is_watertight = bool(mesh.is_watertight)
        lines.append(f"  Watertight        : {is_watertight}")

        if is_watertight:
            lines.append(f"  Volume            : {mesh.volume:.4f} mm³")
            lines.append(f"  Surface area      : {mesh.area:.4f} mm²")
            # Derived density-ready metric
            lines.append(f"  Volume/Area ratio : {(mesh.volume / mesh.area):.4f}")
        else:
            lines.append(f"  Surface area      : {mesh.area:.4f} mm²")
            lines.append("  Volume            : N/A (mesh is not watertight)")

        # Winding / normal consistency
        is_consistent = bool(mesh.is_winding_consistent)
        lines.append(f"  Winding consistent: {is_consistent}")

        # Degenerate faces
        degen = int((mesh.area_faces == 0).sum())
        lines.append(f"  Degenerate faces  : {degen}")
        if degen > 0:
            lines.append(f"  ⚠ WARNING: {degen} degenerate (zero-area) faces detected — may cause manufacturing issues.")

        # Euler number / genus
        try:
            euler = mesh.euler_number
            genus = (2 - euler) // 2
            lines.append(f"  Euler number      : {euler}")
            lines.append(f"  Topological genus : {genus}")
        except Exception:
            pass

        # Body count (connected components)
        try:
            components = mesh.split(only_watertight=False)
            lines.append(f"  Connected bodies  : {len(components)}")
            if len(components) > 1:
                lines.append(f"  ℹ Multi-body mesh — {len(components)} separate solid(s).")
        except Exception:
            pass

        lines.append("")

    lines.append(f"=== TOTALS ===")
    lines.append(f"  Total vertices : {total_verts:,}")
    lines.append(f"  Total faces    : {total_faces:,}")
    lines.append("")
    lines.append(
        "NOTE: All units are assumed to be millimetres unless the source file "
        "specifies otherwise. This report is suitable for engineering review."
    )

    return "\n".join(lines)


def _parse_gltf(file, filename: str) -> str:
    """
    For GLTF (JSON) and GLB (binary) files:
      1. Extract embedded JSON metadata, node names, material names, extras.
      2. Run trimesh geometry analysis on all mesh primitives.
    """
    lines = [f"=== GLTF/GLB FILE REPORT ===", f"File: {filename}", ""]

    raw_bytes = file.read()

    # ── 1. JSON metadata extraction ──────────────────────────────────────
    try:
        if filename.endswith(".glb"):
            json_data = _extract_glb_json(raw_bytes)
        else:
            json_data = json.loads(raw_bytes.decode("utf-8", errors="ignore"))

        if json_data:
            lines.append("--- Embedded JSON Metadata ---")

            # Asset block
            asset = json_data.get("asset", {})
            if asset:
                lines.append(f"  glTF version   : {asset.get('version', 'unknown')}")
                lines.append(f"  Generator      : {asset.get('generator', 'unknown')}")
                lines.append(f"  Copyright      : {asset.get('copyright', 'none')}")
                extras = asset.get("extras", {})
                if extras:
                    lines.append(f"  Asset extras   : {json.dumps(extras, indent=2)}")

            # Scene nodes (object names)
            nodes = json_data.get("nodes", [])
            if nodes:
                node_names = [n.get("name", f"node_{i}") for i, n in enumerate(nodes)]
                lines.append(f"  Scene nodes ({len(nodes)}): {', '.join(node_names[:30])}")
                if len(node_names) > 30:
                    lines.append(f"    … and {len(node_names) - 30} more nodes")

            # Materials
            materials = json_data.get("materials", [])
            if materials:
                mat_names = [m.get("name", f"material_{i}") for i, m in enumerate(materials)]
                lines.append(f"  Materials ({len(materials)}): {', '.join(mat_names[:20])}")
                for mat in materials[:10]:
                    extras = mat.get("extras", {})
                    if extras:
                        lines.append(f"    {mat.get('name', '?')} extras: {json.dumps(extras)}")

            # Meshes
            meshes_json = json_data.get("meshes", [])
            if meshes_json:
                mesh_names = [m.get("name", f"mesh_{i}") for i, m in enumerate(meshes_json)]
                lines.append(f"  Mesh objects ({len(meshes_json)}): {', '.join(mesh_names[:20])}")

            # Animations
            animations = json_data.get("animations", [])
            if animations:
                anim_names = [a.get("name", f"anim_{i}") for i, a in enumerate(animations)]
                lines.append(f"  Animations ({len(animations)}): {', '.join(anim_names)}")

            # Top-level extras (custom annotations)
            top_extras = json_data.get("extras", {})
            if top_extras:
                lines.append(f"  Top-level extras: {json.dumps(top_extras, indent=2)}")

            lines.append("")

    except Exception as exc:
        lines.append(f"  (JSON metadata extraction failed: {exc})")
        lines.append("")

    # ── 2. Trimesh geometry analysis ─────────────────────────────────────
    try:
        import trimesh
        ext = "glb" if filename.endswith(".glb") else "gltf"
        mesh_or_scene = trimesh.load(
            io.BytesIO(raw_bytes),
            file_type=ext,
        )
        lines.append("--- Geometry Analysis (trimesh) ---")

        if isinstance(mesh_or_scene, trimesh.Scene):
            for name, geom in mesh_or_scene.geometry.items():
                if hasattr(geom, "vertices"):
                    lines.append(f"  Mesh: {name}")
                    lines.append(f"    Vertices      : {len(geom.vertices):,}")
                    lines.append(f"    Faces         : {len(geom.faces):,}")
                    dims = geom.bounds[1] - geom.bounds[0]
                    lines.append(f"    Bounding box  : {dims[0]:.3f} × {dims[1]:.3f} × {dims[2]:.3f}")
                    lines.append(f"    Watertight    : {geom.is_watertight}")
                    degen = int((geom.area_faces == 0).sum())
                    if degen:
                        lines.append(f"    ⚠ Degenerate faces: {degen}")
                    lines.append("")
        elif hasattr(mesh_or_scene, "vertices"):
            m = mesh_or_scene
            lines.append(f"  Vertices  : {len(m.vertices):,}")
            lines.append(f"  Faces     : {len(m.faces):,}")
            dims = m.bounds[1] - m.bounds[0]
            lines.append(f"  Bounding box : {dims[0]:.3f} × {dims[1]:.3f} × {dims[2]:.3f}")
            lines.append(f"  Watertight: {m.is_watertight}")
            degen = int((m.area_faces == 0).sum())
            if degen:
                lines.append(f"  ⚠ Degenerate faces: {degen}")
    except ImportError:
        lines.append("  (trimesh not installed — geometry analysis skipped)")
    except Exception as exc:
        lines.append(f"  (geometry analysis failed: {exc})")

    return "\n".join(lines)


def _extract_glb_json(data: bytes) -> dict:
    """
    Parse the binary glTF (GLB) container and return the JSON chunk as a dict.
    GLB format: 12-byte header + chunks (each: 4-byte length, 4-byte type, data).
    """
    if len(data) < 12:
        return {}
    magic, version, total_len = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:  # 'glTF'
        return {}
    offset = 12
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk_data = data[offset: offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:  # JSON chunk
            return json.loads(chunk_data.decode("utf-8", errors="ignore"))
    return {}


def _parse_step(file) -> str:
    """
    Parse STEP / STP files. These are ISO 10303 text files — extract:
      - Header metadata (description, author, organisation, preprocessor)
      - Entity type inventory (counts of PRODUCT, ADVANCED_FACE, EDGE_CURVE, etc.)
    trimesh does not reliably support STEP, so we do lightweight text analysis.
    """
    try:
        raw = file.read()
        text = raw.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise ValueError(f"STEP file read failed: {exc}") from exc

    lines_out = ["=== STEP / ISO 10303 FILE REPORT ===", ""]

    # Header section
    header_start = text.find("HEADER;")
    header_end   = text.find("ENDSEC;", header_start) if header_start >= 0 else -1
    if header_start >= 0 and header_end >= 0:
        header_block = text[header_start:header_end]
        lines_out.append("--- Header ---")
        for tag in ("FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA"):
            idx = header_block.find(tag)
            if idx >= 0:
                end = header_block.find(";", idx)
                lines_out.append(f"  {header_block[idx:end].strip()}")
        lines_out.append("")

    # Count entity types in DATA section
    data_start = text.find("DATA;")
    data_end   = text.find("ENDSEC;", data_start) if data_start >= 0 else -1
    if data_start >= 0 and data_end >= 0:
        data_block = text[data_start:data_end]
        lines_out.append("--- Entity Inventory ---")

        important_entities = [
            "PRODUCT",
            "PRODUCT_DEFINITION",
            "ADVANCED_BREP_SHAPE_REPRESENTATION",
            "MANIFOLD_SOLID_BREP",
            "ADVANCED_FACE",
            "FACE_OUTER_BOUND",
            "EDGE_CURVE",
            "VERTEX_POINT",
            "CARTESIAN_POINT",
            "DIRECTION",
            "AXIS2_PLACEMENT_3D",
            "CYLINDRICAL_SURFACE",
            "PLANE",
            "LINE",
            "CIRCLE",
            "B_SPLINE_CURVE",
            "B_SPLINE_SURFACE",
        ]

        for entity in important_entities:
            count = data_block.count(entity + "(")
            if count > 0:
                lines_out.append(f"  {entity:<45}: {count:>6,}")

        total_entities = data_block.count("\n#")
        lines_out.append(f"  {'TOTAL ENTITIES':<45}: {total_entities:>6,}")
        lines_out.append("")

    lines_out.append(
        "NOTE: STEP files encode precise B-rep geometry. "
        "Entity counts above reflect the complexity of the model. "
        "ADVANCED_FACE count approximates total geometric surfaces."
    )

    return "\n".join(lines_out)