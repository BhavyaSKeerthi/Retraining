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
    <title>Annotator Pro - High Performance</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 480px; text-align: center; }
        .feature-tag { display: inline-block; background: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: bold; margin-bottom: 10px; }
        button { background: #1e293b; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="feature-tag">HIGH PERFORMANCE MODE ACTIVE</div>
        <h2>Retraining Dashboard</h2>
        <p>Smart filtering enabled for large files.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Analyze & Group Cohorts</button>
        </form>
        <div class="info">
            <strong>What's New:</strong><br>
            • <b>Auto-Filter:</b> Automatically ignores text columns like 'question_id' to prevent hanging.<br>
            • <b>Error Logic:</b> Sums Rubric 0 and 1 for retraining focus.<br>
            • <b>Cohort Logic:</b> Groups users based on their primary mistake.
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
        # Load data (No skiprows needed for this specific file)
        df = pd.read_csv(file)
        
        # 1. Robust ID Identification
        user_col = 'annotator_id'
        if user_col not in df.columns:
            # Fallback: find column with 'id' or 'user' in name
            match = [c for c in df.columns if any(x in str(c).lower() for x in ['id', 'user', 'soul'])]
            target_col = match[0] if match else df.columns[0]
            df.rename(columns={target_col: user_col}, inplace=True)
        
        df[user_col] = df[user_col].astype(str).str.strip()
        
        # 2. SMART FILTERING: Identify only numeric rubric columns
        # We only want columns that have 0, 1, or 2
        rubric_cols = []
        for col in df.columns:
            if col == user_col: continue
            if df[col].dtype in ['int64', 'float64']:
                # Ensure it's not a high-cardinality column like 'task_number'
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) <= 5: # Rubrics typically only have 3-5 values
                    rubric_cols.append(col)

        # 3. Generate Pivot & Error Summation
        unique_users = df[user_col].unique()
        result = pd.DataFrame({user_col: unique_users})

        for col in rubric_cols:
            # Pivot only the 0, 1, 2 values
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            
            # Sum Rubric 0 and 1 (Mistakes)
            r0 = counts[0] if 0 in counts.columns else 0
            r1 = counts[1] if 1 in counts.columns else 0
            
            # Map back to result
            result[f"{col}_total_mistakes"] = result[user_col].map(r0 + r1).fillna(0)

        # 4. Global Metrics & Cohorts
        mistake_cols = [c for c in result.columns if c.endswith('_total_mistakes')]
        result['overall_total_errors'] = result[mistake_cols].sum(axis=1)

        def assign_cohort(row):
            if row['overall_total_errors'] == 0:
                return "Cohort: Top Performers"
            max_err_col = row[mistake_cols].idxmax()
            clean_name = max_err_col.replace('_total_mistakes', '').replace('_', ' ').title()
            return f"Retraining: {clean_label} Focus" if 'clean_label' in locals() else f"Cohort: {clean_name}"

        result['cohort_group'] = result.apply(assign_cohort, axis=1)

        # Final Cleaning
        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = result[c].astype(int)

        # 5. Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="retraining_analysis.csv")

    except Exception as e:
        import traceback
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
