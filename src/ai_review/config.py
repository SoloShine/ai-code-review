"""Configuration system for AI Code Review."""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from enum import Enum


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


@dataclass
class OllamaConfig:
    """Ollama backend configuration."""
    base_url: str = "http://localhost:11434"
    model: str = "codellama"
    timeout: int = 30


@dataclass
class OpenAICompatibleConfig:
    """OpenAI compatible backend configuration."""
    base_url: str = "http://localhost:8000/v1"
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-4"
    timeout: int = 30
    max_tokens: int = 16000


@dataclass
class LLMConfig:
    """LLM backend configuration."""
    backend: str = "ollama"
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai_compatible: OpenAICompatibleConfig = field(default_factory=OpenAICompatibleConfig)

    def get_backend_config(self) -> Union[OllamaConfig, OpenAICompatibleConfig]:
        """Get the configuration for the selected backend."""
        if self.backend == "ollama":
            return self.ollama
        elif self.backend == "openai_compatible":
            return self.openai_compatible
        else:
            raise ConfigError(f"Unknown backend: {self.backend}")


@dataclass
class RulesFilterConfig:
    """Rules filtering configuration."""
    severities: List[str] = field(default_factory=lambda: ["error"])


@dataclass
class HookConfig:
    """Pre-commit hook configuration."""
    timeout: int = 60
    block_on: List[str] = field(default_factory=lambda: ["CRITICAL", "ERROR"])
    context: bool = False
    rules_filter: RulesFilterConfig = field(default_factory=RulesFilterConfig)
    bypass_message_patterns: List[str] = field(default_factory=list)
    bypass_env_vars: List[str] = field(default_factory=list)
    llm_override: Optional[LLMConfig] = None


@dataclass
class PostCommitConfig:
    """Post-commit hook configuration."""
    enabled: bool = True
    llm_override: Optional[LLMConfig] = None


@dataclass
class MemoryConfig:
    """Memory management configuration."""
    enabled: bool = True
    decay_days: int = 30
    risk_threshold: int = 5
    reminder: Dict[str, int] = field(default_factory=lambda: {
        "full": 10,
        "short": 5,
        "minimal": 3
    })


@dataclass
class ReviewConfig:
    """Review configuration."""
    group_threshold: int = 3
    triage_threshold: int = 2


@dataclass
class ContextConfig:
    """Context configuration."""
    budget: Dict[str, int] = field(default_factory=lambda: {
        "default": 5000,
        "medium": 15000,
        "large": 50000,
        "max": 100000
    })
    auto: Dict[str, bool] = field(default_factory=lambda: {
        "file_tree": True,
        "git_log": True,
        "diff_stats": True,
        "nearby_files": True
    })


@dataclass
class ReportConfig:
    """Report configuration."""
    dir: str = ".ai-review-reports"
    retention: Dict[str, int] = field(default_factory=lambda: {
        "pass_days": 30,
        "warning_days": 90,
        "blocking_days": 180
    })


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    auto_open: bool = True


@dataclass
class AppConfig:
    """Top-level application configuration."""
    version: str = "0.1.0"
    mode: str = "balanced"
    llm: LLMConfig = field(default_factory=LLMConfig)
    hooks: Dict[str, HookConfig] = field(default_factory=lambda: {
        "pre_commit": HookConfig(),
        "post_commit": PostCommitConfig()
    })
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    rules: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "dirs": [],
        "markdown": True
    })
    exclude: List[str] = field(default_factory=list)
    report: ReportConfig = field(default_factory=ReportConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)


