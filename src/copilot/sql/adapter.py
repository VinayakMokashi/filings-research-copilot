"""text2sql-analyst's model interface, served by this project's gateway.

text2sql-analyst sends every model request through one method, `LLM.complete(system,
user)`. `GatewayLLM` implements it on top of an `LLMClient`, normally the cached and paced
gateway, so the data agent's calls get the same model roles, cache, pacing, retries and
cost accounting as the rest of the copilot. text2sql-analyst's two roles map onto ours:
"sql" (writing and repairing SQL) to the strong model, "helper" (choosing tables and
writing the analysis) to the fast one.
"""

from __future__ import annotations

from typing import Literal

from text2sql.llm import LLM
from text2sql.llm import LLMError as Text2SQLError
from text2sql.llm import LLMResponse as Text2SQLResponse

from copilot.llm import LLMClient, LLMError, ModelRole, system, user

Text2SQLRole = Literal["sql", "helper"]
ROLES: dict[Text2SQLRole, ModelRole] = {"sql": "strong", "helper": "fast"}


class GatewayLLM(LLM):
    """One of text2sql-analyst's model roles, answered by an `LLMClient`."""

    provider = "gateway"

    def __init__(self, client: LLMClient, role: Text2SQLRole, model: str = "") -> None:
        self._client = client
        self._role = ROLES[role]
        self.model = model or self._role

    def _complete(
        self, system_text: str, user_text: str, temperature: float, max_tokens: int
    ) -> Text2SQLResponse:
        try:
            response = self._client.complete(
                [system(system_text), user(user_text)],
                role=self._role,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMError as exc:
            raise Text2SQLError(str(exc), rate_limited=exc.rate_limited) from exc
        return Text2SQLResponse(
            text=response.text,
            model=response.model,
            latency_s=response.latency_s,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
