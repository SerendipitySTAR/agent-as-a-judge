def get_planning_prompt(criteria: str, language: str = "en") -> str:
    """
    Returns the LLM prompt to generate a step-by-step plan for evaluating or resolving the given criteria.
    The prompt includes demonstrations to guide the LLM in creating effective plans without repeating the action descriptions.
    """
    
    english_prompt = f"""
    You are tasked with generating a list of actions to evaluate or resolve the following requirement. 
    Select only the necessary actions and arrange them in a logical order to systematically collect evidence and verify whether the requirement is satisfied.

    Requirement: "{criteria}"

    Here are some examples of how to create a plan:

    Example 1:
    Requirement: "The system must generate a summary report saved as `output/report.txt`."
    Plan:
    - [Locate]: Locate the `output/report.txt` file in the workspace.
    - [Read]: Read the contents of the `report.txt` file to verify it contains the summary report.
    - [Search]: Search the codebase for any functions or methods responsible for generating `report.txt`.

    Example 2:
    Requirement: "The machine learning model must be trained and saved as `results/model.pkl`."
    Plan:
    - [Locate]: Locate `results/model.pkl` in the workspace.
    - [Search]: Search for the model training code in the source files.
    - [Read]: Read the model training code to verify it aligns with the specified requirement.
    - [Trajectory]: Analyze the historical development of the model training process to understand any prior modifications.

    Now, generate a step-by-step plan for the following requirement:

    Requirement: "{criteria}"

    Response:
    """

    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"""
[[ZH_PLACEHOLDER:
{english_prompt}
]]
"""
    else:
        raise NotImplementedError(f"The language '{language}' is not supported for the planning prompt.")
