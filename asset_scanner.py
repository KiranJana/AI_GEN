"""
Asset Scanner Module
Scans BMS asset packs and extracts visual 3D assets with accurate dimension calculations.
Supports memory-efficient per-collection extraction for large files (>500MB).
"""

import os
import json
import logging
import time
import subprocess
import tempfile
from typing import Dict, List, Optional, Any
from collections import defaultdict
import bpy

# Handle both relative and absolute imports (for standalone and addon usage)
try:
    from .database import get_database, AssetDatabase
except ImportError:
    from database import get_database, AssetDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RobustAssetScanner:
    """
    Asset scanner with accurate dimension calculations.
    Automatically switches to memory-efficient per-collection extraction for large files.
    """

    LARGE_FILE_THRESHOLD = 500 * 1024 * 1024  # 500 MB threshold for per-collection extraction

    def __init__(self, database: AssetDatabase = None):
        self.db = database or get_database()
        self.blender_executable = self._find_blender_executable()
        self._load_classification_patterns()
        logger.info(f"Scanner initialized with Blender: {self.blender_executable}")
    
    # ============================================================================
    # Initialization & Configuration
    # ============================================================================

    def _find_blender_executable(self) -> str:
        """Find Blender executable with multiple fallback methods."""
        # Try current Blender path
        try:
            blender_path = bpy.app.binary_path
            if blender_path and os.path.exists(blender_path):
                if 'blender.exe' in blender_path.lower() or blender_path.endswith('blender'):
                    return blender_path
        except Exception as e:
            logger.warning(f"Could not get current Blender path: {e}")
        
        # Try common Windows paths
        common_paths = [
            "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",
            "C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",
            "P:\\Blender\\4.5\\blender.exe",
            "P:\\Blender\\blender.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        # Fallback
        return bpy.app.binary_path
    
    def _load_classification_patterns(self):
        """Load classification patterns from database."""
        self.category_patterns = {}
        self.style_patterns = {}
        self.material_patterns = {}
        
        try:
            for pattern_type, storage in [
                ('category', self.category_patterns),
                ('style', self.style_patterns),
                ('material_family', self.material_patterns)
            ]:
                patterns = self.db.get_classification_patterns(pattern_type)
                for pattern in patterns:
                    storage[pattern['pattern_name']] = {
                        'keywords': pattern['keywords'],
                        'confidence': pattern['confidence'],
                        'priority': pattern['priority']
                    }
            
            logger.info(f"Loaded {len(self.category_patterns)} category, "
                       f"{len(self.style_patterns)} style, "
                       f"{len(self.material_patterns)} material patterns")
        except Exception as e:
            logger.error(f"Failed to load classification patterns: {e}")
            # Initialize empty patterns as fallback
            self.category_patterns = {}
            self.style_patterns = {}
            self.material_patterns = {}
    
    # ============================================================================
    # Main Scanning API
    # ============================================================================

    def scan_asset_pack_robust(self, pack_path: str, pack_name: str = None,
                              force_rescan: bool = False) -> Dict[str, Any]:
        """
        Scan an asset pack and extract all visual assets with accurate dimensions.
        Automatically selects optimal extraction strategy based on file size.
        """
        start_time = time.time()
        logger.info(f"Starting asset pack scan: {pack_path}")
        
        # Validate inputs
        if not os.path.exists(pack_path):
            raise FileNotFoundError(f"Asset pack path does not exist: {pack_path}")
        
        if pack_name is None:
            pack_name = os.path.basename(pack_path.rstrip('/\\'))
        
        # Handle existing pack
        pack_id = self._get_or_create_pack(pack_name, pack_path, force_rescan)
        
        # Find and process blend files
        blend_files = self._find_blend_files(pack_path)
        if not blend_files:
            logger.warning("No blend files found")
            return self._create_summary(pack_id, 0, 0, start_time)
        
        logger.info(f"Found {len(blend_files)} blend files")
        
        # Process each file
        processed = 0
        failed = 0
        
        for i, blend_file in enumerate(blend_files):
            logger.info(f"Processing {i+1}/{len(blend_files)}: {os.path.basename(blend_file)}")
            
            try:
                assets_created = self._process_blend_file(blend_file, pack_id)
                processed += 1
                logger.info(f"  ✅ Created {assets_created} assets")
            except Exception as e:
                failed += 1
                logger.error(f"  ❌ Failed: {e}")
        
        return self._create_summary(pack_id, processed, failed, start_time)
    
    # ============================================================================
    # Pack & File Management
    # ============================================================================

    def _get_or_create_pack(self, pack_name: str, pack_path: str, force_rescan: bool) -> int:
        """Get existing pack or create new one, handling force rescan."""
        existing_pack = self.db.get_asset_pack(name=pack_name)
        
        if existing_pack and not force_rescan:
            logger.info(f"Using existing pack: {pack_name}")
            return existing_pack['id']
        elif existing_pack and force_rescan:
            pack_id = existing_pack['id']
            logger.info(f"Force rescanning pack: {pack_name}")
            self._clear_pack_assets(pack_id)
            return pack_id
        else:
            pack_id = self.db.create_asset_pack(
                name=pack_name,
                path=pack_path,
                version="1.0",
                description=f"Scanned BMS asset pack from {pack_path}"
            )
            logger.info(f"Created new pack: {pack_name} (ID: {pack_id})")
            return pack_id
    
    def _clear_pack_assets(self, pack_id: int):
        """Clear existing assets for force rescan."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM asset_tags WHERE asset_id IN (SELECT id FROM assets WHERE pack_id = ?)", (pack_id,))
                conn.execute("DELETE FROM asset_properties WHERE asset_id IN (SELECT id FROM assets WHERE pack_id = ?)", (pack_id,))
                conn.execute("DELETE FROM assets WHERE pack_id = ?", (pack_id,))
                conn.execute("DELETE FROM scan_queue WHERE pack_id = ?", (pack_id,))
                conn.commit()
                logger.info("Cleared existing pack assets")
        except Exception as e:
            logger.error(f"Failed to clear pack assets: {e}")
    
    def _find_blend_files(self, pack_path: str) -> List[str]:
        """Find all valid .blend files in the pack directory."""
        blend_files = []
        
        for root, dirs, files in os.walk(pack_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                      d.lower() not in ['backup', 'temp', 'cache', '__pycache__']]
            
            for file in files:
                if file.lower().endswith('.blend') and not file.startswith('.'):
                    full_path = os.path.join(root, file)
                    try:
                        if os.path.getsize(full_path) > 1024:  # At least 1KB
                            blend_files.append(full_path)
                    except OSError:
                        logger.warning(f"Skipping unreadable file: {file}")
        
        return sorted(blend_files)
    
    # ============================================================================
    # Blend File Processing
    # ============================================================================

    def _process_blend_file(self, blend_file_path: str, pack_id: int) -> int:
        """
        Process a single blend file with automatic strategy selection.
        Large files (>500MB) use per-collection extraction for memory efficiency.
        """
        # Check file size and select strategy
        file_size = os.path.getsize(blend_file_path)
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.1f} MB")

        if file_size > self.LARGE_FILE_THRESHOLD:
            logger.info("🚀 Using per-collection extraction (memory-efficient for large files)")
            return self._process_large_blend_file(blend_file_path, pack_id)
        else:
            logger.info("⚡ Using standard extraction (fast for small files)")
            return self._process_standard_blend_file(blend_file_path, pack_id)

    def _process_standard_blend_file(self, blend_file_path: str, pack_id: int) -> int:
        """Process a small/medium blend file using standard extraction (loads entire file)."""
        # Use unified script generator
        script_content = self._create_extraction_script(
            mode='full_file',
            blend_file_path=blend_file_path
        )

        # Validate script before execution
        self._validate_script_generation(script_content, 'full_file')

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(script_content)
            script_path = script_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
            output_path = output_file.name

        try:
            # Run Blender subprocess with explicit file path argument
            cmd = [
                self.blender_executable,
                "--background",
                "--python", script_path,
                "--", blend_file_path, output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=os.path.dirname(blend_file_path)
            )

            if result.returncode != 0:
                error_details = f"Blender subprocess failed (code {result.returncode})"
                if result.stderr:
                    error_details += f"\nSTDERR: {result.stderr[-1000:]}"
                if result.stdout:
                    error_details += f"\nSTDOUT (last 500): {result.stdout[-500:]}"
                raise Exception(error_details)
            
            # Read and process results
            if not os.path.exists(output_path):
                raise Exception("No output data generated")
            
            with open(output_path, 'r') as f:
                extraction_data = json.load(f)
            
            if 'error' in extraction_data:
                raise Exception(f"Extraction failed: {extraction_data['error']}")
            
            return self._store_extracted_data(extraction_data, pack_id, blend_file_path)
                
        finally:
            # Clean up temp files
            for temp_path in [script_path, output_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as e:
                    logger.debug(f"Failed to cleanup temp file {temp_path}: {e}")

    def _quick_scan_collections(self, blend_file_path: str) -> List[str]:
        """
        Quickly scan blend file to get list of collection names without loading geometry.
        Uses metadata-only access for speed (~5-10 seconds for large files).
        """
        # Use unified script generator
        script_content = self._create_extraction_script(
            mode='quick_scan',
            blend_file_path=blend_file_path
        )

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(script_content)
            script_path = script_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
            output_path = output_file.name

        try:
            # Run quick scan subprocess with explicit file path argument
            cmd = [
                self.blender_executable,
                "--background",
                "--python", script_path,
                "--", blend_file_path, output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # Quick scan should be fast
                cwd=os.path.dirname(blend_file_path)
            )

            if result.returncode != 0:
                error_details = f"Quick scan failed (code {result.returncode})"
                if result.stderr:
                    error_details += f"\nSTDERR: {result.stderr[-1000:]}"
                if result.stdout:
                    error_details += f"\nSTDOUT (last 500): {result.stdout[-500:]}"
                raise Exception(error_details)

            # Read results
            with open(output_path, 'r') as f:
                scan_data = json.load(f)

            if not scan_data.get('success'):
                raise Exception(f"Quick scan error: {scan_data.get('error')}")

            collection_names = [c['name'] for c in scan_data['collections']]
            logger.info(f"Quick scan found {len(collection_names)} collections")
            return collection_names

        finally:
            # Clean up temp files
            for temp_path in [script_path, output_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as e:
                    logger.debug(f"Failed to cleanup temp file {temp_path}: {e}")

    # ============================================================================
    # Script Generation (Blender Subprocess Scripts)
    # ============================================================================

    def _validate_script_generation(self, script: str, mode: str):
        """
        Validate generated script before execution.
        Catches generation errors early with clear error messages.
        """
        # 1. Syntax validation
        try:
            compile(script, f'<{mode}_script>', 'exec')
        except SyntaxError as e:
            raise ValueError(f"Generated {mode} script has syntax error at line {e.lineno}: {e.msg}")

        # 2. Required function validation
        required_functions = {
            'single_collection': ['main', 'get_all_collection_objects'],
            'full_file': ['main', 'get_all_collection_objects'],
            'standalone': ['main', 'get_all_collection_objects'],
            'quick_scan': ['main', 'has_visual_objects_recursive']
        }

        if mode in required_functions:
            for func in required_functions[mode]:
                if f'def {func}(' not in script:
                    raise ValueError(f"Generated {mode} script missing required function: {func}")

        # 3. Argument parsing validation
        if 'output_path' not in script:
            raise ValueError(f"Generated {mode} script missing output_path handling")

    def _get_common_extraction_functions(self) -> str:
        """Get the common helper functions used by all extraction scripts."""
        return """
# IMPORTANT: Functions are ordered by dependencies - base functions first!

def get_polygon_count(obj):
    \"\"\"Safely get polygon count from object.\"\"\"
    try:
        if obj and obj.type == 'MESH' and obj.data and hasattr(obj.data, 'polygons'):
            return len(obj.data.polygons)
    except:
        pass
    return 0

def get_vertex_count(obj):
    \"\"\"Safely get vertex count from object.\"\"\"
    try:
        if obj and obj.type == 'MESH' and obj.data and hasattr(obj.data, 'vertices'):
            return len(obj.data.vertices)
    except:
        pass
    return 0

def is_visual_object(obj):
    \"\"\"Check if object is a visual mesh with geometry.\"\"\"
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    if get_polygon_count(obj) == 0:
        return False

    try:
        if hasattr(obj, 'dimensions'):
            if max(obj.dimensions) < 0.0001:
                return False
    except:
        pass

    return True

def calculate_object_bounds(obj):
    \"\"\"Calculate accurate world-space bounding box for an object.\"\"\"
    if not obj or not obj.data or obj.type != 'MESH':
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]

    mesh = obj.data
    if len(mesh.vertices) == 0:
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]

    try:
        if hasattr(obj, 'matrix_world') and mesh.vertices:
            world_vertices = []
            for vertex in mesh.vertices:
                world_pos = obj.matrix_world @ vertex.co
                world_vertices.append([world_pos.x, world_pos.y, world_pos.z])

            if world_vertices:
                bbox_min = [min(v[i] for v in world_vertices) for i in range(3)]
                bbox_max = [max(v[i] for v in world_vertices) for i in range(3)]
                dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]

                if max(dimensions) > 0.0001:
                    return bbox_min, bbox_max, dimensions
    except Exception as e:
        print(f"Bounds calculation failed for {{obj.name}}: {{e}}")

    return [0, 0, 0], [0, 0, 0], [0, 0, 0]

