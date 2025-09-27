from flask import Flask, request, render_template_string, jsonify
import base64
import cv2
import numpy as np
from pyzbar import pyzbar
from PIL import Image
import io
import requests
import json
import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("API_KEY"))

app = Flask(__name__)
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")

    if not user_message:
        return jsonify({"reply": "⚠️ Please type something."})

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"You are a health assistant. Answer: {user_message}")

    return jsonify({"reply": response.text})

# Add CORS headers manually
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Serve HTML page
@app.route("/")
def index():
    return render_template_string(open("index.html").read())

# Add a debug route to check available routes
@app.route("/debug-routes")
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': rule.rule
        })
    return jsonify(routes)

# Receive captured image
@app.route("/upload", methods=["POST", "OPTIONS"])
def upload():
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"})
    
    data = request.json["image"]
    header, encoded = data.split(",", 1)
    image_bytes = base64.b64decode(encoded)

    with open("captured.png", "wb") as f:
        f.write(image_bytes)

    return {"status": "success"}

# Scan barcode and get nutrition info
@app.route("/scan-barcode", methods=["POST", "OPTIONS"])
def scan_barcode():
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"})
    
    print(f"Received request to /scan-barcode with method: {request.method}")
    try:
        if not request.json:
            return jsonify({"status": "error", "message": "No JSON data received"})
        
        if "image" not in request.json:
            return jsonify({"status": "error", "message": "No image data in request"})
            
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
        
        # Save to shared data file for Streamlit
        if nutrition_info and 'error' not in nutrition_info:
            save_scanned_food(nutrition_info)
        
        return jsonify({
            "status": "success",
            "barcode": barcode_data,
            "barcode_type": barcode_type,
            "nutrition": nutrition_info
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def save_scanned_food(nutrition_info):
    """Save scanned food to shared JSON file"""
    try:
        # Load existing data
        data_file = 'scanned_foods.json'
        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                data = json.load(f)
        else:
            data = {'foods': []}
        
        # Add new food with timestamp
        food_entry = {
            'name': nutrition_info.get('product_name', 'Unknown Product'),
            'brand': nutrition_info.get('brand', ''),
            'calories': nutrition_info.get('calories', 0),
            'protein': nutrition_info.get('protein', 0),
            'carbs': nutrition_info.get('carbs', 0),
            'fat': nutrition_info.get('fat', 0),
            'fiber': nutrition_info.get('fiber', 0),
            'sugar': nutrition_info.get('sugar', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        data['foods'].append(food_entry)
        
        # Save updated data
        with open(data_file, 'w') as f:
            json.dump(data, f)
            
        print(f"Saved food: {food_entry['name']} ({food_entry['calories']} cal)")
        
    except Exception as e:
        print(f"Error saving food data: {e}")

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
                nutriments = product.get("nutriments", {})
                
                # Prefer per-serving values, fall back to per-100g
                nutrition = {
                    "product_name": product.get("product_name", "Unknown Product"),
                    "brand": product.get("brands", "Unknown Brand"),
                    "quantity": product.get("quantity"),
                    "serving_size": product.get("serving_size"),
                    
                    # Try to get per-serving values first, then per-container, then per-100g
                    "calories": (
                        nutriments.get("energy-kcal_serving") or 
                        nutriments.get("energy-kcal") or 
                        nutriments.get("energy-kcal_100g")
                    ),
                    "protein": (
                        nutriments.get("proteins_serving") or 
                        nutriments.get("proteins") or 
                        nutriments.get("proteins_100g")
                    ),
                    "fat": (
                        nutriments.get("fat_serving") or 
                        nutriments.get("fat") or 
                        nutriments.get("fat_100g")
                    ),
                    "carbs": (
                        nutriments.get("carbohydrates_serving") or 
                        nutriments.get("carbohydrates") or 
                        nutriments.get("carbohydrates_100g")
                    ),
                    "fiber": (
                        nutriments.get("fiber_serving") or 
                        nutriments.get("fiber") or 
                        nutriments.get("fiber_100g")
                    ),
                    "sugar": (
                        nutriments.get("sugars_serving") or 
                        nutriments.get("sugars") or 
                        nutriments.get("sugars_100g")
                    ),
                    "salt": (
                        nutriments.get("salt_serving") or 
                        nutriments.get("salt") or 
                        nutriments.get("salt_100g")
                    ),
                    
                    # Also include per-100g for reference
                    "calories_per_100g": nutriments.get("energy-kcal_100g"),
                    "protein_per_100g": nutriments.get("proteins_100g"),
                    "fat_per_100g": nutriments.get("fat_100g"),
                    "carbs_per_100g": nutriments.get("carbohydrates_100g"),
                    
                    "image_url": product.get("image_url"),
                    "nutrition_grade": product.get("nutrition_grades")
                }
                
                return nutrition
            else:
                return {"error": "Product not found in database"}
        else:
            return {"error": "Failed to fetch product data"}
            
    except Exception as e:
        return {"error": f"API request failed: {str(e)}"}

if __name__ == "__main__":
    print("Starting Flask server...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} - Methods: {list(rule.methods)}")
    app.run(debug=True, host='127.0.0.1', port=5001)