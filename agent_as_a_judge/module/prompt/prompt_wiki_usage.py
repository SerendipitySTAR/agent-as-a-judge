def get_usage_prompt(language: str = "en") -> str:
    english_prompt = """
Create a comprehensive usage guide for this repository. Include:

1. Getting started with basic examples
2. How to initialize and configure the system
3. Common usage patterns with code examples
4. Advanced usage scenarios with step-by-step instructions
5. Performance optimization tips
6. Best practices and recommended approaches
7. Include specific file paths or imports that users need to know about

Include at least 3-5 different code examples for different use cases.
Show both basic and advanced usage patterns.

Format your response as clear markdown with proper structure.
Be detailed but practical - focus on helping users accomplish real tasks with the code.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for usage prompt.")
