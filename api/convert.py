from flask import Flask, request, jsonify, make_response
import vtracer
import re
import tempfile
import os

app = Flask(__name__)

# A catch-all route that handles both GET and POST for /api/convert
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    if request.method == 'GET':
        return jsonify({"status": "API is running. Send a POST request with an 'image' file to convert."}), 200

    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save to temp file
    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, "input_image.png")
    output_path = os.path.join(temp_dir, "output_image.svg")
    
    file.save(input_path)
    
    try:
        # Convert logic
        vtracer.convert_image_to_svg_py(
            input_path, 
            output_path,
            "color",    
            "cutout",   
            "spline",   
            10,         
            6,          
            16,         
            60,         
            5.0,        
            10,         
            45,         
            8           
        )
        
        # Post-process for coloring regions
        with open(output_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
            
        def replacer(match):
            color = match.group(1)
            if len(color) == 7:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                brightness = (r + g + b) / 3
                if brightness > 128:
                    return 'fill="#FFFFFF"'
                else:
                    return 'fill="#000000"'
            return match.group(0)

        new_svg = re.sub(r'fill="(\#[A-Fa-f0-9]{6})"', replacer, svg_content)
        
        # Return SVG directly
        response = make_response(new_svg)
        response.headers['Content-Type'] = 'image/svg+xml'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Cleanup
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

if __name__ == '__main__':
    app.run(debug=True)
