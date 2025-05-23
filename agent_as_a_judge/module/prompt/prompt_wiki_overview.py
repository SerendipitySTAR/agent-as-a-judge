def get_overview_prompt(language: str = "en") -> str:
    english_prompt = """
Provide a concise overview of this repository focused primarily on:

* Purpose and Scope: What is this project's main purpose?
* Core Features: What are the key features and capabilities?
* Target audience/users
* Main technologies or frameworks used

Extract this information directly from the README.md when possible, using the same structure and terminology.
Focus on being factual rather than interpretive.

Use short, direct headings without number prefixes. For example, use "Core Features" instead of "3. Core Features".
Keep explanations clear and direct. Format as clean markdown.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for overview prompt.")
