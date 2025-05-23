def get_ask_prompt(question: str, evidence: str, language: str = "en") -> str:

    if language == "en":
        return f"""
Provided below is relevant information about the project or context:
{evidence}

Kindly respond to the following user input:
{question}

As per the guidelines, provide a comprehensive answer referencing specific elements from the provided information where applicable.
    """
    elif language == "zh":
        return f"""
[[ZH_PLACEHOLDER: Provided below is relevant information about the project or context:
{evidence}

Kindly respond to the following user input:
{question}

As per the guidelines, provide a comprehensive answer referencing specific elements from the provided information where applicable.]]
    """
    else:
        raise NotImplementedError(f"The language '{language}' is not supported for the ask prompt.")
