import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# Professional UI
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro</title>
    <style>
        body { font-family: sans-serif; background: #f0f2f5; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 400px; text-align: center; }
        button { background: #1a73e8; color: white; border: none; padding: 12px; width: 100%; border-radius: 6px; cursor: pointer; margin-top: 20px; font-weight: bold; }
        .footer { margin-top: 20px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Annotator Tool</h2>
        <p>Upload CSV to get user distributions</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Process & Download</button>
        </form>
        <div class="footer">Ready for Deployment</div>
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
        # 1. Load data
        df = pd.read_csv(file, skiprows=[1])
        
        # 2. Hard-target the annotator column (assumed 3rd column)
        # Using .iloc ensures we get a Series, preventing the 'DataFrame' error
        user_col = 'annotator_id'
        df[user_col] = df.iloc[:, 2].astype(str).str.strip()

        # 3. Identify value columns
        value_cols = [col for col in df.columns if 'Unnamed' not in str(col) and col != user_col]

        # 4. Process
        result = pd.DataFrame({user_col: df[user_col].unique()})
        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            counts = counts.add_prefix(f'{col}_')
            result = result.merge(counts, on=user_col, how='left')

        # 5. Cleanup
        result = result.fillna(0)
        for c in result.columns:
            if c != user_col:
                result[c] = result[c].astype(int)

        # 6. Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="processed_results.csv")

    except Exception as e:
        return f"Processing Error: {str(e)}", 500

if __name__ == '__main__':
    # CRITICAL FOR RENDER: 
    # Must listen on 0.0.0.0 and use the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
