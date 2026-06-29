import os
import base64
import json
import urllib.request
import urllib.error
from utils.logger import get_logger

log = get_logger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "xenosfinance-prog/waves")
GITHUB_PATH  = os.getenv("GITHUB_PATH", "market-brief.html")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")


class GitHubPublisher:
    def __init__(self):
        self.token  = GITHUB_TOKEN
        self.repo   = GITHUB_REPO
        self.path   = GITHUB_PATH
        self.branch = GITHUB_BRANCH
        self.api    = f"https://api.github.com/repos/{self.repo}/contents/{self.path}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept":        "application/vnd.github.v3+json",
            "User-Agent":    "XenosFinance-MarketAgent/1.0",
            "Content-Type":  "application/json",
        }

    def _request(self, method: str, data: dict = None) -> dict:
        body = json.dumps(data).encode("utf-8") if data else None
        req  = urllib.request.Request(self.api, data=body, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            raise RuntimeError(f"GitHub {method} {e.code}: {body[:200]}")

    def _get_sha(self) -> str | None:
        """Get current file SHA (needed for updates)."""
        try:
            data = self._request("GET")
            return data.get("sha")
        except RuntimeError as e:
            if "404" in str(e):
                return None  # File doesn't exist yet — first publish
            raise

    def publish(self, html_path: str) -> bool:
        if not self.token:
            log.warning("GITHUB_TOKEN not set — skipping GitHub publish")
            return False

        try:
            # Read generated HTML
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Base64 encode (GitHub API requirement)
            encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

            # Get current SHA if file exists
            sha = self._get_sha()

            # Build commit payload
            payload = {
                "message": "🤖 Auto-update: Market Intelligence Brief",
                "content": encoded,
                "branch":  self.branch,
                "committer": {
                    "name":  "XenosFinance Bot",
                    "email": "bot@xenosfinance.com",
                },
            }
            if sha:
                payload["sha"] = sha  # Required for updates

            # Push to GitHub
            result = self._request("PUT", payload)
            commit = result.get("commit", {}).get("sha", "?")[:8]
            log.info(f"✓ Published to GitHub: {self.repo}/{self.path} (commit {commit})")
            log.info(f"  Live at: https://xenosfinance.com/market-brief")
            return True

        except FileNotFoundError:
            log.error(f"HTML file not found: {html_path}")
            return False
        except Exception as e:
            log.error(f"GitHub publish failed: {e}")
            return False
