from .prompt_wiki_overview import get_overview_prompt
from .prompt_wiki_architecture import get_architecture_prompt
from .prompt_wiki_diagram import get_diagram_prompt
from .prompt_wiki_component_analysis import get_component_analysis_prompt
from .prompt_wiki_component_detail import get_component_detail_prompt
from .prompt_wiki_usage import get_usage_prompt
from .prompt_wiki_installation import get_installation_prompt
from .prompt_wiki_advanced import get_advanced_topics_prompt
from .prompt_wiki_examples import get_examples_prompt
from .prompt_code_quality import get_code_quality_prompt # New import

__all__ = [
    "get_overview_prompt",
    "get_architecture_prompt",
    "get_diagram_prompt",
    "get_component_analysis_prompt",
    "get_component_detail_prompt",
    "get_usage_prompt",
    "get_installation_prompt",
    "get_advanced_topics_prompt",
    "get_examples_prompt",
    "get_code_quality_prompt", # Added to __all__
]
