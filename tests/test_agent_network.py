"""
Example tests for AG2 Agent Network
Run with: pytest tests/
"""

import pytest
from agent_network import AgentFactory, TeamDefinition, ParallelAgentNetwork
from config import Config, LLMConfig as ConfigLLMConfig


@pytest.fixture
def llm_config():
    """Fixture for LLM config."""
    cfg = Config()
    return cfg.llm


@pytest.fixture
def agent_factory(llm_config):
    """Fixture for agent factory."""
    # Note: Requires actual LLM API for full testing
    return AgentFactory(
        llm_config=None,  # Mock config for unit tests
        helix_db_host="localhost:6379",
    )


def test_agent_factory_creation(agent_factory):
    """Test agent factory creates agents correctly."""
    # This would require mocking LLMConfig
    assert agent_factory is not None


def test_team_definition_initialization():
    """Test team initialization."""
    team = TeamDefinition(
        team_id="test",
        team_name="Test Team",
        task_description="Test task",
        docs_paths={"test": "./docs"},
        agents_factory=None,  # Would be mocked
    )
    assert team.team_id == "test"
    assert team.team_name == "Test Team"


@pytest.mark.asyncio
async def test_parallel_network_initialization():
    """Test network initialization."""
    # Note: Full test requires LLM API
    # This is a placeholder for integration testing
    pass