def get_all_collection_objects(collection):
    \"\"\"Recursively get all objects including from child collections.\"\"\"
    objects = [obj for obj in collection.objects if is_visual_object(obj)]

    # Add objects from child collections recursively
    for child_coll in collection.children:
        objects.extend(get_all_collection_objects(child_coll))

    return objects

def calculate_collection_bounds(visual_objects):
    \"\"\"Calculate accurate bounding box for a collection of objects.\"\"\"
    if not visual_objects:
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]

    bbox_min = [float('inf')] * 3
    bbox_max = [float('-inf')] * 3
    valid_bounds_found = False

    for obj in visual_objects:
        obj_bbox_min, obj_bbox_max, obj_dimensions = calculate_object_bounds(obj)

        if max(obj_dimensions) > 0.001:
            valid_bounds_found = True
            for i in range(3):
                bbox_min[i] = min(bbox_min[i], obj_bbox_min[i])
                bbox_max[i] = max(bbox_max[i], obj_bbox_max[i])

    if not valid_bounds_found:
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]

    dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
    return bbox_min, bbox_max, dimensions

def should_skip_object_name(name):
    \"\"\"Skip rig controls and system objects by name.\"\"\"
    if not name:
        return True
    name_lower = name.lower()
    skip_prefixes = ['cs_', 'ctrl', 'ik_', 'bone', 'meta', 'wgt_']
    if any(name_lower.startswith(prefix) for prefix in skip_prefixes):
        return True
    skip_keywords = ['control', 'constraint', 'driver', 'target', 'pole', 'helper', 'locator']
    return any(keyword in name_lower for keyword in skip_keywords)

