# asset_scanner.py - Fixed dimension calculation version
"""
Asset Scanner Module with Fixed Dimension Calculations
Scans BMS asset packs and extracts visual 3D assets with accurate dimensions.
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

from .database import get_database, AssetDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RobustAssetScanner:
    """Asset scanner with fixed dimension calculations."""
    
    def __init__(self, database: AssetDatabase = None):
        self.db = database or get_database()
        self.blender_executable = self._find_blender_executable()
        self._load_classification_patterns()
        logger.info(f"Scanner initialized with Blender: {self.blender_executable}")
    
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
    
    def scan_asset_pack_robust(self, pack_path: str, pack_name: str = None, 
                              force_rescan: bool = False) -> Dict[str, Any]:
        """Main scanning method with fixed dimension calculations."""
        start_time = time.time()
        logger.info(f"Starting asset pack scan with FIXED dimensions: {pack_path}")
        
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
                logger.info(f"  ✅ Created {assets_created} assets with FIXED dimensions")
            except Exception as e:
                failed += 1
                logger.error(f"  ❌ Failed: {e}")
        
        return self._create_summary(pack_id, processed, failed, start_time)
    
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
    
    def _process_blend_file(self, blend_file_path: str, pack_id: int) -> int:
        """Process a single blend file using subprocess with FIXED dimension calculation."""
        # Test Blender executable
        try:
            test_cmd = [self.blender_executable, "--version"]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
            if test_result.returncode != 0:
                raise Exception(f"Blender test failed: {test_result.stderr}")
        except Exception as e:
            raise Exception(f"Blender executable not working: {e}")
        
        # Create extraction script with FIXED dimension calculation
        script_content = self._create_fixed_extraction_script()
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(script_content)
            script_path = script_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Run Blender subprocess
            cmd = [
                self.blender_executable,
                "--background",
                blend_file_path,
                "--python", script_path,
                "--", output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=os.path.dirname(blend_file_path)
            )
            
            if result.returncode != 0:
                raise Exception(f"Blender subprocess failed (code {result.returncode}): {result.stderr[-200:]}")
            
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
                except:
                    pass
    
    def _create_fixed_extraction_script(self) -> str:
        """Create the complete Blender extraction script with FIXED dimension calculations."""
        script = f"""
import bpy
import json
import sys
import os
import mathutils
from mathutils import Vector

output_path = sys.argv[-1] if len(sys.argv) > 6 else "output.json"
CATEGORY_PATTERNS = {json.dumps(self.category_patterns)}

def extract_visual_assets():
    \"\"\"Extract visual assets with FIXED dimension calculations.\"\"\"
    data = {{
        'file_info': {{
            'path': bpy.data.filepath,
            'name': os.path.basename(bpy.data.filepath),
            'collections': [],
            'objects': []
        }},
        'success': True
    }}
    
    print(f"🔍 FIXED SCANNER: Scanning file: {{os.path.basename(bpy.data.filepath)}}")
    
    # Process collections with FIXED dimension calculation
    for collection in bpy.data.collections:
        if should_skip_collection(collection):
            continue
        
        visual_objects = [obj for obj in collection.objects if is_visual_object(obj)]
        if not visual_objects:
            continue
        
        # Calculate collection stats
        total_polygons = sum(get_polygon_count(obj) for obj in visual_objects)
        total_vertices = sum(get_vertex_count(obj) for obj in visual_objects)
        
        # FIXED: Calculate proper bounding box for collection
        bbox_min, bbox_max, dimensions = calculate_collection_bounds(visual_objects)
        
        # Only include collections with actual size and geometry
        if total_polygons > 0 and max(dimensions) > 0.001:  # At least 1mm
            category = classify_name(collection.name, CATEGORY_PATTERNS) or 'props'
            
            data['file_info']['collections'].append({{
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
            }})
            print(f"✅ FIXED: Collection {{collection.name}} - {{total_polygons}} polys, dims: {{[round(d, 3) for d in dimensions]}}")
        else:
            print(f"⚠️  FIXED: Skipped collection {{collection.name}} - {{total_polygons}} polys, dims: {{[round(d, 3) for d in dimensions]}}")
    
    # Process standalone objects with FIXED dimension calculation
    for obj in bpy.data.objects:
        if not is_visual_object(obj) or len(obj.users_collection) > 1:
            continue
        
        if should_skip_object_name(obj.name):
            continue
        
        polygon_count = get_polygon_count(obj)
        vertex_count = get_vertex_count(obj)
        
        # FIXED: Calculate proper dimensions for object
        bbox_min, bbox_max, dimensions = calculate_object_bounds(obj)
        
        if polygon_count > 0 and max(dimensions) > 0.001:  # At least 1mm
            category = classify_name(obj.name, CATEGORY_PATTERNS) or 'props'
            
            data['file_info']['objects'].append({{
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
            }})
            print(f"✅ FIXED: Object {{obj.name}} - {{polygon_count}} polys, dims: {{[round(d, 3) for d in dimensions]}}")
        else:
            print(f"⚠️  FIXED: Skipped object {{obj.name}} - {{polygon_count}} polys, dims: {{[round(d, 3) for d in dimensions]}}")
    
    collections = len(data['file_info']['collections'])
    objects = len(data['file_info']['objects'])
    print(f"📊 FIXED EXTRACTION complete: {{collections}} collections, {{objects}} objects")
    return data

