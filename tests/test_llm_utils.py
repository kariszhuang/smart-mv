import unittest

from smv.utils.llm_utils import LLMHelper


class _FakeFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, tool_call_id: str, name: str, arguments: str):
        self.id = tool_call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResponse:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return _FakeResponse(
                _FakeMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(
                            "call_1",
                            "list_directory",
                            '{"path": "/tmp", "limit": 5}',
                        )
                    ],
                )
            )
        return _FakeResponse(_FakeMessage(content="Final response", tool_calls=None))


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


class LLMUtilsToolCallTest(unittest.TestCase):
    def test_call_llm_runs_tool_calls_for_openai_compatible_models(self):
        helper = LLMHelper(
            api_key="test",
            base_url="http://localhost:11434/v1",
            model_name="fake-model",
            provider_id="openai",
        )
        helper.client = _FakeClient()
        called_tools = []

        def tool_handler(name, arguments):
            called_tools.append((name, arguments))
            return '{"entries": []}'

        result = helper.call_llm(
            messages=[{"role": "user", "content": "Find folders"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "list_directory",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                            },
                            "required": ["path"],
                        },
                    },
                }
            ],
            tool_handler=tool_handler,
            max_tool_rounds=2,
        )

        self.assertEqual(result, "Final response")
        self.assertEqual(
            called_tools,
            [("list_directory", {"path": "/tmp", "limit": 5})],
        )

        calls = helper.client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertTrue(any(message.get("role") == "tool" for message in calls[1]["messages"]))


if __name__ == "__main__":
    unittest.main()
