# asset_scanner.py
"""
Asset Scanner Module - Production-Grade with Subprocess Isolation
Robust scanning system using external Blender processes and data-driven classification.
"""

import os
import json
import logging
import time
import subprocess
import tempfile
import threading
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict
import queue
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from .database import create_database, AssetDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RobustAssetScanner:
    """
    Production-grade asset scanner using subprocess isolation and data-driven classification.
    Resilient to crashes and highly configurable.
    """
    
    def __init__(self, database: AssetDatabase = None, max_workers: int = 2):
        """Initialize the robust asset scanner."""
        self.db = database or create_database()
        self.max_workers = max_workers
        self.scan_stats = {
            'files_queued': 0,
            'files_processed': 0,
            'files_failed': 0,
            'start_time': None,
            'end_time': None,
            'workers_active': 0
        }
        
        # Get classification patterns from database
        self._load_classification_patterns()
        
        # Blender executable path (auto-detect or set manually)
        self.blender_executable = self._find_blender_executable()
    
    def _find_blender_executable(self) -> str:
        """Auto-detect Blender executable path."""
        import bpy
        
        # Try to get from current Blender instance
        try:
            import sys
            blender_path = sys.executable
            if blender_path and os.path.exists(blender_path):
                return blender_path
        except:
            pass
        
        # Common Blender installation paths
        common_paths = [
            "blender",  # If in PATH
            "/usr/bin/blender",  # Linux
            "/Applications/Blender.app/Contents/MacOS/Blender",  # macOS
            "C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",  # Windows
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        # If we can't find it, use the one we're running from
        return bpy.app.binary_path
    
    def _load_classification_patterns(self):
        """Load classification patterns from database."""
        self.category_patterns = {}
        self.style_patterns = {}
        self.material_patterns = {}
        
        try:
            # Load category patterns
            patterns = self.db.get_classification_patterns('category')
            for pattern in patterns:
                self.category_patterns[pattern['pattern_name']] = {
                    'keywords': pattern['keywords'],
                    'confidence': pattern['confidence'],
                    'priority': pattern['priority']
                }
            
            # Load style patterns
            patterns = self.db.get_classification_patterns('style')
            for pattern in patterns:
                self.style_patterns[pattern['pattern_name']] = {
                    'keywords': pattern['keywords'],
                    'confidence': pattern['confidence'],
                    'priority': pattern['priority']
                }
            
            # Load material patterns
            patterns = self.db.get_classification_patterns('material_family')
            for pattern in patterns:
                self.material_patterns[pattern['pattern_name']] = {
                    'keywords': pattern['keywords'],
                    'confidence': pattern['confidence'],
                    'priority': pattern['priority']
                }
                
            logger.info(f"Loaded {len(self.category_patterns)} category patterns, "
                       f"{len(self.style_patterns)} style patterns, "
                       f"{len(self.material_patterns)} material patterns")
        except Exception as e:
            logger.error(f"Failed to load classification patterns: {e}")
            # Initialize empty patterns as fallback
            self.category_patterns = {}
            self.style_patterns = {}
            self.material_patterns = {}
    
    def scan_asset_pack_robust(self, pack_path: str, pack_name: str = None, 
                              force_rescan: bool = False, 
                              max_concurrent: int = None) -> Dict[str, Any]:
        """
        Robust asset pack scanning using subprocess isolation and queue-based processing.
        
        Args:
            pack_path: Path to the asset pack directory
            pack_name: Name of the pack (auto-detected if None)
            force_rescan: Whether to rescan existing assets
            max_concurrent: Maximum concurrent Blender processes (defaults to max_workers)
            
        Returns:
            Dictionary with scan results and statistics
        """
        self.scan_stats = {
            'files_queued': 0,
            'files_processed': 0,
            'files_failed': 0,
            'start_time': time.time(),
            'end_time': None,
            'workers_active': 0
        }
        
        logger.info(f"Starting robust asset pack scan: {pack_path}")
        
        # Validate pack path
        if not os.path.exists(pack_path):
            raise FileNotFoundError(f"Asset pack path does not exist: {pack_path}")
        
        # Auto-detect pack name if not provided
        if pack_name is None:
            pack_name = os.path.basename(pack_path.rstrip('/\\'))
        
        # Create or get pack entry
        existing_pack = self.db.get_asset_pack(name=pack_name)
        if existing_pack:
            pack_id = existing_pack['id']
            if not force_rescan:
                logger.info(f"Pack '{pack_name}' already exists. Use force_rescan=True to update.")
                return self._get_scan_summary(pack_id)
        else:
            pack_id = self.db.create_asset_pack(
                name=pack_name,
                path=pack_path,
                version="1.0",
                description=f"Auto-scanned BMS asset pack from {pack_path}"
            )
        
        # Phase 1: Populate scan queue
        self._populate_scan_queue(pack_path, pack_id, force_rescan)
        
        # Phase 2: Process queue with multiple workers
        max_concurrent = max_concurrent or self.max_workers
        self._process_scan_queue_concurrent(max_concurrent)
        
        self.scan_stats['end_time'] = time.time()
        
        # Generate scan summary
        summary = self._get_scan_summary(pack_id)
        logger.info(f"Robust asset pack scan completed: {summary}")
        
        return summary
    
    def _populate_scan_queue(self, pack_path: str, pack_id: int, force_rescan: bool):
        """Populate the scan queue with all blend files."""
        blend_files = self._find_blend_files(pack_path)
        logger.info(f"Found {len(blend_files)} blend files")
        
        for blend_file in blend_files:
            try:
                # Check if already processed (unless force_rescan)
                if not force_rescan:
                    # Could add logic to check if file was already scanned
                    pass
                
                queue_id = self.db.add_to_scan_queue(blend_file, pack_id)
                if queue_id:
                    self.scan_stats['files_queued'] += 1
                    
            except Exception as e:
                logger.error(f"Error adding {blend_file} to queue: {e}")
        
        logger.info(f"Added {self.scan_stats['files_queued']} files to scan queue")
    
    def _process_scan_queue_concurrent(self, max_workers: int):
        """Process scan queue using multiple concurrent workers."""
        logger.info(f"Starting {max_workers} concurrent scan workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Start worker threads
            futures = []
            for worker_id in range(max_workers):
                future = executor.submit(self._scan_worker, f"worker_{worker_id}")
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Worker failed: {e}")
        
        logger.info("All scan workers completed")
    
    def _scan_worker(self, worker_id: str):
        """Individual worker that processes items from the scan queue."""
        logger.info(f"Scan worker {worker_id} started")
        self.scan_stats['workers_active'] += 1
        
        try:
            while True:
                # Get next item from queue
                item = self.db.get_next_scan_item(worker_id)
                if not item:
                    logger.info(f"Worker {worker_id}: No more items in queue")
                    break
                
                # Process the blend file
                try:
                    self._process_blend_file_subprocess(item, worker_id)
                    self.db.update_scan_status(item['id'], 'complete')
                    self.scan_stats['files_processed'] += 1
                    
                    # Log progress
                    if self.scan_stats['files_processed'] % 5 == 0:
                        logger.info(f"Worker {worker_id}: Processed {self.scan_stats['files_processed']} files")
                        
                except Exception as e:
                    error_msg = f"Worker {worker_id} failed to process {item['blend_file_path']}: {e}"
                    logger.error(error_msg)
                    self.db.update_scan_status(item['id'], 'failed', str(e))
                    self.scan_stats['files_failed'] += 1
                    
        finally:
            self.scan_stats['workers_active'] -= 1
            logger.info(f"Scan worker {worker_id} finished")
    
    def _process_blend_file_subprocess(self, queue_item: Dict, worker_id: str):
        """Process a blend file using isolated subprocess."""
        blend_file_path = queue_item['blend_file_path']
        pack_id = queue_item['pack_id']
        
        logger.debug(f"Worker {worker_id}: Processing {blend_file_path}")
        
        # Create temporary script for Blender to execute
        script_content = self._generate_extraction_script(blend_file_path, pack_id, worker_id)
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(script_content)
            script_path = script_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Run Blender in headless mode with our script
            cmd = [
                self.blender_executable,
                "--background",
                blend_file_path,
                "--python", script_path,
                "--", output_path  # Pass output file as argument
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per file
                cwd=os.path.dirname(blend_file_path)
            )
            
            if result.returncode != 0:
                raise Exception(f"Blender subprocess failed: {result.stderr}")
            
            # Read results from output file
            if os.path.exists(output_path):
                with open(output_path, 'r') as f:
                    extraction_data = json.load(f)
                
                # Store extracted data in database
                self._store_extraction_data(extraction_data, pack_id, blend_file_path)
            else:
                raise Exception("No output data generated")
                
        finally:
            # Clean up temporary files
            for temp_path in [script_path, output_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
    
    def _generate_extraction_script(self, blend_file_path: str, pack_id: int, worker_id: str) -> str:
        """Generate Python script for Blender to extract asset metadata."""
        
        # Include database path and classification patterns in script
        db_path = self.db.db_path
        
        return f'''
import bpy
import json
import sys
import os
import mathutils
from pathlib import Path

# Get output file path from command line args
output_path = sys.argv[-1]

# Classification patterns (loaded from database)
CATEGORY_PATTERNS = {json.dumps(self.category_patterns)}
STYLE_PATTERNS = {json.dumps(self.style_patterns)}
MATERIAL_PATTERNS = {json.dumps(self.material_patterns)}

def extract_asset_data():
    """Extract comprehensive asset data from current blend file."""
    
    data = {{
        'file_info': {{
            'path': bpy.data.filepath,
            'name': os.path.basename(bpy.data.filepath),
            'collections': [],
            'objects': []
        }},
        'pack_id': {pack_id},
        'worker_id': '{worker_id}'
    }}
    
    # Process collections
    for collection in bpy.data.collections:
        if len(collection.objects) == 0 or collection.name in ['Collection', 'Scene Collection']:
            continue
            
        try:
            coll_data = extract_collection_metadata(collection)
            if coll_data:
                data['file_info']['collections'].append(coll_data)
        except Exception as e:
            print(f"Error processing collection {{collection.name}}: {{e}}")
    
    # Process standalone objects
    standalone_objects = []
    for obj in bpy.data.objects:
        if (obj.type == 'MESH' and 
            obj.data and 
            len(obj.users_collection) <= 1 and  
            not is_system_object(obj)):
            standalone_objects.append(obj)
    
    for obj in standalone_objects:
        try:
            obj_data = extract_object_metadata(obj)
            if obj_data:
                data['file_info']['objects'].append(obj_data)
        except Exception as e:
            print(f"Error processing object {{obj.name}}: {{e}}")
    
    return data

def extract_collection_metadata(collection):
    """Extract metadata from a collection."""
    objects = list(collection.objects)
    mesh_objects = [obj for obj in objects if obj.type == 'MESH' and obj.data]
    
    if not mesh_objects:
        return None
    
    # Calculate bounding box and statistics
    bbox_min = [float('inf')] * 3
    bbox_max = [float('-inf')] * 3
    total_polygons = 0
    total_vertices = 0
    materials = set()
    
    for obj in mesh_objects:
        # Update bounding box
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            for i in range(3):
                bbox_min[i] = min(bbox_min[i], world_corner[i])
                bbox_max[i] = max(bbox_max[i], world_corner[i])
        
        # Accumulate statistics
        if obj.data:
            total_polygons += len(obj.data.polygons)
            total_vertices += len(obj.data.vertices)
            
            for material_slot in obj.material_slots:
                if material_slot.material:
                    materials.add(material_slot.material.name)
    
    dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
    
    return {{
        'name': collection.name,
        'type': 'collection',
        'object_count': len(objects),
        'mesh_count': len(mesh_objects),
        'polygon_count': total_polygons,
        'vertex_count': total_vertices,
        'dimensions': dimensions,
        'volume': dimensions[0] * dimensions[1] * dimensions[2],
        'materials': list(materials),
        'material_count': len(materials),
        'complexity_score': calculate_complexity_score(total_polygons, len(mesh_objects)),
        'category': classify_by_patterns(collection.name, CATEGORY_PATTERNS),
        'style': classify_by_patterns(collection.name, STYLE_PATTERNS),
        'material_families': [classify_by_patterns(mat, MATERIAL_PATTERNS) for mat in materials]
    }}

def extract_object_metadata(obj):
    """Extract metadata from a single object."""
    if not obj.data or obj.type != 'MESH':
        return None
    
    mesh = obj.data
    
    # Calculate world-space dimensions
    bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    bbox_min = [min(corner[i] for corner in bbox_corners) for i in range(3)]
    bbox_max = [max(corner[i] for corner in bbox_corners) for i in range(3)]
    dimensions = [bbox_max[i] - bbox_min[i] for i in range(3)]
    
    # Extract materials
    materials = []
    for material_slot in obj.material_slots:
        if material_slot.material:
            materials.append(material_slot.material.name)
    
    polygon_count = len(mesh.polygons)
    vertex_count = len(mesh.vertices)
    
    return {{
        'name': obj.name,
        'type': 'object',
        'polygon_count': polygon_count,
        'vertex_count': vertex_count,
        'dimensions': dimensions,
        'volume': dimensions[0] * dimensions[1] * dimensions[2],
        'materials': materials,
        'material_count': len(materials),
        'has_uv_maps': len(mesh.uv_layers) > 0,
        'complexity_score': calculate_complexity_score(polygon_count, 1),
        'quality_tier': determine_quality_tier(polygon_count, len(materials)),
        'category': classify_by_patterns(obj.name, CATEGORY_PATTERNS),
        'style': classify_by_patterns(obj.name, STYLE_PATTERNS),
        'material_families': [classify_by_patterns(mat, MATERIAL_PATTERNS) for mat in materials]
    }}

def classify_by_patterns(name, patterns):
    """Classify name using pattern matching."""
    name_lower = name.lower()
    best_match = None
    best_confidence = 0.0
    
    # Sort patterns by priority
    sorted_patterns = sorted(patterns.items(), 
                           key=lambda x: x[1]['priority'], reverse=True)
    
    for pattern_name, pattern_data in sorted_patterns:
        keywords = pattern_data['keywords']
        confidence = pattern_data['confidence']
        
        for keyword in keywords:
            if keyword.lower() in name_lower:
                if confidence > best_confidence:
                    best_match = pattern_name
                    best_confidence = confidence
                break
    
    return best_match

def calculate_complexity_score(polygon_count, object_count=1):
    """Calculate complexity score from 0-10."""
    if polygon_count < 100:
        poly_score = 1
    elif polygon_count < 500:
        poly_score = 3
    elif polygon_count < 2000:
        poly_score = 5
    elif polygon_count < 10000:
        poly_score = 7
    else:
        poly_score = 9
    
    object_multiplier = min(1.0 + (object_count - 1) * 0.1, 2.0)
    return min(poly_score * object_multiplier, 10.0)

def determine_quality_tier(polygon_count, material_count):
    """Determine quality tier."""
    if polygon_count < 500 or material_count == 0:
        return 'low'
    elif polygon_count < 2000 and material_count < 3:
        return 'medium'
    elif polygon_count < 10000 and material_count < 5:
        return 'high'
    else:
        return 'ultra'

def is_system_object(obj):
    """Check if object is a system object."""
    return obj.type in ['CAMERA', 'LIGHT', 'EMPTY', 'ARMATURE', 'LATTICE']

# Main execution
try:
    extracted_data = extract_asset_data()
    
    # Write results to output file
    with open(output_path, 'w') as f:
        json.dump(extracted_data, f, indent=2)
    
    print(f"Successfully extracted data from {{bpy.data.filepath}}")
    
except Exception as e:
    error_data = {{
        'error': str(e),
        'file_path': bpy.data.filepath,
        'worker_id': '{worker_id}'
    }}
    
    with open(output_path, 'w') as f:
        json.dump(error_data, f, indent=2)
    
    print(f"Error extracting data: {{e}}")
    raise
'''
    
    def _store_extraction_data(self, data: Dict, pack_id: int, blend_file_path: str):
        """Store extracted data in the database."""
        if 'error' in data:
            raise Exception(data['error'])
        
        file_info = data['file_info']
        relative_path = os.path.relpath(blend_file_path, 
                                       self.db.get_asset_pack(pack_id)['path'])
        
        # Store collections as assets
        for coll_data in file_info.get('collections', []):
            self._create_asset_from_data(coll_data, pack_id, relative_path, blend_file_path)
        
        # Store objects as assets
        for obj_data in file_info.get('objects', []):
            self._create_asset_from_data(obj_data, pack_id, relative_path, blend_file_path)
    
    def _create_asset_from_data(self, asset_data: Dict, pack_id: int, 
                               relative_path: str, blend_file_path: str):
        """Create asset entry from extracted data."""
        
        # Determine size category
        dimensions = asset_data.get('dimensions', [0, 0, 0])
        max_dim = max(dimensions) if dimensions else 0
        if max_dim < 1.0:
            size_category = 'small'
        elif max_dim < 5.0:
            size_category = 'medium'
        elif max_dim < 20.0:
            size_category = 'large'
        else:
            size_category = 'huge'
        
        # Calculate performance estimates
        polygon_count = asset_data.get('polygon_count', 0)
        material_count = asset_data.get('material_count', 0)
        
        estimated_load_time = max(0.1, (polygon_count / 1000) * 0.5 + material_count * 0.1)
        memory_estimate = max(1.0, (polygon_count / 100) * 0.1 + material_count * 2.0)
        
        # Create asset with optimized method
        asset_id = self.db.create_asset_optimized(
            name=asset_data['name'],
            pack_id=pack_id,
            category=asset_data.get('category', 'props'),
            blend_file_path=blend_file_path,
            subcategory=None,  # Could be enhanced
            collection_name=asset_data['name'] if asset_data['type'] == 'collection' else None,
            file_path=relative_path,
            polygon_count=polygon_count,
            vertex_count=asset_data.get('vertex_count', 0),
            material_count=material_count,
            object_count=asset_data.get('object_count', 1),
            dimensions=dimensions,
            complexity_score=asset_data.get('complexity_score', 0.0),
            quality_tier=asset_data.get('quality_tier', 'medium'),
            estimated_load_time=round(estimated_load_time, 2),
            memory_estimate=round(memory_estimate, 1),
            primary_style=asset_data.get('style'),
            size_category=size_category
        )
        
        # Add material family tags
        material_families = asset_data.get('material_families', [])
        for family in material_families:
            if family:
                self.db.add_asset_tag(asset_id, family, 'material', 0.8)
        
        # Add other auto-detected tags
        if asset_data.get('category'):
            self.db.add_asset_tag(asset_id, asset_data['category'], 'category', 1.0)
        
        if asset_data.get('style'):
            self.db.add_asset_tag(asset_id, asset_data['style'], 'style', 0.8)
        
        complexity_score = asset_data.get('complexity_score', 0.0)
        if complexity_score < 3:
            complexity_tag = 'simple'
        elif complexity_score < 6:
            complexity_tag = 'moderate'
        elif complexity_score < 8:
            complexity_tag = 'complex'
        else:
            complexity_tag = 'very_complex'
        
        self.db.add_asset_tag(asset_id, complexity_tag, 'complexity', 0.9)
        self.db.add_asset_tag(asset_id, size_category, 'size', 0.9)
        
        logger.debug(f"Created asset: {asset_data['name']} (ID: {asset_id})")
        return asset_id
    
    def _find_blend_files(self, pack_path: str) -> List[str]:
        """Recursively find all .blend files in the pack directory."""
        blend_files = []
        
        for root, dirs, files in os.walk(pack_path):
            # Skip hidden directories and common non-asset directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                      d.lower() not in ['backup', 'temp', 'cache', '__pycache__']]
            
            for file in files:
                if file.lower().endswith('.blend') and not file.startswith('.'):
                    blend_files.append(os.path.join(root, file))
        
        return sorted(blend_files)
    
    def _get_scan_summary(self, pack_id: int) -> Dict[str, Any]:
        """Generate a summary of the scan results."""
        # Get pack info
        pack_info = self.db.get_asset_pack(pack_id)
        
        # Get asset counts by category
        assets = self.db.fast_asset_search(pack_id=pack_id, limit=10000)
        category_counts = defaultdict(int)
        quality_counts = defaultdict(int)
        
        for asset in assets:
            category_counts[asset['category']] += 1
            quality_counts[asset['quality_tier']] += 1
        
        # Calculate scan duration
        duration = None
        if self.scan_stats['start_time'] and self.scan_stats['end_time']:
            duration = self.scan_stats['end_time'] - self.scan_stats['start_time']
        
        return {
            'pack_info': pack_info,
            'scan_stats': self.scan_stats,
            'duration_seconds': duration,
            'total_assets': len(assets),
            'category_breakdown': dict(category_counts),
            'quality_breakdown': dict(quality_counts),
            'database_stats': self.db.get_database_stats()
        }


# Backward compatibility wrapper
class AssetScanner(RobustAssetScanner):
    """Backward compatibility wrapper for the original AssetScanner."""
    
    def scan_asset_pack(self, pack_path: str, pack_name: str = None, 
                       force_rescan: bool = False) -> Dict[str, Any]:
        """Legacy method that uses the robust scanner."""
        return self.scan_asset_pack_robust(pack_path, pack_name, force_rescan, max_concurrent=1)


# Convenience functions
def scan_bms_pack_robust(pack_path: str, pack_name: str = None, 
                        force_rescan: bool = False, max_workers: int = 2) -> Dict[str, Any]:
    """
    Robust convenience function to scan a BMS asset pack.
    Uses subprocess isolation and concurrent processing.
    """
    scanner = RobustAssetScanner(max_workers=max_workers)
    return scanner.scan_asset_pack_robust(pack_path, pack_name, force_rescan)

def scan_bms_pack(pack_path: str, pack_name: str = None, 
                 force_rescan: bool = False) -> Dict[str, Any]:
    """Legacy convenience function for backward compatibility."""
    return scan_bms_pack_robust(pack_path, pack_name, force_rescan, max_workers=1)

def add_classification_pattern(pattern_type: str, pattern_name: str, 
                             keywords: List[str], confidence: float = 0.8):
    """Add a new classification pattern to the database."""
    from .database import get_database
    db = get_database()
    db.add_classification_pattern(pattern_type, pattern_name, keywords, confidence)
    logger.info(f"Added {pattern_type} pattern: {pattern_name}")

def get_scan_queue_status() -> Dict[str, Any]:
    """Get current scan queue status."""
    from .database import get_database
    db = get_database()
    stats = db.get_database_stats()
    return {
        'total_in_queue': stats.get('scan_queue', 0),
        'queue_status': stats.get('scan_queue_status', {}),
        'database_stats': stats
    }