def calculate_collection_bounds(visual_objects):
    \"\"\"Calculate accurate bounding box for a collection of objects.\"\"\"
    if not visual_objects:
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]
    
    # Initialize with impossible values
    bbox_min = [float('inf')] * 3
    bbox_max = [float('-inf')] * 3
    valid_bounds_found = False
    
    for obj in visual_objects:
        obj_bbox_min, obj_bbox_max, obj_dimensions = calculate_object_bounds(obj)
        
        # Only include if object has valid dimensions
        if max(obj_dimensions) > 0.001:
            valid_bounds_found = True
            for i in range(3):
                bbox_min[i] = min(bbox_min[i], obj_bbox_min[i])
                bbox_max[i] = max(bbox_max[i], obj_bbox_max[i])
    
    # Handle case where no valid bounds found
    if not valid_bounds_found:
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]
    
    dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
    return bbox_min, bbox_max, dimensions

def calculate_object_bounds(obj):
    \"\"\"Calculate accurate world-space bounding box for an object with multiple methods.\"\"\"
    if not obj or not obj.data or obj.type != 'MESH':
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]
    
    mesh = obj.data
    
    # Handle empty mesh
    if len(mesh.vertices) == 0:
        return [0, 0, 0], [0, 0, 0], [0, 0, 0]
    
    # Method 1: Transform all vertices to world space (most accurate)
    try:
        if hasattr(obj, 'matrix_world') and mesh.vertices:
            world_vertices = []
            
            # Transform each vertex to world coordinates
            for vertex in mesh.vertices:
                world_pos = obj.matrix_world @ vertex.co
                world_vertices.append([world_pos.x, world_pos.y, world_pos.z])
            
            if world_vertices:
                bbox_min = [min(v[i] for v in world_vertices) for i in range(3)]
                bbox_max = [max(v[i] for v in world_vertices) for i in range(3)]
                dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
                
                # Validate dimensions are reasonable
                if max(dimensions) > 0.0001:  # At least 0.1mm
                    return bbox_min, bbox_max, dimensions
    except Exception as e:
        print(f"FIXED: Method 1 failed for {{obj.name}}: {{e}}")
    
    # Method 2: Use object's bound_box property
    try:
        if hasattr(obj, 'bound_box') and obj.bound_box:
            # Transform bound box corners to world space
            world_corners = []
            for corner in obj.bound_box:
                world_pos = obj.matrix_world @ Vector(corner)
                world_corners.append([world_pos.x, world_pos.y, world_pos.z])
            
            if world_corners:
                bbox_min = [min(corner[i] for corner in world_corners) for i in range(3)]
                bbox_max = [max(corner[i] for corner in world_corners) for i in range(3)]
                dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
                
                if max(dimensions) > 0.0001:
                    return bbox_min, bbox_max, dimensions
    except Exception as e:
        print(f"FIXED: Method 2 failed for {{obj.name}}: {{e}}")
    
    # Method 3: Use object dimensions property with scale
    try:
        if hasattr(obj, 'dimensions') and hasattr(obj, 'location'):
            dims = list(obj.dimensions)
            loc = list(obj.location)
            
            # Apply object scale if available
            if hasattr(obj, 'scale'):
                for i in range(3):
                    dims[i] *= obj.scale[i]
            
            if max(dims) > 0.0001:
                # Create bounding box around location
                bbox_min = [loc[i] - dims[i]/2 for i in range(3)]
                bbox_max = [loc[i] + dims[i]/2 for i in range(3)]
                return bbox_min, bbox_max, dims
    except Exception as e:
        print(f"FIXED: Method 3 failed for {{obj.name}}: {{e}}")
    
    # Final fallback: object location as point
    try:
        if hasattr(obj, 'location'):
            loc = list(obj.location)
            return loc, loc, [0, 0, 0]
    except:
        pass
    
    # Ultimate fallback
    return [0, 0, 0], [0, 0, 0], [0, 0, 0]

