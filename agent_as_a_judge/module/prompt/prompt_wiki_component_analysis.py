def get_component_analysis_prompt(language: str = "en") -> str:
    english_prompt = """
Provide a comprehensive analysis of all key components in this codebase. For each component:

* Name of the component
* Purpose and main responsibility
* How it interacts with other components
* Design patterns or techniques used
* Key characteristics (stateful/stateless, etc.)
* File paths that implement this component

Create a table with Component names and their descriptions.
Organize components by logical groupings or layers if appropriate.

IMPORTANT: When describing components in the table, use natural language sentences 
rather than Markdown formatting. Avoid using bullet points, code formatting, or other 
Markdown syntax in the description column.

For example, instead of:
"- Handles data **processing**. \n- Uses `singleton` pattern."

Write:
"Handles data processing. Uses singleton pattern. Provides utility functions for transforming inputs."

For each component, explain not just what it does, but why it exists and how it fits into the larger system.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for component analysis prompt.")
