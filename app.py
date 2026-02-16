import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Error & Cohort Tracker</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 500px; text-align: center; }
        .feature-tag { display: inline-block; background: #fff7ed; color: #9a3412; padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: bold; margin-bottom: 10px; border: 1px solid #ffedd5; }
        button { background: #1e293b; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="feature-tag">ERROR SUMMATION LOGIC ENABLED</div>
        <h2>Retraining Dashboard</h2>
        <p>Upload CSV to identify error counts and cohort groups.</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Analyze Mistakes</button>
        </form>
        <div class="info">
            <strong>Analysis Logic:</strong><br>
            • Ignores Rubric 2 (Correct).<br>
            • Calculates <b>Total_Mistakes</b> (Sum of Rubric 0 + Rubric 1).<br>
            • Assigns Cohorts based on the highest mistake category.
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
        
        # Identify original rubric/attribute columns
        attr_cols = [c for c in df.columns if c not in [user_col, target_col] and 'Unnamed' not in str(c)]

        # 2. Process User-Level Error Sums
        unique_users = df[user_col].unique()
        result = pd.DataFrame({user_col: unique_users})

        for col in attr_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Count occurrences per user
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            
            # Filter for Rubric 0 and Rubric 1 specifically
            r0 = counts[0] if 0 in counts.columns else 0
            r1 = counts[1] if 1 in counts.columns else 0
            
            # Create the Summation Column: Mistakes_In_Attribute
            result[f"{col}_total_mistakes"] = (r0 + r1).values if hasattr((r0 + r1), 'values') else (r0 + r1)

        # 3. Global Mistake Count
        mistake_cols = [c for c in result.columns if c.endswith('_total_mistakes')]
        result['overall_total_errors'] = result[mistake_cols].sum(axis=1)

        # 4. Cohort Assignment Logic
        def assign_cohort(row):
            if row['overall_total_errors'] == 0:
                return "Cohort: Proficient"
            
            # Find the attribute with the most errors
            max_error_col = row[mistake_cols].idxmax()
            clean_name = max_error_col.replace('_total_mistakes', '').replace('_', ' ').title()
            return f"Cohort: {clean_name} Retraining"

        result['cohort_group'] = result.apply(assign_cohort, axis=1)

        # Final Formatting
        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = result[c].astype(int)

        # 5. Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="retraining_cohorts.csv")

    except Exception as e:
        import traceback
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
