"""Test step model definitions."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of browser actions."""
    
    NAVIGATE = "navigate"        # 导航到 URL
    CLICK = "click"              # 点击元素
    TYPE = "type"                # 输入文本
    SELECT = "select"            # 选择下拉选项
    HOVER = "hover"              # 悬停
    SCROLL = "scroll"            # 滚动
    WAIT = "wait"                # 等待
    SCREENSHOT = "screenshot"    # 截图
    ASSERT = "assert"            # 断言
    EXECUTE_JS = "execute_js"    # 执行 JavaScript
    
    # New action types for modular execution and data
    EXTRACT = "extract"          # 从页面提取数据保存到上下文
    DB_ASSERT = "db_assert"      # 数据库断言
    DB_QUERY = "db_query"        # 数据库查询并保存结果
    USE_MODULE = "use_module"    # 引用可复用模块
    NATURAL_LANGUAGE = "natural_language"  # 自然语言指令
    CONDITIONAL = "conditional"  # 条件分支


class AssertionType(str, Enum):
    """Types of assertions for ASSERT action."""
    
    TEXT_CONTAINS = "text_contains"      # 文本包含
    TEXT_EQUALS = "text_equals"          # 文本相等
    ELEMENT_VISIBLE = "element_visible"  # 元素可见
    ELEMENT_EXISTS = "element_exists"    # 元素存在
    URL_CONTAINS = "url_contains"        # URL 包含
    URL_EQUALS = "url_equals"            # URL 相等
    TITLE_CONTAINS = "title_contains"    # 标题包含
    TITLE_EQUALS = "title_equals"        # 标题相等


class TestStep(BaseModel):
    """A single step in a test case."""
    
    action: ActionType = Field(description="Type of action to perform")
    
    # Action parameters
    url: str | None = Field(default=None, description="URL for navigate action")
    text: str | None = Field(default=None, description="Text for type action")
    selector_hint: str | None = Field(
        default=None,
        description="Human-readable element description for LLM to locate",
    )
    
    # Assertion parameters
    assertion_type: AssertionType | None = Field(
        default=None,
        description="Type of assertion for assert action",
    )
    expected_value: str | None = Field(
        default=None,
        description="Expected value for assertion",
    )
    
    # Recorded execution info (populated after first run)
    recorded_ref: str | None = Field(
        default=None,
        description="Recorded element reference from accessibility tree",
    )
    recorded_snapshot_id: str | None = Field(
        default=None,
        description="ID of accessibility snapshot when this step was recorded",
    )
    
    # Step metadata
    is_key_step: bool = Field(
        default=False,
        description="Whether this is a key step requiring confirmation",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of this step",
    )
    
    # Extra parameters for flexibility
    extra_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for specific actions",
    )
    
    # Data placeholders for interactive data handling
    data_placeholders: dict[str, "DataPlaceholder"] = Field(
        default_factory=dict,
        description="Data placeholders detected in this step, e.g. {{username}}",
    )
    
    # Extract action fields
    save_as: str | None = Field(
        default=None,
        description="Variable name to save extracted data to context",
    )
    
    # Database action fields
    db_query: str | None = Field(
        default=None,
        description="SQL query for db_assert or db_query actions",
    )
    db_column: str | None = Field(
        default=None,
        description="Column to check in db_assert",
    )
    db_expected: str | None = Field(
        default=None,
        description="Expected value for db_assert",
    )
    
    # Module action fields
    module_name: str | None = Field(
        default=None,
        description="Name of module to use for use_module action",
    )
    module_params: dict[str, str] = Field(
        default_factory=dict,
        description="Parameters to pass to module",
    )
    skip_if_complete: bool = Field(
        default=True,
        description="Skip module if already completed in this session",
    )
    
    # Conditional action fields
    condition: str | None = Field(
        default=None,
        description="Natural language condition for conditional action",
    )
    then_steps: list["TestStep"] = Field(
        default_factory=list,
        description="Steps to execute if condition is true",
    )
    else_steps: list["TestStep"] = Field(
        default_factory=list,
        description="Steps to execute if condition is false",
    )


class DataPlaceholder(BaseModel):
    """Configuration for a data placeholder in test steps.
    
    Placeholders use syntax: {{variable_name}}
    Example: "输入用户名 {{username}} 和密码 {{password}}"
    """
    
    name: str = Field(description="Placeholder variable name")
    label: str = Field(default="", description="Human-readable label for prompts")
    mode: str = Field(
        default="prompt",
        description="Data input mode: preset, prompt, or generate",
    )
    
    # For preset mode
    default_value: str | None = Field(
        default=None,
        description="Default value for preset mode",
    )
    env_var: str | None = Field(
        default=None,
        description="Environment variable name to read value from",
    )
    
    # For generate mode
    generate_hint: str | None = Field(
        default=None,
        description="Hint for LLM when generating test data",
    )
    
    # Runtime value (populated during execution)
    resolved_value: str | None = Field(
        default=None,
        description="Resolved value after data injection",
    )
    
    # Metadata
    is_sensitive: bool = Field(
        default=False,
        description="Whether this data is sensitive (password, token, etc.)",
    )


# Resolve forward reference
TestStep.model_rebuild()

