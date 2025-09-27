# test_scanner.py
import bpy
import os
import time
import sys

# Import the specific functions and classes from your modules
from . import database
from . import asset_scanner

def run_full_scan_test():
    """
    An end-to-end test for the asset scanner and database.
    1. Sets up the database.
    2. Points to an asset pack.
    3. Runs the robust scanner.
    4. Prints a summary of the results.
    """
    print("="*50)
    print("STARTING ASSET INTELLIGENCE BRAIN TEST")
    print("="*50)
    
    # --- 1. Define the Asset Pack Path ---
    # !!! IMPORTANT !!!
    # Change this path to a SMALL sample asset pack on your computer for the first test.
    # Use a folder with only 5-10 .blend files to start.
    pack_to_scan_path = "P:/PATH/TO/YOUR/ASSET/PACK"  # <-- CHANGE THIS
    
    if not os.path.exists(pack_to_scan_path):
        print(f"ERROR: The asset pack path does not exist: {pack_to_scan_path}")
        print("Please update the 'pack_to_scan_path' variable in the script.")
        return
    
    # --- 2. Initialize the Database ---
    # We will create a fresh, temporary database for this test.
    # This keeps your main database clean.
    test_db_path = os.path.join(os.path.dirname(__file__), "test_asset_brain.db")
    print(f"Creating a temporary test database at: {test_db_path}")
    
    if os.path.exists(test_db_path):
        os.remove(test_db_path)  # Delete old test database
        
    db_instance = database.create_database(db_path=test_db_path)
    
    # --- 3. Initialize and Run the Scanner ---
    # We pass the test database instance to the scanner (Dependency Injection).
    print("\nInitializing the Robust Asset Scanner...")
    
    try:
        scanner = asset_scanner.RobustAssetScanner(database=db_instance, max_workers=1)  # Start with 1 worker for testing
        
        # Check if the scanner found the Blender executable
        if not scanner.blender_executable or not os.path.exists(scanner.blender_executable):
            print(f"ERROR: Blender executable not found or invalid: {scanner.blender_executable}")
            print("The scanner cannot proceed without a valid Blender path.")
            
            # Try to use current Blender
            try:
                scanner.blender_executable = bpy.app.binary_path
                print(f"Trying current Blender path: {scanner.blender_executable}")
            except:
                print("Could not determine current Blender path either.")
                return
        
        print(f"Scanner will use Blender executable at: {scanner.blender_executable}")
        
        # Run the main scanning function
        print(f"\nStarting scan of: {pack_to_scan_path}")
        start_time = time.time()
        
        scan_summary = scanner.scan_asset_pack_robust(
            pack_path=pack_to_scan_path,
            pack_name="My Test Pack",
            force_rescan=True,  # Always rescan for testing
            max_concurrent=1    # Use only 1 process for initial testing
        )
        
        end_time = time.time()
        
    except Exception as e:
        print(f"ERROR during scanning: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # --- 4. Print the Results ---
    print("\n" + "="*50)
    print("SCAN COMPLETE - RESULTS")
    print("="*50)
    
    print(f"Total Scan Duration: {end_time - start_time:.2f} seconds")
    
    if scan_summary:
        print(f"Pack Name: {scan_summary['pack_info']['name']}")
        print(f"Files Queued: {scan_summary['scan_stats']['files_queued']}")
        print(f"Files Processed: {scan_summary['scan_stats']['files_processed']}")
        print(f"Files Failed: {scan_summary['scan_stats']['files_failed']}")
        print(f"Total Assets Discovered: {scan_summary['total_assets']}")
        
        print("\nCategory Breakdown:")
        for category, count in scan_summary.get('category_breakdown', {}).items():
            print(f"  - {category}: {count} assets")
        
        print("\nQuality Breakdown:")
        for quality, count in scan_summary.get('quality_breakdown', {}).items():
            print(f"  - {quality}: {count} assets")
            
        print("\nDatabase Stats:")
        for table, count in scan_summary.get('database_stats', {}).items():
            if table != 'scan_queue_status':
                print(f"  - {table}: {count} rows")
        
        # Print scan queue status if available
        queue_status = scan_summary.get('database_stats', {}).get('scan_queue_status', {})
        if queue_status:
            print("\nScan Queue Status:")
            for status, count in queue_status.items():
                print(f"  - {status}: {count} files")
    else:
        print("Scan did not return a summary.")
    
    # --- 5. Test Database Queries ---
    print("\n" + "="*50)
    print("TESTING DATABASE QUERIES")
    print("="*50)
    
    try:
        # Test fast search
        all_assets = db_instance.fast_asset_search(limit=10)
        print(f"Fast search returned {len(all_assets)} assets (limited to 10)")
        
        if all_assets:
            print("\nSample Asset Details:")
            asset = all_assets[0]
            print(f"  Name: {asset['name']}")
            print(f"  Category: {asset['category']}")
            print(f"  Quality: {asset['quality_tier']}")
            print(f"  Polygons: {asset['polygon_count']}")
            print(f"  Dimensions: {asset['width']:.2f} x {asset['height']:.2f} x {asset['depth']:.2f}")
            print(f"  Complexity: {asset['complexity_score']:.2f}")
        
        # Test pattern-based search
        cyberpunk_assets = db_instance.fast_asset_search(style='cyberpunk', limit=5)
        print(f"\nFound {len(cyberpunk_assets)} cyberpunk assets")
        
        lighting_assets = db_instance.fast_asset_search(category='lighting', limit=5)
        print(f"Found {len(lighting_assets)} lighting assets")
        
        # Test classification patterns
        patterns = db_instance.get_classification_patterns('category')
        print(f"\nLoaded {len(patterns)} category classification patterns")
        
        # --- 6. Test Enhanced AI Integration ---
        print("\n" + "="*50)
        print("TESTING AI INTEGRATION WITH ASSETS")
        print("="*50)
        
        if all_assets:
            from . import backend
            
            print("Testing asset-aware scene generation...")
            
            # Test asset recommendations
            recommendations = backend.get_asset_recommendations(
                prompt="cyberpunk street scene",
                style="cyberpunk",
                available_assets=all_assets,
                count=5
            )
            
            print(f"Asset recommendations for 'cyberpunk street scene':")
            for i, asset in enumerate(recommendations[:5]):
                print(f"  {i+1}. {asset['name']} ({asset['category']}, {asset.get('quality_tier', 'unknown')})")
            
            # Test mock scene generation with assets
            print("\nTesting mock scene generation with asset intelligence...")
            mock_instructions = backend.generate_asset_aware_mock_data(all_assets[:10], 5)
            
            print("Mock scene generation results:")
            print(f"  Locations: {len(mock_instructions['locations'])}")
            print(f"  Selected Assets: {mock_instructions['selected_assets']}")
            print(f"  Reasoning: {mock_instructions['reasoning']}")
        
    except Exception as e:
        print(f"Error testing database queries: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTest finished. Database saved at: {test_db_path}")
    print("You can inspect the database file or run additional queries.")
    print("\nNext steps:")
    print("1. Update your backend.py with a valid API key")
    print("2. Use the UI panel to scan your actual asset pack")
    print("3. Enable 'Use Asset Intelligence' in the scene generator")

def quick_database_test():
    """Quick test of just the database functionality."""
    print("="*50)
    print("QUICK DATABASE TEST")
    print("="*50)
    
    test_db_path = os.path.join(os.path.dirname(__file__), "quick_test.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    try:
        print("Creating test database...")
        db = database.create_database(test_db_path)
        print("✓ Database created successfully")
        
        # Test pack creation
        print("Testing asset pack creation...")
        pack_id = db.create_asset_pack("Test Pack", "/test/path")
        print(f"✓ Created asset pack with ID: {pack_id}")
        
        # Test asset creation
        print("Testing asset creation...")
        asset_id = db.create_asset_optimized(
            name="Test Asset",
            pack_id=pack_id,
            category="props",
            blend_file_path="/test/file.blend",
            polygon_count=1000,
            complexity_score=5.0
        )
        print(f"✓ Created asset with ID: {asset_id}")
        
        # Test search
        print("Testing asset search...")
        assets = db.fast_asset_search(category="props")
        print(f"✓ Found {len(assets)} props assets")
        
        # Test patterns
        print("Testing classification patterns...")
        patterns = db.get_classification_patterns('category')
        print(f"✓ Loaded {len(patterns)} classification patterns")
        
        # Test enhanced features
        print("Testing pattern addition...")
        db.add_classification_pattern('category', 'test_category', ['test', 'sample'])
        new_patterns = db.get_classification_patterns('category')
        print(f"✓ Added pattern, now have {len(new_patterns)} patterns")
        
        # Test database stats
        print("Testing database statistics...")
        stats = db.get_database_stats()
        print(f"✓ Database contains {stats.get('assets', 0)} assets in {len(stats)} tables")
        
        print("\n" + "="*50)
        print("✓ ALL DATABASE TESTS PASSED!")
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print("✓ Test database cleaned up")

def test_ui_integration():
    """Test UI integration with the scene properties."""
    print("="*50)
    print("UI INTEGRATION TEST")
    print("="*50)
    
    try:
        # Test that we can access scene properties
        if hasattr(bpy.context.scene, 'my_tool_properties'):
            props = bpy.context.scene.my_tool_properties
            
            print("✓ Scene properties accessible")
            print(f"  Current pack path: '{props.asset_pack_path}'")
            print(f"  Use asset intelligence: {props.use_asset_intelligence}")
            print(f"  Total assets in DB: {props.total_assets_in_db}")
            print(f"  Scan status: '{props.scan_status}'")
            
            # Update database stats
            print("Testing database connection from UI...")
            from . import database
            db = database.get_database()
            stats = db.get_database_stats()
            props.total_assets_in_db = stats.get('assets', 0)
            
            print(f"✓ Updated assets count to: {props.total_assets_in_db}")
            
            # Test property updates
            original_status = props.scan_status
            props.scan_status = "UI Test Complete"
            print(f"✓ Updated scan status from '{original_status}' to '{props.scan_status}'")
            
            print("\n✓ UI integration test passed!")
            
        else:
            print("✗ Scene properties not found - addon may not be properly registered")
            print("Make sure the addon is enabled and try restarting Blender")
            
    except Exception as e:
        print(f"✗ UI integration test failed: {e}")
        import traceback
        traceback.print_exc()

def test_import_structure():
    """Test that all modules can be imported correctly."""
    print("="*50)
    print("IMPORT STRUCTURE TEST")
    print("="*50)
    
    try:
        print("Testing imports...")
        
        # Test database import
        from . import database
        print("✓ Database module imported")
        
        # Test asset scanner import
        from . import asset_scanner
        print("✓ Asset scanner module imported")
        
        # Test backend import
        from . import backend
        print("✓ Backend module imported")
        
        # Test limit manager import
        from . import limit_manager
        print("✓ Limit manager module imported")
        
        # Test properties import
        from . import properties
        print("✓ Properties module imported")
        
        # Test UI panel import
        from . import ui_panel
        print("✓ UI panel module imported")
        
        # Test operator import
        from . import operator
        print("✓ Operator module imported")
        
        print("\n✓ All modules imported successfully!")
        
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback
        traceback.print_exc()

# --- How to Run These Tests ---
# 1. Open this script in Blender's Text Editor
# 2. Click the "Run Script" button (the play icon)
# 3. Check the System Console for the output
# 4. For full asset scan test, update the pack_to_scan_path variable

# Main execution - choose which tests to run
def run_tests():
    """Run all tests in sequence."""
    
    # Test 1: Import structure
    test_import_structure()
    print("\n")
    
    # Test 2: Quick database test
    quick_database_test()
    print("\n")
    
    # Test 3: UI integration test
    test_ui_integration()
    print("\n")
    
    # Test 4: Full scan test (optional - requires valid path)
    # Uncomment the next two lines and set a valid path to test full scanning
    # print("Full asset scan test skipped - set pack_to_scan_path to enable")
    # run_full_scan_test()
    
    print("="*50)
    print("ALL TESTS COMPLETE")
    print("="*50)
    print("Next steps:")
    print("1. If all tests passed, your addon is ready to use!")
    print("2. Set a valid asset pack path in the UI to scan real assets")
    print("3. Add your Gemini API key to backend.py for AI functionality")

# Execute tests when script is run
if __name__ == "__main__":
    run_tests()