import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.commitment import CommitmentStatus
from app.models.user import User
from app.schemas.ai import AICommitmentDraft, CommitmentFormPrefill
from app.services.auth_service import AuthService
from app.services.commitment_service import CommitmentService

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    @property
    def is_available(self) -> bool:
        return bool(self.settings.deepseek_api_key or self.settings.claude_api_key)

    @property
    def _ai_provider_label(self) -> str:
        return "DeepSeek" if self.settings.deepseek_api_key else "Claude"

    async def parse_commitment_prompt(
        self, prompt: str
    ) -> tuple[CommitmentFormPrefill | None, str | None]:
        if not self.is_available:
            return (
                None,
                "AI is not configured. Set DEEPSEEK_API_KEY (recommended) or CLAUDE_API_KEY in your environment.",
            )

        prompt = prompt.strip()
        if not prompt:
            return None, "Describe the commitment in a few words."

        projects = await CommitmentService(self.session).list_projects()
        users = await AuthService(self.session).list_users()

        try:
            draft = await self._call_llm(prompt, projects, users)
        except Exception as exc:
            logger.exception("AI parse failed")
            return None, f"AI request failed: {exc}"

        return self._to_prefill(draft, projects, users), None

    async def _call_llm(
        self, prompt: str, projects: list, users: list[User]
    ) -> AICommitmentDraft:
        project_lines = "\n".join(f"- {p.name}" for p in projects) or "- (none)"
        user_lines = "\n".join(
            f"- {u.full_name} ({u.email})" for u in users
        ) or "- (none)"
        statuses = ", ".join(s.value for s in CommitmentStatus)
        today = datetime.now(UTC).date().isoformat()

        system = f"""You extract commitment data from user text for a team calendar.
Return JSON only with these fields:
- title (short, required)
- description (optional details)
- project_name (must match one of the projects below, or null)
- executor_name (must match a user full name below, or null)
- reviewer_name (must match a user full name below, or null)
- deadline (ISO 8601 datetime with timezone, or null; interpret relative dates like "Friday" or "tomorrow" relative to today {today})
- status (one of: {statuses}; default to_check; use ideas_backlog only if no deadline and it's a vague idea)

Available projects:
{project_lines}

Available users:
{user_lines}
"""

        if self.settings.deepseek_api_key:
            raw = await self._call_deepseek(system, prompt)
        else:
            raw = await self._call_claude(system, prompt)
        if not raw:
            raise ValueError("Empty response from model")
        return AICommitmentDraft.model_validate(json.loads(raw))

    async def _call_deepseek(self, system: str, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        return body["choices"][0]["message"]["content"] or ""

    async def _call_claude(self, system: str, prompt: str) -> str:
        try:
            from anthropic import AsyncAnthropic  # lazy import for optional dependency
        except ImportError as exc:
            raise RuntimeError(
                "Claude support requires the 'anthropic' package. Install dependencies from requirements.txt."
            ) from exc

        client = AsyncAnthropic(api_key=self.settings.claude_api_key)
        response = await client.messages.create(
            model=self.settings.claude_model,
            system=(
                f"{system}\n\n"
                "Return ONLY valid JSON object, with no markdown and no prose."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=700,
        )
        text_chunks = [b.text for b in response.content if getattr(b, "type", "") == "text"]
        return "".join(text_chunks).strip()

    def _to_prefill(
        self, draft: AICommitmentDraft, projects: list, users: list[User]
    ) -> CommitmentFormPrefill:
        deadline_str = ""
        if draft.deadline:
            dt = draft.deadline
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            deadline_str = dt.strftime("%Y-%m-%dT%H:%M")

        return CommitmentFormPrefill(
            title=draft.title,
            description=draft.description or "",
            project_id=self._match_project(draft.project_name, projects),
            executor_id=self._match_user(draft.executor_name, users),
            reviewer_id=self._match_user(draft.reviewer_name, users),
            deadline=deadline_str,
            status=draft.status.value,
        )

    @staticmethod
    def _match_project(name: str | None, projects: list) -> int | None:
        if not name:
            return None
        key = name.strip().lower()
        for p in projects:
            if p.name.lower() == key:
                return p.id
        return None

    @staticmethod
    def _match_user(name: str | None, users: list[User]) -> int | None:
        if not name:
            return None
        key = name.strip().lower()
        for u in users:
            if u.full_name.lower() == key:
                return u.id
        for u in users:
            if key in u.full_name.lower():
                return u.id
        return None
