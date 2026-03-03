import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# Updated UI to reflect the Error Summation logic
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro - Error & Cohort Analysis</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 480px; text-align: center; }
        .feature-tag { display: inline-block; background: #fff7ed; color: #9a3412; padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: bold; margin-bottom: 10px; border: 1px solid #ffedd5; }
        button { background: #1e293b; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="feature-tag">LOGIC: SUM(RUBRIC 0 + 1) ACTIVE</div>
        <h2>Retraining Dashboard</h2>
        <p>Upload CSV to generate error-based cohorts.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Analyze Mistakes & Group</button>
        </form>
        <div class="info">
            <strong>Updated Analysis Logic:</strong><br>
            • <b>Ignores Rubric 2:</b> Correct answers are not counted.<br>
            • <b>Summed Mistakes:</b> Combines Rubric 0 and Rubric 1 into a single total per attribute.<br>
            • <b>Cohort Splitting:</b> Groups users based on their highest mistake category.
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
        # Load data
        df = pd.read_csv(file)
        
        # 1. Identify Annotator ID Column
        user_col = 'annotator_id'
        possible_ids = ['id', 'user', 'soul', 'annotator']
        target_col_name = next((c for c in df.columns if any(p in str(c).lower() for p in possible_ids)), df.columns[2])
        
        # Safe extraction to prevent DataFrame attribute errors
        df[user_col] = df[target_col_name].astype(str).str.strip()
        
        # Identify attribute columns (excluding IDs and junk)
        attr_cols = [c for c in df.columns if c not in [user_col, target_col_name] and 'Unnamed' not in str(c)]

        # 2. Generate Pivot & Summation
        unique_users = df[user_col].unique()
        result = pd.DataFrame({user_col: unique_users})

        for col in attr_cols:
            # Force numeric conversion for the specific column
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Count occurrences per user
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            
            # Get Rubric 0 and Rubric 1 counts (default to 0 if they don't exist)
            r0 = counts[0] if 0 in counts.columns else 0
            r1 = counts[1] if 1 in counts.columns else 0
            
            # Sum them and add to the result table
            # We use .map to ensure alignment with the unique_users in 'result'
            result[f"{col}_total_mistakes"] = result[user_col].map(r0 + r1).fillna(0)

        # 3. Global Metrics
        mistake_cols = [c for c in result.columns if c.endswith('_total_mistakes')]
        result['overall_total_errors'] = result[mistake_cols].sum(axis=1)

        # 4. Cohort Assignment
        def assign_cohort(row):
            if row['overall_total_errors'] == 0:
                return "Cohort: Proficient (No Mistakes)"
            
            # Find the column where the user made the most total mistakes
            max_err_col = row[mistake_cols].idxmax()
            clean_label = max_err_col.replace('_total_mistakes', '').replace('_', ' ').title()
            return f"Cohort: {clean_label} Retraining"

        if mistake_cols:
            result['cohort_group'] = result.apply(assign_cohort, axis=1)
        else:
            result['cohort_group'] = "Insufficient Data"

        # 5. Final Formatting
        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = pd.to_numeric(result[c]).astype(int)

        # 6. Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="retraining_cohort_report.csv")

    except Exception as e:
        import traceback
        return f"Processing Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