def is_parent_collection(collection):
    \"\"\"Check if collection is a top-level parent (not nested inside another collection).\"\"\"
    import bpy
    # A collection is a parent if it's not a child of any other collection
    for potential_parent in bpy.data.collections:
        if potential_parent == collection:
            continue
        # Check if this collection is in the parent's children
        if collection.name in [child.name for child in potential_parent.children]:
            return False  # This collection is a child
    return True  # This collection is a top-level parent

def classify_name(name, patterns):
    \"\"\"Classify name using patterns.\"\"\"
    if not name:
        return None

    name_lower = name.lower()
    best_match = None
    best_confidence = 0.0

    for pattern_name, pattern_data in patterns.items():
        keywords = pattern_data.get('keywords', [])
        confidence = pattern_data.get('confidence', 0.5)

        for keyword in keywords:
            if keyword.lower() in name_lower:
                if confidence > best_confidence:
                    best_match = pattern_name
                    best_confidence = confidence
                break
    return best_match

def calculate_complexity(polygon_count, object_count=1):
    \"\"\"Calculate 0-10 complexity score.\"\"\"
    if polygon_count < 100: poly_score = 1
    elif polygon_count < 500: poly_score = 3
    elif polygon_count < 2000: poly_score = 5
    elif polygon_count < 10000: poly_score = 7
    else: poly_score = 9

    object_multiplier = min(1.0 + (object_count - 1) * 0.1, 2.0)
    return min(poly_score * object_multiplier, 10.0)

def determine_quality(polygon_count):
    \"\"\"Determine quality tier.\"\"\"
    if polygon_count < 500: return 'low'
    elif polygon_count < 2000: return 'medium'
    elif polygon_count < 10000: return 'high'
    else: return 'ultra'
"""

    def _create_extraction_script(self,
                                  mode: str,
                                  blend_file_path: str,
                                  collection_name: Optional[str] = None,
                                  excluded_collections: Optional[List[str]] = None) -> str:
        """
        Unified script generator for all extraction modes.

        Args:
            mode: 'single_collection', 'full_file', 'standalone', or 'quick_scan'
            blend_file_path: Path to the blend file (passed as explicit argument)
            collection_name: Name of collection (for single_collection mode)
            excluded_collections: Collections to exclude (for standalone mode)

        Returns:
            Complete Python script as string
        """
        # Generate mode-specific configuration
        mode_config = self._get_mode_config(mode, collection_name, excluded_collections)

        # Generate mode-specific main function
        main_function = self._get_mode_main_function(mode)

        # Build complete script
        script = f"""
import bpy
import json
import sys
import os
import mathutils
from mathutils import Vector

