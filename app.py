from flask import Flask, request, send_file, render_template_string
import pandas as pd
import io
import os

app = Flask(__name__)

# This is the "Front-end" of your product (HTML/CSS)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Annotator Analytics Tool</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); width: 100%; max-width: 450px; text-align: center; }
        h1 { color: #1a73e8; margin-bottom: 1rem; }
        p { color: #5f6368; font-size: 0.9rem; margin-bottom: 2rem; }
        input[type="file"] { margin-bottom: 1.5rem; display: block; width: 100%; }
        button { background-color: #1a73e8; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; transition: background 0.3s; }
        button:hover { background-color: #1557b0; }
        .footer { margin-top: 2rem; font-size: 0.8rem; color: #9aa0a6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Annotator Pro</h1>
        <p>Upload your .csv file to generate user-level distribution counts automatically.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Process & Download Results</button>
        </form>
        <div class="footer">Powered by Python & Flask</div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    
    try:
        # --- Your Original Logic Optimized for Web ---
        df = pd.read_csv(file, skiprows=[1])
        
        # Identify the ID column (defaults to 3rd column if Unnamed: 2 isn't found)
        user_col = 'annotator_id'
        target_col = 'Unnamed: 2' if 'Unnamed: 2' in df.columns else df.columns[2]
        df.rename(columns={target_col: user_col}, inplace=True)
        
        # Clean ID column
        df[user_col] = df[user_col].astype(str).str.strip()
        
        # Identify value columns
        value_cols = [col for col in df.columns if col != user_col and 'Unnamed:' not in col]
        
        # Aggregate logic
        result = pd.DataFrame({user_col: df[user_col].unique()})
        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            counts = counts.add_prefix(f'{col}_')
            result = result.merge(counts, on=user_col, how='left')

        result = result.fillna(0).convert_dtypes() # Clean up NaNs and types

        # Convert to CSV in memory (no local file saving needed)
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
    # Use environment variable for Port (required for deployment)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)