def get_polygon_count(obj):
    \"\"\"Safely get polygon count from object.\"\"\"
    try:
        if obj and obj.type == 'MESH' and obj.data and hasattr(obj.data, 'polygons'):
            return len(obj.data.polygons)
    except:
        pass
    return 0

def get_vertex_count(obj):
    \"\"\"Safely get vertex count from object.\"""
    try:
        if obj and obj.type == 'MESH' and obj.data and hasattr(obj.data, 'vertices'):
            return len(obj.data.vertices)
    except:
        pass
    return 0

def should_skip_collection(collection):
    \"\"\"Skip empty or system collections.\"""
    if not collection or len(collection.objects) == 0:
        return True
    name_lower = collection.name.lower()
    if name_lower in ['collection', 'scene collection']:
        return True
    skip_keywords = ['rig', 'control', 'bone', 'constraint', 'driver', 'meta']
    return any(keyword in name_lower for keyword in skip_keywords)

def should_skip_object_name(name):
    \"\"\"Skip rig controls and system objects by name.\"""
    if not name:
        return True
    name_lower = name.lower()
    skip_prefixes = ['cs_', 'ctrl', 'ik_', 'bone', 'meta', 'wgt_']
    if any(name_lower.startswith(prefix) for prefix in skip_prefixes):
        return True
    skip_keywords = ['control', 'constraint', 'driver', 'target', 'pole', 'helper', 'locator']
    return any(keyword in name_lower for keyword in skip_keywords)

def is_visual_object(obj):
    \"\"\"Check if object is a visual mesh with geometry.\"""
    if not obj or obj.type != 'MESH' or not obj.data:
        return False
    
    # Check if has actual geometry
    polygon_count = get_polygon_count(obj)
    if polygon_count == 0:
        return False
    
    # Quick dimension check to filter out obvious empties
    try:
        if hasattr(obj, 'dimensions'):
            if max(obj.dimensions) < 0.0001:  # Less than 0.1mm
                return False
    except:
        pass
    
    return True

def classify_name(name, patterns):
    \"\"\"Classify name using patterns.\"""
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
    \"\"\"Calculate 0-10 complexity score.\"""
    if polygon_count < 100: poly_score = 1
    elif polygon_count < 500: poly_score = 3
    elif polygon_count < 2000: poly_score = 5
    elif polygon_count < 10000: poly_score = 7
    else: poly_score = 9
    
    object_multiplier = min(1.0 + (object_count - 1) * 0.1, 2.0)
    return min(poly_score * object_multiplier, 10.0)

def determine_quality(polygon_count):
    \"\"\"Determine quality tier.\"""
    if polygon_count < 500: return 'low'
    elif polygon_count < 2000: return 'medium'
    elif polygon_count < 10000: return 'high'
    else: return 'ultra'

# Main execution
try:
    result = extract_visual_assets()
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
except Exception as e:
    import traceback
    error_data = {{"error": str(e), "traceback": traceback.format_exc(), "success": False}}
    with open(output_path, 'w') as f:
        json.dump(error_data, f)
    print(f"FIXED SCANNER ERROR: {{e}}")
    raise
"""
        return script
    
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


# Convenience functions
def scan_bms_pack_robust(pack_path: str, pack_name: str = None, 
                        force_rescan: bool = False, max_workers: int = 1) -> Dict[str, Any]:
    """Scan BMS asset pack with fixed dimension calculations."""
    scanner = RobustAssetScanner()
    return scanner.scan_asset_pack_robust(pack_path, pack_name, force_rescan)

def scan_bms_pack(pack_path: str, pack_name: str = None, 
                 force_rescan: bool = False) -> Dict[str, Any]:
    """Legacy convenience function."""
    return scan_bms_pack_robust(pack_path, pack_name, force_rescan)

def add_classification_pattern(pattern_type: str, pattern_name: str, 
                             keywords: List[str], confidence: float = 0.8):
    """Add classification pattern to database."""
    db = get_database()
    db.add_classification_pattern(pattern_type, pattern_name, keywords, confidence)
    logger.info(f"Added {pattern_type} pattern: {pattern_name}")

def get_scan_queue_status() -> Dict[str, Any]:
    """Get scan queue status."""
    db = get_database()
    stats = db.get_database_stats()
    return {
        'total_in_queue': stats.get('scan_queue', 0),
        'queue_status': stats.get('scan_queue_status', {}),
        'database_stats': stats
    }