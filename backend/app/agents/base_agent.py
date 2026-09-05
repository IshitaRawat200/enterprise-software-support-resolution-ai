from __future__ import annotations

import json
from typing import Any

from app.llm.gateway import get_llm
from langchain_core.prompts import ChatPromptTemplate


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

    async def invoke(
        self,
        prompt: ChatPromptTemplate,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Invoke the configured LLM and parse its JSON response.
        """

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

        messages = prompt.invoke(
            prepared_data
        )

        # ----------------------------------------------------
        # Invoke LLM
        # ----------------------------------------------------

        response = await self.llm.ainvoke(
            messages
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

        content = str(
            content
        ).strip()

        # ----------------------------------------------------
        # Remove Markdown JSON fences
        # ----------------------------------------------------

        if content.startswith(
            "```json"
        ):
            content = content[7:]

        elif content.startswith(
            "```"
        ):
            content = content[3:]

        content = content.removesuffix(
            "```"
        ).strip()

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:
            result = json.loads(
                content
            )

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{self.agent_name} returned invalid JSON:\n"
                f"{content}"
            ) from exc

        # ----------------------------------------------------
        # Validate result type
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict,
        ):
            raise ValueError(
                f"{self.agent_name} returned JSON "
                "that is not an object."
            )

        return result