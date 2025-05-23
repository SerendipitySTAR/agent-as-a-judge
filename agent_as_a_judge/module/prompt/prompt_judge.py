def get_judge_prompt(criteria: str, evidence: str, language: str = "en") -> str:

    english_prompt_format = f"""
Provided below is relevant information about the project:
{evidence}

Kindly perform an evaluation of the following criteria:
{criteria}

As per the guidelines, respond with either <SATISFIED> or <UNSATISFIED>, followed by a concise justification that references specific elements from the project information, such as code snippets, data samples, or output results.
    """

    if language == "en":
        return english_prompt_format
    elif language == "zh":
        return f"""
[[ZH_PLACEHOLDER:
{english_prompt_format}
]]
    """
    else:
        raise NotImplementedError(f"The language '{language}' is not supported for the judge prompt.")