# Mode defaults
MODE_DEFAULTS = {
    "strict": {
        "hooks": {
            "pre_commit": {
                "timeout": 90,
                "block_on": ["CRITICAL", "ERROR", "WARNING"],
                "context": True,
                "rules_filter": {"severities": ["all"]},
                "full_rules": True
            },
            "post_commit": {
                "enabled": False
            }
        },
        "memory": {
            "enabled": False
        }
    },
    "balanced": {
        "hooks": {
            "pre_commit": {
                "timeout": 60,
                "block_on": ["CRITICAL", "ERROR"],
                "context": False,
                "rules_filter": {"severities": ["error"]}
            },
            "post_commit": {
                "enabled": True
            }
        },
        "memory": {
            "enabled": True,
            "risk_threshold": 5
        }
    }
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load a YAML configuration file."""
    if not config_path.exists():
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to load config {config_path}: {e}")


def resolve_config(project_root: Optional[Path] = None) -> AppConfig:
    """Resolve configuration by merging mode defaults, global config, and project config."""
    if project_root is None:
        project_root = Path.cwd()

    # Start with mode defaults
    mode = os.environ.get("AI_REVIEW_MODE", "balanced")
    if mode not in MODE_DEFAULTS:
        raise ConfigError(f"Unknown mode: {mode}. Valid modes: {list(MODE_DEFAULTS.keys())}")

    config_dict = MODE_DEFAULTS[mode].copy()

    # Load global config from home directory
    global_config_path = Path.home() / ".ai-review" / "config.yaml"
    global_config = load_config_file(global_config_path)
    config_dict = deep_merge(config_dict, global_config)

    # Load project config from project root
    project_config_path = project_root / ".ai-review.yaml"
    project_config = load_config_file(project_config_path)
    config_dict = deep_merge(config_dict, project_config)

    # Convert dictionary to AppConfig
    try:
        return _dict_to_app_config(config_dict)
    except Exception as e:
        raise ConfigError(f"Failed to resolve configuration: {e}")


def _dict_to_app_config(config_dict: Dict[str, Any]) -> AppConfig:
    """Convert a dictionary to an AppConfig instance."""
    app_config = AppConfig()

    # Override basic fields
    for field_name in ["version", "mode"]:
        if field_name in config_dict:
            setattr(app_config, field_name, config_dict[field_name])

    # LLM config
    if "llm" in config_dict:
        llm_dict = config_dict["llm"]
        app_config.llm = LLMConfig()
        if "backend" in llm_dict:
            app_config.llm.backend = llm_dict["backend"]

        # Backend-specific configs
        if "ollama" in llm_dict:
            ollama_dict = llm_dict["ollama"]
            app_config.llm.ollama = OllamaConfig(
                base_url=ollama_dict.get("base_url", "http://localhost:11434"),
                model=ollama_dict.get("model", "codellama"),
                timeout=ollama_dict.get("timeout", 30)
            )

        if "openai_compatible" in llm_dict:
            openai_dict = llm_dict["openai_compatible"]
            app_config.llm.openai_compatible = OpenAICompatibleConfig(
                base_url=openai_dict.get("base_url", "http://localhost:8000/v1"),
                api_key_env=openai_dict.get("api_key_env", "OPENAI_API_KEY"),
                model=openai_dict.get("model", "gpt-4"),
                timeout=openai_dict.get("timeout", 30),
                max_tokens=openai_dict.get("max_tokens", 8000)
            )

    # Hooks config
    if "hooks" in config_dict:
        hooks_dict = config_dict["hooks"]

        # Pre-commit hook
        if "pre_commit" in hooks_dict:
            pre_commit_dict = hooks_dict["pre_commit"]
            app_config.hooks["pre_commit"] = HookConfig(
                timeout=pre_commit_dict.get("timeout", 10),
                block_on=pre_commit_dict.get("block_on", ["CRITICAL", "ERROR"]),
                context=pre_commit_dict.get("context", False),
                bypass_message_patterns=pre_commit_dict.get("bypass_message_patterns", []),
                bypass_env_vars=pre_commit_dict.get("bypass_env_vars", [])
            )

            # Rules filter
            if "rules_filter" in pre_commit_dict:
                rules_filter_dict = pre_commit_dict["rules_filter"]
                app_config.hooks["pre_commit"].rules_filter = RulesFilterConfig(
                    severities=rules_filter_dict.get("severities", ["error"])
                )

            # LLM override
            if "llm_override" in pre_commit_dict:
                llm_override_dict = pre_commit_dict["llm_override"]
                app_config.hooks["pre_commit"].llm_override = LLMConfig()
                if "backend" in llm_override_dict:
                    app_config.hooks["pre_commit"].llm_override.backend = llm_override_dict["backend"]

        # Post-commit hook
        if "post_commit" in hooks_dict:
            post_commit_dict = hooks_dict["post_commit"]
            app_config.hooks["post_commit"] = PostCommitConfig(
                enabled=post_commit_dict.get("enabled", True)
            )

            # LLM override
            if "llm_override" in post_commit_dict:
                llm_override_dict = post_commit_dict["llm_override"]
                app_config.hooks["post_commit"].llm_override = LLMConfig()
                if "backend" in llm_override_dict:
                    app_config.hooks["post_commit"].llm_override.backend = llm_override_dict["backend"]

    # Memory config
    if "memory" in config_dict:
        memory_dict = config_dict["memory"]
        app_config.memory = MemoryConfig(
            enabled=memory_dict.get("enabled", True),
            decay_days=memory_dict.get("decay_days", 30),
            risk_threshold=memory_dict.get("risk_threshold", 5)
        )

        if "reminder" in memory_dict:
            app_config.memory.reminder = memory_dict["reminder"]

    # Review config
    if "review" in config_dict:
        review_dict = config_dict["review"]
        app_config.review = ReviewConfig(
            group_threshold=review_dict.get("group_threshold", 3),
            triage_threshold=review_dict.get("triage_threshold", 2)
        )

    # Context config
    if "context" in config_dict:
        context_dict = config_dict["context"]
        app_config.context = ContextConfig()

        if "budget" in context_dict:
            app_config.context.budget = context_dict["budget"]

        if "auto" in context_dict:
            app_config.context.auto = context_dict["auto"]

    # Rules config
    if "rules" in config_dict:
        app_config.rules = config_dict["rules"]

    # Exclude config
    if "exclude" in config_dict:
        app_config.exclude = config_dict["exclude"]

    # Report config
    if "report" in config_dict:
        report_dict = config_dict["report"]
        app_config.report = ReportConfig(
            dir=report_dict.get("dir", ".ai-review-reports")
        )

        if "retention" in report_dict:
            app_config.report.retention = report_dict["retention"]

    # Dashboard config
    if "dashboard" in config_dict:
        dash_dict = config_dict["dashboard"]
        app_config.dashboard = DashboardConfig(
            auto_open=dash_dict.get("auto_open", True)
        )

    return app_config


def validate_config(config: AppConfig) -> List[str]:
    """Validate configuration and return list of warnings/errors."""
    warnings = []

    # Validate backend
    if config.llm.backend not in ["ollama", "openai_compatible"]:
        warnings.append(f"Invalid backend: {config.llm.backend}. Must be 'ollama' or 'openai_compatible'")

    # Validate block_on severities
    valid_severities = ["CRITICAL", "ERROR", "WARNING", "INFO"]
    for severity in config.hooks["pre_commit"].block_on:
        if severity not in valid_severities:
            warnings.append(f"Invalid block_on severity: {severity}. Must be one of {valid_severities}")

    # Validate rules filter severities
    valid_filter_severities = ["all", "critical", "error", "warning", "info"]
    for severity in config.hooks["pre_commit"].rules_filter.severities:
        if severity.lower() not in valid_filter_severities:
            warnings.append(f"Invalid rules filter severity: {severity}. Must be one of {valid_filter_severities}")

    # Validate memory threshold
    if config.memory.risk_threshold < 0:
        warnings.append(f"Memory risk threshold must be positive, got: {config.memory.risk_threshold}")

    # Validate reminder counts
    for reminder_type, count in config.memory.reminder.items():
        if count < 0:
            warnings.append(f"Memory reminder count for {reminder_type} must be positive, got: {count}")

    # Validate review thresholds
    if config.review.group_threshold < 0:
        warnings.append(f"Review group threshold must be positive, got: {config.review.group_threshold}")

    if config.review.triage_threshold < 0:
        warnings.append(f"Review triage threshold must be positive, got: {config.review.triage_threshold}")

    # Validate context budget
    for budget_type, budget in config.context.budget.items():
        if budget < 0:
            warnings.append(f"Context budget for {budget_type} must be positive, got: {budget}")

    # Validate retention days
    for retention_type, days in config.report.retention.items():
        if days < 0:
            warnings.append(f"Report retention for {retention_type} must be positive, got: {days}")

    return warnings