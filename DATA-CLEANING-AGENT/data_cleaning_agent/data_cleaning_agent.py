# Libraries
from typing import TypedDict
import os
import logging

import pandas as pd

from langchain.prompts import PromptTemplate
from langgraph.types import Checkpointer
from langgraph.graph import StateGraph, END

from .utils import (
    PythonOutputParser,
    get_dataframe_summary,
    execute_agent_code,
    fix_agent_code,
)

# Setup
logger = logging.getLogger(__name__)
AGENT_NAME = "lightweight_data_cleaning_agent"
LOG_PATH = os.path.join(os.getcwd(), "logs/")


class LightweightDataCleaningAgent:
    """
    LLM-powered agent that generates and executes Python code to clean pandas DataFrames.
    
    Uses an LLM to create data cleaning functions based on user instructions. The agent
    automatically retries with error correction if the generated code fails.
    
    Parameters
    ----------
    model : LLM
        Language model for generating cleaning code (e.g., ChatOpenAI).
    log : bool, default=False
        Whether to save generated code to a file.
    log_path : str, optional
        Directory for log files. Defaults to './logs/' if log=True and not specified.
    file_name : str, default="data_cleaner.py"
        Name of the log file when log=True.
    function_name : str, default="data_cleaner"
        Name of the generated cleaning function.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for saving agent state.
    
    Attributes
    ----------
    response : dict or None
        Stores the full response after invoke_agent() is called.
    """
    
    def __init__(
        self, 
        model, 
        log=False, 
        log_path=None, 
        file_name="data_cleaner.py", 
        function_name="data_cleaner",
        checkpointer: Checkpointer = None
    ):
        self.model = model
        self.log = log
        self.log_path = log_path
        self.file_name = file_name
        self.function_name = function_name
        self.checkpointer = checkpointer
        self.response = None
        # Build the LangGraph workflow with code generation, execution, and error fixing nodes
        self._compiled_graph = make_lightweight_data_cleaning_agent(
            model=model,
            log=log,
            log_path=log_path,
            file_name=file_name,
            function_name=function_name,
            checkpointer=checkpointer
        )
    
    def invoke_agent(self, data_raw: pd.DataFrame, user_instructions: str=None, max_retries:int=3, retry_count:int=0, **kwargs):
        """
        Generate and execute data cleaning code on the provided DataFrame.
        
        Parameters
        ----------
        data_raw : pd.DataFrame
            Raw dataset to clean.
        user_instructions : str, optional
            Custom cleaning instructions. If None, applies default cleaning steps:
            removing columns with >40% missing values, imputing missing values,
            and removing duplicates.
        max_retries : int, default=3
            Maximum number of retry attempts if generated code fails.
        retry_count : int, default=0
            Starting retry count (typically left at 0).
        **kwargs
            Additional arguments passed to the underlying graph invoke method.
        
        Returns
        -------
        None
            Results are stored in self.response and accessed via getter methods.
        """
        response = self._compiled_graph.invoke({
            "user_instructions": user_instructions,
            "data_raw": data_raw.to_dict(),
            "max_retries": max_retries,
            "retry_count": retry_count,
        }, **kwargs)
        self.response = response  # Store full workflow response for getter methods
        return None
    
    def get_data_cleaned(self):
        """
        Retrieves the cleaned data stored after running invoke_agent.
        """
        if self.response:
            return pd.DataFrame(self.response.get("data_cleaned"))
        
    def get_data_raw(self):
        """
        Retrieves the raw data.
        """
        if self.response:
            return pd.DataFrame(self.response.get("data_raw"))
    
    def get_data_cleaner_function(self):
        """
        Retrieves the agent's cleaning function code.
        """
        if self.response:
            return self.response.get("data_cleaner_function")


# Agent Factory Function

