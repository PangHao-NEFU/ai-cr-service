"""Core Code Review service orchestrating GitLab and AI services."""

import logging

# import redis  # TODO: Redis 暂时不启用，后续可能接入

from ..config import Settings, get_settings
from ..models.schemas import AICRResult, CRIssue, CRIssueLevel, MRTriggerRequest
from .ai_service import AIService
from .gitlab_service import GitLabService

logger = logging.getLogger(__name__)


class CRService:
    """Core Code Review service."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.gitlab_service = GitLabService(self.settings)
        self.ai_service = AIService(self.settings)
        # self._redis_client: redis.Redis | None = None  # TODO: Redis 暂不启用

    # @property
    # def redis_client(self) -> redis.Redis:
    #     """Get or create Redis client."""
    #     if self._redis_client is None:
    #         self._redis_client = redis.from_url(self.settings.redis_url)
    #     return self._redis_client

    def perform_code_review(self, request: MRTriggerRequest) -> AICRResult:
        """
        Perform code review for a merge request.

        This is the main entry point that orchestrates:
        1. Fetch MR changes from GitLab
        2. Get MR basic info (title, description)
        3. Call AI service for review
        4. Post comments to GitLab

        Args:
            request: MR trigger request

        Returns:
            AICRResult with issues found
        """
        logger.info(f"Starting code review for project {request.project_id}, MR {request.mr_iid}")

        # 1. Get MR changes (所有文件都会被CR)
        diff_files = self.gitlab_service.get_mr_changes(
            request.project_id,
            request.mr_iid,
        )

        if not diff_files:
            logger.info("No files to review")
            result = AICRResult(total_issues=0, issues=[])
            self._post_summary_comment(request, result, "No files to review")
            return result

        # 2. Get MR basic info
        mr_info = self.gitlab_service.get_mr_info(request.project_id, request.mr_iid)
        context = {
            "mr_title": mr_info.get("title", ""),
            "mr_description": mr_info.get("description", ""),
            "source_branch": mr_info.get("source_branch", ""),
            "target_branch": mr_info.get("target_branch", ""),
            "author": mr_info.get("author", {}).get("username", "unknown"),
        }

        # TODO: Redis 缓存暂不启用，后续可能接入
        # cache_key = self._get_cache_key(diff_files, context.get("mr_title", ""))
        # cached_result = self._get_cached_result(cache_key)
        # if cached_result:
        #     logger.info("Using cached review result")
        #     self._post_cr_comments(request, cached_result)
        #     return cached_result

        # 3. Perform AI review (只传 diff，不获取额外上下文)
        try:
            result = self.ai_service.review_code(
                diff_files=diff_files,
                context=context,
            )
            logger.info(f"AI review completed, found {result.total_issues} issues")
        except Exception as e:
            logger.error(f"AI review failed: {e}")
            self._post_error_comment(request, str(e))
            raise

        # 4. Post comments to GitLab
        self._post_cr_comments(request, result)

        # TODO: Redis 缓存暂不启用
        # self._cache_result(cache_key, result)

        return result

    # TODO: Redis 缓存相关方法，后续可能接入
    # def _get_cache_key(self, diff_files: List[GitLabDiffFile], mr_title: str = "") -> str:
    #     """Generate cache key based on file contents and MR title."""
    #     content = mr_title + "".join(f"{f.new_path}:{f.diff}" for f in diff_files)
    #     hash_value = hashlib.sha256(content.encode()).hexdigest()
    #     return f"cr:cache:{hash_value}"

    # def _get_cached_result(self, cache_key: str) -> AICRResult | None:
    #     """Get cached review result if available."""
    #     try:
    #         cached = self.redis_client.get(cache_key)
    #         if cached:
    #             data = json.loads(cached)
    #             issues = [CRIssue(**issue) for issue in data.get("issues", [])]
    #             return AICRResult(total_issues=data.get("total_issues", 0), issues=issues)
    #     except Exception as e:
    #         logger.warning(f"Failed to get cache: {e}")
    #     return None

    # def _cache_result(self, cache_key: str, result: AICRResult) -> None:
    #     """Cache review result."""
    #     try:
    #         data = {
    #             "total_issues": result.total_issues,
    #             "issues": [issue.model_dump() for issue in result.issues],
    #         }
    #         self.redis_client.setex(
    #             cache_key,
    #             self.settings.redis_cache_ttl,
    #             json.dumps(data),
    #         )
    #     except Exception as e:
    #         logger.warning(f"Failed to cache result: {e}")

    def _post_cr_comments(
        self,
        request: MRTriggerRequest,
        result: AICRResult,
    ) -> None:
        """Post code review comments to GitLab MR."""
        # Post summary comment
        self._post_summary_comment(request, result)

        # Post line comments for each issue
        for issue in result.issues:
            self._post_issue_comment(request, issue)

    def _post_summary_comment(
        self,
        request: MRTriggerRequest,
        result: AICRResult,
        extra_note: str = "",
    ) -> None:
        """Post summary comment on MR."""
        bugs = [i for i in result.issues if i.level == CRIssueLevel.BUG]
        suggestions = [i for i in result.issues if i.level == CRIssueLevel.SUGGESTION]

        comment = "## 🤖 AI Code Review Result\n\n"

        if extra_note:
            comment += f"**Note:** {extra_note}\n\n"

        comment += f"**Total Issues:** {result.total_issues}\n"
        comment += f"- 🐛 **Bugs (Must Fix):** {len(bugs)}\n"
        comment += f"- 💡 **Suggestions:** {len(suggestions)}\n\n"

        if result.issues:
            comment += "### Issue List\n\n"
            for idx, issue in enumerate(result.issues, 1):
                level_emoji = "🐛" if issue.level == CRIssueLevel.BUG else "💡"
                comment += f"{idx}. {level_emoji} **{issue.title}**\n"
                comment += f"   - File: `{issue.file_path}:{issue.line_number}`\n"
                comment += f"   - Level: {issue.level.value}\n\n"

        comment += "\n---\n*Reviewed by AI Code Review Service*"

        self.gitlab_service.create_mr_comment(
            request.project_id,
            request.mr_iid,
            comment,
        )

    def _post_issue_comment(
        self,
        request: MRTriggerRequest,
        issue: CRIssue,
    ) -> None:
        """Post individual issue comment on specific line."""
        level_emoji = "🐛" if issue.level == CRIssueLevel.BUG else "💡"
        level_tag = "BUG" if issue.level == CRIssueLevel.BUG else "SUGGESTION"

        body = f"**{level_emoji} [{level_tag}]** {issue.title}\n\n{issue.content}"

        if issue.code_snippet:
            body += f"\n\n```{issue.code_snippet}```"

        self.gitlab_service.create_mr_discussion(
            request.project_id,
            request.mr_iid,
            body,
            issue.file_path,
            issue.line_number,
        )

    def _post_error_comment(
        self,
        request: MRTriggerRequest,
        error_message: str,
    ) -> None:
        """Post error comment when review fails."""
        comment = f"## ⚠️ AI Code Review Failed\n\nError: {error_message}\n\nPlease check the service logs."
        self.gitlab_service.create_mr_comment(
            request.project_id,
            request.mr_iid,
            comment,
        )
