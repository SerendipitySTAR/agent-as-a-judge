#!/usr/bin/env python3
import os
import sys
import re
import argparse
import logging
import time
import json
import datetime
import tempfile
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse
from typing import Optional, Dict, List, Any 

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_as_a_judge.agent import JudgeAgent
from agent_as_a_judge.config import AgentConfig
from agent_as_a_judge.doc_config_utils import load_doc_config
from agent_as_a_judge.module.prompt import (
    get_overview_prompt,
    get_architecture_prompt,
    get_diagram_prompt,
    get_component_analysis_prompt,
    get_component_detail_prompt,
    get_usage_prompt,
    get_installation_prompt,
    get_advanced_topics_prompt,
    get_examples_prompt,
    get_code_quality_prompt 
)

# Default configuration for document sections
DEFAULT_SECTIONS_CONFIG: List[Dict[str, Any]] = [
    {"id": "overview", "title": "Repository Overview", "type": "overview", "enabled": True, "prompt_key": "get_overview_prompt"},
    {"id": "architecture", "title": "Architecture Overview", "type": "architecture", "enabled": True, "prompt_key": "get_architecture_prompt"},
    {"id": "diagrams", "title": "Architectural Diagrams", "type": "diagrams", "enabled": True, "prompt_key": "get_diagram_prompt"},
    {"id": "component_analysis", "title": "Key Components Analysis", "type": "component_analysis", "enabled": True, "prompt_key": "get_component_analysis_prompt"},
    {"id": "components", "title": "Component Details", "type": "components", "enabled": True, "prompt_key_detail": "get_component_detail_prompt"}, 
    {"id": "usage", "title": "Usage Guide", "type": "usage", "enabled": True, "prompt_key": "get_usage_prompt"},
    {"id": "installation", "title": "Installation Guide", "type": "installation", "enabled": True, "prompt_key": "get_installation_prompt"},
    {"id": "advanced_topics", "title": "Advanced Topics", "type": "advanced_topics", "enabled": True, "prompt_key": "get_advanced_topics_prompt"},
    {"id": "examples", "title": "Examples and Tutorials", "type": "examples", "enabled": True, "prompt_key": "get_examples_prompt"},
    {"id": "code_quality", "title": "Code Quality Assessment", "type": "code_quality", "enabled": True, "max_files_to_assess": 5}
]

PROMPT_FUNCTION_MAP = {
    "get_overview_prompt": get_overview_prompt,
    "get_architecture_prompt": get_architecture_prompt,
    "get_diagram_prompt": get_diagram_prompt,
    "get_component_analysis_prompt": get_component_analysis_prompt,
    "get_component_detail_prompt": get_component_detail_prompt,
    "get_usage_prompt": get_usage_prompt,
    "get_installation_prompt": get_installation_prompt,
    "get_advanced_topics_prompt": get_advanced_topics_prompt,
    "get_examples_prompt": get_examples_prompt,
}


def download_github_repo(repo_url, target_dir):
    logging.info(f"Downloading repository from {repo_url}")
    
    parsed_url = urlparse(repo_url)
    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {repo_url}")
    
    org_name, repo_name = path_parts[0], path_parts[1]
    repo_dir = Path(target_dir) / repo_name
    
    if repo_dir.exists():
        logging.info(f"Repository directory already exists at {repo_dir}")
        if not (repo_dir / ".git").exists():
            logging.info(f"Directory {repo_dir} is not a valid git repository. Removing and re-cloning...")
            shutil.rmtree(repo_dir)
        else:
            return repo_dir
    
    try:
        logging.info(f"Cloning repository {repo_url} to {repo_dir}...")
        subprocess.run(
            ["git", "clone", repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"Repository downloaded to {repo_dir}")
        
        if not any(repo_dir.iterdir()):
            raise ValueError(f"Repository was cloned but appears to be empty: {repo_dir}")
        
        return repo_dir
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to clone repository: {e.stderr}")
        raise


def extract_markdown_content(text):
    md_content = re.sub(r'```(?:json|python|bash)?(.*?)```', r'\1', text, flags=re.DOTALL)
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)
    md_content = re.sub(r'(#+)([^\s#])', r'\1 \2', md_content)
    md_content = re.sub(r'^(#+)\s+\d+[\.\)\-]\s+', r'\1 ', md_content, flags=re.MULTILINE)
    return md_content.strip()


def extract_code_examples(text):
    return re.findall(r'```(?:python|javascript|typescript|java|cpp|c\+\+|bash|sh)(.*?)```', text, re.DOTALL)


def extract_json_from_llm_response(response):
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    try:
        matches = re.findall(r'(\{[\s\S]*\}|\[[\s\S]*\])', response)
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    logging.warning("Failed to extract JSON from LLM response")
    return None


