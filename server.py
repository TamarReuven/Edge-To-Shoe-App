import os
import re
import io
import base64
import torch
import traceback
import numpy as np
from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import torchvision.transforms as transforms
from generator import Generator
import torch.nn.functional as F

app = Flask(__name__)

# Set fixed seeds for reproducibility
torch.manual_seed(42)
np.random.seed(42)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(42)

# Paths
BASE_DIR = "/Users/tamarreuven/ShoeSketchBackend"
TMP_DIR = os.path.join(BASE_DIR, "tmp")
CKPT_PATH = os.path.join(BASE_DIR, "generator_final (4).pth")
TS_PATH   = os.path.join(BASE_DIR, "generator.pt")

# Create tmp directory if it doesn't exist
os.makedirs(TMP_DIR, exist_ok=True)

# Load model with the SAME parameters as in Colab
model = Generator(n_channels=3, n_classes=3, bilinear=True)
checkpoint = torch.load(CKPT_PATH, map_location="cpu")
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

print(f"[✓] Model loaded. Generator parameters: {sum(p.numel() for p in model.parameters())}")
print(f"[✓] n_channels: {model.n_channels}, n_classes: {model.n_classes}")

# Apply the SAME transform used in training and for custom images
my_transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Lambda(lambda x: (x - x.min()) / (x.max() - x.min())),  # [0,1]
    transforms.Lambda(lambda x: 2.0 * x - 1.0)                         # [-1,1]
])

def fix_base64_padding(s):
    """Add padding to base64 string if necessary"""
    padding_needed = len(s) % 4
    if padding_needed:
        s += "=" * (4 - padding_needed)
    return s

@app.route("/generate", methods=["POST"])
def generate():
    try:
        torch.manual_seed(42)
        data = request.json
        sketch_base64 = data.get("sketch", "")
        sketch_base64 = fix_base64_padding(sketch_base64)

        # Decode and preprocess
        image_data = base64.b64decode(sketch_base64)
        original_image = Image.open(io.BytesIO(image_data))
        processed_image = original_image.convert("RGB")
        processed_image.save(f"{TMP_DIR}/processed_input.png")

        input_tensor = my_transform(processed_image).unsqueeze(0)
        debug_input = (input_tensor.squeeze(0) + 1) / 2
        transforms.ToPILImage()(debug_input).save(f"{TMP_DIR}/debug_input.png")

        # Inference
        with torch.no_grad():
            gen_out = model(input_tensor)
        output_tensor = torch.clamp((gen_out.squeeze(0) + 1) / 2, 0, 1)

        # Return base64 PNG
        output_image = transforms.ToPILImage()(output_tensor)
        output_image.save(f"{TMP_DIR}/final_output.png")
        buf = io.BytesIO()
        output_image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

        return jsonify({"generated_image": encoded})

    except Exception as e:
        print(f"[!] Error in /generate: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "ok",
        "model": "Generator",
        "n_channels": model.n_channels,
        "n_classes": model.n_classes
    })

@app.route("/download_checkpoint", methods=["GET"])
def download_checkpoint():
    """Download the raw .pth checkpoint as an attachment."""
    if not os.path.isfile(CKPT_PATH):
        return jsonify({"error": "Checkpoint not found"}), 404
    return send_file(
        CKPT_PATH,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=os.path.basename(CKPT_PATH)
    )

@app.route("/download_torchscript", methods=["GET"])
def download_torchscript():
    """Download the TorchScript-exported .pt model as an attachment."""
    if not os.path.isfile(TS_PATH):
        return jsonify({"error": "TorchScript model not found"}), 404
    return send_file(
        TS_PATH,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=os.path.basename(TS_PATH)
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
