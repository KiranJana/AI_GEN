# backend.py - Improved version with actual asset loading

import bpy
import random
import json
import os

# new commit 
import sys
import os
user_lib_path = os.path.join(os.path.expanduser("~"), "blender_python_libs")
if user_lib_path not in sys.path:
    sys.path.append(user_lib_path)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- Main Backend Logic ---

API_KEY = "" # Make sure your key is pasted here

def call_ai_service(prompt, style, count):
    """Original AI service call for basic scene generation."""
    if not genai:
        print("Google Generative AI library not found. Returning mock data.")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 1) for _ in range(count)]}
    if API_KEY == "YOUR_GEMINI_API_KEY" or not API_KEY:
        print("Gemini API Key not set. Please add it to the script.")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 1) for _ in range(count)]}

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        generation_config = genai.GenerationConfig(response_mime_type="application/json")
        
        # Improved prompt with examples and a recipe for success
        full_prompt = (
            "You are an expert Blender scene layout assistant. Your task is to generate a list of 3D coordinates in a JSON format. "
            "The JSON object must contain a single key: 'locations'. The value of 'locations' must be a list of coordinate arrays. "
            "Each coordinate array MUST be in the format [X, Y, Z], and the Z value should always be 1.0. "
            "\n"
            "Analyze the user's prompt to determine the best spatial arrangement. "
            "For example, for a 'circle', the coordinates should be arranged evenly around a central point. You can calculate circular coordinates using the formula: "
            "X = radius * cos(angle), Y = radius * sin(angle). "
            "For a 'line' or 'street', they should be arranged along an axis. For a 'forest', they should be scattered with some randomness. "
            "\n"
            f"User Request: Create a '{style}' scene based on the prompt '{prompt}' with exactly {count} objects."
        )
        
        response = model.generate_content(full_prompt, generation_config=generation_config)
        
        print("--- Raw AI Response ---"); print(response.text); print("-----------------------")
        
        return json.loads(response.text)
    except Exception as e:
        print(f"An error occurred with the Gemini API: {e}")
        return None


