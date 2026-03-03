import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# UI Design
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro - Detailed Analysis</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 480px; text-align: center; }
        .feature-tag { display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: bold; margin-bottom: 10px; }
        button { background: #1e293b; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="feature-tag">DETAILED SCORING MODE ACTIVE</div>
        <h2>Retraining Dashboard</h2>
        <p>Now showing 0s, 1s, and 2s separately for all rubrics.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Generate Detailed Report</button>
        </form>
        <div class="info">
            <strong>What this report includes:</strong><br>
            • <b>Separate Counts:</b> Columns for every 0, 1, and 2 found per rubric.<br>
            • <b>Total Errors:</b> A sum of all 0s and 1s for each user.<br>
            • <b>Cohort Logic:</b> Groups users by their primary area of struggle.
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
        if user_col not in df.columns:
            match = [c for c in df.columns if any(x in str(c).lower() for x in ['id', 'user', 'soul'])]
            target_col = match[0] if match else df.columns[0]
            df.rename(columns={target_col: user_col}, inplace=True)
        
        df[user_col] = df[user_col].astype(str).str.strip()
        
        # 2. Identify Rubric Columns (Numeric with few unique values)
        rubric_cols = []
        for col in df.columns:
            if col == user_col: continue
            if df[col].dtype in ['int64', 'float64']:
                unique_vals = df[col].dropna().unique()
                # Filtering high-cardinality columns prevents the "hanging" issue
                if len(unique_vals) <= 5: 
                    rubric_cols.append(col)

        # 3. Generate Pivot with Separate 0, 1, 2 Columns
        unique_users = df[user_col].unique()
        result = pd.DataFrame({user_col: unique_users})

        for col in rubric_cols:
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            
            # Map counts for 0, 1, and 2 separately
            for val in [0, 1, 2]:
                if val in counts.columns:
                    result[f"{col}_{val}"] = result[user_col].map(counts[val]).fillna(0)
                else:
                    result[f"{col}_{val}"] = 0

        # 4. Calculate Overall Errors and Cohorts
        # Mistakes are defined as any score of 0 or 1
        mistake_cols = [c for c in result.columns if c.endswith('_0') or c.endswith('_1')]
        result['overall_total_errors'] = result[mistake_cols].sum(axis=1)

        def assign_cohort(row):
            if row['overall_total_errors'] == 0:
                return "Cohort: Top Performers"
            # Find the rubric where the user had the most combined 0s and 1s
            rubric_mistake_totals = {}
            for col in rubric_cols:
                rubric_mistake_totals[col] = row.get(f"{col}_0", 0) + row.get(f"{col}_1", 0)
            
            max_rubric = max(rubric_mistake_totals, key=rubric_mistake_totals.get)
            clean_name = max_rubric.replace('_', ' ').title()
            return f"Cohort: {clean_name} Retraining"

        result['cohort_group'] = result.apply(assign_cohort, axis=1)

        # Final Cleanup: Convert counts to integers
        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = result[c].astype(int)

        # 5. Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="detailed_retraining_report.csv")

    except Exception as e:
        import traceback
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