# Parse command-line arguments explicitly
# Expected: blender --background --python script.py -- blend_file output_path
if '--' in sys.argv:
    args_start = sys.argv.index('--') + 1
    args = sys.argv[args_start:]
    blend_file_path = args[0] if len(args) > 0 else None
    output_path = args[1] if len(args) > 1 else "output.json"
else:
    # Fallback for old-style invocation
    blend_file_path = bpy.data.filepath
    output_path = sys.argv[-1] if len(sys.argv) > 6 else "output.json"

{mode_config}

{self._get_common_extraction_functions()}

{main_function}

# Main execution
try:
    result = main()
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
except Exception as e:
    import traceback
    error_data = {{"error": str(e), "traceback": traceback.format_exc(), "success": False}}
    with open(output_path, 'w') as f:
        json.dump(error_data, f)
    print(f"{{'{mode.upper()}'}} EXTRACTION ERROR: {{e}}")
    raise
"""
        return script

    def _get_mode_config(self, mode: str, collection_name: Optional[str],
                        excluded_collections: Optional[List[str]]) -> str:
        """Generate mode-specific configuration variables."""
        config = f"CATEGORY_PATTERNS = {json.dumps(self.category_patterns)}\n"

        if mode == 'single_collection' and collection_name:
            config += f'TARGET_COLLECTION = "{collection_name}"\n'
        elif mode == 'standalone' and excluded_collections:
            config += f'EXCLUDED_COLLECTIONS = {json.dumps(excluded_collections)}\n'

        return config

    def _get_mode_main_function(self, mode: str) -> str:
        """Generate mode-specific main function."""
        if mode == 'quick_scan':
            return self._get_quick_scan_main()
        elif mode == 'single_collection':
            return self._get_single_collection_main()
        elif mode == 'full_file':
            return self._get_full_file_main()
        elif mode == 'standalone':
            return self._get_standalone_main()
        else:
            raise ValueError(f"Unknown extraction mode: {mode}")

    def _get_quick_scan_main(self) -> str:
        """Generate main function for quick_scan mode."""
        return """
def has_visual_objects_recursive(collection):
    '''Recursively check if collection or any child has mesh objects.'''
    # Check direct objects
    for obj in collection.objects:
        if obj.type == 'MESH':
            return True
    # Check child collections recursively
    for child_coll in collection.children:
        if has_visual_objects_recursive(child_coll):
            return True
    return False

def should_skip_collection(collection):
    '''Skip empty or system collections.'''
    if not collection:
        return True
    name_lower = collection.name.lower()
    if name_lower in ['collection', 'scene collection']:
        return True
    skip_keywords = ['rig', 'control', 'bone', 'constraint', 'driver', 'meta']
    return any(keyword in name_lower for keyword in skip_keywords)

def main():
    collections = []
    child_collections_skipped = 0

    for collection in bpy.data.collections:
        if should_skip_collection(collection):
            continue

        # Skip child collections - only process parents
        if not is_parent_collection(collection):
            child_collections_skipped += 1
            continue

        # Check if it has visual objects (including in child collections)
        if has_visual_objects_recursive(collection):
            collections.append({
                'name': collection.name,
                'object_count': len(collection.objects)
            })

    result = {
        'success': True,
        'collections': collections,
        'total_collections': len(collections),
        'child_collections_skipped': child_collections_skipped
    }

    print(f"Found {len(collections)} parent collections (skipped {child_collections_skipped} child collections)")
    return result
"""

    def _get_single_collection_main(self) -> str:
        """Generate main function for single_collection mode."""
        return """
def main():
    \"\"\"Extract data for a single specified collection.\"\"\"
    # Explicitly open the blend file
    if blend_file_path and os.path.exists(blend_file_path):
        if not bpy.data.filepath or bpy.data.filepath != blend_file_path:
            bpy.ops.wm.open_mainfile(filepath=blend_file_path)

    data = {
        'file_info': {
            'path': bpy.data.filepath,
            'name': os.path.basename(bpy.data.filepath) if bpy.data.filepath else 'unknown',
            'collections': [],
            'objects': []
        },
        'success': True
    }

    # Find the target collection
    target_coll = None
    for collection in bpy.data.collections:
        if collection.name == TARGET_COLLECTION:
            target_coll = collection
            break

    if not target_coll:
        print(f"❌ Collection '{TARGET_COLLECTION}' not found")
        data['success'] = False
        data['error'] = f"Collection '{TARGET_COLLECTION}' not found"
        return data

    # Get visual objects in this collection AND all child collections (recursive)
    visual_objects = []
    try:
        visual_objects = get_all_collection_objects(target_coll)
    except Exception as e:
        import traceback
        error_msg = f"Failed to get collection objects: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"   Collection name: {target_coll.name if target_coll else 'None'}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Full traceback:")
        print(f"{traceback.format_exc()}")
        data['success'] = False
        data['error'] = error_msg
        data['traceback'] = traceback.format_exc()
        data['debug_info'] = {
            'collection_name': target_coll.name if target_coll else None,
            'error_type': type(e).__name__,
            'bpy_filepath': bpy.data.filepath,
            'total_collections': len(bpy.data.collections)
        }
        return data

    if not visual_objects:
        print(f"⚠️  No visual objects in collection '{TARGET_COLLECTION}' or its children")
        return data

    # Calculate collection stats (aggregated from parent and all children)
    try:
        total_polygons = sum(get_polygon_count(obj) for obj in visual_objects)
        total_vertices = sum(get_vertex_count(obj) for obj in visual_objects)
        bbox_min, bbox_max, dimensions = calculate_collection_bounds(visual_objects)
    except Exception as e:
        import traceback
        error_msg = f"Failed to calculate collection stats: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Number of objects being processed: {len(visual_objects) if visual_objects else 0}")
        print(f"   Full traceback:")
        print(f"{traceback.format_exc()}")
        data['success'] = False
        data['error'] = error_msg
        data['traceback'] = traceback.format_exc()
        data['debug_info'] = {
            'error_type': type(e).__name__,
            'object_count': len(visual_objects) if visual_objects else 0,
            'collection_name': target_coll.name if target_coll else None
        }
        return data

    child_count = len(list(target_coll.children))
    if child_count > 0:
        print(f"   Including {len(visual_objects)} objects from {child_count} child collections")

    if total_polygons > 0 and max(dimensions) > 0.001:
        category = classify_name(target_coll.name, CATEGORY_PATTERNS) or 'props'

        data['file_info']['collections'].append({
            'name': target_coll.name,
            'type': 'collection',
            'polygon_count': total_polygons,
            'vertex_count': total_vertices,
            'object_count': len(visual_objects),
            'dimensions': dimensions,
            'bbox_min': bbox_min,
            'bbox_max': bbox_max,
            'category': category,
            'complexity_score': calculate_complexity(total_polygons, len(visual_objects)),
            'quality_tier': determine_quality(total_polygons),
            'has_geometry': True
        })

        print(f"✅ COLLECTION: {target_coll.name} - {total_polygons} polys, dims: {[round(d, 3) for d in dimensions]} ({len(visual_objects)} objects)")
    else:
        print(f"⚠️  SKIPPED: Collection has no valid geometry")

    return data
