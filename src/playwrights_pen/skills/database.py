"""Database skill for LLM to query and validate database state."""

import asyncio
from typing import Any
from pydantic import BaseModel, Field

from ..config import settings


class DatabaseConfig(BaseModel):
    """Database connection configuration."""
    
    driver: str = Field(
        default="postgresql",
        description="Database driver: postgresql, mysql"
    )
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(...)
    username: str = Field(...)
    password: str = Field(default="")
    
    @property
    def connection_string(self) -> str:
        """Generate connection string."""
        if self.driver == "postgresql":
            return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.driver == "mysql":
            return f"mysql+aiomysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"Unsupported driver: {self.driver}")


class QueryResult(BaseModel):
    """Result of a database query."""
    
    success: bool = True
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    error: str | None = None
    
    @property
    def first(self) -> dict[str, Any] | None:
        """Get first row or None."""
        return self.rows[0] if self.rows else None
    
    def get_value(self, column: str, row_index: int = 0) -> Any:
        """Get a specific column value from a row."""
        if row_index < len(self.rows):
            return self.rows[row_index].get(column)
        return None


class DatabaseSkill:
    """Skill for querying databases during test execution.
    
    This skill allows the LLM to:
    - Query database to check data state
    - Validate that operations were persisted correctly
    - Extract data for use in subsequent steps
    
    Example usage in test:
        assertion:
          type: database
          query: "SELECT status FROM orders WHERE id = '{{order_id}}'"
          expect_column: status
          expect_value: COMPLETED
    """
    
    def __init__(self, config: DatabaseConfig | None = None) -> None:
        """Initialize database skill.
        
        Args:
            config: Database configuration. If None, uses settings.
        """
        self.config = config
        self._engine = None
    
    async def connect(self) -> None:
        """Establish database connection."""
        if self._engine:
            return
        
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            
            conn_str = self.config.connection_string if self.config else settings.database_url
            self._engine = create_async_engine(conn_str, echo=False)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to database: {e}")
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
    
    async def query(self, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
        """Execute a SQL query and return results.
        
        Args:
            sql: SQL query string (use :param_name for parameters)
            params: Optional parameter dict for parameterized queries
            
        Returns:
            QueryResult with rows and metadata
        """
        if not self._engine:
            await self.connect()
        
        try:
            from sqlalchemy import text
            
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql), params or {})
                
                # Fetch all rows as dicts
                rows = [dict(row._mapping) for row in result.fetchall()]
                
                return QueryResult(
                    success=True,
                    rows=rows,
                    row_count=len(rows),
                )
        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
            )
    
    async def assert_value(
        self,
        sql: str,
        column: str,
        expected: Any,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Assert that a query returns an expected value.
        
        Args:
            sql: SQL query
            column: Column to check
            expected: Expected value
            params: Query parameters
            
        Returns:
            Tuple of (success, message)
        """
        result = await self.query(sql, params)
        
        if not result.success:
            return False, f"Query failed: {result.error}"
        
        if result.row_count == 0:
            return False, f"Query returned no rows"
        
        actual = result.get_value(column)
        
        if actual == expected:
            return True, f"✓ {column} = {expected}"
        else:
            return False, f"✗ Expected {column} = {expected}, got {actual}"
    
    async def assert_exists(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Assert that a query returns at least one row.
        
        Args:
            sql: SQL query
            params: Query parameters
            
        Returns:
            Tuple of (success, message)
        """
        result = await self.query(sql, params)
        
        if not result.success:
            return False, f"Query failed: {result.error}"
        
        if result.row_count > 0:
            return True, f"✓ Found {result.row_count} row(s)"
        else:
            return False, f"✗ Expected at least 1 row, found 0"
    
    async def assert_count(
        self,
        sql: str,
        expected_count: int,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Assert that a query returns expected number of rows.
        
        Args:
            sql: SQL query
            expected_count: Expected row count
            params: Query parameters
            
        Returns:
            Tuple of (success, message)
        """
        result = await self.query(sql, params)
        
        if not result.success:
            return False, f"Query failed: {result.error}"
        
        if result.row_count == expected_count:
            return True, f"✓ Found {result.row_count} row(s)"
        else:
            return False, f"✗ Expected {expected_count} row(s), found {result.row_count}"
    
    # Convenience method for LLM description
    def get_skill_description(self) -> str:
        """Get description of this skill for LLM context."""
        return """
Database Skill: You can query the database to verify data state.

Available operations:
1. query(sql) - Execute SQL and get results
2. assert_value(sql, column, expected) - Check a column value
3. assert_exists(sql) - Check that rows exist
4. assert_count(sql, count) - Check row count

Example:
- Check order status: query("SELECT status FROM orders WHERE id = '123'")
- Verify data saved: assert_value("SELECT name FROM users WHERE id = 1", "name", "John")
"""


# Singleton for easy access
_db_skill: DatabaseSkill | None = None


def get_database_skill(config: DatabaseConfig | None = None) -> DatabaseSkill:
    """Get or create database skill instance."""
    global _db_skill
    if _db_skill is None:
        _db_skill = DatabaseSkill(config)
    return _db_skill
