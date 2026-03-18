"""Repository for test cases and sessions storage."""

import json
from pathlib import Path
from typing import TypeVar

from ..config import settings
from ..models import Session, TestCase

T = TypeVar("T", TestCase, Session)


class Repository:
    """File-based repository for test cases and sessions."""
    
    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize repository.
        
        Args:
            data_dir: Base directory for data storage
        """
        self.data_dir = data_dir or settings.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def testcases_dir(self) -> Path:
        """Directory for test cases."""
        path = self.data_dir / "testcases"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def sessions_dir(self) -> Path:
        """Directory for sessions."""
        path = self.data_dir / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # ==================== Test Cases ====================
    
    def save_testcase(self, testcase: TestCase) -> None:
        """Save a test case.
        
        Args:
            testcase: Test case to save
        """
        file_path = self.testcases_dir / f"{testcase.id}.json"
        file_path.write_text(testcase.model_dump_json(indent=2), encoding="utf-8")
    
    def get_testcase(self, testcase_id: str) -> TestCase | None:
        """Get a test case by ID.
        
        Args:
            testcase_id: Test case ID
            
        Returns:
            Test case or None if not found
        """
        file_path = self.testcases_dir / f"{testcase_id}.json"
        if not file_path.exists():
            return None
        
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return TestCase.model_validate(data)
    
    def list_testcases(self) -> list[TestCase]:
        """List all test cases.
        
        Returns:
            List of test cases
        """
        testcases = []
        for file_path in self.testcases_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                testcases.append(TestCase.model_validate(data))
            except (json.JSONDecodeError, Exception):
                continue
        return sorted(testcases, key=lambda x: x.created_at, reverse=True)
    
    def delete_testcase(self, testcase_id: str) -> bool:
        """Delete a test case.
        
        Args:
            testcase_id: Test case ID
            
        Returns:
            True if deleted, False if not found
        """
        file_path = self.testcases_dir / f"{testcase_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    # ==================== Sessions ====================
    
    def save_session(self, session: Session) -> None:
        """Save a session.
        
        Args:
            session: Session to save
        """
        file_path = self.sessions_dir / f"{session.id}.json"
        file_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    
    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session or None if not found
        """
        file_path = self.sessions_dir / f"{session_id}.json"
        if not file_path.exists():
            return None
        
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return Session.model_validate(data)
    
    def list_sessions(self, test_case_id: str | None = None) -> list[Session]:
        """List sessions, optionally filtered by test case.
        
        Args:
            test_case_id: Optional filter by test case ID
            
        Returns:
            List of sessions
        """
        sessions = []
        for file_path in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                session = Session.model_validate(data)
                if test_case_id is None or session.test_case_id == test_case_id:
                    sessions.append(session)
            except (json.JSONDecodeError, Exception):
                continue
        return sorted(sessions, key=lambda x: x.started_at or x.id, reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if deleted, False if not found
        """
        file_path = self.sessions_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def get_latest_session(self, test_case_id: str) -> Session | None:
        """Get the latest session for a test case.
        
        Args:
            test_case_id: Test case ID
            
        Returns:
            Most recent session or None
        """
        sessions = self.list_sessions(test_case_id)
        return sessions[0] if sessions else None