"""

    def _get_full_file_main(self) -> str:
        """Generate main function for full_file mode."""
        return """
def should_skip_collection(collection):
    \"\"\"Skip utility collections by name.\"\"\"
    if not collection or not collection.name:
        return True
    name_lower = collection.name.lower()
    skip_keywords = ['temp', 'hidden', 'backup', 'deleted', 'old']
    return any(keyword in name_lower for keyword in skip_keywords)

def main():
    \"\"\"Extract visual assets with accurate dimension calculations.\"\"\"
    # Explicitly open the blend file
    if blend_file_path and os.path.exists(blend_file_path):
        if not bpy.data.filepath or bpy.data.filepath != blend_file_path:
            bpy.ops.wm.open_mainfile(filepath=blend_file_path)

    data = {
        'file_info': {
            'path': bpy.data.filepath,
            'name': os.path.basename(bpy.data.filepath) if bpy.data.filepath else 'unknown',
            'collections': [],
            'objects': []
        },
        'success': True
    }

    # Track objects that are already part of a collection asset
    objects_in_collections = set()

    # Process collections (parent collections only)
    child_collections_skipped = 0
    for collection in bpy.data.collections:
        if should_skip_collection(collection):
            continue

        # Skip child collections - only process parents
        if not is_parent_collection(collection):
            child_collections_skipped += 1
            continue

        # Get visual objects from this collection AND all child collections (recursive)
        visual_objects = get_all_collection_objects(collection)
        if not visual_objects:
            continue

        # Calculate collection stats
        total_polygons = sum(get_polygon_count(obj) for obj in visual_objects)
        total_vertices = sum(get_vertex_count(obj) for obj in visual_objects)

        # Calculate proper bounding box for collection
        bbox_min, bbox_max, dimensions = calculate_collection_bounds(visual_objects)

        # Only include collections with actual size and geometry
        if total_polygons > 0 and max(dimensions) > 0.001:  # At least 1mm
            category = classify_name(collection.name, CATEGORY_PATTERNS) or 'props'

            data['file_info']['collections'].append({
                'name': collection.name,
                'type': 'collection',
                'polygon_count': total_polygons,
                'vertex_count': total_vertices,
                'object_count': len(visual_objects),
                'dimensions': dimensions,
                'bbox_min': bbox_min,
                'bbox_max': bbox_max,
                'category': category,
                'complexity_score': calculate_complexity(total_polygons, len(visual_objects)),
                'quality_tier': determine_quality(total_polygons),
                'has_geometry': True
            })

            # Track all objects that are part of this collection asset
            for obj in visual_objects:
                objects_in_collections.add(obj.name)

            print(f"✅ COLLECTION: {collection.name} - {total_polygons} polys, dims: {[round(d, 3) for d in dimensions]} ({len(visual_objects)} objects tracked)")
        else:
            print(f"⚠️  SKIPPED: Collection {collection.name} - {total_polygons} polys, dims: {[round(d, 3) for d in dimensions]}")

    # Process standalone objects
    for obj in bpy.data.objects:
        # Skip objects that are already part of a collection asset
        if obj.name in objects_in_collections:
            continue

        if not is_visual_object(obj) or len(obj.users_collection) > 1:
            continue

        if should_skip_object_name(obj.name):
            continue

        polygon_count = get_polygon_count(obj)
        vertex_count = get_vertex_count(obj)

        # Calculate proper dimensions for object
        bbox_min, bbox_max, dimensions = calculate_object_bounds(obj)

        if polygon_count > 0 and max(dimensions) > 0.001:  # At least 1mm
            category = classify_name(obj.name, CATEGORY_PATTERNS) or 'props'

            data['file_info']['objects'].append({
                'name': obj.name,
                'type': 'object',
                'polygon_count': polygon_count,
                'vertex_count': vertex_count,
                'dimensions': dimensions,
                'bbox_min': bbox_min,
                'bbox_max': bbox_max,
                'category': category,
                'complexity_score': calculate_complexity(polygon_count, 1),
                'quality_tier': determine_quality(polygon_count),
                'has_geometry': True
            })
            print(f"✅ STANDALONE: Object {obj.name} - {polygon_count} polys, dims: {[round(d, 3) for d in dimensions]}")
        else:
            print(f"⚠️  SKIPPED: Object {obj.name} - {polygon_count} polys, dims: {[round(d, 3) for d in dimensions]}")

    collections = len(data['file_info']['collections'])
    objects = len(data['file_info']['objects'])
    tracked = len(objects_in_collections)
    print(f"📊 COLLECTION-FIRST EXTRACTION complete: {collections} parent collection assets, {objects} standalone assets")
    print(f"   ({child_collections_skipped} child collections skipped, {tracked} objects tracked in collections)")
    return data
