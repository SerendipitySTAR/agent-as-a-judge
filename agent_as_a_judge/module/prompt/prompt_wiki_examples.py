def get_examples_prompt(language: str = "en") -> str:
    english_prompt = """
Create a set of comprehensive examples and tutorials for this repository. Include:

1. A "Getting Started" tutorial for absolute beginners
2. Basic examples showing core functionality
3. Advanced examples demonstrating more complex use cases
4. Common integration scenarios
5. End-to-end examples showing how to build something useful with this code

For each example/tutorial, provide:
- A clear explanation of what the example demonstrates
- Step-by-step instructions
- Complete code with comments
- Expected output or results

Format your response as clear markdown with proper headings and structure.
Make the examples practical and realistic - they should help users accomplish real tasks.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for examples prompt.")
