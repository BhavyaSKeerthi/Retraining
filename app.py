import os
import io
import pandas as pd
from flask import Flask, request, send_file, render_template_string

# CRITICAL: This defines 'app' so Render/Gunicorn can find it
app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Annotator Pro - Deduplicated</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; display: flex; justify-content: center; padding-top: 50px; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 480px; text-align: center; }
        button { background: #1e293b; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        .info { text-align: left; font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Retraining Dashboard</h2>
        <p>Deduplication & Detailed Scoring Active</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Generate Clean Report</button>
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
        df = pd.read_csv(file)
        
        # 1. Standardize ID and Remove Duplicates
        user_col = 'annotator_id'
        if user_col not in df.columns:
            match = [c for c in df.columns if any(x in str(c).lower() for x in ['id', 'user', 'soul'])]
            target_col = match[0] if match else df.columns[0]
            df.rename(columns={target_col: user_col}, inplace=True)
        
        # Force lowercase and strip to merge "User1" and "user1"
        df[user_col] = df[user_col].astype(str).str.lower().str.strip()
        df = df[df[user_col] != 'nan']

        # 2. Identify Rubric Columns
        rubric_cols = []
        for col in df.columns:
            if col == user_col: continue
            if df[col].dtype in ['int64', 'float64']:
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) <= 5: 
                    rubric_cols.append(col)

        # 3. Create Deduplicated Results
        unique_users = sorted(df[user_col].unique())
        result = pd.DataFrame({user_col: unique_users})

        for col in rubric_cols:
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            for val in [0, 1, 2]:
                col_name = f"{col}_{val}"
                if val in counts.columns:
                    result[col_name] = result[user_col].map(counts[val]).fillna(0)
                else:
                    result[col_name] = 0

        # 4. Metrics & Cohorts
        mistake_cols = [c for c in result.columns if c.endswith('_0') or c.endswith('_1')]
        result['overall_total_errors'] = result[mistake_cols].sum(axis=1)

        def assign_cohort(row):
            if row['overall_total_errors'] == 0: return "Cohort: Top Performers"
            # Find rubric with most mistakes (0s + 1s)
            err_map = {rc: row.get(f"{rc}_0", 0) + row.get(f"{rc}_1", 0) for rc in rubric_cols}
            max_rc = max(err_map, key=err_map.get)
            return f"Cohort: {max_rc.replace('_', ' ').title()} Retraining"

        result['cohort_group'] = result.apply(assign_cohort, axis=1)

        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = result[c].astype(int)

        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="final_report.csv")

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
