import asyncio
import tempfile
import unittest
from pathlib import Path

from backend.engine import llm_client
from backend.engine.conversation import ConversationSystem
from backend.engine.llm_client import LLMClient
from backend.engine.rules import RuleBook
from backend.mbti.personas import PERSONA_DEFINITIONS
from tests.test_llm_client import FakeProvider, make_config


class ConversationRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rules = RuleBook(Path(self.tmp.name) / "interaction_rules.json")
        self.rules.update({
            "conversation": {
                "chance": 1.0,
                "cooldown_ticks": 0,
                "max_per_tick": 2,
                "templates": {
                    "greetings": ["Hello {symbol}"],
                    "bullish": ["Adding {symbol}"],
                    "bearish": ["Trimming {symbol}"],
                    "neutral": ["Watching {symbol}"],
                },
            },
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_rule_conversation_is_tagged_and_formatted(self):
        system = ConversationSystem(self.rules)
        positions = {"INTJ": (9, 2), "INTP": (9, 3), "ENTJ": (10, 2)}
        traits = PERSONA_DEFINITIONS["INTJ"]["traits"]
        conv = asyncio.run(system.try_converse(
            "INTJ", traits, positions, "cafe", 1,
            {"AAPL": 100.0}, {"AAPL": 0.01},
        ))
        self.assertIsNotNone(conv)
        self.assertTrue(conv.turns)
        self.assertEqual(conv.turns[0].content, "Hello AAPL")
        self.assertTrue(all(turn.source == "rule" for turn in conv.turns))

    def test_optional_llm_lines_are_tagged(self):
        original = llm_client._CLIENT
        llm_client._CLIENT = LLMClient(
            make_config(mode="conversation"),
            FakeProvider("The tape is thin, but I am patient."),
        )
        try:
            system = ConversationSystem(self.rules)
            positions = {"INTJ": (9, 2), "INTP": (9, 3)}
            traits = PERSONA_DEFINITIONS["INTJ"]["traits"]
            conv = asyncio.run(system.try_converse(
                "INTJ", traits, positions, "cafe", 1,
                {"AAPL": 100.0}, {"AAPL": 0.01},
            ))
        finally:
            llm_client._CLIENT = original
        self.assertIsNotNone(conv)
        self.assertTrue(conv.turns)
        self.assertTrue(all(turn.source == "llm" for turn in conv.turns))

    def test_zero_chance_and_zero_max_disable_conversation(self):
        system = ConversationSystem(self.rules)
        positions = {"INTJ": (9, 2), "INTP": (9, 3)}
        traits = PERSONA_DEFINITIONS["INTJ"]["traits"]
        self.rules.update({"conversation": {"chance": 0.0}})
        conv = asyncio.run(system.try_converse(
            "INTJ", traits, positions, "cafe", 1,
            {"AAPL": 100.0}, {"AAPL": 0.01},
        ))
        self.assertIsNone(conv)


if __name__ == "__main__":
    unittest.main()
