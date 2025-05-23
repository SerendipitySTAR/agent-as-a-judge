def get_advanced_topics_prompt(language: str = "en") -> str:
    english_prompt = """
Provide documentation on advanced topics for this repository. Include:

* Performance optimization strategies
* Extending or customizing the system
* Internal architecture details
* Complex algorithms or techniques used
* Integration with other systems
* Scaling considerations
* Security considerations

Divide into clearly marked sections with short, direct headings (no number prefixes).
Include code examples where helpful.

Format as clean markdown with proper headings.
This should be technical content for experienced users.
"""
    if language == "en":
        return english_prompt
    elif language == "zh":
        return f"[[ZH_PLACEHOLDER:\n{english_prompt}\n]]"
    else:
        raise NotImplementedError(f"Language '{language}' is not supported for advanced topics prompt.")
