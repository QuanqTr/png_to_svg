from flask import Flask, request, jsonify, make_response
import vtracer
import re
import tempfile
import os

# Create Flask app and serve static files from the parent directory
app = Flask(__name__)

@app.route('/api/convert', methods=['POST'])
def convert_to_svg():
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
        # Pre-process: Handle alpha channel and Binarize
        from PIL import Image, ImageFilter
        with Image.open(input_path) as img:
            # Handle transparency by blending with white background
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[3])
                gray = bg.convert("L")
            else:
                gray = img.convert("L")
            
            # Anti-aliasing / smoothing trick:
            # 1. Upscale 2x to give vtracer more resolution for curves
            # 2. Blur to destroy the 90-degree pixel staircases
            # 3. Threshold to get a perfectly smooth, continuous edge
            w, h = gray.size
            smoothed = gray.resize((w * 2, h * 2), Image.BICUBIC)
            smoothed = smoothed.filter(ImageFilter.GaussianBlur(radius=1))
            
            # Threshold (200) to guarantee thick, closed lines
            bw = smoothed.point(lambda x: 255 if x > 200 else 0, mode="L").convert("RGB")
            bw.save(input_path)

        # Convert logic
        vtracer.convert_image_to_svg_py(
            input_path, 
            output_path,
            "color",    
            "cutout",   
            "spline",   
            4,          # filter_speckle
            6,          # color_precision
            16,         # layer_difference
            60,         # corner_threshold (Restored to 60 to KEEP 90-degree canvas corners and sharp drawing tips)
            4.0,        # length_threshold
            10,         # max_iterations
            45,         # splice_threshold
            8           # path_precision
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

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # This serves the index.html from the root folder
    root_dir = os.path.dirname(os.path.dirname(__file__))
    html_path = os.path.join(root_dir, 'index.html')
    
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "UI not found", 404

if __name__ == '__main__':
    app.run(debug=True)
