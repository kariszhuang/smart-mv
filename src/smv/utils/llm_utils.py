"""
LLM interaction utilities for SMV.
"""

import re
import time
import xml.etree.ElementTree as ET
from typing import Optional, Any, Dict, List
from openai import OpenAI


class LLMHelper:
    """Helper class for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        max_retries: int = 2,
        retry_delay: int = 2,
    ):
        """
        Initialize the LLM helper.

        Args:
            api_key (str): API key for the LLM service.
            base_url (str): Base URL for the API.
            model_name (str): Name of the model to use.
            max_retries (int): Maximum number of retries for API calls.
            retry_delay (int): Delay between retries in seconds.
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.current_context = ""

    def update_context(self, new_info: str, is_user_hint: bool = False) -> None:
        """
        Update the current context for the LLM.

        Args:
            new_info (str): New information to add to the context.
            is_user_hint (bool): Whether the new info is a user hint.
        """
        if new_info:
            prefix = (
                "User's refinement hint: "
                if is_user_hint
                else "Key context from prior step: "
            )
            self.current_context = f"{prefix}{new_info}"

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Optional[str]:
        """
        Call the LLM API.

        Args:
            messages (List[Dict[str, str]]): Messages to send to the API.
            temperature (float): Temperature parameter for generation.
            max_tokens (int): Maximum tokens to generate.

        Returns:
            Optional[str]: The content of the LLM response, or None if an error occurred.
        """
        print("\n>>> Calling LLM...")
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content.strip()
            print(f"LLM Raw Response (first 300 chars):\n{content[:300]}...\n")
            return content
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return None

    def parse_xml_string(
        self, xml_string: Optional[str], expected_root_tag: Optional[str] = None
    ) -> Optional[ET.Element]:
        """
        Parse XML string from LLM response.

        Args:
            xml_string (Optional[str]): XML string to parse.
            expected_root_tag (Optional[str]): Expected root tag of the XML.

        Returns:
            Optional[ET.Element]: Parsed XML element, or None if parsing failed.
        """
        if xml_string is None:
            print("Error: XML string is None, cannot parse.")
            return None
        if not xml_string.strip():
            print("Error: XML string is empty or whitespace, cannot parse.")
            return None

        try:
            cleaned_xml_string = xml_string
            if cleaned_xml_string.startswith("```xml"):
                cleaned_xml_string = cleaned_xml_string[len("```xml") :]
            elif cleaned_xml_string.startswith("```"):
                cleaned_xml_string = cleaned_xml_string[len("```") :]
            if cleaned_xml_string.endswith("```"):
                cleaned_xml_string = cleaned_xml_string[: -len("```")]
            cleaned_xml_string = cleaned_xml_string.strip()

            cleaned_xml_string = re.sub(r"\s+", " ", cleaned_xml_string).strip()

            # Filter out invalid XML characters
            temp_string_builder = []
            for char_val in cleaned_xml_string:
                cp = ord(char_val)
                if (
                    cp == 0x9
                    or cp == 0xA
                    or cp == 0xD
                    or (0x20 <= cp <= 0xD7FF)
                    or (0xE000 <= cp <= 0xFFFD)
                    or (0x10000 <= cp <= 0x10FFFF)
                ):
                    temp_string_builder.append(char_val)
            cleaned_xml_string = "".join(temp_string_builder)

            if not cleaned_xml_string:
                print("Error: XML string became empty after cleaning.")
                return None

            # Extract XML if it's embedded in other text
            if not cleaned_xml_string.startswith(
                "<"
            ) or not cleaned_xml_string.endswith(">"):
                print(f"Warning: Cleaned XML string may contain extraneous text.")
                start_tag = "<"
                end_tag = ">"

                actual_start_tag = (
                    f"<{expected_root_tag}" if expected_root_tag else start_tag
                )
                start_index = cleaned_xml_string.find(actual_start_tag)

                actual_end_tag = (
                    f"</{expected_root_tag}>" if expected_root_tag else None
                )
                end_index = -1

                if actual_end_tag and start_index != -1:
                    end_index = cleaned_xml_string.find(
                        actual_end_tag, start_index
                    ) + len(actual_end_tag)

                if start_index != -1 and end_index != -1 and start_index < end_index:
                    cleaned_xml_string = cleaned_xml_string[start_index:end_index]

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
        messages: List[Dict[str, str]],
        expected_root_tag: str,
        max_tokens: int = 1000,
        step_name: str = "Unknown Step",
    ) -> Optional[ET.Element]:
        """
        Call LLM API and parse XML response with retry logic.

        Args:
            messages (List[Dict[str, str]]): Messages to send to the API.
            expected_root_tag (str): Expected root tag of the response XML.
            max_tokens (int): Maximum tokens to generate.
            step_name (str): Name of the step for logging purposes.

        Returns:
            Optional[ET.Element]: Parsed XML element, or None if parsing failed after all retries.
        """
        for attempt in range(self.max_retries + 1):
            current_messages = list(messages)
            if attempt > 0:
                # Add retry hint if not the first attempt
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