def call_ai_service_with_assets(prompt, style, count, available_assets):
    """Enhanced AI service call that uses asset intelligence."""
    if not genai:
        print("Google Generative AI library not found. Using asset-aware mock data.")
        return generate_asset_aware_mock_data(available_assets, count)
    
    if API_KEY == "YOUR_GEMINI_API_KEY" or not API_KEY:
        print("Gemini API Key not set. Using asset-aware mock data.")
        return generate_asset_aware_mock_data(available_assets, count)

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        generation_config = genai.GenerationConfig(response_mime_type="application/json")
        
        # Filter out character rig controls and other non-visual assets
        filtered_assets = filter_visual_assets(available_assets)
        
        if not filtered_assets:
            print("No suitable visual assets found, falling back to mock data")
            return generate_asset_aware_mock_data(available_assets, count)
        
        # Create asset information for the AI (limit to reasonable number)
        asset_info = []
        for asset in filtered_assets[:30]:  # Limit to first 30 good assets
            asset_info.append({
                'name': asset['name'],
                'category': asset['category'],
                'quality': asset['quality_tier'],
                'complexity': asset['complexity_score'],
                'polygons': asset['polygon_count'],
                'style': asset.get('primary_style', 'unknown')
            })
        
        # Enhanced prompt with asset intelligence
        full_prompt = (
            "You are an expert Blender scene layout assistant with access to a database of 3D assets. "
            "Your task is to generate a scene layout in JSON format that intelligently uses available assets. "
            "\n"
            "REQUIRED OUTPUT FORMAT:\n"
            "{\n"
            '  "locations": [[X, Y, Z], [X, Y, Z], ...],\n'
            '  "selected_assets": ["asset_name_1", "asset_name_2", ...],\n'
            '  "reasoning": "Brief explanation of asset choices and layout"\n'
            "}\n"
            "\n"
            "AVAILABLE ASSETS (these are actual 3D objects, vehicles, props, and lighting):\n"
            f"{json.dumps(asset_info, indent=2)}\n"
            "\n"
            "SCENE REQUIREMENTS:\n"
            f"- Style: {style}\n"
            f"- User Prompt: {prompt}\n"
            f"- Number of Objects: {count}\n"
            "\n"
            "INSTRUCTIONS:\n"
            "1. Select ONLY from the available assets listed above\n"
            "2. Choose assets that make sense for the scene (avoid character controls, rigs, etc.)\n"
            "3. Create realistic 3D coordinates for each selected asset\n"
            "4. Consider asset complexity for proper spacing\n"
            "5. Ensure the layout makes sense for the requested scene type\n"
            "6. Z coordinates should be appropriate (ground objects = 0, elevated objects higher)\n"
            "7. Focus on vehicles, props, lighting, and architecture assets\n"
            "\n"
            "Avoid selecting assets with names containing: 'cs_', 'ctrl', 'ik_', 'bone', 'rig'"
        )
        
        response = model.generate_content(full_prompt, generation_config=generation_config)
        
        print("--- Enhanced AI Response with Assets ---")
        print(response.text)
        print("----------------------------------------")
        
        ai_response = json.loads(response.text)
        
        # Validate and enhance the response
        if 'locations' not in ai_response:
            raise ValueError("AI response missing 'locations' key")
        
        if 'selected_assets' not in ai_response:
            ai_response['selected_assets'] = [f"asset_{i}" for i in range(len(ai_response['locations']))]
        
        # Ensure we have the right number of objects and valid asset names
        locations = ai_response['locations']
        selected_assets = ai_response['selected_assets']
        
        # Validate selected assets exist in our database
        asset_names = {asset['name'] for asset in filtered_assets}
        validated_assets = []
        
        for asset_name in selected_assets:
            if asset_name in asset_names:
                validated_assets.append(asset_name)
            else:
                # Find a replacement from filtered assets
                replacement = random.choice(filtered_assets)['name']
                validated_assets.append(replacement)
                print(f"Replaced invalid asset '{asset_name}' with '{replacement}'")
        
        # Pad or trim to match requested count
        while len(locations) < count or len(validated_assets) < count:
            # Add more locations with random selection from filtered assets
            random_asset = random.choice(filtered_assets)
            locations.append([
                random.uniform(-10, 10),
                random.uniform(-10, 10),
                0.0
            ])
            validated_assets.append(random_asset['name'])
        
        # Trim if too many
        ai_response['locations'] = locations[:count]
        ai_response['selected_assets'] = validated_assets[:count]
        
        return ai_response
        
    except Exception as e:
        print(f"An error occurred with the enhanced Gemini API: {e}")
        print("Falling back to asset-aware mock data...")
        return generate_asset_aware_mock_data(available_assets, count)


def filter_visual_assets(available_assets):
    """Filter out character rig controls and keep only visual 3D assets."""
    visual_assets = []
    
    # Words that indicate non-visual or rig assets
    exclude_keywords = [
        'cs_', 'ctrl', 'ik_', 'bone', 'rig', 'control', 'constraint',
        'driver', 'target', 'pole', 'helper', 'locator', 'null',
        'ankle_str', 'arm_ik', 'belly_ctrl', 'breath', 'brow_ctrl',
        'arm_toon', 'arm_scale'
    ]
    
    for asset in available_assets:
        asset_name = asset['name'].lower()
        
        # Skip if name contains exclude keywords
        if any(keyword in asset_name for keyword in exclude_keywords):
            continue
        
        # Skip if it has zero polygons (likely a control object)
        if asset.get('polygon_count', 0) <= 0:
            continue
        
        # Skip if dimensions are all zero
        if (asset.get('width', 0) == 0 and 
            asset.get('height', 0) == 0 and 
            asset.get('depth', 0) == 0):
            continue
        
        visual_assets.append(asset)
    
    print(f"Filtered to {len(visual_assets)} visual assets from {len(available_assets)} total")
    return visual_assets


