import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro - Final Fix</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 450px; text-align: center; }
        .info { text-align: left; font-size: 13px; color: #475569; background: #f1f5f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        button { background: #2563eb; color: white; border: none; padding: 12px; width: 100%; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .error { color: #dc2626; font-size: 14px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Annotator Tool</h2>
        <div class="info">
            <strong>Requirements:</strong><br>
            • Upload a CSV file.<br>
            • Ensure one column has IDs (like "annotator_id" or "user_id").<br>
            • Value columns should contain the labels/scores.
        </div>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Process & Download Results</button>
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
    file = request.files.get('file')
    if not file: return "No file uploaded", 400

    try:
        # 1. Load data without skipping rows first to inspect headers
        df = pd.read_csv(file)
        
        # 2. Find the ID column automatically
        # We look for common names, otherwise default to the 3rd column
        user_col = None
        possible_id_names = ['id', 'user', 'annotator', 'soul', 'worker']
        
        for col in df.columns:
            if any(name in str(col).lower() for name in possible_id_names):
                user_col = col
                break
        
        if user_col is None:
            user_col = df.columns[2] if len(df.columns) >= 3 else df.columns[0]

        # 3. Clean the ID column (Crucial Fix for 'DataFrame' error)
        # We ensure we select ONLY the series and drop any rows that are completely empty
        df = df.dropna(subset=[user_col])
        df['temp_id'] = df[user_col].astype(str).str.strip()
        final_user_col = 'annotator_id'
        df = df.rename(columns={'temp_id': final_user_col})

        # 4. Identify value columns (ignore ID columns and Unnamed noise)
        value_cols = [col for col in df.columns if 'Unnamed' not in str(col) 
                      and str(col).lower() not in possible_id_names 
                      and col != final_user_col]

        # 5. Build Results
        # Start with unique users
        unique_users = df[final_user_col].unique()
        result = pd.DataFrame({final_user_col: unique_users})

        for col in value_cols:
            # Convert values to numeric, turning text into NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Pivot table: Count occurrences of each value for each user
            counts = (
                df.groupby(final_user_col)[col]
                .value_counts()
                .unstack(fill_value=0)
            )
            
            # Rename columns to be descriptive: "Attribute_Score"
            counts.columns = [f"{col}_{int(c) if isinstance(c, float) else c}" for c in counts.columns]
            result = result.merge(counts, on=final_user_col, how='left')

        # 6. Final cleanup of result
        result = result.fillna(0)
        # Convert all count columns to integers
        for c in result.columns:
            if c != final_user_col:
                result[c] = pd.to_numeric(result[c]).astype(int)

        # 7. Return the file
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="annotator_report.csv")

    except Exception as e:
        return f"Processing Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
