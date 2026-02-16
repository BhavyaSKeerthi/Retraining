import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# Professional UI Design (HTML/CSS)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Annotator Analytics Pro</title>
    <style>
        body { font-family: 'Inter', system-ui, sans-serif; background-color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 2.5rem; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); width: 100%; max-width: 400px; text-align: center; border: 1px solid #e2e8f0; }
        h1 { color: #1e293b; font-size: 1.5rem; margin-bottom: 0.5rem; }
        p { color: #64748b; font-size: 0.9rem; margin-bottom: 2rem; line-height: 1.5; }
        .upload-area { border: 2px dashed #cbd5e1; padding: 20px; border-radius: 12px; margin-bottom: 1.5rem; transition: border-color 0.3s; }
        .upload-area:hover { border-color: #3b82f6; }
        input[type="file"] { width: 100%; font-size: 0.8rem; }
        button { background-color: #2563eb; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; width: 100%; transition: background 0.2s; }
        button:hover { background-color: #1d4ed8; }
        .error-msg { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 6px; margin-top: 10px; font-size: 0.85rem; display: none; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Annotator Pro</h1>
        <p>Upload your CSV to transform raw labels into user-level count distributions.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <div class="upload-area">
                <input type="file" name="file" accept=".csv" required>
            </div>
            <button type="submit">Process & Download CSV</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    try:
        # Load data - skipping 2nd row as per your original logic
        df = pd.read_csv(file, skiprows=[1])
        
        # Identify the ID column (defensive targeting)
        user_col = 'annotator_id'
        if len(df.columns) >= 3:
            # Replaces 'Unnamed: 2' safely by index
            df.rename(columns={df.columns[2]: user_col}, inplace=True)
        else:
            df.rename(columns={df.columns[0]: user_col}, inplace=True)

        # CLEANING: Ensure we only strip the string column to avoid 'DataFrame' has no attribute 'str' error
        df[user_col] = df[user_col].astype(str).str.strip()

        # Identify value columns (ignoring the ID and any junk 'Unnamed' columns)
        value_cols = [col for col in df.columns if col != user_col and 'Unnamed:' not in col]

        # Aggregate: Long to Wide Transformation
        result = pd.DataFrame({user_col: df[user_col].unique()})

        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            counts = (
                df.groupby(user_col)[col]
                .value_counts()
                .unstack(fill_value=0)
            )
            counts = counts.add_prefix(f'{col}_')
            result = result.merge(counts, on=user_col, how='left')

        # Final Formatting
        result = result.fillna(0)
        for col in result.columns:
            if col != user_col:
                result[col] = result[col].astype(int)

        # Output to user
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype="text/csv",
            as_attachment=True,
            download_name="user_level_counts.csv"
        )

    except Exception as e:
        return f"Processing Error: {str(e)}", 500

if __name__ == '__main__':
    # Deploy-ready port handling
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