def generate_asset_aware_mock_data(available_assets, count):
    """Generate mock data that's aware of available assets."""
    # Filter for visual assets first
    filtered_assets = filter_visual_assets(available_assets)
    
    if not filtered_assets:
        print("No visual assets available, using basic mock data")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 0) for _ in range(count)]}
    
    selected_assets = []
    locations = []
    
    for i in range(count):
        # Randomly select from filtered visual assets
        asset = random.choice(filtered_assets)
        selected_assets.append(asset['name'])
        
        # Generate location based on asset type
        if asset['category'] == 'architecture':
            # Buildings should be on the ground and spaced out
            x = random.uniform(-15, 15)
            y = random.uniform(-15, 15)
            z = 0.0
        elif asset['category'] == 'vehicles':
            # Vehicles on roads/ground
            x = random.uniform(-10, 10)
            y = random.uniform(-8, 8)
            z = 0.0
        elif asset['category'] == 'lighting':
            # Lights can be elevated
            x = random.uniform(-12, 12)
            y = random.uniform(-12, 12)
            z = random.uniform(2, 8)
        else:
            # General props
            x = random.uniform(-8, 8)
            y = random.uniform(-8, 8)
            z = random.uniform(0, 2)
        
        locations.append([x, y, z])
    
    return {
        "locations": locations,
        "selected_assets": selected_assets,
        "reasoning": f"Mock selection from {len(filtered_assets)} filtered visual assets with category-aware placement"
    }


def build_scene_from_instructions(instructions):
    """Enhanced scene builder that loads actual assets instead of cubes."""
    # Clear existing mesh objects
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_by_type(type='MESH')
    bpy.ops.object.delete()

    if not instructions or not isinstance(instructions, dict) or "locations" not in instructions:
        print("Safeguard: AI response was missing the 'locations' key or was not a dictionary.")
        return

    locations = instructions["locations"]
    selected_assets = instructions.get("selected_assets", [])
    reasoning = instructions.get("reasoning", "No reasoning provided")

    if not isinstance(locations, list):
        print(f"Safeguard: AI returned 'locations' as a {type(locations)}, but it must be a list.")
        return

    print(f"AI Reasoning: {reasoning}")
    
    if selected_assets:
        print(f"Selected Assets: {selected_assets}")
        print("Attempting to load actual assets...")

    # Get database for asset lookup
    try:
        from . import database
        db = database.get_database()
        
        for i, loc in enumerate(locations):
            if not isinstance(loc, (list, tuple)) or len(loc) != 3:
                print(f"Safeguard: Skipping invalid location at index {i}. Expected 3 coordinates, but got {loc}")
                continue
            
            if not all(isinstance(item, (int, float)) for item in loc):
                print(f"Safeguard: Skipping invalid location at index {i}. Contains non-numeric values: {loc}")
                continue
            
            # Try to load actual asset if available
            asset_loaded = False
            if i < len(selected_assets) and selected_assets[i]:
                asset_name = selected_assets[i]
                
                try:
                    # Search for the asset in database
                    assets = db.fast_asset_search(limit=1000)
                    matching_asset = None
                    
                    for asset in assets:
                        if asset['name'] == asset_name:
                            matching_asset = asset
                            break
                    
                    if matching_asset:
                        asset_loaded = load_actual_asset(matching_asset, loc)
                        if asset_loaded:
                            print(f"✅ Loaded actual asset: {asset_name} at {loc}")
                        
                except Exception as e:
                    print(f"❌ Failed to load asset {asset_name}: {e}")
            
            # Fallback to cube if asset loading failed
            if not asset_loaded:
                bpy.ops.mesh.primitive_cube_add(location=loc)
                obj = bpy.context.active_object
                
                if i < len(selected_assets) and selected_assets[i]:
                    obj.name = f"{selected_assets[i]}_cube_{i}"
                    obj["asset_name"] = selected_assets[i]
                    obj["asset_index"] = i
                    print(f"📦 Created cube placeholder for: {selected_assets[i]} at {loc}")
                else:
                    obj.name = f"object_{i}"
                    print(f"📦 Created cube at: {loc}")
                    
    except Exception as e:
        print(f"Error with asset loading system: {e}")
        # Fallback to original cube creation
        for i, loc in enumerate(locations):
            if isinstance(loc, (list, tuple)) and len(loc) == 3:
                bpy.ops.mesh.primitive_cube_add(location=loc)
                if i < len(selected_assets):
                    obj = bpy.context.active_object
                    obj.name = f"{selected_assets[i]}_cube_{i}"


