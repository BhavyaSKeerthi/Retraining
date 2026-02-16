import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro + Cohort Analysis</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 480px; text-align: center; }
        .feature-tag { display: inline-block; background: #eff6ff; color: #1e40af; padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: bold; margin-bottom: 10px; }
        button { background: #2563eb; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="feature-tag">NEW: COHORT CLUSTERING ACTIVE</div>
        <h2>Annotator Tool</h2>
        <p>Upload CSV to generate counts and error cohorts.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Process & Group Cohorts</button>
        </form>
        <div class="info">
            <strong>Cohort Logic:</strong><br>
            • Rubric 2 is marked as Correct.<br>
            • Rubric 0 & 1 are marked as Mistakes.<br>
            • Users are grouped by their most frequent mistake column.
        </div>
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
        df = pd.read_csv(file)
        
        # 1. Identify Annotator ID
        user_col = 'annotator_id'
        possible_ids = ['id', 'user', 'soul', 'annotator']
        target_col = next((c for c in df.columns if any(p in str(c).lower() for p in possible_ids)), df.columns[2])
        
        df[user_col] = df[target_col].astype(str).str.strip()
        value_cols = [c for c in df.columns if c not in [user_col, target_col] and 'Unnamed' not in str(c)]

        # 2. Generate Pivot Counts
        result = pd.DataFrame({user_col: df[user_col].unique()})
        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            # Standardize names to Column_Value
            counts.columns = [f"{col}_{str(int(c)) if isinstance(c, float) else c}" for c in counts.columns]
            result = result.merge(counts, on=user_col, how='left')

        result = result.fillna(0)

        # 3. Cohort Analysis Logic
        # Identify mistake columns (anything ending in _0 or _1)
        mistake_cols = [c for c in result.columns if c.endswith('_0') or c.endswith('_1')]
        
        def assign_cohort(row):
            # Find the column where the user made the most mistakes
            if row[mistake_cols].sum() == 0:
                return "Top Performers (No Mistakes)"
            
            # Get the name of the column with the highest value among mistakes
            primary_mistake = row[mistake_cols].idxmax()
            # Clean up the name for the label (e.g., 'grammar_0' -> 'Grammar Issues')
            label = primary_mistake.rsplit('_', 1)[0].replace('_', ' ').title()
            return f"Retraining: {label} Focus"

        if mistake_cols:
            result['cohort_group'] = result.apply(assign_cohort, axis=1)
        else:
            result['cohort_group'] = "Insufficient Data for Cohorts"

        # Final Formatting
        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = pd.to_numeric(result[c]).astype(int)

        # 4. Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="cohort_analysis_report.csv")

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
