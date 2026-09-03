from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from app.llm.gateway import get_llm


class BaseAgent:
    agent_name: str = "base_agent"

    def __init__(self, complexity: str = "complex") -> None:
        self.complexity = complexity.strip().lower()
        self.llm = get_llm(complexity=self.complexity)

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
            if isinstance(value, (dict, list)):
                prepared_data[key] = json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                prepared_data[key] = value

        messages = prompt.invoke(prepared_data)

        response = await self.llm.ainvoke(messages)

        content = response.content

        if isinstance(content, list):
            content = "".join(
                item.get("text", str(item))
                if isinstance(item, dict)
                else str(item)
                for item in content
            )

        content = str(content).strip()

        if content.startswith("```json"):
            content = content[7:]

        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{self.agent_name} returned invalid JSON:\n{content}"
            ) from exc