def load_actual_asset(asset_data, location):
    """
    Load actual asset from blend file.
    """
    blend_file_path = asset_data.get('blend_file_path')
    collection_name = asset_data.get('collection_name')
    
    if not blend_file_path or not os.path.exists(blend_file_path):
        print(f"Asset file not found: {blend_file_path}")
        return False
    
    try:
        if collection_name:
            # Load collection from blend file
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                if collection_name in data_from.collections:
                    data_to.collections = [collection_name]
                else:
                    print(f"Collection '{collection_name}' not found in {blend_file_path}")
                    return False
            
            # Instance the collection
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]
                
                # Create an empty object to instance the collection
                bpy.ops.object.empty_add(location=location)
                empty_obj = bpy.context.active_object
                empty_obj.name = f"{asset_data['name']}_instance"
                
                # Set the empty to instance the collection
                empty_obj.instance_type = 'COLLECTION'
                empty_obj.instance_collection = collection
                
                print(f"Successfully loaded collection: {collection_name}")
                return True
        else:
            # Try to load individual objects
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                # Look for meshes with similar name
                matching_meshes = [mesh for mesh in data_from.meshes if asset_data['name'].lower() in mesh.lower()]
                if matching_meshes:
                    data_to.meshes = [matching_meshes[0]]
                    data_to.materials = data_from.materials  # Load materials too
                else:
                    return False
            
            # Create object with loaded mesh
            if matching_meshes[0] in bpy.data.meshes:
                mesh = bpy.data.meshes[matching_meshes[0]]
                obj = bpy.data.objects.new(asset_data['name'], mesh)
                bpy.context.collection.objects.link(obj)
                obj.location = location
                
                print(f"Successfully loaded mesh: {matching_meshes[0]}")
                return True
                
    except Exception as e:
        print(f"Failed to load asset {asset_data['name']}: {e}")
        return False
    
    return False


def get_asset_recommendations(prompt, style, available_assets, count):
    """
    Get AI recommendations for which assets to use without generating the full scene.
    Enhanced to filter visual assets.
    """
    # Filter for visual assets first
    filtered_assets = filter_visual_assets(available_assets)
    
    if not filtered_assets:
        return []
    
    # Simple keyword-based matching as fallback
    keywords = prompt.lower().split()
    style_lower = style.lower()
    
    scored_assets = []
    
    for asset in filtered_assets:
        score = 0
        
        # Score based on name matching keywords
        asset_name = asset['name'].lower()
        for keyword in keywords:
            if keyword in asset_name:
                score += 2
        
        # Score based on category relevance
        if any(keyword in asset['category'].lower() for keyword in keywords):
            score += 3
        
        # Score based on style matching
        if asset.get('primary_style') and style_lower in asset['primary_style'].lower():
            score += 5
        
        # Prefer higher quality assets but not exclusively
        quality_scores = {'low': 1, 'medium': 2, 'high': 3, 'ultra': 4}
        score += quality_scores.get(asset.get('quality_tier', 'medium'), 2)
        
        # Prefer assets with reasonable polygon counts (not too simple, not too complex)
        poly_count = asset.get('polygon_count', 0)
        if 100 <= poly_count <= 5000:
            score += 2
        elif poly_count > 5000:
            score += 1
        
        scored_assets.append((asset, score))
    
    # Sort by score and return top assets
    scored_assets.sort(key=lambda x: x[1], reverse=True)
    return [asset for asset, score in scored_assets[:count * 2]]  # Return more options than needed
# diagnostic_backend.py - Add this to your backend.py to debug asset loading

