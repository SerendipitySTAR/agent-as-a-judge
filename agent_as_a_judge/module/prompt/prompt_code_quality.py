def get_code_quality_prompt(code_snippet: str, file_path: str = "unknown_file", language: str = "en") -> str:
    """
    Generates a prompt for an LLM to assess the quality of a given code snippet.
    """
    
    english_prompt = f"""
Analyze the following code snippet from the file '{file_path}' for basic code quality.
Provide your assessment in Markdown format, covering these aspects:

### Code Quality Assessment for {file_path}

#### 1. Complexity Analysis:
(Briefly describe code complexity, readability, and maintainability. For example, are there deeply nested structures, very long functions, or is it generally easy to follow?)

#### 2. Code Duplication:
(Comment on any apparent code duplication within this snippet. If the snippet is too small to judge, state that. If the structure suggests potential duplication with other parts of the codebase, mention that possibility.)

#### 3. Style Consistency:
(Observe adherence to common styling conventions for the likely language of the code, e.g., naming conventions for variables and functions, spacing, indentation. Be general if the language is not obvious.)

#### 4. Potential Bugs & Anti-patterns:
(List any potential bugs, error handling issues (e.g., unhandled exceptions, empty catch blocks), resource management problems (e.g., unclosed files/connections), or common anti-patterns observed.)

#### 5. Refactoring Recommendations:
(Suggest specific, actionable improvements or adherence to best practices. For example, suggest renaming variables for clarity, breaking down complex functions, or improving error handling.)

---
Code Snippet:
```
{code_snippet}
```
---
Please be concise and provide actionable feedback. Focus on clear, impactful observations.
"""

    if language == "en":
        return english_prompt
    elif language == "zh":
        # Using a more direct translation for the placeholder instruction
        return f"""[[ZH_PLACEHOLDER:
对来自文件 '{file_path}' 的以下代码片段进行基本代码质量分析。
请使用 Markdown 格式提供您的评估，涵盖以下方面：

### {file_path} 的代码质量评估

#### 1. 复杂度分析：
（简要描述代码的复杂度、可读性和可维护性。例如，是否存在深度嵌套的结构、过长的函数，或者代码是否通常易于理解？）

#### 2. 代码重复：
（评论此代码片段中任何明显的代码重复。如果片段太小无法判断，请说明。如果结构表明可能与代码库的其他部分存在重复，请提及这种可能性。）

#### 3. 风格一致性：
（观察代码是否遵循了其可能语言的常见风格约定，例如变量和函数的命名约定、间距、缩进。如果语言不明显，请进行概括性评论。）

#### 4. 潜在错误和反模式：
（列出任何观察到的潜在错误、错误处理问题（例如，未处理的异常、空的 catch 块）、资源管理问题（例如，未关闭的文件/连接）或常见的反模式。）

#### 5. 重构建议：
（提出具体的、可操作的改进建议或遵循最佳实践的建议。例如，建议为清晰起见重命名变量，分解复杂函数或改进错误处理。）

---
代码片段：
```
{code_snippet}
```
---
请保持简洁并提供可操作的反馈。专注于清晰且有影响力的观察结果。
]]
"""
    else:
        # Default to English if language is not supported, or raise error
        # For now, let's default to English with a warning, or raise error as per original plan.
        # raise NotImplementedError(f"Language '{language}' is not supported for the code quality prompt.")
        logging.warning(f"Language '{language}' not explicitly supported for code quality prompt, defaulting to English.")
        return english_prompt
