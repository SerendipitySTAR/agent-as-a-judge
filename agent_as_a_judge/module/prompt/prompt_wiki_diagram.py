def get_diagram_prompt(language: str = "en") -> str:
    english_prompt = """
Create three high-level architectural diagrams using mermaid syntax:

1. A system overview diagram showing the main components and their relationships
2. A workflow diagram showing the main process flows
3. A detailed component relationship diagram

Make sure the diagrams are specific to this codebase, using actual component names from the code.
Add brief explanations for each diagram to help users understand what they're seeing.

Use the proper mermaid syntax wrapped in ```mermaid blocks.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for diagram prompt.")