def load_actual_asset_debug(asset_data, location):
    """
    Debug version of load_actual_asset with detailed logging.
    """
    print(f"\n=== DEBUGGING ASSET LOADING ===")
    print(f"Asset Name: {asset_data.get('name', 'Unknown')}")
    print(f"Asset Data Keys: {list(asset_data.keys())}")
    print(f"Blend File Path: {asset_data.get('blend_file_path', 'None')}")
    print(f"Collection Name: {asset_data.get('collection_name', 'None')}")
    print(f"Category: {asset_data.get('category', 'None')}")
    print(f"Location: {location}")
    
    blend_file_path = asset_data.get('blend_file_path')
    collection_name = asset_data.get('collection_name')
    
    # Check 1: File path validation
    if not blend_file_path:
        print("❌ FAIL: No blend_file_path in asset data")
        return False
    
    print(f"Blend file path exists: {os.path.exists(blend_file_path)}")
    
    if not os.path.exists(blend_file_path):
        print(f"❌ FAIL: Blend file not found at: {blend_file_path}")
        return False
    
    print("✓ Blend file exists")
    
    # Check 2: Collection name
    if not collection_name:
        print("⚠️  WARNING: No collection_name, trying mesh loading instead")
        return load_mesh_instead(asset_data, location, blend_file_path)
    
    print(f"Attempting to load collection: {collection_name}")
    
    try:
        # Check 3: Preview what's in the blend file
        print("Checking blend file contents...")
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            print(f"Available collections: {list(data_from.collections)}")
            print(f"Available meshes: {list(data_from.meshes)[:10]}...")  # First 10 meshes
            print(f"Available objects: {list(data_from.objects)[:10]}...")  # First 10 objects
            
            if collection_name in data_from.collections:
                print(f"✓ Found collection '{collection_name}' in blend file")
                data_to.collections = [collection_name]
            else:
                print(f"❌ Collection '{collection_name}' not found")
                print("Available collections:", data_from.collections)
                return False
        
        # Check 4: Verify collection was loaded
        if collection_name in bpy.data.collections:
            print(f"✓ Collection '{collection_name}' loaded into Blender")
            collection = bpy.data.collections[collection_name]
            print(f"Collection has {len(collection.objects)} objects")
            
            # Check 5: Create instance
            print("Creating collection instance...")
            bpy.ops.object.empty_add(location=location)
            empty_obj = bpy.context.active_object
            empty_obj.name = f"{asset_data['name']}_instance"
            
            # Set the empty to instance the collection
            empty_obj.instance_type = 'COLLECTION'
            empty_obj.instance_collection = collection
            
            print(f"✅ SUCCESS: Created collection instance for {asset_data['name']}")
            return True
        else:
            print(f"❌ FAIL: Collection not available after loading")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION during loading: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_mesh_instead(asset_data, location, blend_file_path):
    """Try to load individual mesh instead of collection."""
    print("\n--- Attempting mesh loading instead ---")
    
    try:
        asset_name = asset_data['name']
        print(f"Looking for mesh similar to: {asset_name}")
        
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            # Look for meshes with similar name
            matching_meshes = []
            asset_name_lower = asset_name.lower()
            
            for mesh_name in data_from.meshes:
                if (asset_name_lower in mesh_name.lower() or 
                    mesh_name.lower() in asset_name_lower):
                    matching_meshes.append(mesh_name)
            
            print(f"Found {len(matching_meshes)} matching meshes: {matching_meshes[:5]}")
            
            if matching_meshes:
                # Load the first matching mesh
                selected_mesh = matching_meshes[0]
                data_to.meshes = [selected_mesh]
                print(f"Loading mesh: {selected_mesh}")
            else:
                print("No matching meshes found")
                return False
        
        # Create object with loaded mesh
        if selected_mesh in bpy.data.meshes:
            mesh = bpy.data.meshes[selected_mesh]
            obj = bpy.data.objects.new(asset_data['name'], mesh)
            bpy.context.collection.objects.link(obj)
            obj.location = location
            
            print(f"✅ SUCCESS: Created mesh object for {asset_data['name']}")
            return True
        else:
            print("❌ Mesh not available after loading")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION during mesh loading: {e}")
        return False


