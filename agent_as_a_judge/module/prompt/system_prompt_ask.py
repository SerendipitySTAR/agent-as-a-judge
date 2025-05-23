def get_ask_system_prompt(language="en"): # Standardize to "en"

    if language == "en":
        return """
You are a knowledgeable assistant capable of answering user queries clearly and accurately.
Your goal is to respond to the user input provided, using relevant project information and context where necessary.
        """
    elif language == "zh":
        return """
[[ZH_PLACEHOLDER: You are a knowledgeable assistant capable of answering user queries clearly and accurately.
Your goal is to respond to the user input provided, using relevant project information and context where necessary.]]
        """
    else:
        raise NotImplementedError(f"The language '{language}' is not supported.")
