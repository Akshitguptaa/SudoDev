from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Literal
import requests
import re


class AgentRunRequest(BaseModel):
    mode: Literal["swebench", "github"] = Field(default="swebench")

    instance_id: Optional[str] = None

    github_url: Optional[str] = None
    branch: Optional[str] = "main"

    issue_description: Optional[str] = None
    issue_url: Optional[str] = None
    issue_number: Optional[int] = None

    problem_statement: Optional[str] = None

    @model_validator(mode='after')
    def validate_and_fetch_issue(self):
        if self.mode == "swebench":
            if not self.instance_id:
                raise ValueError("instance_id is required for swebench mode")

        elif self.mode == "github":
            if self.issue_url and not self.github_url:
                extracted = self._extract_repo_url_from_issue(self.issue_url)
                if extracted:
                    self.github_url = extracted

            if not self.github_url:
                raise ValueError(
                    "github_url is required for github mode. "
                    "Provide it directly or use a valid issue_url to auto-extract it."
                )

            if self.issue_url:
                self.issue_description = self._fetch_github_issue(self.issue_url)

            elif self.issue_number:
                issue_url = self._construct_issue_url(self.github_url, self.issue_number)
                self.issue_description = self._fetch_github_issue(issue_url)

            elif not self.issue_description:
                raise ValueError(
                    "Must provide one of: issue_description, issue_url, or issue_number"
                )

        return self

    def _extract_repo_url_from_issue(self, issue_url: str) -> Optional[str]:
        match = re.match(
            r'https://github\.com/([^/]+)/([^/]+)/issues/\d+',
            issue_url.rstrip('/')
        )
        if match:
            owner, repo = match.groups()
            return f"https://github.com/{owner}/{repo}"
        return None

    def _construct_issue_url(self, repo_url: str, issue_number: int) -> str:
        clean_url = repo_url.rstrip('/')
        if clean_url.endswith('.git'):
            clean_url = clean_url[:-4]
        return f"{clean_url}/issues/{issue_number}"

    def _fetch_github_issue(self, issue_url: str) -> str:
        clean_url = issue_url.rstrip('/')

        match = re.match(
            r'https://github\.com/([^/]+)/([^/]+)/issues/(\d+)',
            clean_url
        )

        if not match:
            raise ValueError(
                f"Invalid GitHub issue URL: {issue_url}\n"
                f"Expected format: https://github.com/owner/repo/issues/123"
            )

        owner, repo, issue_number = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

        try:
            response = requests.get(
                api_url,
                headers={
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'SudoDev-Agent'
                },
                timeout=10
            )

            if response.status_code == 404:
                raise ValueError(
                    f"Issue not found: {issue_url}\n"
                    f"Make sure the repository and issue number are correct."
                )

            response.raise_for_status()
            issue_data = response.json()
            return self._format_issue(issue_data)

        except requests.exceptions.Timeout:
            raise ValueError("GitHub API request timed out. Please try again.")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to fetch GitHub issue: {str(e)}")

    def _format_issue(self, issue_data: dict) -> str:
        title = issue_data.get('title', 'Untitled Issue')
        body = issue_data.get('body', 'No description provided.')
        state = issue_data.get('state', 'open')
        labels = [label['name'] for label in issue_data.get('labels', [])]
        html_url = issue_data.get('html_url', '')

        formatted = f"""# GitHub Issue: {title}

**Issue URL**: {html_url}
**Status**: {state}
**Labels**: {', '.join(labels) if labels else 'None'}

## Issue Description

{body}
"""

        comments_url = issue_data.get('comments_url')
        if comments_url and issue_data.get('comments', 0) > 0:
            try:
                comments_response = requests.get(
                    comments_url,
                    headers={
                        'Accept': 'application/vnd.github.v3+json',
                        'User-Agent': 'SudoDev-Agent'
                    },
                    timeout=10
                )

                if comments_response.status_code == 200:
                    comments = comments_response.json()

                    if comments:
                        formatted += "\n\n## Recent Comments\n"

                        for i, comment in enumerate(comments[:3], 1):
                            author = comment['user']['login']
                            comment_body = comment['body'][:500]
                            formatted += f"\n**Comment {i}** by @{author}:\n{comment_body}\n"

                        if len(comments) > 3:
                            formatted += f"\n... and {len(comments) - 3} more comments (see issue URL)\n"

            except:
                pass

        return formatted.strip()


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    message: Optional[str] = None


class AgentStatusResponse(BaseModel):
    run_id: str
    status: str
    message: Optional[str] = None
    logs: Optional[List[str]] = []
    current_step: Optional[int] = 0
    patch: Optional[str] = None
