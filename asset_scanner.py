# asset_scanner.py
"""
Clean Asset Scanner Module - Refactored and Simplified
Scans BMS asset packs and extracts only visual 3D assets, filtering out rig controls.
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
    """Clean, working asset scanner that filters out rig controls and extracts only visual assets."""
    
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
        """Main scanning method - processes asset pack and extracts visual assets only."""
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
        """Process a single blend file using subprocess."""
        # Test Blender executable
        try:
            test_cmd = [self.blender_executable, "--version"]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
            if test_result.returncode != 0:
                raise Exception(f"Blender test failed: {test_result.stderr}")
        except Exception as e:
            raise Exception(f"Blender executable not working: {e}")
        
        # Create extraction script
        script_content = self._create_extraction_script()
        
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
    
    def _create_extraction_script(self) -> str:
        """Create the Blender extraction script with visual asset filtering."""
        return f'''
import bpy
import json
import sys
import os
import mathutils

output_path = sys.argv[-1] if len(sys.argv) > 6 else "output.json"
CATEGORY_PATTERNS = {json.dumps(self.category_patterns)}

def extract_visual_assets():
    """Extract only visual assets with actual geometry."""
    data = {{
        'file_info': {{
            'path': bpy.data.filepath,
            'name': os.path.basename(bpy.data.filepath),
            'collections': [],
            'objects': []
        }},
        'success': True
    }}
    
    # Process collections
    for collection in bpy.data.collections:
        if should_skip_collection(collection):
            continue
        
        visual_objects = [obj for obj in collection.objects if is_visual_object(obj)]
        if not visual_objects:
            continue
        
        # Calculate collection stats
        total_polygons = sum(len(obj.data.polygons) for obj in visual_objects)
        total_vertices = sum(len(obj.data.vertices) for obj in visual_objects)
        
        # Calculate bounding box
        bbox_min = [float('inf')] * 3
        bbox_max = [float('-inf')] * 3
        
        for obj in visual_objects:
            for corner in obj.bound_box:
                world_pos = obj.matrix_world @ mathutils.Vector(corner)
                for i in range(3):
                    bbox_min[i] = min(bbox_min[i], world_pos[i])
                    bbox_max[i] = max(bbox_max[i], world_pos[i])
        
        dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
        
        # Only include collections with actual size and geometry
        if total_polygons > 0 and max(dimensions) > 0.01:
            category = classify_name(collection.name, CATEGORY_PATTERNS) or 'props'
            
            data['file_info']['collections'].append({{
                'name': collection.name,
                'type': 'collection',
                'polygon_count': total_polygons,
                'vertex_count': total_vertices,
                'object_count': len(visual_objects),
                'dimensions': dimensions,
                'category': category,
                'complexity_score': calculate_complexity(total_polygons, len(visual_objects)),
                'quality_tier': determine_quality(total_polygons),
                'has_geometry': True
            }})
            print(f"Added collection: {{collection.name}} - {{total_polygons}} polys")
    
    # Process standalone objects
    for obj in bpy.data.objects:
        if not is_visual_object(obj) or len(obj.users_collection) > 1:
            continue
        
        if should_skip_object_name(obj.name):
            continue
        
        polygon_count = len(obj.data.polygons)
        vertex_count = len(obj.data.vertices)
        
        # Calculate dimensions
        bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        bbox_min = [min(corner[i] for corner in bbox_corners) for i in range(3)]
        bbox_max = [max(corner[i] for corner in bbox_corners) for i in range(3)]
        dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
        
        if polygon_count > 0 and max(dimensions) > 0.01:
            category = classify_name(obj.name, CATEGORY_PATTERNS) or 'props'
            
            data['file_info']['objects'].append({{
                'name': obj.name,
                'type': 'object',
                'polygon_count': polygon_count,
                'vertex_count': vertex_count,
                'dimensions': dimensions,
                'category': category,
                'complexity_score': calculate_complexity(polygon_count, 1),
                'quality_tier': determine_quality(polygon_count),
                'has_geometry': True
            }})
            print(f"Added object: {{obj.name}} - {{polygon_count}} polys")
    
    collections = len(data['file_info']['collections'])
    objects = len(data['file_info']['objects'])
    print(f"Extraction complete: {{collections}} collections, {{objects}} objects")
    return data

def should_skip_collection(collection):
    """Skip empty or system collections."""
    if len(collection.objects) == 0:
        return True
    name_lower = collection.name.lower()
    if name_lower in ['collection', 'scene collection']:
        return True
    skip_keywords = ['rig', 'control', 'bone', 'constraint', 'driver', 'meta']
    return any(keyword in name_lower for keyword in skip_keywords)

def should_skip_object_name(name):
    """Skip rig controls and system objects by name."""
    name_lower = name.lower()
    skip_prefixes = ['cs_', 'ctrl', 'ik_', 'bone', 'meta', 'wgt_']
    if any(name_lower.startswith(prefix) for prefix in skip_prefixes):
        return True
    skip_keywords = ['control', 'constraint', 'driver', 'target', 'pole', 'helper', 'locator']
    return any(keyword in name_lower for keyword in skip_keywords)

def is_visual_object(obj):
    """Check if object is a visual mesh with geometry."""
    if obj.type != 'MESH' or not obj.data:
        return False
    if len(obj.data.polygons) == 0:
        return False
    if max(obj.dimensions) < 0.01:  # Less than 1cm
        return False
    return True

def classify_name(name, patterns):
    """Classify name using patterns."""
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
    """Calculate 0-10 complexity score."""
    if polygon_count < 100: poly_score = 1
    elif polygon_count < 500: poly_score = 3
    elif polygon_count < 2000: poly_score = 5
    elif polygon_count < 10000: poly_score = 7
    else: poly_score = 9
    
    object_multiplier = min(1.0 + (object_count - 1) * 0.1, 2.0)
    return min(poly_score * object_multiplier, 10.0)

def determine_quality(polygon_count):
    """Determine quality tier."""
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
    error_data = {{"error": str(e), "success": False}}
    with open(output_path, 'w') as f:
        json.dump(error_data, f)
    print(f"ERROR: {{e}}")
    raise
'''
    
    def _store_extracted_data(self, data: Dict, pack_id: int, blend_file_path: str) -> int:
        """Store extracted asset data in database."""
        if not data.get('success') or 'error' in data:
            raise Exception(data.get('error', 'Extraction failed'))
        
        file_info = data['file_info']
        relative_path = os.path.relpath(blend_file_path, self.db.get_asset_pack(pack_id)['path'])
        assets_created = 0
        
        # Store collections
        for coll_data in file_info.get('collections', []):
            try:
                asset_id = self._create_database_asset(coll_data, pack_id, relative_path, blend_file_path)
                assets_created += 1
            except Exception as e:
                logger.error(f"Failed to create collection asset {coll_data['name']}: {e}")
        
        # Store objects
        for obj_data in file_info.get('objects', []):
            try:
                asset_id = self._create_database_asset(obj_data, pack_id, relative_path, blend_file_path)
                assets_created += 1
            except Exception as e:
                logger.error(f"Failed to create object asset {obj_data['name']}: {e}")
        
        return assets_created
    
    def _create_database_asset(self, asset_data: Dict, pack_id: int, 
                              relative_path: str, blend_file_path: str) -> int:
        """Create single asset entry in database."""
        # Extract data with defaults
        polygon_count = asset_data.get('polygon_count', 0)
        vertex_count = asset_data.get('vertex_count', 0)
        complexity_score = asset_data.get('complexity_score', 0.0)
        quality_tier = asset_data.get('quality_tier', 'medium')
        dimensions = asset_data.get('dimensions', [0.0, 0.0, 0.0])
        
        # Create asset in database
        asset_id = self.db.create_asset_optimized(
            name=asset_data['name'],
            pack_id=pack_id,
            category=asset_data.get('category', 'props'),
            blend_file_path=blend_file_path,
            subcategory=None,
            collection_name=asset_data['name'] if asset_data['type'] == 'collection' else None,
            file_path=relative_path,
            polygon_count=polygon_count,
            vertex_count=vertex_count,
            material_count=0,
            object_count=asset_data.get('object_count', 1),
            dimensions=dimensions,
            complexity_score=complexity_score,
            quality_tier=quality_tier,
            estimated_load_time=max(0.1, polygon_count / 10000),
            memory_estimate=max(1.0, polygon_count / 1000),
            primary_style=None,
            size_category='medium'
        )
        
        # Add category tag
        try:
            if asset_data.get('category'):
                self.db.add_asset_tag(asset_id, asset_data['category'], 'category', 1.0)
        except:
            pass  # Ignore tag errors
        
        return asset_id
    
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


# Compatibility wrapper
class AssetScanner(RobustAssetScanner):
    """Backward compatibility wrapper."""
    
    def scan_asset_pack(self, pack_path: str, pack_name: str = None, 
                       force_rescan: bool = False) -> Dict[str, Any]:
        return self.scan_asset_pack_robust(pack_path, pack_name, force_rescan)


# Convenience functions
def scan_bms_pack_robust(pack_path: str, pack_name: str = None, 
                        force_rescan: bool = False, max_workers: int = 1) -> Dict[str, Any]:
    """Scan BMS asset pack with visual asset filtering."""
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