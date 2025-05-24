import yaml # PyYAML library
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any # Use Dict for older Python if needed

logger = logging.getLogger(__name__)

# Define a basic schema or expected structure for validation (optional but good)
# For now, we'll do basic structural checks.
# More advanced schema validation (e.g., with Pydantic or jsonschema) can be added later.

def _validate_section(section: Dict[str, Any], index: int) -> bool:
    if not isinstance(section, dict):
        logger.error(f"Config error: Section at index {index} is not a dictionary.")
        return False
    if "id" not in section or not isinstance(section["id"], str):
        logger.error(f"Config error: Section at index {index} missing or invalid 'id'. Found: {section.get('id')}")
        return False
    if "title" not in section or not isinstance(section["title"], str):
        logger.error(f"Config error: Section '{section.get('id', 'Unknown')}' missing or invalid 'title'. Found: {section.get('title')}")
        return False
    if "type" not in section or not isinstance(section["type"], str):
        logger.error(f"Config error: Section '{section.get('id', 'Unknown')}' missing or invalid 'type'. Found: {section.get('type')}")
        return False
    
    # Validate 'prompt' or 'prompt_file' for custom types
    if section["type"] == "custom":
        has_prompt = "prompt" in section and isinstance(section["prompt"], str)
        has_prompt_file = "prompt_file" in section and isinstance(section["prompt_file"], str)
        if not (has_prompt ^ has_prompt_file): # XOR: one and only one must be present
            logger.error(f"Config error: Custom section '{section['id']}' must have either 'prompt' or 'prompt_file', but not both or neither.")
            return False
    
    # Validate 'enabled' if present
    if "enabled" in section and not isinstance(section["enabled"], bool):
        logger.error(f"Config error: Section '{section['id']}' has invalid 'enabled' value (must be boolean). Found: {section['enabled']}")
        return False
        
    return True

def load_doc_config(config_path_str: Optional[str]) -> Optional[Dict[str, Any]]:
    actual_config_path: Optional[Path] = None

    if config_path_str:
        path_obj = Path(config_path_str)
        if path_obj.is_file():
            actual_config_path = path_obj
        else:
            logger.warning(f"Specified config file '{config_path_str}' not found. Trying default 'openwiki_config.yaml'.")
    
    if not actual_config_path:
        default_path = Path("openwiki_config.yaml") # Assumes it's in the current working directory / project root
        if default_path.is_file():
            logger.info("Using default 'openwiki_config.yaml' found in project root.")
            actual_config_path = default_path
        else:
            logger.info("No config file specified and default 'openwiki_config.yaml' not found. Proceeding with default document structure.")
            return None

    if not actual_config_path: # Should only happen if specified path was bad AND default not found
         return None

    try:
        with open(actual_config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if not isinstance(config_data, dict):
            logger.error(f"Config error: Root of '{actual_config_path}' is not a dictionary.")
            return None

        # Basic validation
        if "sections" not in config_data or not isinstance(config_data["sections"], list):
            logger.error(f"Config error: '{actual_config_path}' is missing 'sections' list or it's not a list.")
            return None

        validated_sections = []
        for i, section_conf in enumerate(config_data["sections"]):
            if not _validate_section(section_conf, i):
                # _validate_section logs the specific error
                logger.error(f"Invalid section configuration at index {i} in '{actual_config_path}'. Skipping this section.")
                continue # Skip invalid section
            
            # Resolve prompt_file to prompt content
            if section_conf.get("type") == "custom" and "prompt_file" in section_conf:
                prompt_file_path_str = section_conf["prompt_file"]
                # Try to resolve relative to config file's directory, then relative to CWD
                prompt_file_path = actual_config_path.parent / prompt_file_path_str
                if not prompt_file_path.is_file():
                    prompt_file_path = Path(prompt_file_path_str) # Try as CWD relative

                if prompt_file_path.is_file():
                    try:
                        with open(prompt_file_path, 'r', encoding='utf-8') as pf:
                            section_conf["prompt"] = pf.read()
                        del section_conf["prompt_file"] # Remove to avoid confusion
                    except Exception as e:
                        logger.error(f"Error reading prompt file '{prompt_file_path}' for section '{section_conf['id']}': {e}")
                        # Decide if this makes the section invalid or just proceeds without prompt
                        logger.warning(f"Section '{section_conf['id']}' will proceed without prompt content due to file read error.")
                        section_conf["prompt"] = "" # Or mark as invalid
                else:
                    logger.error(f"Prompt file '{prompt_file_path_str}' not found for section '{section_conf['id']}'. Searched relative to config and CWD.")
                    logger.warning(f"Section '{section_conf['id']}' will proceed without prompt content as prompt file was not found.")
                    section_conf["prompt"] = "" # Or mark as invalid
            
            # Set default for 'enabled' if not present
            if 'enabled' not in section_conf:
                section_conf['enabled'] = True
                
            validated_sections.append(section_conf)
        
        config_data["sections"] = validated_sections # Replace with validated (and potentially modified) sections
        
        if not config_data["sections"]: # If all sections were invalid
             logger.warning(f"All sections in '{actual_config_path}' were invalid or removed. Proceeding as if no config was loaded.")
             return None

        logger.info(f"Successfully loaded and validated document configuration from '{actual_config_path}'.")
        return config_data

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration file '{actual_config_path}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading configuration file '{actual_config_path}': {e}")
        return None
