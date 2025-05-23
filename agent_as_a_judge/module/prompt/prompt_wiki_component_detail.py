def get_component_detail_prompt(component_name: str, language: str = "en") -> str:
    english_prompt_template = f"""
Provide detailed documentation for the '{component_name}' component:

1. What is its primary purpose and responsibility?
2. How is it implemented? Describe design patterns, algorithms, or techniques.
3. How do developers use or interact with it?
4. What are its key methods, classes, or interfaces?
5. What parameters or configuration options does it accept?
6. What are common usage scenarios?
7. What are potential pitfalls or gotchas when using this component?
8. What advanced features or optimizations does it offer?
9. Provide multiple code examples showing different usage patterns
10. In what file(s) is this component implemented? Provide exact file paths.

For methods, please format as:
- `method_name()`: Description of what the method does

For parameters, please format as:
- `parameter_name` (default_value): Description of the parameter

Be thorough and insightful - go beyond just describing what the code does and explain why it's designed this way.
"""
    if language == "en":
        return english_prompt_template
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER_COMPONENT_NAME:{component_name}:\n{english_prompt_template}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for component detail prompt.")
