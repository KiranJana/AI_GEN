# backend.py

import bpy
import random
import json

# Add Custom Library Path
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
    if not genai:
        print("Google Generative AI library not found. Returning mock data.")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 1) for _ in range(count)]}
    if API_KEY == "YOUR_GEMINI_API_KEY":
        print("Gemini API Key not set. Please add it to the script.")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 1) for _ in range(count)]}

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
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

def build_scene_from_instructions(instructions):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_by_type(type='MESH')
    bpy.ops.object.delete()

    if not instructions or not isinstance(instructions, dict) or "locations" not in instructions:
        print("Safeguard: AI response was missing the 'locations' key or was not a dictionary.")
        return

    locations = instructions["locations"]

    if not isinstance(locations, list):
        print(f"Safeguard: AI returned 'locations' as a {type(locations)}, but it must be a list.")
        return

    for i, loc in enumerate(locations):
        if not isinstance(loc, (list, tuple)) or len(loc) != 3:
            print(f"Safeguard: Skipping invalid location at index {i}. Expected 3 coordinates, but got {loc}")
            continue
        
        if not all(isinstance(item, (int, float)) for item in loc):
            print(f"Safeguard: Skipping invalid location at index {i}. Contains non-numeric values: {loc}")
            continue
            
        bpy.ops.mesh.primitive_cube_add(location=loc)
        print(f"Placed cube at: {loc}")
