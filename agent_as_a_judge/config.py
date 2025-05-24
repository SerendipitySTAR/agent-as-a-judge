from dataclasses import dataclass
from typing import List, Optional, Dict # Added Dict
from pathlib import Path


@dataclass
class AgentConfig:
    include_dirs: Optional[List[str]] = None
    exclude_dirs: Optional[List[str]] = None
    exclude_files: Optional[List[str]] = None
    setting: str = "gray_box"
    planning: str = "efficient (no planning)"
    judge_dir: Optional[Path] = None
    workspace_dir: Optional[Path] = None
    instance_dir: Optional[Path] = None
    trajectory_file: Optional[Path] = None
    output_format: str = "html"
    local_path: Optional[str] = None
    language: str = "en"
    assess_quality: bool = False
    doc_config_path: Optional[str] = None
    doc_config: Optional[Dict] = None # Or Optional[dict] if Python 3.9+ is assumed

    @classmethod
    def from_args(cls, args):

        return cls(
            include_dirs=(
                args.include_dirs
                if hasattr(args, "include_dirs")
                else ["src", "results", "models", "data"]
            ),
            exclude_dirs=(
                args.exclude_dirs
                if hasattr(args, "exclude_dirs")
                else ["__pycache__", "env"]
            ),
            exclude_files=(
                args.exclude_files if hasattr(args, "exclude_files") else [".DS_Store"]
            ),
            setting=args.setting,
            planning=args.planning,
            judge_dir=Path(args.judge_dir),
            workspace_dir=Path(args.workspace_dir),
            instance_dir=Path(args.instance_dir),
            trajectory_file=(
                Path(args.trajectory_file) if hasattr(args, "trajectory_file") and args.trajectory_file else None
            ),
            output_format=(
                args.output_format if hasattr(args, "output_format") else "html"
            ),
            local_path=(
                args.local_path if hasattr(args, "local_path") else None
            ),
            language=(
                args.language if hasattr(args, "language") else "en"
            ),
            assess_quality=(
                args.assess_quality if hasattr(args, "assess_quality") else False
            ),
            doc_config_path=(
                args.config_file if hasattr(args, "config_file") else None
            ),
            doc_config=None # This will be loaded later
        )