"""

    def _get_standalone_main(self) -> str:
        """Generate main function for standalone mode."""
        return """
def main():
    \"\"\"Extract standalone objects not in named collections.\"\"\"
    # Ensure the blend file is properly loaded
    try:
        if not bpy.data.filepath:
            if '--background' in sys.argv:
                blend_file_idx = sys.argv.index('--background') + 1
                if blend_file_idx < len(sys.argv):
                    blend_file = sys.argv[blend_file_idx]
                    if os.path.exists(blend_file):
                        bpy.ops.wm.open_mainfile(filepath=blend_file)
    except Exception:
        pass  # File already loaded via --background

    data = {
        'file_info': {
            'path': bpy.data.filepath,
            'name': os.path.basename(bpy.data.filepath) if bpy.data.filepath else 'unknown',
            'collections': [],
            'objects': []
        },
        'success': True
    }

    # Track objects in excluded collections (including child collections recursively)
    objects_in_collections = set()
    for coll_name in EXCLUDED_COLLECTIONS:
        for collection in bpy.data.collections:
            if collection.name == coll_name:
                for obj in get_all_collection_objects(collection):
                    objects_in_collections.add(obj.name)
                break

    # Process standalone objects
    for obj in bpy.data.objects:
        # Skip if in an excluded collection
        if obj.name in objects_in_collections:
            continue

        if not is_visual_object(obj) or len(obj.users_collection) > 1:
            continue

        if should_skip_object_name(obj.name):
            continue

        polygon_count = get_polygon_count(obj)
        vertex_count = get_vertex_count(obj)
        bbox_min, bbox_max, dimensions = calculate_object_bounds(obj)

        if polygon_count > 0 and max(dimensions) > 0.001:
            category = classify_name(obj.name, CATEGORY_PATTERNS) or 'props'

            data['file_info']['objects'].append({
                'name': obj.name,
                'type': 'object',
                'polygon_count': polygon_count,
                'vertex_count': vertex_count,
                'dimensions': dimensions,
                'bbox_min': bbox_min,
                'bbox_max': bbox_max,
                'category': category,
                'complexity_score': calculate_complexity(polygon_count, 1),
                'quality_tier': determine_quality(polygon_count),
                'has_geometry': True
            })
            print(f"✅ STANDALONE: {obj.name} - {polygon_count} polys, dims: {[round(d, 3) for d in dimensions]}")

    print(f"📊 Found {len(data['file_info']['objects'])} standalone objects")
    return data
