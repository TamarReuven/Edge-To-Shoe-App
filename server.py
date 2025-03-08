import torch
import base64
import io
import re
import numpy as np
from flask import Flask, request, jsonify
import traceback
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import torchvision.transforms as transforms
from generator import Generator
import torch.nn.functional as F
import os

app = Flask(__name__)

# Set fixed seeds for reproducibility
torch.manual_seed(42)
np.random.seed(42)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(42)

# Create tmp directory if it doesn't exist
tmp_dir = "/Users/tamarreuven/ShoeSketchBackend/tmp"
os.makedirs(tmp_dir, exist_ok=True)

# Load model with the SAME parameters as in Colab
model = Generator(n_channels=3, n_classes=3, bilinear=True)
checkpoint = torch.load("/Users/tamarreuven/ShoeSketchBackend/final_generator.pth", map_location="cpu")
model.load_state_dict(checkpoint["generator_state_dict"])
model.eval()

# Print model information for debugging
print(f"Model parameters loaded. Generator has {sum(p.numel() for p in model.parameters())} parameters")
print(f"n_channels: {model.n_channels}, n_classes: {model.n_classes}")

# Apply the SAME transform used in training and for custom images
my_transform = transforms.Compose([
    transforms.Resize((128, 128)),
    # Convert to grayscale with 3 channels to match your Colab processing
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    # Normalize to [0,1] first by using min-max scaling
    transforms.Lambda(lambda x: (x - x.min()) / (x.max() - x.min())),  # [0,1]
    # Then scale to [-1,1] which is what your model expects
    transforms.Lambda(lambda x: 2.0 * x - 1.0)                         # [-1,1]
])

def fix_base64_padding(s):
    """Add padding to base64 string if necessary"""
    padding_needed = len(s) % 4
    if padding_needed:
        s += '=' * (4 - padding_needed)
    return s

@app.route("/generate", methods=["POST"])
def generate():
    try:
        # Set fixed seed for reproducibility
        torch.manual_seed(42)
        
        data = request.json
        sketch_base64 = data.get("sketch")
        
        # 1. Decode base64 to a PIL image
        image_data = base64.b64decode(sketch_base64)
        original_image = Image.open(io.BytesIO(image_data))
        
        print(f"Original image mode: {original_image.mode}, size: {original_image.size}")
        
        # 2. Convert to RGB mode first (this will be converted to grayscale by transform)
        # We always convert to RGB to ensure consistent processing
        processed_image = original_image.convert('RGB')
            
        print(f"Processed image mode: {processed_image.mode}, size: {processed_image.size}")
        
        # Save the processed input image for debugging
        processed_image.save(f"{tmp_dir}/processed_input.png")
        
        # 3. Apply exactly the same preprocessing used in training
        input_tensor = my_transform(processed_image).unsqueeze(0)
        print(f"Input tensor shape: {input_tensor.shape}")
        print(f"Input tensor range: min={input_tensor.min().item():.4f}, max={input_tensor.max().item():.4f}, mean={input_tensor.mean().item():.4f}")
        
        # Save debug image to verify preprocessing
        debug_input = (input_tensor.squeeze(0) + 1) / 2
        debug_img = transforms.ToPILImage()(debug_input)
        debug_img.save(f"{tmp_dir}/debug_input.png")
        
        # 4. Run model inference
        with torch.no_grad():
            generated_tensor = model(input_tensor)
            
        print(f"Output tensor stats: min={generated_tensor.min().item():.4f}, max={generated_tensor.max().item():.4f}, mean={generated_tensor.mean().item():.4f}")
            
        # 5. Proper denormalization from [-1,1] to [0,1]
        output_tensor = (generated_tensor.squeeze(0) + 1) / 2
        output_tensor = torch.clamp(output_tensor, 0, 1)
        
        # 6. Convert to PIL and then base64
        output_image = transforms.ToPILImage()(output_tensor)
        output_image.save(f"{tmp_dir}/final_output.png")
        
        buffer = io.BytesIO()
        output_image.save(buffer, format="PNG")
        output_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        return jsonify({
            "generated_image": output_base64
        })
    
    except Exception as e:
        print(f"Error in generate endpoint: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "ok", "model": "Generator", "n_channels": model.n_channels, "n_classes": model.n_classes})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)