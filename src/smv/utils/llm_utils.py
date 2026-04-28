"""
LLM interaction utilities for SMV.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI


def _flatten_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif item.get("type") == "image_url":
                    parts.append("[image omitted]")
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


class LLMHelper:
    """Helper class for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str],
        model_name: str,
        provider_id: str = "ollama",
        max_retries: int = 2,
        retry_delay: int = 2,
    ):
        self.provider_id = provider_id.strip().lower()
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.current_context = ""

        self.client = None
        if self.provider_id in {"ollama", "openai"}:
            kwargs: Dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)

    def update_context(self, new_info: str, is_user_hint: bool = False) -> None:
        if new_info:
            prefix = (
                "User's refinement hint: "
                if is_user_hint
                else "Key context from prior step: "
            )
            self.current_context = f"{prefix}{new_info}"

    def _call_openai_compatible(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_handler: Optional[Callable[[str, Dict[str, Any]], str]] = None,
        max_tool_rounds: int = 0,
    ) -> Optional[str]:
        if self.client is None:
            print("Error: OpenAI-compatible client is not initialized.")
            return None

        conversation_messages: List[Dict[str, Any]] = list(messages)
        remaining_tool_rounds = max(0, max_tool_rounds)

        while True:
            kwargs: Dict[str, Any] = {
                "model": self.model_name,
                "messages": conversation_messages,
                "temperature": temperature,
            }
            if self.provider_id != "ollama":
                kwargs["max_tokens"] = max_tokens
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            content = message.content.strip() if message.content else None
            tool_calls = list(getattr(message, "tool_calls", None) or [])

            if not tool_calls:
                return content

            if tool_handler is None:
                print("LLM requested tool calls, but no tool handler was provided.")
                return content

            if remaining_tool_rounds <= 0:
                print("Maximum tool-call rounds reached; returning latest response.")
                return content

            serialized_tool_calls = []
            for tool_call in tool_calls:
                function_info = getattr(tool_call, "function", None)
                serialized_tool_calls.append(
                    {
                        "id": getattr(tool_call, "id", ""),
                        "type": "function",
                        "function": {
                            "name": getattr(function_info, "name", ""),
                            "arguments": getattr(function_info, "arguments", "{}"),
                        },
                    }
                )

            conversation_messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": serialized_tool_calls,
                }
            )

            for tool_call in tool_calls:
                function_info = getattr(tool_call, "function", None)
                tool_name = getattr(function_info, "name", "")
                raw_arguments = getattr(function_info, "arguments", "") or "{}"
                tool_result: str

                try:
                    parsed_arguments = json.loads(raw_arguments)
                    if not isinstance(parsed_arguments, dict):
                        parsed_arguments = {"value": parsed_arguments}
                except json.JSONDecodeError as e:
                    tool_result = json.dumps(
                        {
                            "error": f"Invalid tool arguments JSON for '{tool_name}': {str(e)}"
                        }
                    )
                else:
                    handler_result = tool_handler(tool_name, parsed_arguments)
                    if isinstance(handler_result, str):
                        tool_result = handler_result
                    else:
                        tool_result = json.dumps(handler_result, ensure_ascii=True)

                conversation_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": getattr(tool_call, "id", ""),
                        "content": tool_result,
                    }
                )

            remaining_tool_rounds -= 1

    def _call_anthropic(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        try:
            import anthropic
        except ImportError:
            print(
                "Error: 'anthropic' package is not installed. Run `uv add anthropic`."
            )
            return None

        system_parts: List[str] = []
        anthropic_messages: List[Dict[str, str]] = []
        for message in messages:
            role = message.get("role", "user")
            text_content = _flatten_message_content(message.get("content"))
            if not text_content:
                continue
            if role == "system":
                system_parts.append(text_content)
                continue
            anthropic_messages.append(
                {"role": "assistant" if role == "assistant" else "user", "content": text_content}
            )

        if not anthropic_messages:
            anthropic_messages = [{"role": "user", "content": "Please respond."}]

        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        response = client.messages.create(**kwargs)
        content_parts = []
        for block in response.content:
            text_value = getattr(block, "text", None)
            if text_value:
                content_parts.append(text_value)
        joined = "".join(content_parts).strip()
        return joined or None

    def _call_gemini(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        try:
            import google.generativeai as genai
        except ImportError:
            print(
                "Error: 'google-generativeai' package is not installed. Run `uv add google-generativeai`."
            )
            return None

        prompt_parts = []
        for message in messages:
            role = message.get("role", "user").upper()
            prompt_parts.append(f"{role}:\n{_flatten_message_content(message.get('content'))}")
        final_prompt = "\n\n".join(part for part in prompt_parts if part.strip())
        if not final_prompt.strip():
            final_prompt = "Please respond."

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(
            final_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        text = getattr(response, "text", None)
        if text:
            return text.strip()

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            parts = (
                getattr(getattr(candidate, "content", None), "parts", None) or []
            )
            collected = [getattr(part, "text", "") for part in parts if getattr(part, "text", None)]
            if collected:
                return "\n".join(collected).strip()
        return None

    def call_llm(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_handler: Optional[Callable[[str, Dict[str, Any]], str]] = None,
        max_tool_rounds: int = 0,
    ) -> Optional[str]:
        print(f"\n>>> Calling LLM ({self.provider_id}/{self.model_name})...")
        try:
            if self.provider_id in {"ollama", "openai"}:
                content = self._call_openai_compatible(
                    messages,
                    temperature,
                    max_tokens,
                    tools=tools,
                    tool_handler=tool_handler,
                    max_tool_rounds=max_tool_rounds,
                )
            elif self.provider_id == "anthropic":
                if tools:
                    print(
                        "Warning: Tool calling is currently only enabled for OpenAI-compatible providers."
                    )
                content = self._call_anthropic(messages, temperature, max_tokens)
            elif self.provider_id == "gemini":
                if tools:
                    print(
                        "Warning: Tool calling is currently only enabled for OpenAI-compatible providers."
                    )
                content = self._call_gemini(messages, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported provider '{self.provider_id}'")

            if not content:
                print("LLM response was empty.")
                return None

            print(f"LLM Raw Response (first 300 chars):\n{content[:300]}...\n")
            return content
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return None

    def parse_xml_string(
        self, xml_string: Optional[str], expected_root_tag: Optional[str] = None
    ) -> Optional[ET.Element]:
        if xml_string is None:
            print("Error: XML string is None, cannot parse.")
            return None
        if not xml_string.strip():
            print("Error: XML string is empty or whitespace, cannot parse.")
            return None

        try:
            cleaned_xml_string = xml_string.strip()
            if cleaned_xml_string.startswith("```xml"):
                cleaned_xml_string = cleaned_xml_string[len("```xml") :]
            elif cleaned_xml_string.startswith("```"):
                cleaned_xml_string = cleaned_xml_string[len("```") :]
            if cleaned_xml_string.endswith("```"):
                cleaned_xml_string = cleaned_xml_string[: -len("```")]
            cleaned_xml_string = cleaned_xml_string.strip()

            if expected_root_tag:
                root_open_pattern = re.compile(
                    rf"<{re.escape(expected_root_tag)}(?:\s[^>]*)?>",
                    flags=re.IGNORECASE,
                )
                root_close_pattern = re.compile(
                    rf"</{re.escape(expected_root_tag)}>",
                    flags=re.IGNORECASE,
                )
                open_match = root_open_pattern.search(cleaned_xml_string)
                close_match = root_close_pattern.search(cleaned_xml_string)
                if open_match and close_match and open_match.start() < close_match.end():
                    cleaned_xml_string = cleaned_xml_string[
                        open_match.start() : close_match.end()
                    ]

            # Filter invalid XML characters
            cleaned_xml_string = "".join(
                ch
                for ch in cleaned_xml_string
                if (
                    ord(ch) in (0x9, 0xA, 0xD)
                    or (0x20 <= ord(ch) <= 0xD7FF)
                    or (0xE000 <= ord(ch) <= 0xFFFD)
                    or (0x10000 <= ord(ch) <= 0x10FFFF)
                )
            ).strip()

            if not cleaned_xml_string:
                print("Error: XML string became empty after cleaning.")
                return None

            root = ET.fromstring(cleaned_xml_string)
            if expected_root_tag and root.tag != expected_root_tag:
                print(
                    f"Warning: Expected root tag '{expected_root_tag}', but found '{root.tag}'"
                )
            return root
        except ET.ParseError as e:
            print(
                f"Error parsing XML: {e}\nAttempted to parse (after cleaning):\n{cleaned_xml_string[:500]}..."
            )
            return None
        except Exception as e:
            print(f"An unexpected error occurred during XML parsing: {e}")
            return None

    def call_llm_and_parse_xml(
        self,
        messages: List[Dict[str, Any]],
        expected_root_tag: str,
        max_tokens: int = 1000,
        step_name: str = "Unknown Step",
    ) -> Optional[ET.Element]:
        for attempt in range(self.max_retries + 1):
            current_messages = list(messages)
            if attempt > 0:
                retry_message = {
                    "role": "user",
                    "content": f"Please try again. Make sure to respond with valid XML with root tag <{expected_root_tag}>. "
                    "Don't use backticks or other formatting, just output the XML directly.",
                }
                current_messages.append(retry_message)

            response_str = self.call_llm(current_messages, max_tokens=max_tokens)
            if response_str is None:
                print(
                    f"LLM call failed for {step_name}, attempt {attempt + 1}/{self.max_retries + 1}"
                )
                continue

            root = self.parse_xml_string(response_str, expected_root_tag)
            if root is not None:
                print(
                    f"Successfully parsed XML for {step_name} on attempt {attempt + 1}"
                )
                return root

            print(
                f"Failed to parse XML for {step_name}, attempt {attempt + 1}/{self.max_retries + 1}"
            )
            if attempt < self.max_retries:
                print(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

        print(f"Failed to parse XML for {step_name} after all retries.")
        return None
