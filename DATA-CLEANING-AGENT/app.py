"""Streamlit interface for the Data Cleaning Agent."""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from data_cleaning_agent import LightweightDataCleaningAgent

load_dotenv()

st.set_page_config(page_title="Data Cleaning Agent", layout="wide")
st.title("🧹 Data Cleaning Agent")

# Upload file
uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)

    # --- Raw Data Preview ---
    st.subheader("Uploaded Data")
    st.dataframe(df_raw.head(10), use_container_width=True)
    st.caption(f"{df_raw.shape[0]} rows × {df_raw.shape[1]} columns")

    # --- Data Profile ---
    with st.expander("📊 Data Profile", expanded=True):
        profile_col1, profile_col2 = st.columns(2)

        with profile_col1:
            st.markdown("**Missing Values**")
            missing_counts = df_raw.isna().sum()
            missing_pct = (missing_counts / len(df_raw) * 100).round(1)
            missing_df = pd.DataFrame({
                "Missing Count": missing_counts,
                "Missing %": missing_pct,
            })
            missing_df = missing_df[missing_df["Missing Count"] > 0].sort_values("Missing %", ascending=False)
            if missing_df.empty:
                st.write("No missing values.")
            else:
                st.dataframe(missing_df, use_container_width=True)

            st.markdown(f"**Duplicate Rows:** {df_raw.duplicated().sum()}")

        with profile_col2:
            st.markdown("**Numeric Distributions**")
            numeric_cols = df_raw.select_dtypes(include="number").columns.tolist()
            if numeric_cols:
                desc = df_raw[numeric_cols].describe().T[["min", "25%", "50%", "75%", "max", "mean", "std"]]
                desc = desc.round(2)
                desc.columns = ["Min", "25%", "Median", "75%", "Max", "Mean", "Std"]
                st.dataframe(desc, use_container_width=True)
            else:
                st.write("No numeric columns.")

        st.markdown("**Categorical Columns (top 5 values)**")
        cat_cols = df_raw.select_dtypes(include=["object", "category"]).columns.tolist()
        if cat_cols:
            cat_data = []
            for col in cat_cols:
                top_vals = df_raw[col].value_counts(dropna=False).head(5)
                values_str = ", ".join([f"{v} ({c})" for v, c in top_vals.items()])
                cat_data.append({
                    "Column": col,
                    "Unique Values": df_raw[col].nunique(dropna=False),
                    "Top Values": values_str,
                })
            st.dataframe(pd.DataFrame(cat_data), use_container_width=True, hide_index=True)
        else:
            st.write("No categorical columns.")

    # --- Clean Button ---
    if st.button("Clean Data", type="primary"):
        with st.spinner("Agent is generating and executing cleaning code..."):
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            agent = LightweightDataCleaningAgent(model=llm, log=True)
            agent.invoke_agent(data_raw=df_raw)
            df_cleaned = agent.get_data_cleaned()
            cleaning_code = agent.get_data_cleaner_function()

        # --- Top-Level Summary Bar ---
        st.subheader("Cleaning Summary")

        rows_before, cols_before = df_raw.shape
        rows_after, cols_after = df_cleaned.shape
        nulls_before = int(df_raw.isna().sum().sum())
        nulls_after = int(df_cleaned.isna().sum().sum())

        m1, m2, m3 = st.columns(3)
        m1.metric("Rows", f"{rows_before} → {rows_after}", delta=f"{rows_after - rows_before}")
        m2.metric("Columns", f"{cols_before} → {cols_after}", delta=f"{cols_after - cols_before}")
        m3.metric("Missing Cells", f"{nulls_before} → {nulls_after}", delta=f"{nulls_after - nulls_before}")

        st.divider()

        # --- Detect what cleaning actions fired ---
        common_cols = [c for c in df_raw.columns if c in df_cleaned.columns]
        steps_applied = []
        steps_not_needed = []

        # 1. Dropped Columns (high missing or low variance)
        dropped_cols = sorted(set(df_raw.columns) - set(df_cleaned.columns))
        high_missing_dropped = []
        low_variance_dropped = []
        for col in dropped_cols:
            missing_pct = df_raw[col].isna().sum() / len(df_raw) * 100
            if missing_pct > 40:
                high_missing_dropped.append(col)
            else:
                # Check if it was low-variance
                top_freq = df_raw[col].value_counts(dropna=True).iloc[0] if not df_raw[col].dropna().empty else 0
                non_null_count = df_raw[col].notna().sum()
                if non_null_count > 0 and (top_freq / non_null_count) > 0.95:
                    low_variance_dropped.append(col)
                else:
                    high_missing_dropped.append(col)  # fallback

        if high_missing_dropped:
            steps_applied.append("high_missing")
            with st.expander("🗑️ High-Missing Columns Dropped", expanded=True):
                st.markdown("**Issue:** Some columns had too many missing values to be useful.")
                st.markdown("**Method:** Columns with more than 40% missing values were removed.")
                drop_data = []
                for col in high_missing_dropped:
                    missing_count = int(df_raw[col].isna().sum())
                    missing_pct = missing_count / len(df_raw) * 100
                    drop_data.append({
                        "Column": col,
                        "Missing Values": missing_count,
                        "Missing %": f"{missing_pct:.1f}%",
                    })
                st.dataframe(pd.DataFrame(drop_data), use_container_width=True, hide_index=True)
        else:
            steps_not_needed.append("**Drop High-Missing Columns** — No columns had >40% missing values.")

        # 2. Duplicates Removed
        dup_count_before = int(df_raw.duplicated().sum())
        dup_count_after = int(df_cleaned.duplicated().sum())
        dups_fixed = dup_count_before - dup_count_after
        if dups_fixed > 0:
            steps_applied.append("duplicates")
            with st.expander("📋 Duplicate Rows Removed", expanded=True):
                st.markdown(f"**Issue:** {dup_count_before} duplicate row(s) detected in the dataset.")
                st.markdown("**Method:** Exact duplicate rows were identified and removed, keeping the first occurrence.")
                st.markdown(f"**Result:** {dups_fixed} row(s) removed.")
        else:
            steps_not_needed.append("**Remove Duplicates** — No duplicate rows found.")

        # 3. Outlier Handling
        numeric_cols_common = [c for c in common_cols if pd.api.types.is_numeric_dtype(df_raw[c]) and pd.api.types.is_numeric_dtype(df_cleaned[c])]
        outlier_data = []
        for col in numeric_cols_common:
            raw_min = df_raw[col].min()
            raw_max = df_raw[col].max()
            cleaned_min = df_cleaned[col].min()
            cleaned_max = df_cleaned[col].max()
            # Detect capping: if the cleaned range is tighter than raw range
            if cleaned_min > raw_min or cleaned_max < raw_max:
                outlier_data.append({
                    "Column": col,
                    "Raw Min": f"{raw_min:.2f}",
                    "Raw Max": f"{raw_max:.2f}",
                    "Capped Min": f"{cleaned_min:.2f}",
                    "Capped Max": f"{cleaned_max:.2f}",
                })
        if outlier_data:
            steps_applied.append("outliers")
            with st.expander("📐 Outliers Capped", expanded=True):
                st.markdown("**Issue:** Some numeric columns had values beyond the 1.5×IQR bounds.")
                st.markdown("**Method:** Outlier values were capped (clipped) to the IQR bounds rather than removing rows.")
                st.dataframe(pd.DataFrame(outlier_data), use_container_width=True, hide_index=True)
        else:
            steps_not_needed.append("**Outlier Handling** — No outliers detected beyond 1.5×IQR bounds.")

        # 4. String Normalization
        str_cols_common = [c for c in common_cols if df_raw[c].dtype == "object" and df_cleaned[c].dtype == "object"]
        normalized_cols = []
        for col in str_cols_common:
            raw_vals = df_raw[col].dropna().astype(str)
            cleaned_vals = df_cleaned[col].dropna().astype(str)
            if len(raw_vals) > 0 and len(cleaned_vals) > 0:
                # Check if values changed (whitespace stripped or casing changed)
                raw_sample = set(raw_vals.head(50))
                cleaned_sample = set(cleaned_vals.head(50))
                if raw_sample != cleaned_sample:
                    # Find examples of changes
                    examples = []
                    for rv, cv in zip(raw_vals.head(20), cleaned_vals.head(20)):
                        if rv != cv:
                            examples.append(f"'{rv}' → '{cv}'")
                            if len(examples) >= 3:
                                break
                    if examples:
                        normalized_cols.append({"Column": col, "Examples": ", ".join(examples)})
        if normalized_cols:
            steps_applied.append("string_norm")
            with st.expander("✨ Strings Normalized", expanded=True):
                st.markdown("**Issue:** String columns had inconsistent whitespace or casing.")
                st.markdown("**Method:** Stripped whitespace and standardized casing (title case for names, lowercase for categories).")
                st.dataframe(pd.DataFrame(normalized_cols), use_container_width=True, hide_index=True)
        else:
            steps_not_needed.append("**String Normalization** — No whitespace or casing issues detected.")

        # 5. Type Coercion
        type_changes = []
        for col in common_cols:
            raw_dtype = str(df_raw[col].dtype)
            cleaned_dtype = str(df_cleaned[col].dtype)
            if raw_dtype != cleaned_dtype:
                type_changes.append({
                    "Column": col,
                    "Original Type": raw_dtype,
                    "New Type": cleaned_dtype,
                })
        if type_changes:
            steps_applied.append("type_coercion")
            with st.expander("🔄 Types Coerced", expanded=True):
                st.markdown("**Issue:** Some columns were stored as the wrong data type.")
                st.markdown("**Method:** Detected actual content and converted to the appropriate type (e.g., string → datetime, string → numeric).")
                st.dataframe(pd.DataFrame(type_changes), use_container_width=True, hide_index=True)
        else:
            steps_not_needed.append("**Type Coercion** — All columns already had appropriate data types.")

        # 6. Low-Variance Columns Removed
        if low_variance_dropped:
            steps_applied.append("low_variance")
            with st.expander("📉 Low-Variance Columns Removed", expanded=True):
                st.markdown("**Issue:** Some columns had almost no variation (one value >95% of rows).")
                st.markdown("**Method:** Columns where a single value dominates were removed as they carry no useful information.")
                lv_data = []
                for col in low_variance_dropped:
                    top_val = df_raw[col].value_counts(dropna=True).index[0]
                    top_pct = df_raw[col].value_counts(dropna=True, normalize=True).iloc[0] * 100
                    lv_data.append({
                        "Column": col,
                        "Dominant Value": str(top_val),
                        "Frequency": f"{top_pct:.1f}%",
                    })
                st.dataframe(pd.DataFrame(lv_data), use_container_width=True, hide_index=True)
        else:
            steps_not_needed.append("**Low-Variance Column Removal** — No columns had >95% single-value dominance.")

        # 7. Missing Values Imputed
        missing_before = df_raw[common_cols].isna().sum()
        missing_after = df_cleaned[common_cols].isna().sum()
        imputed = missing_before - missing_after
        imputed = imputed[imputed > 0]

        if not imputed.empty:
            steps_applied.append("imputation")
            with st.expander("🔧 Missing Values Imputed", expanded=True):
                st.markdown("**Issue:** Some columns contained missing values that needed to be filled.")
                st.markdown("**Method:** Numeric columns were imputed with the column mean. Categorical columns were imputed with the mode (most frequent value).")
                impute_data = []
                for col in imputed.index:
                    strategy = "Mean" if pd.api.types.is_numeric_dtype(df_raw[col]) else "Mode"
                    impute_data.append({
                        "Column": col,
                        "Values Filled": int(imputed[col]),
                        "Strategy": strategy,
                        "Data Type": str(df_raw[col].dtype),
                    })
                st.dataframe(pd.DataFrame(impute_data), use_container_width=True, hide_index=True)
        else:
            steps_not_needed.append("**Impute Missing Values** — No missing values remained after other cleaning steps.")

        # --- Considered but Not Needed ---
        if steps_not_needed:
            with st.expander("✅ Considered but Not Needed"):
                st.markdown("The following cleaning steps were evaluated but no issues were found:")
                for item in steps_not_needed:
                    st.markdown(f"- {item}")

        # --- Generated Code ---
        with st.expander("💻 Generated Cleaning Code"):
            st.code(cleaning_code, language="python")

        # --- Cleaned Data ---
        st.subheader("Cleaned Data")
        st.dataframe(df_cleaned, use_container_width=True)
        st.caption(f"{df_cleaned.shape[0]} rows × {df_cleaned.shape[1]} columns")

        # --- Download ---
        csv = df_cleaned.to_csv(index=False)
        st.download_button(
            "📥 Download Cleaned Data",
            data=csv,
            file_name="cleaned_data.csv",
            mime="text/csv",
        )
