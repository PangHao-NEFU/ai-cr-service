"""Code Review API router."""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from ..models.schemas import APIResponse, MRTriggerRequest, AICRResult
from ..services.cr_service import CRService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cr", tags=["Code Review"])

# Global CR service instance
_cr_service: CRService | None = None


def get_cr_service() -> CRService:
    """Get or create CR service instance."""
    global _cr_service
    if _cr_service is None:
        _cr_service = CRService()
    return _cr_service


@router.post(
    "/trigger",
    response_model=APIResponse,
    summary="Trigger AI Code Review",
    description="Trigger AI code review for a GitLab merge request",
)
async def trigger_code_review(
    request: MRTriggerRequest,
    x_gitlab_token: Optional[str] = Header(None, alias="X-GitLab-Token"),
) -> APIResponse:
    """
    Trigger AI code review for a merge request.

    This endpoint is called by GitLab CI or webhook when an MR is created/updated.
    It will:
    1. Fetch the MR changes from GitLab
    2. Perform AI code review
    3. Post comments back to the MR

    Args:
        request: MR trigger request with project_id, mr_iid, etc.
        x_gitlab_token: Optional GitLab token for authentication

    Returns:
        APIResponse with review result
    """
    logger.info(f"Received CR trigger request: project={request.project_id}, mr={request.mr_iid}")

    try:
        cr_service = get_cr_service()
        result = cr_service.perform_code_review(request)

        return APIResponse(
            code=0,
            msg="AI Code Review completed",
            data=result.model_dump(),
        )
    except Exception as e:
        logger.exception(f"Code review failed: {e}")
        return APIResponse(
            code=500,
            msg=f"Code review failed: {str(e)}",
        )


@router.post(
    "/review",
    response_model=AICRResult,
    summary="Perform Code Review (Direct)",
    description="Perform AI code review and return result without posting to GitLab",
)
async def perform_code_review(
    request: MRTriggerRequest,
) -> AICRResult:
    """
    Perform AI code review without posting comments to GitLab.

    Useful for testing or manual review.

    Args:
        request: MR trigger request

    Returns:
        AICRResult with issues found
    """
    logger.info(f"Received direct review request: project={request.project_id}, mr={request.mr_iid}")

    try:
        cr_service = get_cr_service()
        # Get changes only
        diff_files = cr_service.gitlab_service.get_mr_changes(
            request.project_id,
            request.mr_iid,
        )

        if not diff_files:
            return AICRResult(total_issues=0, issues=[])

        # Perform AI review only
        result = cr_service.ai_service.review_code(diff_files)
        return result
    except Exception as e:
        logger.exception(f"Code review failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/preview",
    response_model=AICRResult,
    summary="Preview Review Comment",
    description="Preview the review comment format for a given diff",
)
async def preview_review(
    diff_files: list[dict],
) -> AICRResult:
    """
    Preview AI code review for provided diff content.

    This endpoint accepts diff content directly and returns the review result.
    Useful for testing the AI review without connecting to GitLab.

    Args:
        diff_files: List of files with 'new_path' and 'diff' fields

    Returns:
        AICRResult with issues found
    """
    from ..models.schemas import GitLabDiffFile

    try:
        files = [
            GitLabDiffFile(
                new_path=f.get("new_path", "unknown"),
                diff=f.get("diff", ""),
                old_path=f.get("old_path"),
                new_file=f.get("new_file", False),
                renamed_file=f.get("renamed_file", False),
                deleted_file=f.get("deleted_file", False),
            )
            for f in diff_files
        ]

        cr_service = get_cr_service()
        result = cr_service.ai_service.review_code(files)
        return result
    except Exception as e:
        logger.exception(f"Preview review failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
