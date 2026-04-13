"""GitLab service for interacting with GitLab API."""

import logging
from typing import List

import gitlab
from gitlab.v4.objects import Project, ProjectMergeRequest

from ..config import Settings, get_settings
from ..models.schemas import GitLabDiffFile

logger = logging.getLogger(__name__)


class GitLabService:
    """Service for GitLab API operations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: gitlab.Gitlab | None = None

    @property
    def client(self) -> gitlab.Gitlab:
        """Get or create GitLab client."""
        if self._client is None:
            self._client = gitlab.Gitlab(
                self.settings.gitlab_url,
                private_token=self.settings.gitlab_private_token,
                ssl_verify=self.settings.gitlab_verify_ssl,
            )
        return self._client

    def get_project(self, project_id: int) -> Project:
        """Get a GitLab project by ID."""
        try:
            return self.client.projects.get(project_id)
        except gitlab.exceptions.GitlabGetError as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise

    def get_merge_request(self, project_id: int, mr_iid: int) -> ProjectMergeRequest:
        """Get a merge request by project ID and MR IID."""
        project = self.get_project(project_id)
        try:
            return project.mergerequests.get(mr_iid)
        except gitlab.exceptions.GitlabGetError as e:
            logger.error(f"Failed to get MR {mr_iid} in project {project_id}: {e}")
            raise

    def get_mr_changes(
        self,
        project_id: int,
        mr_iid: int,
        ignore_patterns: List[str] | None = None,
        ignore_extensions: List[str] | None = None,
    ) -> List[GitLabDiffFile]:
        """
        Get changed files in a merge request.

        Args:
            project_id: GitLab project ID
            mr_iid: Merge request IID
            ignore_patterns: File patterns to ignore
            ignore_extensions: File extensions to ignore

        Returns:
            List of GitLabDiffFile objects
        """
        mr = self.get_merge_request(project_id, mr_iid)
        changes_data = mr.changes()
        changes = changes_data.get("changes", [])

        ignore_patterns = ignore_patterns or self.settings.cr_ignore_files
        ignore_extensions = ignore_extensions or self.settings.cr_ignore_extensions

        diff_files = []
        for change in changes:
            new_path = change.get("new_path", "")

            # Skip deleted files
            if change.get("deleted_file", False):
                logger.debug(f"Skipping deleted file: {new_path}")
                continue

            # Check if file should be ignored
            if self._should_ignore_file(new_path, ignore_patterns, ignore_extensions):
                logger.debug(f"Ignoring file: {new_path}")
                continue

            diff_files.append(GitLabDiffFile(
                old_path=change.get("old_path"),
                new_path=new_path,
                diff=change.get("diff", ""),
                new_file=change.get("new_file", False),
                renamed_file=change.get("renamed_file", False),
                deleted_file=change.get("deleted_file", False),
            ))

        logger.info(f"Found {len(diff_files)} files to review in MR {mr_iid}")
        return diff_files

    def _should_ignore_file(
        self,
        file_path: str,
        ignore_patterns: List[str],
        ignore_extensions: List[str],
    ) -> bool:
        """Check if a file should be ignored based on patterns and extensions."""
        # Check extension
        for ext in ignore_extensions:
            if file_path.endswith(ext):
                return True

        # Check patterns
        for pattern in ignore_patterns:
            if pattern.startswith("*."):
                # Wildcard extension pattern
                if file_path.endswith(pattern[1:]):
                    return True
            elif pattern.endswith("/"):
                # Directory pattern
                if f"/{pattern}" in f"/{file_path}" or file_path.startswith(pattern):
                    return True
            else:
                # Exact match or contains
                if pattern in file_path:
                    return True

        return False

    def create_mr_comment(self, project_id: int, mr_iid: int, body: str) -> dict:
        """
        Create a comment on a merge request.

        Args:
            project_id: GitLab project ID
            mr_iid: Merge request IID
            body: Comment body text

        Returns:
            Created comment data
        """
        mr = self.get_merge_request(project_id, mr_iid)
        note = mr.notes.create({"body": body})
        logger.info(f"Created comment on MR {mr_iid}")
        return note.attributes

    def create_mr_discussion(
        self,
        project_id: int,
        mr_iid: int,
        body: str,
        file_path: str,
        line_number: int,
    ) -> dict:
        """
        Create a discussion (line comment) on a merge request.

        Args:
            project_id: GitLab project ID
            mr_iid: Merge request IID
            body: Comment body text
            file_path: File path for the comment
            line_number: Line number for the comment

        Returns:
            Created discussion data
        """
        mr = self.get_merge_request(project_id, mr_iid)

        # Get diff refs for position
        diff_refs = mr.diff_refs
        if not diff_refs:
            logger.warning(f"No diff refs found for MR {mr_iid}, creating regular comment")
            return self.create_mr_comment(project_id, mr_iid, body)

        try:
            discussion = mr.discussions.create({
                "body": body,
                "position": {
                    "base_sha": diff_refs["base_sha"],
                    "head_sha": diff_refs["head_sha"],
                    "start_sha": diff_refs["base_sha"],
                    "position_type": "text",
                    "new_path": file_path,
                    "new_line": line_number,
                }
            })
            logger.info(f"Created discussion on MR {mr_iid} at {file_path}:{line_number}")
            return discussion.attributes
        except Exception as e:
            logger.warning(f"Failed to create line comment, falling back to regular comment: {e}")
            return self.create_mr_comment(project_id, mr_iid, f"**{file_path}:{line_number}**\n\n{body}")

    def get_mr_info(self, project_id: int, mr_iid: int) -> dict:
        """Get merge request information."""
        mr = self.get_merge_request(project_id, mr_iid)
        return {
            "iid": mr.iid,
            "title": mr.title,
            "description": mr.description,
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch,
            "author": mr.author,
            "state": mr.state,
            "web_url": mr.web_url,
        }
