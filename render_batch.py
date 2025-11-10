import bpy
import os
import glob
from pathlib import Path
import sys
import threading
import time
import io
from datetime import datetime

# ============================================================================
# BATCH RENDER SCRIPT - Renders multiple textures on a single UV-mapped object
# ============================================================================

# Get the directory where this script is located
if bpy.context.space_data and bpy.context.space_data.type == 'TEXT_EDITOR':
    script_dir = Path(bpy.context.space_data.text.filepath).parent
else:
    script_dir = Path(__file__).parent

# Define directories relative to script location
texture_dir = script_dir / "Textures"
output_dir = script_dir / "Output"

# Create directories if they don't exist
output_dir.mkdir(exist_ok=True)

# Get all PNG texture files, sorted alphabetically
texture_files = sorted(glob.glob(str(texture_dir / "*.png")))

if not texture_files:
    print(f"ERROR: No PNG files found in {texture_dir}")
    exit()

print(f"\n{'='*60}")
print(f"BLENDER BATCH RENDER")
print(f"{'='*60}")
print(f"Found {len(texture_files)} textures to render")
print(f"Texture folder: {texture_dir}")
print(f"Output folder:  {output_dir}")
print(f"{'='*60}\n")

# Get the scene
scene = bpy.context.scene

# Configure render settings
scene.render.engine = 'CYCLES'
scene.render.image_settings.file_format = 'PNG'

# ============================================================================
# GPU RENDERING SETUP
# ============================================================================

try:
    preferences = bpy.context.preferences
    cycles_preferences = preferences.addons['cycles'].preferences
    
    # Set compute device type (CUDA, OPTIX, HIP, METAL, or ONEAPI)
    cycles_preferences.compute_device_type = 'CUDA'  # Change to 'OPTIX' for RTX cards
    
    # Get available devices and enable CUDA GPUs
    cycles_preferences.get_devices()
    
    gpu_found = False
    for device in cycles_preferences.devices:
        if device.type == 'CUDA':
            device.use = True
            gpu_found = True
            print(f"✓ Enabled GPU: {device.name}")
    
    if not gpu_found:
        print("⚠ Warning: No CUDA GPUs found, will use CPU")
    
    # Set scene to use GPU compute
    scene.cycles.device = 'GPU'
    
except Exception as e:
    print(f"⚠ Warning: Could not configure GPU rendering: {e}")
    print("  Falling back to CPU rendering")
    scene.cycles.device = 'CPU'

print(f"✓ Render engine: {scene.render.engine}")
print(f"✓ Compute device: {scene.cycles.device}")

# Store original render path
original_filepath = scene.render.filepath

# ============================================================================
# CONFIGURATION - MODIFY THESE VALUES FOR YOUR SETUP
# ============================================================================

OBJECT_NAME = "Cube"
MATERIAL_NAME = None
IMAGE_NODE_NAME = "Image Texture"

# ============================================================================
# VALIDATION
# ============================================================================

obj = bpy.data.objects.get(OBJECT_NAME)
if not obj:
    print(f"ERROR: Could not find object '{OBJECT_NAME}'")
    exit()

if not obj.data.materials:
    print(f"ERROR: Object '{OBJECT_NAME}' has no materials assigned")
    exit()

if MATERIAL_NAME:
    material = bpy.data.materials.get(MATERIAL_NAME)
    if not material:
        print(f"ERROR: Could not find material '{MATERIAL_NAME}'")
        exit()
else:
    material = obj.data.materials[0]

if not material or not material.node_tree:
    print(f"ERROR: Material does not have node tree enabled")
    exit()

img_node = material.node_tree.nodes.get(IMAGE_NODE_NAME)
if not img_node:
    print(f"ERROR: Could not find '{IMAGE_NODE_NAME}' node in material")
    exit()

print(f"✓ Object: {OBJECT_NAME}")
print(f"✓ Material: {material.name}")
print(f"✓ Image Node: {IMAGE_NODE_NAME}")
print(f"\nStarting batch render...\n")

# ============================================================================
# OUTPUT CAPTURE CLASS
# ============================================================================

class OutputCapture:
    """Captures stdout/stderr during rendering"""
    
    def __init__(self):
        self.output_buffer = io.StringIO()
        self.old_stdout = None
        self.old_stderr = None
        
    def start(self):
        """Start capturing output"""
        self.output_buffer = io.StringIO()
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = self.output_buffer
        sys.stderr = self.output_buffer
    
    def stop(self):
        """Stop capturing and return captured output"""
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        output = self.output_buffer.getvalue()
        self.output_buffer.close()
        return output

# ============================================================================
# MAIN RENDERING LOOP
# ============================================================================

output_capture = OutputCapture()
successful_renders = 0
failed_renders = 0

for idx, texture_file in enumerate(texture_files, 1):
    texture_path = Path(texture_file)
    filename_without_ext = texture_path.stem
    
    # Clear screen for new render (optional, comment out if you don't want this)
    if idx > 1:
        os.system('cls' if os.name == 'nt' else 'clear')
    
    print(f"\n{'='*60}")
    print(f"RENDER {idx}/{len(texture_files)}")
    print(f"{'='*60}")
    print(f"File: {filename_without_ext}")
    print(f"{'='*60}\n")
    
    render_start = time.time()
    
    try:
        
        # Start capturing Blender output
        output_capture.start()
        
        # Load the image
        img = bpy.data.images.load(str(texture_file))
        
        # Assign to the Image Texture node
        img_node.image = img
        
        # Set output path with unique filename
        output_filename = f"{filename_without_ext}_render.png"
        scene.render.filepath = str(output_dir / output_filename)
        
        # Render (output is being captured)
        bpy.ops.render.render(write_still=True)
        
        # Stop capturing output
        captured_output = output_capture.stop()
        
        # Unload the image
        bpy.data.images.remove(img)
        
        render_time = time.time() - render_start
        
        # Print the captured Blender output
        print("RENDER OUTPUT:")
        print("-" * 60)
        print(captured_output)
        print("-" * 60)
        print(f"✓ Render complete in {render_time:.2f}s")
        print(f"✓ Saved to: {output_filename}")
        
        successful_renders += 1
        
        # Pause briefly so user can see the output
        if idx < len(texture_files):
            time.sleep(1.5)
        
    except Exception as e:
        try:
            captured_output = output_capture.stop()
        except:
            captured_output = ""
        
        print(f"\n✗ ERROR rendering {texture_path.name}: {str(e)}")
        if captured_output:
            print("\nCaptured output before error:")
            print("-" * 60)
            print(captured_output)
            print("-" * 60)
        
        failed_renders += 1
        time.sleep(2)
        continue

# ============================================================================
# CLEANUP AND SUMMARY
# ============================================================================

scene.render.filepath = original_filepath

# Clear screen for final summary
os.system('cls' if os.name == 'nt' else 'clear')

print(f"\n{'='*60}")
print(f"RENDERING COMPLETE")
print(f"{'='*60}")
print(f"✓ Successful renders: {successful_renders}")
if failed_renders > 0:
    print(f"✗ Failed renders:     {failed_renders}")
print(f"Output folder:        {output_dir}")
print(f"{'='*60}\n")
