"""Configuration management for PlaywrightsPen."""

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Search for .env file starting from CWD, walking up to project root."""
    current = Path.cwd().resolve()
    for _ in range(10):  # max 10 levels up
        env_path = current / ".env"
        if env_path.exists():
            return str(env_path)
        # Also check for pyproject.toml as project root marker
        if (current / "pyproject.toml").exists():
            return str(env_path) if env_path.exists() else None
        parent = current.parent
        if parent == current:
            break
        current = parent
    return ".env"  # fallback to default


class ConfirmationMode(str, Enum):
    """Confirmation mode for first-run execution."""
    
    EVERY_STEP = "every_step"  # 每步确认
    KEY_STEPS = "key_steps"    # 仅关键步骤确认
    NONE = "none"              # 完全自动


class DataInputMode(str, Enum):
    """Mode for handling data placeholders in test steps."""
    
    PRESET = "preset"       # 预置数据 - 从配置/环境变量读取
    PROMPT = "prompt"       # 交互询问 - 运行时暂停等待用户输入
    GENERATE = "generate"   # 自动生成 - LLM 生成测试数据


class RecordingMode(str, Enum):
    """Recording mode for test execution."""
    
    NONE = "none"           # 不录制
    MINIMAL = "minimal"     # 仅操作序列 + 最终截图
    STANDARD = "standard"   # 每步截图 + 快照 (推荐默认)
    FULL = "full"           # 视频 + 详细日志


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # LLM Configuration
    llm_api_key: str = Field(
        default="",
        description="API key for LLM service (OpenAI compatible)",
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for LLM API",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="Model name to use",
    )
    
    # Playwright MCP Configuration
    mcp_command: str = Field(
        default="npx",
        description="Command to start MCP server",
    )
    mcp_args: str = Field(
        default="@playwright/mcp@latest",
        description="Arguments for MCP command (space-separated)",
    )
    browser_headless: bool = Field(
        default=False,
        description="Whether to run browser in headless mode",
    )
    
    # Electron Configuration
    electron_executable_path: str = Field(
        default="",
        description="Path to packaged Electron app (.exe, .app, AppImage)",
    )
    electron_project_path: str = Field(
        default="",
        description="Path to Electron project directory (for dev mode)",
    )
    
    # Execution Configuration
    default_confirmation_mode: ConfirmationMode = Field(
        default=ConfirmationMode.KEY_STEPS,
        description="Default confirmation mode for first-run execution",
    )
    default_recording_mode: RecordingMode = Field(
        default=RecordingMode.STANDARD,
        description="Default recording mode: none, minimal, standard (default), full",
    )
    default_data_input_mode: DataInputMode = Field(
        default=DataInputMode.PROMPT,
        description="Default data input mode: preset, prompt (default), generate",
    )
    
    # Service Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # Storage Configuration
    data_dir: Path = Field(
        default=Path("./data"),
        description="Directory for storing data",
    )
    
    # Database Configuration
    database_url: str = Field(
        default="",
        description="PostgreSQL connection URL (postgresql+asyncpg://user:pass@host:port/db). Empty uses SQLite.",
    )
    
    @property
    def mcp_args_list(self) -> list[str]:
        """Parse MCP args string into list."""
        return self.mcp_args.split()
    
    @property
    def testcases_dir(self) -> Path:
        """Directory for test case files."""
        path = self.data_dir / "testcases"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def sessions_dir(self) -> Path:
        """Directory for session files."""
        path = self.data_dir / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def snapshots_dir(self) -> Path:
        """Directory for page snapshots."""
        path = self.data_dir / "snapshots"
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
