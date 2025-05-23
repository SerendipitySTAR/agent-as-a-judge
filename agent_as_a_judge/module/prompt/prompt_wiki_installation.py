def get_installation_prompt(language: str = "en") -> str:
    english_prompt = """
Provide detailed installation and setup instructions for this repository. Include:

1. Prerequisites and dependencies (libraries, tools, accounts, etc.)
2. Step-by-step installation process for different environments (development, production)
3. Configuration options and environment variables with examples
4. How to verify the installation was successful
5. Common installation problems and their solutions
6. Reference any setup files like requirements.txt, package.json, etc. with their exact paths

Include instructions for different operating systems if applicable.
If there are multiple installation methods, explain the benefits and drawbacks of each.

Format your response as clear markdown with proper headings and code blocks.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for installation prompt.")
