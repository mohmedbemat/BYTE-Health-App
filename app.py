from flask import Flask, request, render_template_string, jsonify
import base64
import cv2
import numpy as np
from pyzbar import pyzbar
from PIL import Image
import io
import requests

app = Flask(__name__)

# Serve HTML page
@app.route("/")
def index():
    return render_template_string(open("index.html").read())

# Receive captured image
@app.route("/upload", methods=["POST"])
def upload():
    data = request.json["image"]
    header, encoded = data.split(",", 1)
    image_bytes = base64.b64decode(encoded)

    with open("captured.png", "wb") as f:
        f.write(image_bytes)

    return {"status": "success"}

# Scan barcode and get nutrition info
@app.route("/scan-barcode", methods=["POST"])
def scan_barcode():
    try:
        data = request.json["image"]
        header, encoded = data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to OpenCV format
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Decode barcodes
        barcodes = pyzbar.decode(opencv_image)
        
        if not barcodes:
            return jsonify({"status": "no_barcode", "message": "No barcode detected"})
        
        # Get the first barcode
        barcode = barcodes[0]
        barcode_data = barcode.data.decode('utf-8')
        barcode_type = barcode.type
        
        # Get nutrition info from OpenFoodFacts API
        nutrition_info = get_nutrition_info(barcode_data)
        
        return jsonify({
            "status": "success",
            "barcode": barcode_data,
            "barcode_type": barcode_type,
            "nutrition": nutrition_info
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def get_nutrition_info(barcode):
    """Get nutrition information from OpenFoodFacts API"""
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") == 1:  # Product found
                product = data.get("product", {})
                
                # Extract nutrition information
                nutrition = {
                    "product_name": product.get("product_name", "Unknown Product"),
                    "brand": product.get("brands", "Unknown Brand"),
                    "calories_per_100g": product.get("nutriments", {}).get("energy-kcal_100g"),
                    "protein_per_100g": product.get("nutriments", {}).get("proteins_100g"),
                    "fat_per_100g": product.get("nutriments", {}).get("fat_100g"),
                    "carbs_per_100g": product.get("nutriments", {}).get("carbohydrates_100g"),
                    "fiber_per_100g": product.get("nutriments", {}).get("fiber_100g"),
                    "sugar_per_100g": product.get("nutriments", {}).get("sugars_100g"),
                    "salt_per_100g": product.get("nutriments", {}).get("salt_100g"),
                    "serving_size": product.get("serving_size"),
                    "image_url": product.get("image_url")
                }
                
                return nutrition
            else:
                return {"error": "Product not found in database"}
        else:
            return {"error": "Failed to fetch product data"}
            
    except Exception as e:
        return {"error": f"API request failed: {str(e)}"}

if __name__ == "__main__":
    app.run(debug=True)