"""

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Check if error is transient (worth retrying).
        Returns True for errors that might succeed on retry.
        """
        error_str = str(error).lower()
        transient_indicators = [
            'timeout', 'connection', 'memory', 'lock', 'busy',
            'temporary', 'resource', 'unavailable'
        ]
        return any(indicator in error_str for indicator in transient_indicators)

    def _extract_with_retry(self, blend_file_path: str, collection_name: str,
                           pack_id: int, max_retries: int = 2) -> int:
        """
        Extract collection with automatic retry on transient failures.

        Args:
            blend_file_path: Path to blend file
            collection_name: Name of collection to extract
            pack_id: Database ID of the asset pack
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            Number of assets created
        """
        for attempt in range(max_retries + 1):
            try:
                return self._extract_single_collection(
                    blend_file_path, collection_name, pack_id
                )
            except Exception as e:
                if attempt < max_retries and self._is_transient_error(e):
                    logger.warning(
                        f"Transient error on {collection_name}, "
                        f"retrying ({attempt+1}/{max_retries}): {e}"
                    )
                    time.sleep(1)  # Brief delay before retry
                    continue
                raise

    def _extract_single_collection(self, blend_file_path: str, collection_name: str, pack_id: int) -> int:
        """
        Extract data for a single collection from a blend file (memory-efficient).
        Returns number of assets created.
        """
        # Use unified script generator
        script_content = self._create_extraction_script(
            mode='single_collection',
            blend_file_path=blend_file_path,
            collection_name=collection_name
        )

        # Validate script before execution
        self._validate_script_generation(script_content, 'single_collection')

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as script_file:
            script_file.write(script_content)
            script_path = script_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
            output_path = output_file.name

        try:
            # Run Blender subprocess for this collection only
            # Pass blend file path explicitly as argument for robustness
            cmd = [
                self.blender_executable,
                "--background",
                "--python", script_path,
                "--", blend_file_path, output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes per collection (generous for large collections)
                cwd=os.path.dirname(blend_file_path)
            )

            if result.returncode != 0:
                error_details = f"Collection extraction failed (code {result.returncode})"
                if result.stderr:
                    error_details += f"\nSTDERR: {result.stderr[-1000:]}"
                if result.stdout:
                    error_details += f"\nSTDOUT (last 500): {result.stdout[-500:]}"
                raise Exception(error_details)

            # Read and process results
            if not os.path.exists(output_path):
                raise Exception("No output data generated")

            with open(output_path, 'r') as f:
                extraction_data = json.load(f)

            if 'error' in extraction_data:
                error_msg = extraction_data['error']
                traceback_info = extraction_data.get('traceback', '')

                logger.error(f"Collection extraction failed: {collection_name}")
                logger.error(f"Error: {error_msg}")
                if traceback_info:
                    logger.debug(f"Traceback: {traceback_info}")

                raise Exception(f"Extraction failed: {error_msg}")

            # Store the collection data
            return self._store_extracted_data(extraction_data, pack_id, blend_file_path)

        finally:
            # Clean up temp files
            for temp_path in [script_path, output_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as e:
                    logger.debug(f"Failed to cleanup temp file {temp_path}: {e}")

    def _extract_standalone_objects(self, blend_file_path: str, excluded_collections: List[str], pack_id: int) -> int:
        """
        Extract standalone objects (not in named collections) from a blend file.
        excluded_collections: List of collection names that have already been processed.
        Returns number of assets created.
        """
        # Use unified script generator
        script_content = self._create_extraction_script(
            mode='standalone',
            blend_file_path=blend_file_path,
            excluded_collections=excluded_collections
        )

        # Validate script before execution
        self._validate_script_generation(script_content, 'standalone')

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(script_content)
            script_path = script_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
            output_path = output_file.name

        try:
            # Run Blender subprocess for standalone objects with explicit file path argument
            cmd = [
                self.blender_executable,
                "--background",
                "--python", script_path,
                "--", blend_file_path, output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,  # 3 minutes for standalone objects
                cwd=os.path.dirname(blend_file_path)
            )

            if result.returncode != 0:
                error_details = f"Standalone extraction failed (code {result.returncode})"
                if result.stderr:
                    error_details += f"\nSTDERR: {result.stderr[-1000:]}"
                if result.stdout:
                    error_details += f"\nSTDOUT (last 500): {result.stdout[-500:]}"
                raise Exception(error_details)

            # Read and process results
            if not os.path.exists(output_path):
                raise Exception("No output data generated")

            with open(output_path, 'r') as f:
                extraction_data = json.load(f)

            if 'error' in extraction_data:
                error_msg = extraction_data['error']
                traceback_info = extraction_data.get('traceback', 'No traceback available')
                logger.error(f"Standalone extraction failed: {error_msg}")
                logger.error(f"Full traceback:\n{traceback_info}")
                raise Exception(f"Extraction failed: {error_msg}")

            # Store the standalone object data
            return self._store_extracted_data(extraction_data, pack_id, blend_file_path)

        finally:
            # Clean up temp files
            for temp_path in [script_path, output_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as e:
                    logger.debug(f"Failed to cleanup temp file {temp_path}: {e}")

    def _process_large_blend_file(self, blend_file_path: str, pack_id: int) -> int:
        """
        Process large blend files using per-collection extraction.
        Memory-efficient approach that extracts one collection at a time.
        """
        logger.info("=" * 60)
        logger.info("LARGE FILE PROCESSING - PER-COLLECTION EXTRACTION")
        logger.info("=" * 60)

        # Phase 1: Quick scan to get collection list
        logger.info("Phase 1: Quick scanning for collections...")
        try:
            collections = self._quick_scan_collections(blend_file_path)
        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            logger.info("Falling back to standard extraction")
            return self._process_standard_blend_file(blend_file_path, pack_id)

        if not collections:
            logger.info("No collections found, using standard extraction for standalone objects")
            return self._process_standard_blend_file(blend_file_path, pack_id)

        logger.info(f"Found {len(collections)} collections to extract")

        # Phase 2: Extract each collection individually
        logger.info(f"\nPhase 2: Extracting collections individually...")
        total_assets = 0
        failed_collections = []

        for i, coll_name in enumerate(collections):
            logger.info(f"  [{i+1}/{len(collections)}] Extracting: {coll_name}")
            try:
                assets_created = self._extract_with_retry(blend_file_path, coll_name, pack_id)
                total_assets += assets_created
                logger.info(f"    ✅ Created {assets_created} asset(s)")
            except Exception as e:
                logger.error(f"    ❌ Failed: {e}")
                failed_collections.append(coll_name)
                continue

        # Phase 3: Extract standalone objects (background props)
        logger.info(f"\nPhase 3: Extracting standalone objects...")
        try:
            standalone_assets = self._extract_standalone_objects(blend_file_path, collections, pack_id)
            total_assets += standalone_assets
            logger.info(f"  ✅ Created {standalone_assets} standalone asset(s)")
        except Exception as e:
            logger.error(f"  ❌ Standalone extraction failed: {e}")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info(f"LARGE FILE PROCESSING COMPLETE")
        logger.info(f"  Collections processed: {len(collections) - len(failed_collections)}/{len(collections)}")
        logger.info(f"  Total assets created: {total_assets}")
        if failed_collections:
            logger.warning(f"  Failed collections: {', '.join(failed_collections)}")
        logger.info("=" * 60)

        return total_assets

    # ============================================================================
    # Data Storage
    # ============================================================================

    def _store_extracted_data(self, data: Dict, pack_id: int, blend_file_path: str) -> int:
        """Store extracted asset data with improved dimension handling."""
        if not data.get('success') or 'error' in data:
            raise Exception(data.get('error', 'Extraction failed'))
        
        file_info = data['file_info']
        relative_path = os.path.relpath(blend_file_path, self.db.get_asset_pack(pack_id)['path'])
        assets_created = 0
        
        # Store collections
        for coll_data in file_info.get('collections', []):
            try:
                asset_id = self._create_database_asset_improved(coll_data, pack_id, relative_path, blend_file_path)
                assets_created += 1
                logger.info(f"Created collection asset: {coll_data['name']} with dims: {coll_data.get('dimensions', [0,0,0])}")
            except Exception as e:
                logger.error(f"Failed to create collection asset {coll_data['name']}: {e}")
        
        # Store objects
        for obj_data in file_info.get('objects', []):
            try:
                asset_id = self._create_database_asset_improved(obj_data, pack_id, relative_path, blend_file_path)
                assets_created += 1
                logger.info(f"Created object asset: {obj_data['name']} with dims: {obj_data.get('dimensions', [0,0,0])}")
            except Exception as e:
                logger.error(f"Failed to create object asset {obj_data['name']}: {e}")
        
        return assets_created
    
    def _create_database_asset_improved(self, asset_data: Dict, pack_id: int, 
                                       relative_path: str, blend_file_path: str) -> int:
        """Create single asset entry with improved dimension handling."""
        # Extract data with defaults
        polygon_count = asset_data.get('polygon_count', 0)
        vertex_count = asset_data.get('vertex_count', 0)
        complexity_score = asset_data.get('complexity_score', 0.0)
        quality_tier = asset_data.get('quality_tier', 'medium')

        # IMPROVED: Handle dimensions properly
        dimensions = asset_data.get('dimensions', [0.0, 0.0, 0.0])

        # Ensure we have valid dimensions array
        if not isinstance(dimensions, list) or len(dimensions) < 3:
            dimensions = [0.0, 0.0, 0.0]

        # Extract width, height, depth from dimensions
        width, height, depth = dimensions[0], dimensions[1], dimensions[2]

        # Validate dimensions are reasonable numbers
        for i, dim in enumerate([width, height, depth]):
            if not isinstance(dim, (int, float)) or dim < 0 or dim > 10000:  # Max 10km
                if i == 0: width = 0.0
                elif i == 1: height = 0.0 
                else: depth = 0.0

        # Store bounding box info if available
        bbox_min = asset_data.get('bbox_min', [0.0, 0.0, 0.0])
        bbox_max = asset_data.get('bbox_max', [0.0, 0.0, 0.0])

        # --- NEW: Store object_name and collection_name for accurate loading ---
        # If this is a collection, store collection_name, else store object_name
        collection_name = asset_data['name'] if asset_data.get('type') == 'collection' else None
        object_name = asset_data['name'] if asset_data.get('type') == 'object' else None

        # Create asset in database
        asset_id = self.db.create_asset_optimized(
            name=asset_data['name'],
            pack_id=pack_id,
            category=asset_data.get('category', 'props'),
            blend_file_path=blend_file_path,
            subcategory=None,
            collection_name=collection_name,
            file_path=relative_path,
            polygon_count=polygon_count,
            vertex_count=vertex_count,
            material_count=0,
            object_count=asset_data.get('object_count', 1),
            dimensions=[width, height, depth],  # Pass corrected dimensions
            complexity_score=complexity_score,
            quality_tier=quality_tier,
            estimated_load_time=max(0.1, polygon_count / 10000),
            memory_estimate=max(1.0, polygon_count / 1000),
            primary_style=None,
            size_category=self._determine_size_category(width, height, depth),
            # --- Add object_name for object assets ---
            object_name=object_name
        )

        # Store additional metadata as properties
        try:
            if bbox_min and bbox_max:
                # Store bounding box data
                with self.db.get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO asset_properties 
                        (asset_id, property_type, property_key, property_value, data_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (asset_id, 'technical', 'bbox_min', json.dumps(bbox_min), 'json'))

                    conn.execute("""
                        INSERT OR REPLACE INTO asset_properties 
                        (asset_id, property_type, property_key, property_value, data_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (asset_id, 'technical', 'bbox_max', json.dumps(bbox_max), 'json'))

                    conn.commit()

            # Add category tag
            if asset_data.get('category'):
                with self.db.get_connection() as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO asset_tags 
                        (asset_id, tag_name, tag_category, confidence)
                        VALUES (?, ?, ?, ?)
                    """, (asset_id, asset_data['category'], 'category', 1.0))
                    conn.commit()

        except Exception as e:
            logger.warning(f"Failed to add asset metadata for {asset_data['name']}: {e}")

        return asset_id
    
    def _determine_size_category(self, width: float, height: float, depth: float) -> str:
        """Determine size category based on dimensions."""
        max_dimension = max(width, height, depth)
        
        if max_dimension < 0.5:  # Less than 50cm
            return 'small'
        elif max_dimension < 2.0:  # Less than 2m
            return 'medium'
        elif max_dimension < 10.0:  # Less than 10m
            return 'large'
        else:
            return 'huge'
    
    # ============================================================================
    # Reporting
    # ============================================================================

    def _create_summary(self, pack_id: int, processed: int, failed: int, start_time: float) -> Dict[str, Any]:
        """Create scan summary with results."""
        end_time = time.time()
        duration = end_time - start_time
        
        # Get pack info and assets
        pack_info = self.db.get_asset_pack(pack_id)
        assets = self.db.fast_asset_search(pack_id=pack_id, limit=10000)
        
        # Count by category
        category_counts = defaultdict(int)
        quality_counts = defaultdict(int)
        for asset in assets:
            category_counts[asset['category']] += 1
            quality_counts[asset['quality_tier']] += 1
        
        return {
            'pack_info': pack_info,
            'scan_stats': {
                'files_queued': processed + failed,
                'files_processed': processed,
                'files_failed': failed,
                'duration_seconds': duration
            },
            'total_assets': len(assets),
            'category_breakdown': dict(category_counts),
            'quality_breakdown': dict(quality_counts),
            'database_stats': self.db.get_database_stats()
        }


# Public API
def scan_bms_pack_robust(pack_path: str, pack_name: str = None,
                        force_rescan: bool = False) -> Dict[str, Any]:
    """
    Scan a BMS asset pack and extract all visual assets.

    Args:
        pack_path: Path to the asset pack directory
        pack_name: Name for the pack (defaults to directory name)
        force_rescan: If True, clear existing pack data before scanning

    Returns:
        Dictionary with scan results and statistics
    """
    scanner = RobustAssetScanner()
    return scanner.scan_asset_pack_robust(pack_path, pack_name, force_rescan)

def scan_bms_pack(pack_path: str, pack_name: str = None,
                 force_rescan: bool = False) -> Dict[str, Any]:
    """Legacy alias for scan_bms_pack_robust()."""
    return scan_bms_pack_robust(pack_path, pack_name, force_rescan)

def add_classification_pattern(pattern_type: str, pattern_name: str,
                             keywords: List[str], confidence: float = 0.8):
    """
    Add a classification pattern to the database for automatic asset categorization.

    Args:
        pattern_type: Type of pattern ('category', 'style', or 'material_family')
        pattern_name: Name of the pattern
        keywords: List of keywords to match against asset names
        confidence: Confidence score (0.0-1.0) for this pattern
    """
    db = get_database()
    db.add_classification_pattern(pattern_type, pattern_name, keywords, confidence)
    logger.info(f"Added {pattern_type} pattern: {pattern_name}")

def get_scan_queue_status() -> Dict[str, Any]:
    """Get scan queue status and database statistics."""
    db = get_database()
    stats = db.get_database_stats()
    return {
        'total_in_queue': stats.get('scan_queue', 0),
        'queue_status': stats.get('scan_queue_status', {}),
        'database_stats': stats
    }