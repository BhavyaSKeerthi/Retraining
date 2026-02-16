import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro - Fix Applied</title>
    <style>
        body { font-family: sans-serif; background: #f0f2f5; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 400px; text-align: center; }
        button { background: #1a73e8; color: white; border: none; padding: 12px; width: 100%; border-radius: 6px; cursor: pointer; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Annotator Tool</h2>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Process & Download</button>
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
    if not file: return "No file", 400

    try:
        # Load the raw data
        # We don't skip rows yet to find where the data actually starts
        raw_df = pd.read_csv(file)
        
        # FIND THE USER COLUMN:
        # Instead of 'Unnamed: 2', we look for the column that has IDs
        # Usually the 3rd column (index 2)
        target_index = 2 if len(raw_df.columns) >= 3 else 0
        
        # We force selection of a SINGLE column to prevent the 'DataFrame' error
        user_series = raw_df.iloc[:, target_index]
        
        # Clean the ID column
        annotator_ids = user_series.astype(str).str.strip()
        
        # Create a clean dataframe for processing
        df = raw_df.copy()
        user_col = 'annotator_id'
        df[user_col] = annotator_ids

        # Identify value columns (everything except our new ID and 'Unnamed' noise)
        value_cols = [col for col in df.columns if 'Unnamed' not in str(col) and col != user_col]

        # Aggregate logic
        result = pd.DataFrame({user_col: df[user_col].unique()})

        for col in value_cols:
            # Skip the first row if it was a sub-header (your original logic)
            # We do this by slicing the data
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # This is the pivot logic
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            counts = counts.add_prefix(f'{col}_')
            result = result.merge(counts, on=user_col, how='left')

        # Clean up
        result = result.fillna(0)
        for c in result.columns:
            if c != user_col:
                result[c] = result[c].astype(int)

        # Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="results.csv")

    except Exception as e:
        # This will tell us EXACTLY which line failed
        import traceback
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