def make_lightweight_data_cleaning_agent(
    model, 
    log=False, 
    log_path=None, 
    file_name="data_cleaner.py",
    function_name="data_cleaner",
    checkpointer: Checkpointer = None
):
    """
    Factory function that creates a compiled LangGraph workflow for data cleaning.
    
    Builds a state graph with three nodes: code generation, execution, and error fixing.
    The workflow automatically retries with corrections if generated code fails.
    
    Parameters
    ----------
    model : LLM
        Language model for generating cleaning code.
    log : bool, default=False
        Whether to save generated code to a file.
    log_path : str, optional
        Directory for log files. Defaults to './logs/' if log=True and not specified.
    file_name : str, default="data_cleaner.py"
        Name of the log file when log=True.
    function_name : str, default="data_cleaner"
        Name of the generated cleaning function.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for saving workflow state.
    
    Returns
    -------
    CompiledStateGraph
        Compiled LangGraph workflow ready to process cleaning requests.
    """
    # Setup Log Directory
    if log:
        if log_path is None:
            log_path = LOG_PATH
        if not os.path.exists(log_path):
            os.makedirs(log_path)    

    # Define state schema for the workflow graph
    class GraphState(TypedDict):
        user_instructions: str
        data_raw: dict
        data_cleaned: dict
        data_cleaner_function: str
        data_cleaner_function_path: str
        data_cleaner_function_name: str
        data_cleaner_error: str
        max_retries: int
        retry_count: int

    
    def create_data_cleaner_code(state: GraphState):
        """
        Generate the data cleaning code based on user instructions.
        """
        logger.info("Creating data cleaner code")
        
        data_raw = state.get("data_raw")
        df = pd.DataFrame.from_dict(data_raw)

        dataset_summary = get_dataframe_summary(df)
        
        # TODO: Expand this prompt with more detailed cleaning instructions
        data_cleaning_prompt = PromptTemplate(
            template="""
You are a Data Cleaning Agent. Create a {function_name}() function to clean the data.

Evaluate each of the following cleaning steps based on the dataset summary below.
Apply a step ONLY if the data shows it is needed. Skip steps that don't apply.

Cleaning Checklist:
1. Drop High-Missing Columns: Remove columns with more than 40% missing values.
2. Remove Duplicates: Drop exact duplicate rows, keeping the first occurrence.
3. Outlier Handling: For numeric columns with outliers beyond 1.5×IQR bounds (shown in summary), cap values at the IQR bounds (lower_bound and upper_bound). Do NOT remove rows.
4. String Normalization: For string/object columns, strip leading/trailing whitespace. Apply title case for name-like columns, lowercase for other categorical columns.
5. Type Coercion: If a string column contains values that look like dates (e.g., '2024-01-01', 'Jan 5 2023'), convert to datetime. If a string column contains numeric-looking values (e.g., '123', '45.6'), convert to the appropriate numeric type.
6. Low-Variance Column Removal: Remove columns where a single value accounts for more than 95% of non-null rows (these carry no useful information).
7. Impute Missing Values: After all other steps, impute remaining missing values — use column mean for numeric columns, mode (most frequent value) for categorical columns.

User Instructions (override or extend the above if provided):
{user_instructions}

Dataset Summary:
{all_datasets_summary}

Return Python code in ```python``` format with a single function:

def {function_name}(data_raw):
    import pandas as pd
    import numpy as np
    # Your cleaning code here
    return data_cleaned

Important:
- Only apply steps where the dataset summary shows an actual issue.
- Ensure fit_transform() outputs are flattened with .ravel() when assigning to DataFrame columns.
- Add a brief inline comment before each cleaning step explaining what it does and why.
""",
            input_variables=["user_instructions", "all_datasets_summary", "function_name"]
        )

        data_cleaning_agent = data_cleaning_prompt | model | PythonOutputParser()
        
        response = data_cleaning_agent.invoke({
            "user_instructions": state.get("user_instructions") or "Follow the basic cleaning steps.",
            "all_datasets_summary": dataset_summary,
            "function_name": function_name
        })
        
        # Simple logging if enabled
        file_path = None
        if log:
            file_path = os.path.join(log_path, file_name)
            with open(file_path, 'w') as f:
                f.write(response)
            logger.info(f"Code saved to: {file_path}")
   
        return {
            "data_cleaner_function": response,
            "data_cleaner_function_path": file_path,
            "data_cleaner_function_name": function_name,
        }
        
    def execute_data_cleaner_code(state):
        """
        Execute the generated cleaning code on the data.
        """
        return execute_agent_code(
            state=state,
            data_key="data_raw",
            result_key="data_cleaned",
            error_key="data_cleaner_error",
            code_snippet_key="data_cleaner_function",
            agent_function_name=state.get("data_cleaner_function_name")
        )
        
    def fix_data_cleaner_code(state: GraphState):
        """
        Fix errors in the generated data cleaning code.
        """
        data_cleaner_prompt = """
        You are a Data Cleaning Agent. Fix the broken {function_name}() function.
        
        Return Python code in ```python``` format with the corrected function definition.
        
        Broken code: 
        {code_snippet}

        Error:
        {error}
        """

        return fix_agent_code(
            state=state,
            code_snippet_key="data_cleaner_function",
            error_key="data_cleaner_error",
            llm=model,  
            prompt_template=data_cleaner_prompt,
            function_name=state.get("data_cleaner_function_name"),
        )

    # Build the workflow graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("create_data_cleaner_code", create_data_cleaner_code)
    workflow.add_node("execute_data_cleaner_code", execute_data_cleaner_code)
    workflow.add_node("fix_data_cleaner_code", fix_data_cleaner_code)
    
    # Set entry point
    workflow.set_entry_point("create_data_cleaner_code")
    
    # Add edges
    workflow.add_edge("create_data_cleaner_code", "execute_data_cleaner_code")
    workflow.add_edge("fix_data_cleaner_code", "execute_data_cleaner_code")
    
    # Conditional routing: retry with fixes if error occurs and retries remain
    def should_retry(state):
        has_error = state.get("data_cleaner_error") is not None
        can_retry = (
            state.get("retry_count") is not None
            and state.get("max_retries") is not None
            and state["retry_count"] < state["max_retries"]
        )
        return "fix_code" if (has_error and can_retry) else "end"
    
    workflow.add_conditional_edges(
        "execute_data_cleaner_code",
        should_retry,
        {
            "fix_code": "fix_data_cleaner_code",
            "end": END,
        },
    )
    
    # Compile the workflow
    app = workflow.compile(checkpointer=checkpointer, name=AGENT_NAME)
    
    return app
