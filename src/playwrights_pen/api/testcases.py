"""Test cases API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import TestParser
from ..models import TestCase
from ..storage import Repository

router = APIRouter(prefix="/testcases", tags=["testcases"])
repository = Repository()


class CreateTestCaseRequest(BaseModel):
    """Request body for creating a test case."""
    
    name: str
    description: str
    tags: list[str] = []
    parse_now: bool = True


class UpdateTestCaseRequest(BaseModel):
    """Request body for updating a test case."""
    
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TestCaseResponse(BaseModel):
    """Response model for test case."""
    
    id: str
    name: str
    description: str
    tags: list[str]
    step_count: int
    has_steps: bool


@router.post("", response_model=TestCaseResponse)
async def create_testcase(request: CreateTestCaseRequest) -> TestCaseResponse:
    """Create a new test case.
    
    If parse_now is True, the natural language description will be
    parsed into test steps immediately using LLM.
    """
    testcase = TestCase(
        name=request.name,
        description=request.description,
        tags=request.tags,
    )
    
    if request.parse_now:
        parser = TestParser()
        testcase.steps = await parser.parse(request.description)
        testcase.steps = parser.identify_key_steps(testcase.steps)
    
    repository.save_testcase(testcase)
    
    return TestCaseResponse(
        id=testcase.id,
        name=testcase.name,
        description=testcase.description,
        tags=testcase.tags,
        step_count=len(testcase.steps),
        has_steps=bool(testcase.steps),
    )


@router.get("", response_model=list[TestCaseResponse])
async def list_testcases() -> list[TestCaseResponse]:
    """List all test cases."""
    testcases = repository.list_testcases()
    return [
        TestCaseResponse(
            id=tc.id,
            name=tc.name,
            description=tc.description,
            tags=tc.tags,
            step_count=len(tc.steps),
            has_steps=bool(tc.steps),
        )
        for tc in testcases
    ]


@router.get("/{testcase_id}")
async def get_testcase(testcase_id: str) -> TestCase:
    """Get a test case by ID with full details."""
    testcase = repository.get_testcase(testcase_id)
    if not testcase:
        raise HTTPException(status_code=404, detail="Test case not found")
    return testcase


@router.put("/{testcase_id}", response_model=TestCaseResponse)
async def update_testcase(
    testcase_id: str,
    request: UpdateTestCaseRequest,
) -> TestCaseResponse:
    """Update a test case."""
    testcase = repository.get_testcase(testcase_id)
    if not testcase:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    if request.name is not None:
        testcase.name = request.name
    if request.tags is not None:
        testcase.tags = request.tags
    if request.description is not None:
        testcase.description = request.description
        # Re-parse if description changed
        parser = TestParser()
        testcase.steps = await parser.parse(request.description)
        testcase.steps = parser.identify_key_steps(testcase.steps)
    
    repository.save_testcase(testcase)
    
    return TestCaseResponse(
        id=testcase.id,
        name=testcase.name,
        description=testcase.description,
        tags=testcase.tags,
        step_count=len(testcase.steps),
        has_steps=bool(testcase.steps),
    )


@router.delete("/{testcase_id}")
async def delete_testcase(testcase_id: str) -> dict:
    """Delete a test case."""
    if not repository.delete_testcase(testcase_id):
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"deleted": True}


@router.post("/{testcase_id}/parse")
async def parse_testcase(testcase_id: str) -> TestCase:
    """Parse or re-parse a test case's natural language description."""
    testcase = repository.get_testcase(testcase_id)
    if not testcase:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    parser = TestParser()
    testcase.steps = await parser.parse(testcase.description)
    testcase.steps = parser.identify_key_steps(testcase.steps)
    repository.save_testcase(testcase)
    
    return testcase
