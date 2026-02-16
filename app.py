import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# Professional UI Design
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 450px; text-align: center; }
        .status-badge { display: inline-block; background: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 99px; font-size: 12px; margin-bottom: 20px; }
        button { background: #2563eb; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 10px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; pt: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="status-badge">● Service Live</div>
        <h2>Annotator Tool</h2>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required style="margin-bottom: 20px;">
            <button type="submit">Process & Download Results</button>
        </form>
        <div class="info">
            <p><strong>Tip:</strong> Ensure your CSV has a column for IDs (like "soul ID" or "annotator_id").</p>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# Health check route for Render to keep the port open
@app.route('/healthz')
def healthz():
    return "OK", 200

@app.route('/process', methods=['POST'])
def process():
    file = request.files.get('file')
    if not file: return "No file uploaded", 400

    try:
        # Load data - automatically detecting headers
        df = pd.read_csv(file)
        
        # Flexibly find the ID column
        user_col = 'annotator_id'
        possible_ids = ['id', 'user', 'soul', 'annotator', 'worker']
        target_col = None
        
        for col in df.columns:
            if any(name in str(col).lower() for name in possible_ids):
                target_col = col
                break
        
        # If no name match, default to 3rd column (index 2)
        if target_col is None:
            target_col = df.columns[2] if len(df.columns) >= 3 else df.columns[0]

        # Use .copy() and specific selection to fix 'DataFrame' object has no attribute 'str'
        df[user_col] = df[target_col].astype(str).str.strip()

        # Identify values to count
        value_cols = [col for col in df.columns if col not in [user_col, target_col] and 'Unnamed' not in str(col)]

        # Group and Count logic
        result = pd.DataFrame({user_col: df[user_col].unique()})
        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            counts.columns = [f"{col}_{str(int(c)) if isinstance(c, float) else c}" for c in counts.columns]
            result = result.merge(counts, on=user_col, how='left')

        result = result.fillna(0)
        for c in result.columns:
            if c != user_col:
                result[c] = pd.to_numeric(result[c]).astype(int)

        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="processed_annotator_data.csv")

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    # Force use of Render's port or default to 10000
    port = int(os.environ.get("PORT", 10000))
    # Listen on all interfaces (0.0.0.0)
    app.run(host='0.0.0.0', port=port)
