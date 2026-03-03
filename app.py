@app.route('/process', methods=['POST'])
def process():
    file = request.files.get('file')
    if not file: return "No file uploaded", 400

    try:
        # 1. Load data
        df = pd.read_csv(file)
        
        # 2. Identify and Clean Annotator ID
        user_col = 'annotator_id'
        if user_col not in df.columns:
            match = [c for c in df.columns if any(x in str(c).lower() for x in ['id', 'user', 'soul'])]
            target_col = match[0] if match else df.columns[0]
            df.rename(columns={target_col: user_col}, inplace=True)
        
        # FIX: Force lowercase and remove ALL whitespace to prevent "UserA" vs "usera" duplicates
        df[user_col] = df[user_col].astype(str).str.lower().str.strip()
        # Remove any rows where ID is 'nan' or empty
        df = df[df[user_col] != 'nan']

        # 3. Identify Rubric Columns (Numeric with few unique values)
        rubric_cols = []
        for col in df.columns:
            if col == user_col: continue
            if df[col].dtype in ['int64', 'float64']:
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) <= 5: 
                    rubric_cols.append(col)

        # 4. Generate Pivot with Forced Deduplication
        unique_users = sorted(df[user_col].unique())
        result = pd.DataFrame({user_col: unique_users})

        for col in rubric_cols:
            # Group by user and count values
            counts = df.groupby(user_col)[col].value_counts().unstack(fill_value=0)
            
            # Ensure 0, 1, and 2 columns exist and map them
            for val in [0, 1, 2]:
                col_name = f"{col}_{val}"
                if val in counts.columns:
                    result[col_name] = result[user_col].map(counts[val]).fillna(0)
                else:
                    result[col_name] = 0

        # 5. Global Metrics & Cohorts (Calculated on the merged data)
        mistake_cols = [c for c in result.columns if c.endswith('_0') or c.endswith('_1')]
        result['overall_total_errors'] = result[mistake_cols].sum(axis=1)

        def assign_cohort(row):
            if row['overall_total_errors'] == 0:
                return "Cohort: Top Performers"
            
            # Find the rubric with the most combined mistakes
            rubric_mistake_totals = {}
            for col in rubric_cols:
                rubric_mistake_totals[col] = row.get(f"{col}_0", 0) + row.get(f"{col}_1", 0)
            
            max_rubric = max(rubric_mistake_totals, key=rubric_mistake_totals.get)
            clean_name = max_rubric.replace('_', ' ').title()
            return f"Cohort: {clean_name} Retraining"

        result['cohort_group'] = result.apply(assign_cohort, axis=1)

        # 6. Final cleanup
        for c in result.columns:
            if c not in [user_col, 'cohort_group']:
                result[c] = result[c].astype(int)

        # Export
        output = io.BytesIO()
        result.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="deduplicated_report.csv")

    except Exception as e:
        return f"Error: {str(e)}", 500
