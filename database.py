# database.py
"""
Asset Intelligence Database Module - Optimized for Performance
Handles SQLite database operations with hybrid normalization approach.
"""

import sqlite3
import json
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
from datetime import datetime
import bpy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AssetDatabase:
    """
    Manages the SQLite database for asset intelligence.
    Optimized for high-speed queries with hybrid normalization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection and ensure schema exists."""
        if db_path is None:
            # Store database in Blender's user config directory
            config_path = bpy.utils.user_resource('CONFIG')
            self.db_path = os.path.join(config_path, "bms_asset_intelligence.db")
        else:
            self.db_path = db_path
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize schema
        self._initialize_schema()
        logger.info(f"Asset database initialized at: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            # Enable JSON support
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _initialize_schema(self):
        """Create optimized schema with denormalized critical properties."""
        schema_sql = """
        -- Asset packs table
        CREATE TABLE IF NOT EXISTS asset_packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            version TEXT,
            path TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Core assets table with denormalized critical properties for performance
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pack_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            file_path TEXT NOT NULL,
            collection_name TEXT,
            blend_file_path TEXT NOT NULL,
            thumbnail_path TEXT,
            
            -- DENORMALIZED CRITICAL PROPERTIES (for fast queries without JOINs)
            -- Technical properties
            polygon_count INTEGER DEFAULT 0,
            vertex_count INTEGER DEFAULT 0,
            material_count INTEGER DEFAULT 0,
            object_count INTEGER DEFAULT 1,
            
            -- Dimensions (in Blender units)
            width REAL DEFAULT 0.0,
            height REAL DEFAULT 0.0,
            depth REAL DEFAULT 0.0,
            volume REAL DEFAULT 0.0,
            
            -- Performance metrics
            complexity_score REAL DEFAULT 0.0,
            quality_tier TEXT DEFAULT 'medium', -- 'low', 'medium', 'high', 'ultra'
            estimated_load_time REAL DEFAULT 0.0, -- seconds
            memory_estimate REAL DEFAULT 0.0, -- MB
            
            -- Style and usage
            primary_style TEXT, -- 'cyberpunk', 'industrial', etc.
            size_category TEXT DEFAULT 'medium', -- 'small', 'medium', 'large', 'huge'
            
            -- Status
            is_active BOOLEAN DEFAULT 1,
            scan_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'complete', 'failed'
            last_scanned TIMESTAMP,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (pack_id) REFERENCES asset_packs (id) ON DELETE CASCADE,
            UNIQUE(name, pack_id, collection_name)
        );
        
        -- Extended properties for less frequently accessed metadata
        CREATE TABLE IF NOT EXISTS asset_properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            property_type TEXT NOT NULL, -- 'technical', 'visual', 'performance', 'custom'
            property_key TEXT NOT NULL,
            property_value TEXT NOT NULL,
            data_type TEXT NOT NULL, -- 'int', 'float', 'string', 'json', 'bool'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE,
            UNIQUE(asset_id, property_type, property_key)
        );
        
        -- Data-driven classification patterns (moved from hard-coded)
        CREATE TABLE IF NOT EXISTS classification_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL, -- 'category', 'style', 'material_family'
            pattern_name TEXT NOT NULL, -- 'cyberpunk', 'metal', 'architecture'
            keywords TEXT NOT NULL, -- JSON array of keywords
            confidence REAL DEFAULT 0.8, -- 0.0 to 1.0
            priority INTEGER DEFAULT 5, -- 1-10, higher = checked first
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pattern_type, pattern_name)
        );
        
        -- Professional rules with structured data
        CREATE TABLE IF NOT EXISTS asset_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            category TEXT, -- can apply to category instead of specific asset
            rule_type TEXT NOT NULL, -- 'placement', 'compatibility', 'quality', 'usage'
            rule_name TEXT NOT NULL,
            rule_data TEXT NOT NULL, -- JSON with structured rule data
            priority INTEGER DEFAULT 5,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
        );
        
        -- Asset relationships with performance optimization
        CREATE TABLE IF NOT EXISTS asset_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_1_id INTEGER NOT NULL,
            asset_2_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL, -- 'compatible', 'complementary', 'similar', 'conflicts'
            strength REAL NOT NULL, -- 0.0 to 1.0
            context_data TEXT, -- JSON for additional context
            auto_detected BOOLEAN DEFAULT 1,
            verified_by_expert BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_1_id) REFERENCES assets (id) ON DELETE CASCADE,
            FOREIGN KEY (asset_2_id) REFERENCES assets (id) ON DELETE CASCADE,
            UNIQUE(asset_1_id, asset_2_id, relationship_type)
        );
        
        -- Scene templates with queryable structure
        CREATE TABLE IF NOT EXISTS scene_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            style TEXT NOT NULL,
            complexity_level TEXT DEFAULT 'medium', -- 'simple', 'medium', 'complex'
            object_count_min INTEGER DEFAULT 5,
            object_count_max INTEGER DEFAULT 50,
            template_data TEXT NOT NULL, -- JSON with placement rules
            usage_context TEXT, -- JSON with usage guidelines
            quality_score REAL DEFAULT 0.0,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Material variants table
        CREATE TABLE IF NOT EXISTS material_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            variant_name TEXT NOT NULL,
            material_family TEXT NOT NULL, -- 'metal', 'concrete', 'glass', etc.
            material_data TEXT NOT NULL, -- JSON with material properties
            style_compatibility TEXT, -- JSON array of compatible styles
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE,
            UNIQUE(asset_id, variant_name)
        );
        
        -- Flexible tagging system
        CREATE TABLE IF NOT EXISTS asset_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            tag_name TEXT NOT NULL,
            tag_category TEXT NOT NULL, -- 'function', 'style', 'complexity', 'size'
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE,
            UNIQUE(asset_id, tag_name, tag_category)
        );
        
        -- Scan queue for robust processing
        CREATE TABLE IF NOT EXISTS scan_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blend_file_path TEXT NOT NULL UNIQUE,
            pack_id INTEGER NOT NULL,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'complete', 'failed'
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            assigned_worker TEXT, -- for distributed processing
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pack_id) REFERENCES asset_packs (id) ON DELETE CASCADE
        );
        
        -- Performance-optimized indexes
        CREATE INDEX IF NOT EXISTS idx_assets_fast_search ON assets(category, subcategory, quality_tier, size_category);
        CREATE INDEX IF NOT EXISTS idx_assets_pack ON assets(pack_id);
        CREATE INDEX IF NOT EXISTS idx_assets_style ON assets(primary_style, category);
        CREATE INDEX IF NOT EXISTS idx_assets_complexity ON assets(complexity_score, polygon_count);
        CREATE INDEX IF NOT EXISTS idx_assets_dimensions ON assets(width, height, depth);
        CREATE INDEX IF NOT EXISTS idx_properties_lookup ON asset_properties(asset_id, property_type);
        CREATE INDEX IF NOT EXISTS idx_relationships_fast ON asset_relationships(asset_1_id, relationship_type, strength);
        CREATE INDEX IF NOT EXISTS idx_templates_lookup ON scene_templates(category, style, complexity_level);
        CREATE INDEX IF NOT EXISTS idx_patterns_lookup ON classification_patterns(pattern_type, priority);
        CREATE INDEX IF NOT EXISTS idx_scan_queue_status ON scan_queue(status, priority);
        CREATE INDEX IF NOT EXISTS idx_tags_fast ON asset_tags(asset_id, tag_category);
        """
        
        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
            self._populate_default_patterns()
            logger.info("Optimized database schema initialized successfully")
    
    def _populate_default_patterns(self):
        """Populate default classification patterns in database."""
        default_patterns = [
            # Category patterns
            {
                'pattern_type': 'category',
                'pattern_name': 'architecture',
                'keywords': json.dumps(['building', 'wall', 'roof', 'door', 'window', 'pillar', 'arch', 'facade']),
                'confidence': 0.9,
                'priority': 8
            },
            {
                'pattern_type': 'category',
                'pattern_name': 'vehicles',
                'keywords': json.dumps(['car', 'truck', 'bike', 'vehicle', 'transport', 'wheel', 'motorcycle']),
                'confidence': 0.9,
                'priority': 8
            },
            {
                'pattern_type': 'category',
                'pattern_name': 'lighting',
                'keywords': json.dumps(['light', 'lamp', 'bulb', 'neon', 'led', 'sign', 'glow', 'illumination']),
                'confidence': 0.8,
                'priority': 7
            },
            {
                'pattern_type': 'category',
                'pattern_name': 'props',
                'keywords': json.dumps(['box', 'barrel', 'crate', 'container', 'pipe', 'wire', 'equipment']),
                'confidence': 0.7,
                'priority': 5
            },
            
            # Style patterns
            {
                'pattern_type': 'style',
                'pattern_name': 'cyberpunk',
                'keywords': json.dumps(['cyber', 'neon', 'hologram', 'digital', 'futuristic', 'tech']),
                'confidence': 0.8,
                'priority': 9
            },
            {
                'pattern_type': 'style',
                'pattern_name': 'industrial',
                'keywords': json.dumps(['industrial', 'mechanical', 'factory', 'machinery', 'steel']),
                'confidence': 0.8,
                'priority': 8
            },
            {
                'pattern_type': 'style',
                'pattern_name': 'weathered',
                'keywords': json.dumps(['worn', 'rust', 'damage', 'decay', 'old', 'dirty', 'aged']),
                'confidence': 0.7,
                'priority': 7
            },
            
            # Material family patterns
            {
                'pattern_type': 'material_family',
                'pattern_name': 'metal',
                'keywords': json.dumps(['steel', 'iron', 'aluminum', 'chrome', 'copper', 'brass', 'metal']),
                'confidence': 0.9,
                'priority': 9
            },
            {
                'pattern_type': 'material_family',
                'pattern_name': 'concrete',
                'keywords': json.dumps(['concrete', 'cement', 'stone', 'brick', 'wall', 'pavement']),
                'confidence': 0.9,
                'priority': 9
            },
            {
                'pattern_type': 'material_family',
                'pattern_name': 'glass',
                'keywords': json.dumps(['glass', 'window', 'transparent', 'clear', 'crystal']),
                'confidence': 0.9,
                'priority': 9
            },
            {
                'pattern_type': 'category',
                'pattern_name': 'vehicles',
                'keywords': json.dumps(['bot', 'robot', 'security', 'pack', 'car', 'truck', 'bike']),
                'confidence': 0.8,
                'priority': 7
            },
            {
                'pattern_type': 'category', 
                'pattern_name': 'props',
                'keywords': json.dumps(['snow', 'alpha', 'prop', 'box', 'barrel', 'crate']),
                'confidence': 0.7,
                'priority': 6
            },
        ]
        
        with self.get_connection() as conn:
            for pattern in default_patterns:
                conn.execute("""
                    INSERT OR IGNORE INTO classification_patterns 
                    (pattern_type, pattern_name, keywords, confidence, priority)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    pattern['pattern_type'],
                    pattern['pattern_name'], 
                    pattern['keywords'],
                    pattern['confidence'],
                    pattern['priority']
                ))
            conn.commit()
    
    # Fast Asset Operations (using denormalized data)
    def create_asset_optimized(self, name: str, pack_id: int, category: str, 
                             blend_file_path: str, **properties) -> int:
        """Create asset with critical properties denormalized for performance."""
        
        # Extract critical properties with defaults
        polygon_count = properties.get('polygon_count', 0)
        vertex_count = properties.get('vertex_count', 0)
        material_count = properties.get('material_count', 0)
        object_count = properties.get('object_count', 1)
        
        dimensions = properties.get('dimensions', [0.0, 0.0, 0.0])
        width, height, depth = dimensions[:3] if len(dimensions) >= 3 else (0.0, 0.0, 0.0)
        volume = width * height * depth
        
        complexity_score = properties.get('complexity_score', 0.0)
        quality_tier = properties.get('quality_tier', 'medium')
        estimated_load_time = properties.get('estimated_load_time', 0.0)
        memory_estimate = properties.get('memory_estimate', 0.0)
        primary_style = properties.get('primary_style')
        size_category = properties.get('size_category', 'medium')
        
        subcategory = properties.get('subcategory')
        collection_name = properties.get('collection_name')
        file_path = properties.get('file_path', '')
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO assets (
                    name, pack_id, category, subcategory, file_path, collection_name, 
                    blend_file_path, polygon_count, vertex_count, material_count, 
                    object_count, width, height, depth, volume, complexity_score, 
                    quality_tier, estimated_load_time, memory_estimate, primary_style, 
                    size_category, scan_status, last_scanned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'complete', ?)
            """, (
                name, pack_id, category, subcategory, file_path, collection_name,
                blend_file_path, polygon_count, vertex_count, material_count,
                object_count, width, height, depth, volume, complexity_score,
                quality_tier, estimated_load_time, memory_estimate, primary_style,
                size_category, datetime.now()
            ))
            conn.commit()
            return cursor.lastrowid
    
    def fast_asset_search(self, category: str = None, style: str = None, 
                         quality_tier: str = None, size_category: str = None,
                         max_complexity: float = None, max_polygons: int = None,
                         pack_id: int = None, limit: int = 100) -> List[Dict]:
        """
        High-performance asset search using denormalized properties.
        No JOINs required for common queries.
        """
        query = "SELECT * FROM assets WHERE is_active = 1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if style:
            query += " AND primary_style = ?"
            params.append(style)
        
        if quality_tier:
            query += " AND quality_tier = ?"
            params.append(quality_tier)
        
        if size_category:
            query += " AND size_category = ?"
            params.append(size_category)
        
        if max_complexity:
            query += " AND complexity_score <= ?"
            params.append(max_complexity)
        
        if max_polygons:
            query += " AND polygon_count <= ?"
            params.append(max_polygons)
        
        if pack_id:
            query += " AND pack_id = ?"
            params.append(pack_id)
        
        query += " ORDER BY complexity_score, polygon_count LIMIT ?"
        params.append(limit)
         
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            results = []
            
            for row in cursor.fetchall():
                asset = dict(row)
                
                # RECONSTRUCT dimensions array from width, height, depth
                width = asset.get('width', 0.0) or 0.0
                height = asset.get('height', 0.0) or 0.0  
                depth = asset.get('depth', 0.0) or 0.0
                asset['dimensions'] = [width, height, depth]
                          
                results.append(asset)
        return results
       
    
    # Data-driven classification methods
    def get_classification_patterns(self, pattern_type: str) -> List[Dict]:
        """Get classification patterns from database."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT pattern_name, keywords, confidence, priority 
                FROM classification_patterns 
                WHERE pattern_type = ? AND is_active = 1 
                ORDER BY priority DESC, confidence DESC
            """, (pattern_type,))
            
            patterns = []
            for row in cursor.fetchall():
                pattern = dict(row)
                pattern['keywords'] = json.loads(pattern['keywords'])
                patterns.append(pattern)
            return patterns
    
    def add_classification_pattern(self, pattern_type: str, pattern_name: str, 
                                 keywords: List[str], confidence: float = 0.8, 
                                 priority: int = 5):
        """Add new classification pattern."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO classification_patterns 
                (pattern_type, pattern_name, keywords, confidence, priority, created_by)
                VALUES (?, ?, ?, ?, ?, 'user')
            """, (pattern_type, pattern_name, json.dumps(keywords), confidence, priority))
            conn.commit()
    
    # Scan queue operations for robust processing
    def add_to_scan_queue(self, blend_file_path: str, pack_id: int, priority: int = 5) -> int:
        """Add blend file to scan queue."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO scan_queue (blend_file_path, pack_id, priority)
                VALUES (?, ?, ?)
            """, (blend_file_path, pack_id, priority))
            conn.commit()
            return cursor.lastrowid
    
    def get_next_scan_item(self, worker_id: str = None) -> Optional[Dict]:
        """Get next item from scan queue and mark as processing."""
        with self.get_connection() as conn:
            # Get highest priority pending item
            cursor = conn.execute("""
                SELECT * FROM scan_queue 
                WHERE status = 'pending' AND retry_count < max_retries
                ORDER BY priority DESC, created_at ASC 
                LIMIT 1
            """)
            item = cursor.fetchone()
            
            if item:
                item_dict = dict(item)
                # Mark as processing
                conn.execute("""
                    UPDATE scan_queue 
                    SET status = 'processing', assigned_worker = ?, started_at = ?
                    WHERE id = ?
                """, (worker_id, datetime.now(), item['id']))
                conn.commit()
                return item_dict
            
            return None
    
    def update_scan_status(self, queue_id: int, status: str, error_message: str = None):
        """Update scan queue item status."""
        with self.get_connection() as conn:
            if status == 'failed':
                conn.execute("""
                    UPDATE scan_queue 
                    SET status = ?, error_message = ?, retry_count = retry_count + 1,
                        completed_at = ?
                    WHERE id = ?
                """, (status, error_message, datetime.now(), queue_id))
            else:
                conn.execute("""
                    UPDATE scan_queue 
                    SET status = ?, completed_at = ?
                    WHERE id = ?
                """, (status, datetime.now(), queue_id))
            conn.commit()
    
    # Legacy compatibility methods
    def create_asset(self, name: str, pack_id: int, category: str, file_path: str, 
                    blend_file_path: str, subcategory: str = None, 
                    collection_name: str = None, thumbnail_path: str = None) -> int:
        """Legacy method for backward compatibility."""
        return self.create_asset_optimized(
            name=name, pack_id=pack_id, category=category, 
            blend_file_path=blend_file_path, subcategory=subcategory,
            collection_name=collection_name, file_path=file_path
        )
    
    def search_assets(self, category: str = None, subcategory: str = None, 
                     pack_id: int = None, tags: List[str] = None, 
                     limit: int = 100) -> List[Dict]:
        """Legacy search method - redirects to fast search when possible."""
        if not tags:  # Can use fast search
            return self.fast_asset_search(category=category, pack_id=pack_id, limit=limit)
        else:  # Need JOIN for tags
            query = """
            SELECT DISTINCT a.* FROM assets a 
            JOIN asset_tags at ON a.id = at.asset_id
            WHERE a.is_active = 1
            """
            conditions = []
            params = []
            
            if category:
                conditions.append("a.category = ?")
                params.append(category)
            
            if subcategory:
                conditions.append("a.subcategory = ?")
                params.append(subcategory)
            
            if pack_id:
                conditions.append("a.pack_id = ?")
                params.append(pack_id)
            
            if tags:
                tag_conditions = " OR ".join(["at.tag_name = ?" for _ in tags])
                conditions.append(f"({tag_conditions})")
                params.extend(tags)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += f" ORDER BY a.complexity_score LIMIT {limit}"
            
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
    
    # Keep all other methods from original implementation
    def create_asset_pack(self, name: str, path: str, version: str = None, description: str = None) -> int:
        """Create a new asset pack entry."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO asset_packs (name, version, path, description) 
                   VALUES (?, ?, ?, ?)""",
                (name, version, path, description)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_asset_pack(self, pack_id: int = None, name: str = None) -> Optional[Dict]:
        """Get asset pack by ID or name."""
        with self.get_connection() as conn:
            if pack_id:
                cursor = conn.execute("SELECT * FROM asset_packs WHERE id = ?", (pack_id,))
            elif name:
                cursor = conn.execute("SELECT * FROM asset_packs WHERE name = ?", (name,))
            else:
                raise ValueError("Either pack_id or name must be provided")
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics including scan queue status."""
        with self.get_connection() as conn:
            stats = {}
            
            # Main tables
            tables = ['asset_packs', 'assets', 'asset_properties', 'asset_relationships', 
                     'scene_templates', 'asset_tags', 'material_variants', 'scan_queue']
            
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            # Scan queue breakdown
            cursor = conn.execute("""
                SELECT status, COUNT(*) FROM scan_queue GROUP BY status
            """)
            scan_status = {row[0]: row[1] for row in cursor.fetchall()}
            stats['scan_queue_status'] = scan_status
            
            return stats


# Dependency injection-friendly factory
def create_database(db_path: str = None) -> AssetDatabase:
    """Create a new database instance (for testing and dependency injection)."""
    return AssetDatabase(db_path)

# Global instance for convenience (but not required)
_db_instance = None

def get_database() -> AssetDatabase:
    """Get the global database instance (singleton pattern)."""
    global _db_instance
    if _db_instance is None:
        _db_instance = AssetDatabase()
    return _db_instance

def reset_database():
    """Reset the global database instance (for testing)."""
    global _db_instance
    _db_instance = None