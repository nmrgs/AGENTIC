# Utility functions for lightweight data cleaning agent

import re
import logging
import pandas as pd
from langchain_core.output_parsers import BaseOutputParser

logger = logging.getLogger(__name__)


class PythonOutputParser(BaseOutputParser):
    """Extract Python code from LLM responses."""
    
    def parse(self, text: str):
        """Extract code from ```python``` blocks or return text as-is."""
        python_code_match = re.search(r'```python(.*?)```', text, re.DOTALL)
        if python_code_match:
            return python_code_match.group(1).strip()
        return text


def get_dataframe_summary(df: pd.DataFrame) -> str:
    """
    Generate a detailed summary of a DataFrame for the LLM, including
    distributions for numeric columns and value counts for categorical columns.
    
    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to summarize.
    
    Returns
    -------
    str
        A text summary of the DataFrame.
    """
    num_rows, num_cols = df.shape

    # Column types
    column_types = "\n".join([f"  {col}: {dtype}" for col, dtype in df.dtypes.items()])

    # Missing values
    missing_stats = (df.isna().sum() / len(df) * 100).sort_values(ascending=False)
    missing_summary = "\n".join([f"  {col}: {val:.1f}%" for col, val in missing_stats.items()])

    # Duplicate rows
    dup_count = df.duplicated().sum()

    # Numeric column distributions with IQR and outlier info
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_summary_parts = []
    for col in numeric_cols:
        desc = df[col].describe()
        q1 = desc['25%']
        q3 = desc['75%']
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outlier_count = int(((df[col] < lower_bound) | (df[col] > upper_bound)).sum())
        numeric_summary_parts.append(
            f"  {col}: min={desc['min']:.2f}, 25%={q1:.2f}, "
            f"median={desc['50%']:.2f}, 75%={q3:.2f}, max={desc['max']:.2f}, "
            f"mean={desc['mean']:.2f}, std={desc['std']:.2f}, "
            f"IQR_bounds=[{lower_bound:.2f}, {upper_bound:.2f}], outliers={outlier_count}"
        )
    numeric_summary = "\n".join(numeric_summary_parts) if numeric_summary_parts else "  (none)"

    # Categorical column distributions (top 5 values)
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    categorical_summary_parts = []
    for col in categorical_cols:
        top_values = df[col].value_counts(dropna=False).head(5)
        values_str = ", ".join([f"{v}={c}" for v, c in top_values.items()])
        n_unique = df[col].nunique(dropna=False)
        categorical_summary_parts.append(f"  {col} ({n_unique} unique): {values_str}")
    categorical_summary = "\n".join(categorical_summary_parts) if categorical_summary_parts else "  (none)"

    # Sample rows
    sample = df.head(3).to_string(index=False)

    summary = f"""Dataset Summary:
----------------
Shape: {num_rows} rows × {num_cols} columns
Duplicate Rows: {dup_count}

Column Data Types:
{column_types}

Missing Value Percentage:
{missing_summary}

Numeric Column Distributions:
{numeric_summary}

Categorical Column Value Counts (top 5):
{categorical_summary}

Sample Rows (first 3):
{sample}"""

    return summary


def execute_agent_code(state, data_key, code_snippet_key, result_key, error_key, agent_function_name):
    """
    Execute the generated agent code on the data.
    
    Parameters
    ----------
    state : dict
        The current state containing data and code.
    data_key : str
        Key in state where the input data is stored.
    code_snippet_key : str
        Key in state where the generated code is stored.
    result_key : str
        Key to store the result in.
    error_key : str
        Key to store any error message in.
    agent_function_name : str
        Name of the function to execute from the generated code.
    
    Returns
    -------
    dict
        Dictionary with result and error keys.
    """
    logger.info("Executing agent code")
    
    data = state.get(data_key)
    agent_code = state.get(code_snippet_key)
    df = pd.DataFrame.from_dict(data)
    
    # Execute the LLM-generated code in isolated namespace
    # Note: exec() can be risky - only use with trusted LLM-generated code
    local_vars = {}
    global_vars = {}
    exec(agent_code, global_vars, local_vars)
    
    # Get the function from executed code
    agent_function = local_vars.get(agent_function_name)
    if not agent_function or not callable(agent_function):
        raise ValueError(f"Function '{agent_function_name}' not found in generated code.")
    
    # Run the function and handle errors
    agent_error = None
    result = None
    try:
        result = agent_function(df)
        if isinstance(result, pd.DataFrame):
            result = result.to_dict()
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        agent_error = f"An error occurred during data cleaning: {str(e)}"
    
    return {result_key: result, error_key: agent_error}


def fix_agent_code(state, code_snippet_key, error_key, llm, prompt_template, function_name, retry_count_key="retry_count"):
    """
    Fix errors in the generated agent code using the LLM.
    
    Parameters
    ----------
    state : dict
        The current state containing code and error information.
    code_snippet_key : str
        Key in state where the broken code is stored.
    error_key : str
        Key in state where the error message is stored.
    llm : LLM
        The language model to use for fixing the code.
    prompt_template : str
        Template for the fix prompt (should have {code_snippet}, {error}, {function_name} placeholders).
    function_name : str
        Name of the function being fixed.
    retry_count_key : str, optional
        Key in state for tracking retry count. Defaults to "retry_count".
    
    Returns
    -------
    dict
        Dictionary with updated code, cleared error, and incremented retry count.
    """
    logger.info("Fixing agent code")
    logger.debug(f"Retry count: {state.get(retry_count_key)}")
    
    code_snippet = state.get(code_snippet_key)
    error_message = state.get(error_key)
    
    # Create the fix prompt
    prompt = prompt_template.format(
        code_snippet=code_snippet,
        error=error_message,
        function_name=function_name,
    )
    
    # Get fixed code from LLM
    response = (llm | PythonOutputParser()).invoke(prompt)
    
    return {
        code_snippet_key: response,
        error_key: None,
        retry_count_key: state.get(retry_count_key) + 1
    }
