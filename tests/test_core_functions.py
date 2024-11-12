import unittest
from agent_logic.core_functions import AgentCore

class TestAgentCore(unittest.TestCase):
    def test_run(self):
        agent = AgentCore()
        self.assertIsNone(agent.run())

if __name__ == '__main__':
    unittest.main()
