from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.llm.gateway import get_llm
from app.llm.usage import extract_llm_usage
from app.observability.logging import logger


class BaseAgent:
    agent_name: str = "base_agent"

    def __init__(
        self,
        complexity: str = "complex",
    ) -> None:
        self.complexity = complexity.strip().lower()

        self.llm = get_llm(
            complexity=self.complexity,
        )

        # Stores usage information from the most recent
        # LLM invocation performed by this agent.
        self.last_usage: dict[str, Any] = {}

    async def invoke(
        self,
        prompt: ChatPromptTemplate,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Invoke the configured LLM and parse its JSON response.

        The parsed JSON is returned to the calling agent.

        Token, timing, and prompt-cache metadata from the
        LLM response are stored in self.last_usage so that
        orchestration nodes can collect observability data
        without polluting agent result schemas.
        """

        # Reset previous invocation metadata.
        self.last_usage = {}

        # ----------------------------------------------------
        # Validate prompt type
        # ----------------------------------------------------

        if not isinstance(
            prompt,
            ChatPromptTemplate,
        ):
            raise TypeError(f"{self.agent_name} requires a ChatPromptTemplate.")

        # ----------------------------------------------------
        # Prepare dynamic prompt data
        # ----------------------------------------------------

        prepared_data: dict[str, Any] = {}

        for key, value in data.items():
            if isinstance(
                value,
                (dict, list),
            ):
                prepared_data[key] = json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )

            elif value is None:
                prepared_data[key] = ""

            else:
                prepared_data[key] = value

        # ----------------------------------------------------
        # Build prompt messages
        # ----------------------------------------------------

        messages = prompt.invoke(prepared_data)

        # ----------------------------------------------------
        # Invoke LLM
        # ----------------------------------------------------

        response = await self.llm.ainvoke(messages)

        # ----------------------------------------------------
        # Extract LLM usage
        # ----------------------------------------------------

        self.last_usage = extract_llm_usage(response)

        # Add agent information for observability.
        self.last_usage["agent"] = self.agent_name
        self.last_usage["complexity"] = self.complexity

        # Safely obtain model information.
        model_name = getattr(
            self.llm,
            "model_name",
            None,
        ) or getattr(
            self.llm,
            "model",
            None,
        )

        if model_name:
            self.last_usage["model"] = model_name

        # ----------------------------------------------------
        # Log LLM usage and prompt-cache information
        # ----------------------------------------------------

        logger.info(
            "LLM cache: agent=%s model=%s complexity=%s "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "cached_tokens=%s cache_status=%s cache_hit=%s "
            "cache_hit_rate=%.4f prompt_time=%.4fs "
            "completion_time=%.4fs total_time=%.4fs",
            self.last_usage.get("agent"),
            self.last_usage.get("model"),
            self.last_usage.get("complexity"),
            self.last_usage.get("prompt_tokens"),
            self.last_usage.get("completion_tokens"),
            self.last_usage.get("total_tokens"),
            self.last_usage.get("cached_tokens"),
            self.last_usage.get("cache_status"),
            self.last_usage.get("cache_hit"),
            self.last_usage.get("cache_hit_rate", 0.0),
            self.last_usage.get("prompt_time", 0.0),
            self.last_usage.get("completion_time", 0.0),
            self.last_usage.get("total_time", 0.0),
        )

        # ----------------------------------------------------
        # Extract content
        # ----------------------------------------------------

        content = response.content

        if isinstance(
            content,
            list,
        ):
            content = "".join(
                (
                    item.get(
                        "text",
                        str(item),
                    )
                    if isinstance(
                        item,
                        dict,
                    )
                    else str(item)
                )
                for item in content
            )

        content = str(content).strip()

        # ----------------------------------------------------
        # Remove Markdown JSON fences
        # ----------------------------------------------------

        if content.startswith("```json"):
            content = content[7:]

        elif content.startswith("```"):
            content = content[3:]

        content = content.removesuffix("```").strip()

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:
            result = json.loads(content)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{self.agent_name} returned invalid JSON:\n{content}"
            ) from exc

        # ----------------------------------------------------
        # Validate result type
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict,
        ):
            raise ValueError(  # noqa: TRY004
                f"{self.agent_name} returned JSON that is not an object."
            )

        return result
