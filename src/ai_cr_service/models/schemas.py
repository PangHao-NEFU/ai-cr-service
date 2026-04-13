"""Pydantic models for request/response schemas."""

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class CRIssueLevel(str, Enum):
    """Issue severity levels."""
    BUG = "bug"           # Must fix - potential bugs
    SUGGESTION = "suggestion"  # Should consider - improvement suggestions


class MRTriggerRequest(BaseModel):
    """Request model for MR trigger endpoint."""
    project_id: int = Field(..., description="GitLab project ID")
    mr_iid: int = Field(..., description="Merge request IID")
    commit_sha: Optional[str] = Field(None, description="Commit SHA")
    source_branch: Optional[str] = Field(None, description="Source branch name")
    target_branch: Optional[str] = Field(None, description="Target branch name")


class CRIssue(BaseModel):
    """Single code review issue."""
    file_path: str = Field(..., description="File path")
    line_number: int = Field(..., description="Line number")
    level: CRIssueLevel = Field(..., description="Issue severity level")
    title: str = Field(..., description="Issue title")
    content: str = Field(..., description="Issue description and suggestion")
    code_snippet: Optional[str] = Field(None, description="Problematic code snippet")


class AICRResult(BaseModel):
    """AI code review result."""
    total_issues: int = Field(..., description="Total number of issues found")
    issues: List[CRIssue] = Field(default_factory=list, description="List of issues")


class GitLabDiffFile(BaseModel):
    """Represents a changed file in GitLab MR."""
    old_path: Optional[str] = None
    new_path: str
    diff: str
    new_file: bool = False
    renamed_file: bool = False
    deleted_file: bool = False


class WebhookPushEvent(BaseModel):
    """GitLab push webhook event."""
    object_kind: str = "push"
    project_id: int
    ref: str
    before: str
    after: str
    commits: List[dict]


class WebhookMREvent(BaseModel):
    """GitLab merge request webhook event."""
    object_kind: str = "merge_request"
    object_attributes: dict
    project: dict


class APIResponse(BaseModel):
    """Standard API response."""
    code: int = 0
    msg: str = "success"
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    llm_connected: bool
    redis_connected: bool
