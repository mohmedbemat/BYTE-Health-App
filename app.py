from flask import Flask, request, render_template_string
import base64

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

if __name__ == "__main__":
    app.run(debug=True)