def extract_mermaid_diagrams(text):
    diagrams = re.findall(r'```mermaid\s*(.*?)\s*```', text, re.DOTALL)
    
    results = []
    for diagram in diagrams:
        desc_match = re.search(r'([^```]{10,}?)```mermaid\s*' + re.escape(diagram), text, re.DOTALL)
        if desc_match:
            description = desc_match.group(1).strip()
        else:
            desc_match = re.search(re.escape(diagram) + r'\s*```([^```]{10,}?)', text, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else ""
        
        title_match = re.search(r'^(.*?)(?:\n|$)', description)
        title = title_match.group(1).strip() if title_match else "Diagram"
        
        results.append({
            "mermaid_code": diagram.strip(),
            "description": description,
            "title": title
        })
    
    return results


def extract_parameters_from_content(content):
    parameters = []
    
    table_pattern = r'(?:Parameter|Name|Parameter name)[\s\|]+(?:Value|Default|Typical Values?)[\s\|]+(?:Description|Notes).*?\n[-\|\s]+\n(.*?)(?:\n\n|\n#|\n$)'
    table_matches = re.findall(table_pattern, content, re.DOTALL | re.IGNORECASE)
    
    if table_matches:
        for table_content in table_matches:
            rows = table_content.strip().split('\n')
            for row in rows:
                cells = re.split(r'\s*\|\s*', row.strip())
                if len(cells) >= 3:
                    parameters.append({
                        "name": cells[0].strip('` '),
                        "values": cells[1].strip(),
                        "notes": cells[2].strip()
                    })
    
    if not parameters:
        param_matches = re.findall(r'[`•\-*]\s*`([a-zA-Z0-9_]+)`\s*(?:\(([^)]+)\))?\s*:\s*(.+?)(?:\n\n|\n[`•\-*]|\n#|\n$)', content, re.DOTALL)
        for param_name, param_value, param_desc in param_matches:
            parameters.append({
                "name": param_name,
                "values": param_value if param_value else "Not specified",
                "notes": param_desc.strip()
            })
    
    code_blocks = re.findall(r'```(?:python|javascript|typescript|java|cpp|c\+\+|bash|sh)?(.*?)```', content, re.DOTALL)
    for code_block in code_blocks:
        func_matches = re.findall(r'def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', code_block)
        
        for func_name, func_params in func_matches:
            if func_params.strip():
                param_list = [p.strip() for p in func_params.split(',')]
                for param in param_list:
                    if '=' in param:
                        name, default = param.split('=', 1)
                        name = name.strip()
                        default = default.strip()
                        if name in ('self', 'cls') or name.startswith('**'):
                            continue
                        
                        if not any(p['name'] == name for p in parameters):
                            parameters.append({
                                "name": name,
                                "values": default,
                                "notes": f"Parameter for function {func_name}"
                            })
                    elif param not in ('self', 'cls') and not param.startswith('**'):
                        if not any(p['name'] == param for p in parameters):
                            parameters.append({
                                "name": param,
                                "values": "Required",
                                "notes": f"Required parameter for function {func_name}"
                            })
        
        attr_matches = re.findall(r'self\.([a-zA-Z0-9_]+)\s*=\s*([^#\n]+)', code_block)
        
        for attr_name, attr_value in attr_matches:
            if not any(p['name'] == attr_name for p in parameters):
                parameters.append({
                    "name": attr_name,
                    "values": attr_value.strip(),
                    "notes": "Class attribute"
                })
    
    return parameters


def extract_component_table(content):
    components = []
    
    table_matches = re.findall(r'\|\s*Component\s*\|\s*Description\s*\|.*?\n\|\s*[-:]+\s*\|\s*[-:]+\s*\|.*?\n(.*?)(?=\n\n|\Z)', content, re.DOTALL | re.IGNORECASE)
    
    for table_content in table_matches:
        rows = table_content.strip().split('\n')
        for row in rows:
            if '|' in row:
                parts = [part.strip() for part in row.split('|')]
                if len(parts) >= 3:
                    name_part = next((part for part in parts if part), "")
                    desc_parts = [part for part in parts[parts.index(name_part)+1:] if part]
                    
                    if name_part and desc_parts:
                        components.append({
                            "name": name_part,
                            "description": clean_description_for_table(" ".join(desc_parts))
                        })
    
    if not components:
        component_matches = re.findall(r'(?:^|\n)[-*]\s*\*\*([^*]+)\*\*\s*[:：]\s*(.*?)(?=\n[-*]|\Z)', content, re.DOTALL)
        
        for name, description in component_matches:
            components.append({
                "name": name.strip(),
                "description": clean_description_for_table(description.strip())
            })
        
        heading_matches = re.findall(r'(?:^|\n)#+\s*([^#\n]+?)\s*\n+((?:(?!#)[^\n]*\n)+)', content, re.DOTALL)
        
        for heading, content_below in heading_matches:
            if len(content_below.strip()) > 20:
                components.append({
                    "name": heading.strip(),
                    "description": clean_description_for_table(content_below.strip())
                })
    
    return components


def clean_description_for_table(description):
    description = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', description)
    description = re.sub(r'\*\*([^*]+)\*\*|\*([^*]+)\*|_([^_]+)_', r'\1', description)
    description = re.sub(r'`([^`]+)`', r'\1', description)
    description = re.sub(r'```(?:\w+)?\n(.*?)\n```', r'\1', description, flags=re.DOTALL)
    description = re.sub(r'^\s*[-*+]\s+|\s*\d+\.\s+', '', description, flags=re.MULTILINE)
    description = re.sub(r'\n{2,}', ' ', description)
    description = re.sub(r'\s{2,}', ' ', description)
    
    return description.strip().capitalize()


def extract_method_descriptions(component_doc):
    methods = []
    
    method_matches = re.findall(r'[`•\-*]\s*(?:`|\*\*)([a-zA-Z0-9_]+(?:\(\))?|[a-zA-Z0-9_]+\([^)]*\))(?:`|\*\*)\s*:?\s*(.+?)(?:\n\n|\n[`•\-*]|\n#|\n$)', component_doc, re.DOTALL)
    
    if method_matches:
        for method_name, method_desc in method_matches:
            methods.append({
                "name": method_name,
                "description": method_desc.strip()
            })
    else:
        simple_matches = re.findall(r'`([a-zA-Z0-9_]+(?:\(\))?|[a-zA-Z0-9_]+\([^)]*\))`\s*-\s*(.+?)(?:\n\n|\n`|\n#|\n$)', component_doc, re.DOTALL)
        
        for method_name, method_desc in simple_matches:
            methods.append({
                "name": method_name,
                "description": method_desc.strip()
            })
    
    return methods


def extract_parameters_for_component(component_doc):
    parameters = []
    
    param_sections = re.findall(r'(?:Parameters|Configuration|Options|Arguments):(.*?)(?:\n#|\n\n\w|\n$)', component_doc, re.DOTALL | re.IGNORECASE)
    
    if param_sections:
        param_section = param_sections[0]
        param_matches = re.findall(r'[`•\-*]\s*`?([a-zA-Z0-9_]+)`?\s*(?:\(([^)]+)\))?\s*:?\s*(.+?)(?:\n\n|\n[`•\-*]|\n#|\n$)', param_section, re.DOTALL)
        
        for param_name, param_default, param_desc in param_matches:
            parameters.append({
                "name": param_name,
                "values": param_default if param_default else "Not specified",
                "notes": param_desc.strip()
            })
    
    return parameters


def extract_use_cases_and_benchmarks(content):
    use_cases = ""
    benchmark_table = []
    
    use_cases_match = re.search(r'(?:##?\s*Use Cases|##?\s*Applications)(?:.+?)(?:##|$)', content, re.DOTALL | re.IGNORECASE)
    if use_cases_match:
        use_cases = use_cases_match.group(0)
    
    table_matches = re.findall(r'(?:Benchmark|Task|Test)[\s\|]+(?:Description|Details)[\s\|]+(?:Agent Types|Agents|Configuration).*?\n[-\|\s]+\n(.*?)(?:\n\n|\n#|\n$)', content, re.DOTALL | re.IGNORECASE)
    
    if table_matches:
        for table_content in table_matches:
            rows = table_content.strip().split('\n')
            for row in rows:
                cells = re.split(r'\s*\|\s*', row.strip())
                if len(cells) >= 3:
                    benchmark_table.append({
                        "benchmark": cells[0].strip(),
                        "description": cells[1].strip(),
                        "agent_types": cells[2].strip()
                    })
    
    return use_cases, benchmark_table


def extract_architectural_philosophy(content):
    philosophy = ""
    numbered_concepts = []
    
    philosophy_match = re.search(r'(?:##?\s*Architectural Philosophy|##?\s*Design Principles|##?\s*Architecture Concepts)(?:.+?)(?:##|$)', content, re.DOTALL | re.IGNORECASE)
    if philosophy_match:
        philosophy = philosophy_match.group(0)
        
        concept_matches = re.findall(r'(?:\d+\.|\*|\-)\s+([^:]+):\s+(.+?)(?=\n\s*(?:\d+\.|\*|\-|##|\n\n|$))', philosophy, re.DOTALL)
        
        for title, description in concept_matches:
            numbered_concepts.append({
                "title": title.strip(),
                "description": description.strip()
            })
    
    return philosophy, numbered_concepts


def extract_getting_started(content):
    getting_started = ""
    basic_example = ""
    usage_features = []
    
    getting_started_match = re.search(r'(?:##?\s*Getting Started|##?\s*Basic Usage)(?:.+?)(?:```|##|$)', content, re.DOTALL | re.IGNORECASE)
    if getting_started_match:
        getting_started = getting_started_match.group(0)
    
    example_match = re.search(r'```(?:python|bash)?\s*(from[\s\S]+?)(?:```|$)', content, re.DOTALL)
    if example_match:
        basic_example = example_match.group(1).strip()
    
    feature_match = re.search(r'(?:Supports|Features|Capabilities):\s*(?:\n\s*[-*•]\s*(.+?))+(?=\n\n|\n##|$)', content, re.DOTALL | re.IGNORECASE)
    if feature_match:
        feature_items = re.findall(r'[-*•]\s*(.+?)(?=\n\s*[-*•]|\n\n|\n##|$)', feature_match.group(0), re.DOTALL)
        usage_features = [item.strip() for item in feature_items]
    
    return getting_started, basic_example, usage_features


def extract_architecture_sections(content):
    return [
        {
            "id": title.strip().lower().replace(' ', '-'),
            "title": title.strip(),
            "content": content.strip()
        }
        for title, content in re.findall(r'##\s+([\w\s]+)\n(.*?)(?=##|\Z)', content, re.DOTALL)
    ]


def extract_relevant_files(repo_dir, architecture_doc):
    files = []
    
    file_patterns = [
        r'`([^`\n]+\.(py|js|ts|java|c|cpp|go))`',
        r'([a-zA-Z0-9_/\-]+\.(py|js|ts|java|c|cpp|go))',
    ]
    
    all_matches = []
    for pattern in file_patterns:
        matches = re.findall(pattern, architecture_doc)
        if isinstance(matches[0], tuple) if matches else False:
            all_matches.extend([match[0] for match in matches])
        else:
            all_matches.extend(matches)
    
    for file_path in all_matches:
        file_path = file_path.strip('`\'\" ')
        potential_paths = [
            repo_dir / file_path,
            repo_dir / "src" / file_path,
            repo_dir / "lib" / file_path,
            repo_dir / "app" / file_path,
        ]
        
        for path in potential_paths:
            if path.exists() and path.is_file():
                try:
                    rel_path = path.relative_to(repo_dir)
                    files.append(str(rel_path))
                    break
                except ValueError:
                    files.append(file_path)
                    break
    
    return list(set(files))[:15]


def find_definition_line(content, definition_prefix):
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if line.strip().startswith(definition_prefix):
            return i
    return None


def estimate_line_range(file_path, max_lines=50):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        if total_lines <= max_lines:
            return f"1-{total_lines}"
        
        start_line = 1
        for i, line in enumerate(lines, 1):
            if i > 20:
                break
            stripped = line.strip()
            if (stripped and 
                not stripped.startswith('#') and 
                not stripped.startswith('import ') and 
                not stripped.startswith('from ')):
                start_line = i
                break
        
        end_line = min(start_line + max_lines - 1, total_lines)
        
        return f"{start_line}-{end_line}"
    
    except Exception as e:
        logging.warning(f"Error estimating line range for {file_path}: {e}")
        return "1-50"


def extract_code_references(content, python_files, repo_dir, repo_url=None):
    references = []
    
    file_patterns = [
        r'`([^`\n]+\.(?:py|js|ts|java|rb))`',
        r'(\w+\/[\w\/\.]+\.(?:py|js|ts|java|rb))',
        r'([\w_]+\.(?:py|js|ts|java|rb))'
    ]
    
    all_matches = []
    for pattern in file_patterns:
        matches = re.findall(pattern, content)
        all_matches.extend(matches)
    
    class_pattern = r'class\s+([A-Za-z0-9_]+)'
    func_pattern = r'def\s+([A-Za-z0-9_]+)'
    
    class_matches = re.findall(class_pattern, content)
    func_matches = re.findall(func_pattern, content)
    
    for file_path in all_matches:
        file_path = str(file_path).strip('`\'\" ')
        
        file_obj = repo_dir / file_path
        if file_obj.exists() and file_obj.is_file():
            line_range = estimate_line_range(file_obj)
            
            reference = {
                "file": file_path,
                "lines": line_range
            }
            
            if repo_url:
                parsed_url = urlparse(repo_url)
                path_parts = parsed_url.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    org_name, repo_name = path_parts[0], path_parts[1]
                    start_line, end_line = line_range.split('-')
                    github_url = f"https://github.com/{org_name}/{repo_name}/blob/main/{file_path}#L{start_line}-L{end_line}"
                    reference["github_url"] = github_url
                    
            references.append(reference)
    
    for python_file in python_files:
        try:
            file_path = str(python_file)
            file_obj = repo_dir / python_file
            
            if not file_obj.exists() or not file_obj.is_file():
                continue
                
            with open(file_obj, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            for class_name in class_matches:
                pattern = r'class\s+' + re.escape(class_name) + r'\b'
                if re.search(pattern, content):
                    line_num = find_definition_line(content, f"class {class_name}")
                    if line_num:
                        reference = {
                            "file": file_path,
                            "lines": f"{line_num}-{line_num + 10}"
                        }
                        
                        if repo_url:
                            parsed_url = urlparse(repo_url)
                            path_parts = parsed_url.path.strip('/').split('/')
                            if len(path_parts) >= 2:
                                org_name, repo_name = path_parts[0], path_parts[1]
                                start_line, end_line = f"{line_num}", f"{line_num + 10}"
                                github_url = f"https://github.com/{org_name}/{repo_name}/blob/main/{file_path}#L{start_line}-L{end_line}"
                                reference["github_url"] = github_url
                                
                        references.append(reference)
            
            for func_name in func_matches:
                pattern = r'def\s+' + re.escape(func_name) + r'\b'
                if re.search(pattern, content):
                    line_num = find_definition_line(content, f"def {func_name}")
                    if line_num:
                        reference = {
                            "file": file_path,
                            "lines": f"{line_num}-{line_num + 5}"
                        }
                        
                        if repo_url:
                            parsed_url = urlparse(repo_url)
                            path_parts = parsed_url.path.strip('/').split('/')
                            if len(path_parts) >= 2:
                                org_name, repo_name = path_parts[0], path_parts[1]
                                start_line, end_line = f"{line_num}", f"{line_num + 5}"
                                github_url = f"https://github.com/{org_name}/{repo_name}/blob/main/{file_path}#L{start_line}-L{end_line}"
                                reference["github_url"] = github_url
                                
                        references.append(reference)
        
        except Exception as e:
            logging.warning(f"Error processing file {python_file} for code references: {e}")
    
    unique_refs = []
    seen = set()
    
    for ref in references:
        file_line = f"{ref['file']}:{ref['lines']}"
        if file_line not in seen:
            seen.add(file_line)
            unique_refs.append(ref)
    
    return unique_refs[:10]


def deduplicate_sources(documentation):
    seen_refs = set()
    
    for section_key, section_data in documentation.get("sources", {}).items(): # Iterate over sources dictionary
        unique_refs_for_section = []
        for ref in section_data: # section_data is the list of refs for this section
            ref_key = f"{ref.get('file', '')}:{ref.get('lines', '')}"
            if ref_key not in seen_refs:
                seen_refs.add(ref_key)
                unique_refs_for_section.append(ref)
        documentation["sources"][section_key] = unique_refs_for_section


def review_and_optimize_content(documentation):
    logging.info("Reviewing and optimizing documentation content...")
    
    # Example: Merge advanced_topics into architecture if advanced_topics is brief
    # This needs to be adapted to the new structure where content is under section_id
    advanced_topics_section_id = "advanced_topics" # Assuming 'advanced_topics' is the ID
    architecture_section_id = "architecture"

    if advanced_topics_section_id in documentation and \
       isinstance(documentation[advanced_topics_section_id], dict) and \
       documentation[advanced_topics_section_id].get("enabled", True) and \
       len(documentation[advanced_topics_section_id].get("advanced_topics_sections", [])) <=1 and \
       len(documentation[advanced_topics_section_id].get("content","")) < 500 : # Check content length

        if architecture_section_id in documentation and \
           isinstance(documentation[architecture_section_id], dict) and \
           documentation[architecture_section_id].get("enabled", True):
            
            logging.info(f"Merging brief '{documentation[advanced_topics_section_id]['title']}' into '{documentation[architecture_section_id]['title']}' section.")
            
            adv_content = documentation[advanced_topics_section_id].get("content", "")
            if adv_content:
                documentation[architecture_section_id]["content"] += "\n\n## Advanced Considerations\n\n" + adv_content
            
            # Mark original advanced_topics as merged/disabled or remove
            documentation[advanced_topics_section_id]["enabled"] = False
            documentation[advanced_topics_section_id]["content"] = "Content merged into Architecture section."
            documentation[advanced_topics_section_id]["merged_into"] = architecture_section_id
        else:
            logging.info(f"No suitable '{architecture_section_id}' section found or it's disabled; cannot merge '{advanced_topics_section_id}'.")

    # Example: Component merging (remains complex and might need specific section_config flags)
    # This logic will need to be adapted to the new structure if "components" is a specific section type.
    # For now, this part of optimization might be less effective until component processing is fully refactored.
    if "components" in documentation and isinstance(documentation["components"], dict): # Global components dict
        components_to_merge = []
        for component_name, component_data in list(documentation.get("components", {}).items()):
            if isinstance(component_data, dict): # Ensure it's a dict before accessing keys
                content_length = len(component_data.get("purpose", "")) + len(component_data.get("usage", ""))
                if content_length < 200 and not component_data.get("code_example") and not component_data.get("methods_with_descriptions"):
                    logging.info(f"Component {component_name} has limited content, marking for merge")
                    components_to_merge.append(component_name)
        
        if components_to_merge:
            logging.info(f"Merging {len(components_to_merge)} components with limited content into 'Other Components'")
            other_components_data = documentation["components"].get("Other Components", {
                "purpose": "This section contains additional components with related functionality.",
                "usage": "These components provide supporting features and utilities.",
                "methods": [], "methods_with_descriptions": [], "parameters": []
            })
            
            for comp_name in components_to_merge:
                comp_data = documentation["components"].pop(comp_name, {})
                other_components_data["purpose"] += f"\n\n**{comp_name}**: {comp_data.get('purpose', '')}"
                # ... (merge other fields as before) ...
            documentation["components"]["Other Components"] = other_components_data

    # Installation section enhancement (adapting to new structure)
    installation_section_id = "installation" # Assuming 'installation' is the ID
    if installation_section_id in documentation and \
       isinstance(documentation[installation_section_id], dict) and \
       documentation[installation_section_id].get("enabled", True):
        
        current_content = documentation[installation_section_id].get("content", "")
        if len(current_content) < 300:
            logging.info("Installation section is too brief, enhancing with more information")
            enhancement = """

## Common Installation Issues

If you encounter any issues during installation, try the following troubleshooting steps:

1. Make sure you have the correct Python version installed
2. Verify that all dependencies are properly installed
3. Check your environment variables
4. If using virtual environments, ensure it's activated properly
5. For permission issues, try using `sudo` (on Linux/Mac) or run as administrator (on Windows)

For further assistance, please refer to the project documentation or open an issue on the repository.
"""
            documentation[installation_section_id]["content"] += enhancement
    
    # Code examples description enhancement
    if "code_examples" in documentation and isinstance(documentation["code_examples"], list):
        for i, example in enumerate(documentation.get("code_examples", [])):
            if not example.get("description") or len(example.get("description", "")) < 50:
                example["description"] = f"Example demonstrating key functionality of the {documentation.get('repo_name')} library."
    
    return documentation


def generate_repo_documentation(repo_dir, output_dir, config, repo_url):
    logging.info(f"Generating documentation for repository at {repo_dir}")
    
    judge_dir = output_dir / "judge"
    judge_dir.mkdir(parents=True, exist_ok=True)
    
    repo_dir = Path(repo_dir).absolute()
    
    instance_data = {
        "name": repo_dir.name,
        "query": "Generate documentation for this repository",
        "requirements": [
            {
                "criteria": "Provide a comprehensive overview of the repository structure and functionality"
            }
        ]
    }
    
    instance_file = judge_dir / f"{repo_dir.name}.json"
    with open(instance_file, "w") as f:
        json.dump(instance_data, f)
    
    logging.info(f"Using repository directory: {repo_dir}")
    logging.info(f"Judge directory: {judge_dir}")
    
    def print_directory_structure(path, max_depth=3, depth=0):
        if depth > max_depth: return
        try:
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    logging.info(f"{'  ' * depth}[DIR] {item.name}")
                    print_directory_structure(item, max_depth, depth + 1)
                elif item.is_file() and item.suffix in ['.py', '.md', '.json', '.yaml', '.yml']:
                    logging.info(f"{'  ' * depth}[FILE] {item.name}")
        except Exception as e: logging.error(f"Error scanning directory {path}: {e}")
    
    logging.info("Repository structure:")
    print_directory_structure(repo_dir)
    
    try:
        doc_title = f"{repo_dir.name} Documentation"
        output_filename_base = repo_dir.name 
        if config.doc_config:
            doc_title = config.doc_config.get("document_title", doc_title)
            output_filename_base = config.doc_config.get("output_filename", output_filename_base)
            if not output_filename_base.strip(): output_filename_base = repo_dir.name

        documentation: Dict[str, Any] = {
            "name": repo_dir.name, 
            "document_title": doc_title,
            "output_filename_base": output_filename_base,
            "url": str(repo_url),
            "repo_name": repo_dir.name,
            "org_name": repo_url.split("/")[-2] if repo_url and "/" in repo_url else "",
            "last_indexed": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": {key: [] for key in [s['id'] for s in DEFAULT_SECTIONS_CONFIG if s.get('type') != 'components' and s.get('type') != 'code_quality']},
            # Initialize all potential top-level and section-specific data keys used by templates/extractors
            "main_purpose": "", "use_cases": "", "benchmark_table": [],
            "architecture": "", # For backward compat with extract_tech_stack; section-specific content is under documentation[section_id]['content']
            "architectural_philosophy": "", "numbered_concepts": [], "architecture_sections": [], "architecture_files": [], # These might become section-specific
            "flow_diagrams": {}, "component_table": [], "components": {}, # components is for detailed component data
            "getting_started": "", "basic_example": "", "advanced_usage": "", "usage_features": [],
            "installation": "", "parameters": [], # installation for main content, parameters for extracted
            "advanced_topics": "", "advanced_topics_sections": [], # advanced_topics for main content
            "examples": "", "code_examples": [], # examples for main content
            "code_quality_assessments": []
        }
        documentation["sources"]["components"] = [] 
        
        readme_path = repo_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8', errors='replace') as f:
                readme_content = f.read()
            if "overview" in documentation["sources"]:
                documentation["sources"]["overview"].append({"file": "README.md", "lines": f"1-{len(readme_content.splitlines())}"})
        
        judge_agent = JudgeAgent(workspace=repo_dir, instance=instance_file, judge_dir=judge_dir, config=config)
        
        if not judge_agent.graph_file.exists():
            logging.info("Constructing graph for repository...")
            judge_agent.construct_graph()
        
        python_files = list(repo_dir.glob("**/*.py"))
        python_files = [p.relative_to(repo_dir) for p in python_files if not any(ex in str(p) for ex in config.exclude_dirs)]
        
        sections_to_process = DEFAULT_SECTIONS_CONFIG
        if config.doc_config and "sections" in config.doc_config and isinstance(config.doc_config["sections"], list):
            custom_sections = config.doc_config["sections"]
            # Merge custom with default: custom takes precedence for id, but default provides structure if type matches
            processed_ids = set()
            merged_sections = []
            for custom_sec in custom_sections:
                default_sec = next((ds for ds in DEFAULT_SECTIONS_CONFIG if ds["id"] == custom_sec["id"]), None)
                if default_sec:
                    merged_section = {**default_sec, **custom_sec} # Custom overrides default for shared keys
                else: # Truly custom section not in defaults
                    merged_section = custom_sec
                merged_sections.append(merged_section)
                processed_ids.add(custom_sec["id"])
            # Add any default sections that weren't in the custom config, respecting their default 'enabled' state
            for default_sec in DEFAULT_SECTIONS_CONFIG:
                if default_sec["id"] not in processed_ids:
                     merged_sections.append(default_sec)
            sections_to_process = merged_sections
            logging.info(f"Using document structure from config file: {config.doc_config_path}")
        else:
            logging.info("Using default document structure.")

        # --- Main Loop for Section Generation ---
        for section_config in sections_to_process:
            section_id = section_config["id"]
            section_title = section_config.get("title", section_id.replace("_", " ").title())
            section_type = section_config["type"] # Assume type is always present from default or custom config
            
            if not section_config.get("enabled", True): # Default to enabled if not specified
                logging.info(f"Skipping disabled section: {section_title} (ID: {section_id})")
                documentation[section_id] = {"title": section_title, "type": section_type, "content": "This section was disabled by configuration.", "enabled": False}
                continue

            logging.info(f"Generating section: {section_title} (Type: {section_type})")
            # Initialize section in documentation dict, ensuring all expected sub-keys for templates are present
            documentation[section_id] = {
                "title": section_title, "content": "", "type": section_type,
                "prompt_key": section_config.get("prompt_key"),
                "prompt_override": section_config.get("prompt_override"),
                "enabled": True
            }
            # Initialize specific data keys for this section type if they are defined in DEFAULT_SECTIONS_CONFIG
            default_section_meta = next((ds for ds in DEFAULT_SECTIONS_CONFIG if ds["id"] == section_id), None)
            if default_section_meta and "data_keys" in default_section_meta:
                for key in default_section_meta["data_keys"]:
                    documentation[section_id][key] = [] if "sections" in key or "files" in key or "table" in key or "concepts" in key else ""


            prompt_str = None
            if section_config.get("prompt_override"):
                prompt_str = section_config["prompt_override"]
            elif section_config.get("prompt_key") and section_config["prompt_key"] in PROMPT_FUNCTION_MAP:
                prompt_fn = PROMPT_FUNCTION_MAP[section_config["prompt_key"]]
                prompt_str = prompt_fn(language=config.language)
            
            # Skip LLM call if no prompt and not a special handling type
            if not prompt_str and section_type not in ["components", "code_quality", "diagrams", "custom"]:
                logging.warning(f"No valid prompt for pre-defined section '{section_id}' of type '{section_type}'. Skipping LLM call.")
                documentation[section_id]['content'] = "Error: Prompt not configured for this section."
                continue
            
            # --- Section-specific processing ---
            if section_type == "overview":
                if prompt_str:
                    overview_doc_content = judge_agent.ask_anything(prompt_str)
                    documentation[section_id]['content'] = extract_markdown_content(overview_doc_content)
                    documentation['main_purpose'] = documentation[section_id]['content'] # Global key
                    use_cases, benchmark_table = extract_use_cases_and_benchmarks(overview_doc_content)
                    documentation['use_cases'] = use_cases # Global key
                    documentation['benchmark_table'] = benchmark_table # Global key
                    overview_code_refs = extract_code_references(overview_doc_content, python_files, repo_dir, repo_url)
                    if overview_code_refs: documentation["sources"]["overview"].extend(overview_code_refs)
            
            elif section_type == "architecture":
                if prompt_str:
                    architecture_doc_content = judge_agent.ask_anything(prompt_str)
                    main_arch_content = extract_markdown_content(architecture_doc_content)
                    documentation[section_id]['content'] = main_arch_content
                    documentation['architecture'] = main_arch_content # Global key for backward compat (e.g. tech_stack)
                    
                    philosophy, concepts = extract_architectural_philosophy(architecture_doc_content)
                    documentation[section_id]['architectural_philosophy'] = philosophy
                    documentation[section_id]['numbered_concepts'] = concepts
                    documentation[section_id]['architecture_sections'] = extract_architecture_sections(main_arch_content)
                    documentation[section_id]['architecture_files'] = extract_relevant_files(repo_dir, architecture_doc_content)
                    
                    arch_code_refs = extract_code_references(architecture_doc_content, python_files, repo_dir, repo_url)
                    if arch_code_refs: documentation["sources"]["architecture"].extend(arch_code_refs)

            elif section_type == "diagrams":
                diagram_prompt_to_use = prompt_str # This might be from override or PROMPT_FUNCTION_MAP
                if not diagram_prompt_to_use and section_config.get("prompt_key", "get_diagram_prompt") in PROMPT_FUNCTION_MAP : # Default if not overridden
                    diagram_prompt_to_use = PROMPT_FUNCTION_MAP[section_config.get("prompt_key", "get_diagram_prompt")](language=config.language)

                if diagram_prompt_to_use:
                    diagram_response_content = judge_agent.ask_anything(diagram_prompt_to_use)
                    documentation[section_id]['content'] = diagram_response_content 
                    diagrams_data = extract_mermaid_diagrams(diagram_response_content)
                    if diagrams_data:
                        documentation["flow_diagrams"] = { # Global key
                            "architecture": diagrams_data[0],
                            "workflow": diagrams_data[1] if len(diagrams_data) > 1 else None,
                            "component_relationships": diagrams_data[2] if len(diagrams_data) > 2 else None
                        }
                else:
                    logging.warning(f"No prompt for diagrams section '{section_id}'. Skipping.")
                    documentation[section_id]['content'] = "Error: Prompt not configured for this section."

            elif section_type == "component_analysis":
                if prompt_str:
                    component_analysis_content = judge_agent.ask_anything(prompt_str)
                    documentation[section_id]['content'] = extract_markdown_content(component_analysis_content)
                    documentation["component_table"] = extract_component_table(component_analysis_content) # Global
                    comp_code_refs = extract_code_references(component_analysis_content, python_files, repo_dir, repo_url)
                    if comp_code_refs: documentation["sources"]["components"].extend(comp_code_refs) # Shared source

            elif section_type == "usage":
                if prompt_str:
                    usage_doc_content = judge_agent.ask_anything(prompt_str)
                    documentation[section_id]['content'] = extract_markdown_content(usage_doc_content)
                    gs, be, uf = extract_getting_started(usage_doc_content)
                    documentation['getting_started'] = gs
                    documentation['basic_example'] = be
                    documentation['usage_features'] = uf
                    documentation['advanced_usage'] = documentation[section_id]['content'] 

                    code_ex = extract_code_examples(usage_doc_content)
                    if code_ex: documentation["code_examples"].extend([{"title": f"Usage Example {i+1}", "description": "Example from usage guide", "code": ex.strip()} for i, ex in enumerate(code_ex)])
                    usage_code_refs = extract_code_references(usage_doc_content, python_files, repo_dir, repo_url)
                    if usage_code_refs: documentation["sources"]["usage"].extend(usage_code_refs)
            
            elif section_type == "installation":
                if prompt_str:
                    installation_doc_content = judge_agent.ask_anything(prompt_str)
                    documentation[section_id]['content'] = extract_markdown_content(installation_doc_content)
                    documentation['installation'] = documentation[section_id]['content'] 
                    install_code_refs = extract_code_references(installation_doc_content, python_files, repo_dir, repo_url)
                    if install_code_refs: documentation["sources"]["installation"].extend(install_code_refs)
                    
                    if not documentation.get("parameters"): # Populate global parameters if not already done
                        param_content_sources = [
                            documentation.get("architecture", {}).get("content", documentation.get("architecture", "")), 
                            documentation.get("usage", {}).get("content", documentation.get("advanced_usage", "")) 
                        ]
                        all_content_for_params = ""
                        for cs in param_content_sources:
                            if isinstance(cs, str): all_content_for_params += cs + "\n\n"
                        
                        extracted_params = extract_parameters_from_content(all_content_for_params)
                        if extracted_params: documentation["parameters"].extend(extracted_params)
                                     
                        if not documentation.get("parameters"): 
                            all_comp_examples = "".join([comp.get("code_example","") for comp_name, comp in documentation.get("components",{}).items() if isinstance(comp, dict) and comp.get("code_example")])
                            documentation["parameters"].extend(extract_parameters_from_content(all_comp_examples))
            
            elif section_type == "advanced_topics":
                if prompt_str:
                    advanced_topics_content = judge_agent.ask_anything(prompt_str)
                    documentation[section_id]['content'] = extract_markdown_content(advanced_topics_content)
                    documentation['advanced_topics'] = documentation[section_id]['content']
                    documentation[section_id]['advanced_topics_sections'] = extract_architecture_sections(documentation[section_id]['content'])
                    code_ex = extract_code_examples(advanced_topics_content)
                    if code_ex: documentation["code_examples"].extend([{"title": f"Advanced Example {i+1}", "description": "Advanced usage example", "code": ex.strip()} for i, ex in enumerate(code_ex)])

            elif section_type == "examples":
                if prompt_str:
                    examples_content = judge_agent.ask_anything(prompt_str)
                    documentation[section_id]['content'] = extract_markdown_content(examples_content)
                    documentation['examples'] = documentation[section_id]['content']
                    code_ex = extract_code_examples(examples_content)
                    if code_ex:
                        for i, example_code in enumerate(code_ex):
                            title_pattern = r'#+\s*(.*?)\s*\n+```' 
                            relevant_text_for_title = examples_content.split(example_code)[0].split('\n')[-5:] 
                            title_matches = re.findall(title_pattern, "\n".join(relevant_text_for_title))
                            title = title_matches[-1] if title_matches else f"Example {i+1}"
                            documentation["code_examples"].append({"title": title, "description": f"Example from {section_title}", "code": example_code.strip()})
            
            elif section_type == "components": # Special handling for components (detail loop)
                # This section_config is for the overall "Components" section, not individual items
                # The actual component data is stored in documentation['components']
                documentation[section_id]['content'] = "Details for components are listed below." # Placeholder content
                
                # Component details loop (moved from outside the main loop)
                component_names_override = section_config.get("component_names")
                if isinstance(component_names_override, list) and component_names_override:
                    actual_component_names = component_names_override
                elif documentation.get("component_table"): # From component_analysis section
                    actual_component_names = [item["name"] for item in documentation["component_table"]]
                else: 
                    actual_component_names = ["Main Component", "Core Library", "Utilities"] # Fallback
                
                logging.info(f"Processing component details for: {actual_component_names}")
                documentation["components"] = {} # Initialize/reset
                for comp_name in actual_component_names:
                    logging.info(f"Generating documentation for component: {comp_name}")
                    detail_prompt_key = section_config.get("prompt_key_detail", "get_component_detail_prompt")
                    detail_prompt_override = section_config.get("prompt_override_detail")
                    comp_prompt_str = detail_prompt_override or PROMPT_FUNCTION_MAP[detail_prompt_key](comp_name, language=config.language)
                    comp_doc_content = judge_agent.ask_anything(comp_prompt_str)
                    comp_details = {
                        "purpose": extract_markdown_content(re.search(r'^(.+?)(?=\n\n|\n#)', comp_doc_content, re.DOTALL).group(1).strip() if re.search(r'^(.+?)(?=\n\n|\n#)', comp_doc_content, re.DOTALL) else ""),
                        "usage": extract_markdown_content(re.search(r'(?:usage|how to use|interaction):?\s*(?:\n|.)*?(?:##|\n\n|$)', comp_doc_content, re.IGNORECASE).group(0).strip() if re.search(r'(?:usage|how to use|interaction):?\s*(?:\n|.)*?(?:##|\n\n|$)', comp_doc_content, re.IGNORECASE) else ""),
                        "methods_with_descriptions": extract_method_descriptions(comp_doc_content),
                        "parameters": extract_parameters_for_component(comp_doc_content),
                        "code_example": extract_code_examples(comp_doc_content)[0].strip() if extract_code_examples(comp_doc_content) else ""
                    }
                    comp_details["methods"] = [m["name"] for m in comp_details["methods_with_descriptions"]]
                    if not comp_details["parameters"] and comp_details["code_example"]:
                        comp_details["parameters"] = extract_parameters_from_content(comp_details["code_example"])
                    comp_file_refs = extract_code_references(comp_doc_content, python_files, repo_dir, repo_url)
                    if comp_file_refs: 
                        comp_details["source_files"] = comp_file_refs
                        documentation["sources"]["components"].extend(comp_file_refs)
                    documentation["components"][comp_name] = comp_details
                    if comp_details["code_example"] and len(extract_code_examples(comp_doc_content)) > 1:
                         for i, example in enumerate(extract_code_examples(comp_doc_content)[1:], 1):
                            documentation["code_examples"].append({"title": f"{comp_name} Example {i}", "description": f"Example usage of the {comp_name} component", "code": example.strip()})

            elif section_type == "code_quality":
                if config.assess_quality:
                    logging.info("Starting code quality assessment for selected files...")
                    documentation[section_id]["assessments"] = [] # Initialize here
                    
                    MAX_FILES_TO_ASSESS = section_config.get("max_files_to_assess", 5)
                    selected_files_for_assessment_relative_paths = []
                    
                    arch_section_data = documentation.get("architecture", {}) # Check if architecture section was processed
                    arch_files_list = []
                    if isinstance(arch_section_data, dict) and arch_section_data.get("enabled", False): # Check if architecture section was enabled
                        arch_files_list = arch_section_data.get("architecture_files", [])
                    elif isinstance(documentation.get("architecture_files"), list): # Fallback for older global key (if architecture section was custom and didn't populate section_id['architecture_files'])
                        arch_files_list = documentation.get("architecture_files", [])


                    if arch_files_list:
                        for rel_path_str in arch_files_list:
                            if len(selected_files_for_assessment_relative_paths) < MAX_FILES_TO_ASSESS and rel_path_str.endswith(".py"):
                                selected_files_for_assessment_relative_paths.append(rel_path_str)
                    
                    if len(selected_files_for_assessment_relative_paths) < MAX_FILES_TO_ASSESS and python_files:
                        for rel_py_path_obj in python_files:
                            rel_py_path_str = str(rel_py_path_obj)
                            if rel_py_path_str not in selected_files_for_assessment_relative_paths:
                                selected_files_for_assessment_relative_paths.append(rel_py_path_str)
                                if len(selected_files_for_assessment_relative_paths) >= MAX_FILES_TO_ASSESS: break
                    
                    logger.info(f"Selected {len(selected_files_for_assessment_relative_paths)} files for quality assessment: {selected_files_for_assessment_relative_paths}")
                    for file_path_str in selected_files_for_assessment_relative_paths:
                        assessment = judge_agent.assess_code_quality(file_path_str, language=config.language)
                        if assessment:
                            documentation["code_quality_assessments"].append({"file_path": file_path_str, "assessment": assessment}) # Store globally
                    documentation[section_id]["assessments"] = documentation["code_quality_assessments"] # Also store under section
                else:
                    logging.info("Code quality assessment is disabled by global config.")
                    documentation[section_id]["content"] = "Code quality assessment disabled."
                    documentation[section_id]["enabled"] = False # Mark this specific section as not producing output

            elif section_type == "custom":
                if prompt_str: # Prompt should be resolved by config loader from prompt or prompt_file
                    custom_content = judge_agent.ask_anything(prompt_str) # Assuming prompt_str is already in correct language
                    documentation[section_id]['content'] = extract_markdown_content(custom_content)
                    # Add code references from custom content to a generic 'custom' source key or section_id based key
                    if section_id not in documentation["sources"]: documentation["sources"][section_id] = []
                    custom_code_refs = extract_code_references(custom_content, python_files, repo_dir, repo_url)
                    if custom_code_refs: documentation["sources"][section_id].extend(custom_code_refs)
                else:
                    logging.warning(f"Custom section '{section_id}' has no prompt defined. Skipping LLM call.")
                    documentation[section_id]['content'] = "Error: Prompt not defined for this custom section."
            
            # No per-section page generation anymore

        deduplicate_sources(documentation)
        documentation = review_and_optimize_content(documentation)
        
        # Prepare section_render_order for templates
        documentation['section_render_order'] = []
        for sec_conf in sections_to_process: # Use the same list that drove generation
            if documentation.get(sec_conf['id'], {}).get('enabled', False): # Check if section was processed and still enabled
                documentation['section_render_order'].append({
                    'id': sec_conf['id'],
                    'title': documentation[sec_conf['id']].get('title', sec_conf.get('title', sec_conf['id'])),
                    'type': documentation[sec_conf['id']].get('type', sec_conf['type'])
                })
        
        doc_file_name = documentation.get("output_filename_base", repo_dir.name) + "_documentation.json"
        doc_file = output_dir / doc_file_name
        
        with open(doc_file, "w") as f:
            json.dump(documentation, f, indent=2)
        
        if config.output_format == "markdown":
            generate_final_markdown(documentation, output_dir, language=config.language, agent_config_obj=config)
        else:
            generate_final_html(documentation, output_dir, agent_config_obj=config)
        
        logging.info(f"Documentation generated at {output_dir} in '{config.output_format}' format.")
        return doc_file
    
    except Exception as e:
        logging.error(f"Error during documentation generation: {e}")
        import traceback
        logging.error(traceback.format_exc())
        
        doc_title_error = f"{repo_dir.name} Documentation (Error)"
        output_filename_base_error = repo_dir.name
        if config.doc_config:
            doc_title_error = config.doc_config.get("document_title", doc_title_error)
            output_filename_base_error = config.doc_config.get("output_filename", output_filename_base_error)
            if not output_filename_base_error.strip(): output_filename_base_error = repo_dir.name

        error_documentation = {
            "name": repo_dir.name, 
            "document_title": doc_title_error,
            "output_filename_base": output_filename_base_error,
            "url": str(repo_url),
            "repo_name": repo_dir.name,
            "org_name": repo_url.split("/")[-2] if repo_url and "/" in repo_url else "",
            "last_indexed": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": f"Error occurred during documentation generation: {str(e)}",
            "main_purpose": "Documentation could not be generated due to an error.",
            "architecture": "Not generated.", 
            "sources": {"overview": [], "architecture": [], "components": [], "installation": [], "usage": []},
            "code_quality_assessments": [] 
        }
        sections_for_error = config.doc_config.get("sections", DEFAULT_SECTIONS_CONFIG) if config.doc_config else DEFAULT_SECTIONS_CONFIG
        for sec_conf in sections_for_error:
            error_documentation[sec_conf["id"]] = {"title": sec_conf.get("title", sec_conf["id"]), "type": sec_conf["type"], "content": "Not generated due to error.", "enabled": sec_conf.get("enabled", True)}

        doc_file_name_error = error_documentation.get("output_filename_base", repo_dir.name) + "_documentation.json"
        doc_file = output_dir / doc_file_name_error

        with open(doc_file, "w") as f:
            json.dump(error_documentation, f, indent=2)
        
        try:
            if config.output_format == "markdown":
                generate_final_markdown(error_documentation, output_dir, language=config.language, agent_config_obj=config)
            else:
                generate_final_html(error_documentation, output_dir, agent_config_obj=config)
        except Exception as html_error:
            logging.error(f"Error generating final document from error data: {html_error}")
        
        logging.info(f"Basic error documentation generated at {output_dir}")
        return doc_file


def generate_html_page(documentation, output_dir, section=None, agent_config_obj: Optional[AgentConfig] = None): # Added agent_config_obj
    template_dir = Path(__file__).parent / "templates" / "html"
    
    try:      
        import jinja2
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("index.html")
        
        html_content = template.render(
            documentation=documentation,
            doc_config=(agent_config_obj.doc_config if agent_config_obj else None),
            sections_to_render=documentation.get('section_render_order', []),
            architecture={"tech_stack": extract_tech_stack(documentation)}, 
            generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            # section=section # This 'section' param is legacy for per-section generation
        )
        
        html_file_name = documentation.get("output_filename_base", documentation.get("repo_name", "documentation")) + ".html"
        html_file = output_dir / html_file_name

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        logging.info(f"HTML documentation generated: {html_file}")
    except Exception as e:
        logging.error(f"Error in generate_html_page: {e}")


def generate_final_html(documentation, output_dir, agent_config_obj: Optional[AgentConfig] = None): # Added agent_config_obj
    generate_html_page(documentation, output_dir, "complete", agent_config_obj=agent_config_obj) # Pass agent_config_obj
    output_filename_base = documentation.get("output_filename_base", documentation.get("repo_name", "documentation"))
    html_file = output_dir / f"{output_filename_base}.html" 
    return html_file


def generate_markdown_page(documentation, output_dir, section=None): # Legacy, per-section
    logger = logging.getLogger(__name__)
    logger.info(f"Markdown processing for section (legacy call, will be removed): {section}")
    pass


def generate_final_markdown(documentation, output_dir, language: str = "en", agent_config_obj: Optional[AgentConfig] = None) -> Optional[Path]: # Added agent_config_obj
    logger = logging.getLogger(__name__)
    template_dir = Path(__file__).parent / "templates" / "markdown"
    
    try:
        import jinja2 
    except ImportError:
        logger.error("jinja2 library is not installed. Please install it to generate Markdown output.")
        return None

    try:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['md']), 
            undefined=jinja2.StrictUndefined
        )
        
        template_name = "index.md.j2"
        if language == "zh":
            try:
                template = env.get_template("index_zh.md.j2")
                logger.info("Using Chinese Markdown template: index_zh.md.j2")
            except jinja2.exceptions.TemplateNotFound:
                logger.warning("Chinese Markdown template 'index_zh.md.j2' not found. Falling back to default 'index.md.j2'.")
                template = env.get_template("index.md.j2") 
        else:
            template = env.get_template("index.md.j2")
        
        markdown_content = template.render(
            documentation=documentation,
            doc_config=(agent_config_obj.doc_config if agent_config_obj else None), # Pass doc_config from AgentConfig
            sections_to_render=documentation.get('section_render_order', []),
            generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        output_filename_base = documentation.get("output_filename_base", documentation.get("repo_name", "documentation"))
        md_file = output_dir / f"{output_filename_base}.md"

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        logger.info(f"Final Markdown documentation generated at {md_file}")
        return md_file
    except jinja2.exceptions.TemplateNotFound:
        template_to_report = "index_zh.md.j2" if language == "zh" else "index.md.j2"
        logger.error(f"Markdown template '{template_to_report}' not found in '{template_dir}'.")
        logger.warning(f"Please create the Markdown template '{template_to_report}' to generate the full Markdown document.")
        
        output_filename_base = documentation.get("output_filename_base", documentation.get("repo_name", "documentation"))
        dummy_md_file = output_dir / f"{output_filename_base}_TEMPLATE_MISSING.md"

        error_message = f"# Markdown Generation Error\n\nTemplate `{template_to_report}` not found in `{template_dir}`.\nPlease create this template to enable Markdown output."
        with open(dummy_md_file, "w", encoding="utf-8") as f:
            f.write(error_message)
        logger.info(f"Created a placeholder error file at {dummy_md_file} due to missing template.")
        return dummy_md_file
    except Exception as e:
        logger.error(f"Error in generate_final_markdown: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def extract_tech_stack(documentation):
    tech_stack = []
    arch_content_source = documentation.get("architecture", {}) 
    if isinstance(arch_content_source, dict) and "content" in arch_content_source : 
        arch_content = arch_content_source.get("content", "")
    elif isinstance(arch_content_source, str): 
        arch_content = arch_content_source
    else: 
        arch_content = ""


    tech_patterns = [
        r'(?:built with|uses|based on|powered by|technology stack|dependencies include)[^\n.]*?((?:[A-Za-z0-9_\-]+(?:\.js)?(?:,|\s|and)?)+)',
        r'(?:technologies used|frameworks|libraries|languages)[^\n.]*?((?:[A-Za-z0-9_\-]+(?:\.js)?(?:,|\s|and)?)+)',
        r'requirement(?:s)?[^\n.]*?((?:[A-Za-z0-9_\-]+(?:\.js)?(?:,|\s|and)?)+)'
    ]
    
    for pattern in tech_patterns:
        matches = re.finditer(pattern, arch_content, re.IGNORECASE)
        for match in matches:
            tech_text = match.group(1)
            techs = re.findall(r'([A-Za-z0-9_\-\.]+(?:\.js)?)', tech_text)
            for tech in techs:
                if tech.lower() not in ['and', 'or', 'the', 'with', 'using', 'based', 'on', 'built']:
                    tech_stack.append(tech)
    
    if not tech_stack:
        if "package.json" in arch_content.lower():
            tech_stack.append("Node.js")
            tech_stack.append("JavaScript")
        if "requirements.txt" in arch_content.lower():
            tech_stack.append("Python")
        if "Gemfile" in arch_content.lower():
            tech_stack.append("Ruby")
        if "composer.json" in arch_content.lower():
            tech_stack.append("PHP")
    
    tech_stack = list(set(tech_stack))
    
    if not tech_stack:
        tech_stack = ["Not specified"]
    
    return "\n".join([f'<span class="tech-badge">{tech}</span>' for tech in tech_stack])


def generate_sources_html(sources):
    result = {}
    
    for section, source_list in sources.items():
        if not source_list:
            result[section] = ""
            continue
            
        html = ""
        for source in source_list:
            file_path = source.get("file", "")
            lines = source.get("lines", "")
            github_url = source.get("github_url", "")
            
            if github_url:
                html += f'''
                <div class="source-file">
                    <svg class="source-file-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
                        <path fill-rule="evenodd" d="M3.75 1.5a.25.25 0 00-.25.25v11.5c0 .138.112.25.25.25h8.5a.25.25 0 00.25-.25V6H9.75A1.75 1.75 0 018 4.25V1.5H3.75zm5.75.56v2.19c0 .138.112.25.25.25h2.19L9.5 2.06zM2 1.75C2 .784 2.784 0 3.75 0h5.086c.464 0 .909.184 1.237.513l3.414 3.414c.329.328.513.773.513 1.237v8.086A1.75 1.75 0 0112.25 15h-8.5A1.75 1.75 0 012 13.25V1.75z"></path>
                    </svg>
                    <a href="{github_url}" target="_blank" class="source-file-link">
                        <span class="source-file-path">{file_path}</span>
                        {f'<span class="source-line-numbers">{lines}</span>' if lines else ''}
                    </a>
                </div>
                '''
            else:
                html += f'''
                <div class="source-file">
                    <svg class="source-file-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
                        <path fill-rule="evenodd" d="M3.75 1.5a.25.25 0 00-.25.25v11.5c0 .138.112.25.25.25h8.5a.25.25 0 00.25-.25V6H9.75A1.75 1.75 0 018 4.25V1.5H3.75zm5.75.56v2.19c0 .138.112.25.25.25h2.19L9.5 2.06zM2 1.75C2 .784 2.784 0 3.75 0h5.086c.464 0 .909.184 1.237.513l3.414 3.414c.329.328.513.773.513 1.237v8.086A1.75 1.75 0 0112.25 15h-8.5A1.75 1.75 0 012 13.25V1.75z"></path>
                    </svg>
                    <span class="source-file-path">{file_path}</span>
                    {f'<span class="source-line-numbers">{lines}</span>' if lines else ''}
                </div>
                '''
        
        result[section] = html
    
    return result


def generate_components_html(components):
    if not components:
        return ""
        
    html = ""
    for component_name, component_data in components.items():
        purpose = component_data.get("purpose", "")
        usage = component_data.get("usage", "")
        methods = component_data.get("methods", [])
        code_example = component_data.get("code_example", "")
        
        methods_html = ""
        if methods:
            methods_html = "<p><strong>Key Methods:</strong></p><ul>"
            for method in methods:
                methods_html += f"<li><code>{method}</code></li>"
            methods_html += "</ul>"
        
        code_html = ""
        if code_example:
            code_html = f'<pre><code class="language-python">{code_example}</code></pre>'
        
        html += f'''
        <div id="component-{component_name.lower().replace(' ', '-')}" class="card">
            <div class="card-header">{component_name}</div>
            <div class="card-body">
                <p><strong>Purpose:</strong> {purpose}</p>
                <p><strong>Usage:</strong> {usage}</p>
                {methods_html}
                {code_html}
            </div>
        </div>
        '''
    
    return html


def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate documentation for GitHub repositories")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "repo_url",
        type=str,
        help="GitHub repository URL (e.g., https://github.com/metauto-ai/gptswarm)",
        nargs="?",
        default=None
    )
    group.add_argument(
        "--local-path",
        type=str,
        help="Local path to the project directory."
    )
    
    parser.add_argument(
        "--output_dir", 
        type=str, 
        default="./repo_docs",
        help="Directory to save documentation"
    )
    parser.add_argument(
        "--include_dirs",
        nargs="+",
        default=["src", "lib", "app", "tests", "docs"],
        help="Directories to include in search"
    )
    parser.add_argument(
        "--exclude_dirs",
        nargs="+",
        default=[
            "__pycache__", "env", ".git", "venv", "node_modules", "build", 
            "dist", "logs", "output", "tmp", "temp", "cache"
        ],
        help="Directories to exclude in search"
    )
    parser.add_argument(
        "--exclude_files",
        nargs="+",
        default=[".DS_Store", "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.class"],
        help="Files to exclude in search"
    )
    parser.add_argument(
        "--setting",
        type=str,
        default="gray_box",
        choices=["gray_box", "black_box"],
        help="Setting for the JudgeAgent"
    )
    parser.add_argument(
        "--planning",
        type=str,
        default="efficient (no planning)",
        choices=["planning", "comprehensive (no planning)", "efficient (no planning)"],
        help="Planning strategy"
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["html", "markdown"],
        default="html",
        help="Output format for the documentation (html or markdown)."
    )
    parser.add_argument(
        "--language",
        type=str,
        choices=["en", "zh"],
        default="en",
        help="Language for documentation generation (en or zh)."
    )
    parser.add_argument(
        '--assess-quality', 
        action='store_true', 
        help='Enable basic code quality assessment during documentation generation.'
    )
    parser.add_argument(
        "--config-file",
        type=str,
        default=None,
        help="Path to a YAML configuration file for document structure and content (e.g., openwiki_config.yaml)."
    )
    
    return parser.parse_args()


def get_repo_url_interactive():
    print("\n🔍 GitHub Repository Documentation Generator 🔍")
    print("-" * 50)
    print("Generate comprehensive documentation for GitHub repositories")
    print("-" * 50)
    
    repo_url = input("\nEnter GitHub repository URL (e.g., https://github.com/username/repository): ")
    
    if not repo_url.startswith("https://github.com/"):
        print("❌ Invalid GitHub URL. Please provide a valid URL (e.g., https://github.com/metauto-ai/gptswarm)")
        return get_repo_url_interactive()
    
    return repo_url


def main():
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__) 
    
    args = parse_arguments()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    judge_dir = output_dir / "judge"
    judge_dir.mkdir(parents=True, exist_ok=True)
    
    repo_dir: Path
    repo_url: Optional[str]

    if args.local_path:
        project_path_str = args.local_path
        repo_dir = Path(project_path_str).resolve()
        if not repo_dir.is_dir():
            logger.error(f"Local path specified is not a valid directory: {repo_dir}")
            sys.exit(1)
        repo_url = None 
        logger.info(f"Processing local project path: {repo_dir}")
    else:
        repo_url = args.repo_url 
        if not repo_url: 
             repo_url = get_repo_url_interactive()
        logger.info(f"Processing GitHub repository URL: {repo_url}")
        repo_dir = download_github_repo(repo_url, output_dir)

    start_time = time.time()
    
    try:
        include_dirs = args.include_dirs.copy()
        common_code_dirs = ["src", "lib", "app", "core", "utils", "scripts", "tools", "services"]
        
        for common_dir in common_code_dirs:
            if (repo_dir / common_dir).exists() and common_dir not in include_dirs:
                include_dirs.append(common_dir)
        
        agent_config = AgentConfig(
            include_dirs=include_dirs,
            exclude_dirs=args.exclude_dirs,
            exclude_files=args.exclude_files,
            setting=args.setting,
            planning=args.planning,
            judge_dir=judge_dir,
            workspace_dir=repo_dir.parent, 
            instance_dir=judge_dir,
            output_format=args.output_format,
            local_path=args.local_path, 
            language=args.language,
            assess_quality=args.assess_quality,
            doc_config_path=args.config_file 
        )
        
        agent_config.doc_config = load_doc_config(agent_config.doc_config_path)
        
        if agent_config.doc_config:
            logger.info(f"Successfully loaded document structure from: {agent_config.doc_config_path or 'openwiki_config.yaml (default)'}")
        elif args.config_file: 
            logger.warning(f"Failed to load or validate document structure from specified config: {args.config_file}. Proceeding with default structure.")
        else: 
            logger.info("No document structure configuration file specified or default 'openwiki_config.yaml' not found. Proceeding with default structure.")

        
        logger.info(f"Agent configuration: include={agent_config.include_dirs}, exclude={agent_config.exclude_dirs}, "
                    f"files={agent_config.exclude_files}, setting={agent_config.setting}, planning={agent_config.planning}, "
                    f"output_format={agent_config.output_format}, local_path={agent_config.local_path}, language={agent_config.language}, "
                    f"assess_quality={agent_config.assess_quality}, doc_config_path={agent_config.doc_config_path}")
        
        doc_file = generate_repo_documentation(repo_dir, output_dir, agent_config, repo_url)
        
        total_time = time.time() - start_time
        logger.info(f"Total documentation time: {total_time:.2f} seconds")
        
        json_file_path = doc_file 
        final_doc_path: Optional[Path] = None
        
        doc_data_for_naming = {}
        try:
            with open(json_file_path, 'r') as f:
                doc_data_for_naming = json.load(f)
        except Exception: 
            pass
        
        output_filename_base = doc_data_for_naming.get("output_filename_base", repo_dir.name)
        if not output_filename_base.strip(): output_filename_base = repo_dir.name


        if args.output_format == "markdown":
            expected_md_file = output_dir / f"{output_filename_base}.md"
            dummy_md_file = output_dir / f"{output_filename_base}_TEMPLATE_MISSING.md"
            if dummy_md_file.exists(): 
                final_doc_path = dummy_md_file
            else: 
                final_doc_path = expected_md_file
        else: 
            final_doc_path = output_dir / f"{output_filename_base}.html"
        
        try:
            with open(json_file_path, 'r') as f: 
                doc_data = json.load(f)
            
            doc_data["generated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            doc_data["generation_time_seconds"] = total_time
            
            with open(json_file_path, 'w') as f: 
                json.dump(doc_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not update documentation metadata: {e}")
        
        print("\n" + "=" * 80)
        print(f"✅ Documentation generated successfully in {total_time:.2f} seconds!")
        print("-" * 80)
        print(f"📄 JSON Data: {json_file_path}") 

        if final_doc_path and final_doc_path.exists():
            if final_doc_path.name.endswith("_TEMPLATE_MISSING.md"):
                print(f"⚠️ Markdown Documentation (Template Missing): {final_doc_path}")
                print(f"   A placeholder file was created. Please create 'index.md.j2' or 'index_zh.md.j2' in 'scripts/templates/markdown/'.")
            elif args.output_format == "markdown":
                print(f"🖋️ Markdown Documentation: {final_doc_path}")
                print(f"🔗 Open Markdown file: {final_doc_path.absolute()}")
            else: # HTML
                print(f"🌐 HTML Documentation: {final_doc_path}")
                print(f"🔗 Open HTML file in browser: file://{final_doc_path.absolute()}")
        elif final_doc_path : 
             print(f"Output document ({args.output_format}) was expected at '{final_doc_path}' but may not have been generated successfully (file not found).")
        else: 
            print(f"Output document ({args.output_format}) could not be determined or was not generated.")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"Error generating documentation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

[end of scripts/run_wiki.py]
