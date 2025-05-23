def get_architecture_prompt(language: str = "en") -> str:
    english_prompt = """
Create a comprehensive architecture overview for this repository. Include:

* A high-level description of the system architecture
* Main components and their roles (as a bullet list with clear descriptions)
* Data flow between components
* External dependencies and integrations

Write in clear, concise language. Format each component description as:

* **Component Name**: Brief natural language description that explains its role and functionality.

DO NOT use markdown formatting inside the descriptions - they should be plain text sentences.
Avoid using technical jargon without explanation.
Use headings without numerical prefixes.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for architecture prompt.")