# Replace the load_actual_asset function in build_scene_from_instructions
def build_scene_from_instructions_debug(instructions):
    """Debug version of build_scene_from_instructions."""
    # Clear existing mesh objects
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_by_type(type='MESH')
    bpy.ops.object.delete()

    if not instructions or not isinstance(instructions, dict) or "locations" not in instructions:
        print("Safeguard: AI response was missing the 'locations' key or was not a dictionary.")
        return

    locations = instructions["locations"]
    selected_assets = instructions.get("selected_assets", [])
    reasoning = instructions.get("reasoning", "No reasoning provided")

    if not isinstance(locations, list):
        print(f"Safeguard: AI returned 'locations' as a {type(locations)}, but it must be a list.")
        return

    print(f"AI Reasoning: {reasoning}")
    
    if selected_assets:
        print(f"Selected Assets: {selected_assets}")
        print("=== STARTING ASSET LOADING DEBUG ===")

    # Get database for asset lookup
    try:
        from . import database
        db = database.get_database()
        
        # Get all assets from database for debugging
        all_assets = db.fast_asset_search(limit=2000)
        print(f"Total assets in database: {len(all_assets)}")
        
        # Show sample asset structure
        if all_assets:
            sample_asset = all_assets[0]
            print(f"Sample asset keys: {list(sample_asset.keys())}")
            print(f"Sample asset: {sample_asset}")
        
        for i, loc in enumerate(locations):
            if not isinstance(loc, (list, tuple)) or len(loc) != 3:
                print(f"Safeguard: Skipping invalid location at index {i}. Expected 3 coordinates, but got {loc}")
                continue
            
            if not all(isinstance(item, (int, float)) for item in loc):
                print(f"Safeguard: Skipping invalid location at index {i}. Contains non-numeric values: {loc}")
                continue
            
            # Try to load actual asset if available
            asset_loaded = False
            if i < len(selected_assets) and selected_assets[i]:
                asset_name = selected_assets[i]
                print(f"\n--- Processing asset {i+1}/{len(locations)}: {asset_name} ---")
                
                try:
                    # Search for the asset in database
                    matching_asset = None
                    
                    for asset in all_assets:
                        if asset['name'] == asset_name:
                            matching_asset = asset
                            break
                    
                    if matching_asset:
                        print(f"✓ Found asset in database: {asset_name}")
                        asset_loaded = load_actual_asset_debug(matching_asset, loc)
                    else:
                        print(f"❌ Asset '{asset_name}' not found in database")
                        print(f"Available assets starting with same letter: {[a['name'] for a in all_assets if a['name'].lower().startswith(asset_name[0].lower())][:5]}")
                        
                except Exception as e:
                    print(f"❌ Failed to process asset {asset_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Fallback to cube if asset loading failed
            if not asset_loaded:
                print(f"Creating cube fallback for position {i+1}")
                bpy.ops.mesh.primitive_cube_add(location=loc)
                obj = bpy.context.active_object
                
                if i < len(selected_assets) and selected_assets[i]:
                    obj.name = f"{selected_assets[i]}_cube_{i}"
                    obj["asset_name"] = selected_assets[i]
                    obj["asset_index"] = i
                    print(f"📦 Created cube placeholder for: {selected_assets[i]} at {loc}")
                else:
                    obj.name = f"object_{i}"
                    print(f"📦 Created cube at: {loc}")
                    
    except Exception as e:
        print(f"❌ Error with asset loading system: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to original cube creation
        for i, loc in enumerate(locations):
            if isinstance(loc, (list, tuple)) and len(loc) == 3:
                bpy.ops.mesh.primitive_cube_add(location=loc)
                if i < len(selected_assets):
                    obj = bpy.context.active_object
                    obj.name = f"{selected_assets[i]}_cube_{i}"


# To use this debug version:
# Replace the build_scene_from_instructions call in your backend.py with:
# build_scene_from_instructions_debug(instructions)
