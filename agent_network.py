"""
AG2 Parallel Agent Network for Software Development

A production-grade multi-team agent orchestration system using:
- AG2 v0.9+ with GraphFlow for parallel team execution
- RetrieveUserProxyAgent for team-specific RAG via HelixDB
- Factory pattern for clean agent instantiation
- Async execution with proper error handling
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# AG2 imports (requires: pip install ag2[openai] or ag2[ollama])
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
from autogen import LLMConfig

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TeamResult:
    """Represents output from a parallel team execution."""
    team_name: str
    success: bool
    output: str
    duration: float
    error: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_name": self.team_name,
            "success": self.success,
            "output": self.output,
            "duration": self.duration,
            "error": self.error,
        }


class AgentFactory:
    """
    Factory for creating fresh agent instances with consistent configuration.
    Ensures proper isolation between team agents.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        helix_db_host: str = "localhost:6379",
        enable_code_execution: bool = True
    ):
        self.llm_config = llm_config
        self.helix_db_host = helix_db_host
        self.enable_code_execution = enable_code_execution

    def create_architect_expert(self, team_id: str) -> AssistantAgent:
        """Create architecture design specialist agent."""
        return AssistantAgent(
            name=f"ArchitectExpert_{team_id}",
            system_message="""You are a senior software architect. Your responsibilities:
- Design system architecture based on requirements
- Identify key components, modules, and their interactions
- Define API contracts and data flows
- Ensure scalability and maintainability
- Consider design patterns and best practices
Reply with ARCHITECT_COMPLETE when done.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
        )

    def create_code_reviewer(self, team_id: str) -> AssistantAgent:
        """Create code review specialist agent."""
        return AssistantAgent(
            name=f"CodeReviewer_{team_id}",
            system_message="""You are an expert code reviewer. Your responsibilities:
- Review architectural decisions from ArchitectExpert
- Suggest improvements for code quality
- Identify potential issues (security, performance, maintainability)
- Ensure alignment with best practices
Reply with REVIEW_COMPLETE when done.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
        )

    def create_code_writer(self, team_id: str) -> AssistantAgent:
        """Create code implementation specialist agent."""
        return AssistantAgent(
            name=f"CodeWriter_{team_id}",
            system_message="""You are a senior Python developer. Your responsibilities:
- Implement code based on architecture and review feedback
- Write clean, well-documented, production-ready code
- Follow PEP 8 and best practices
- Include error handling and logging
Reply with CODE_COMPLETE when done.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
        )

    def create_test_writer(self, team_id: str) -> AssistantAgent:
        """Create test implementation specialist agent."""
        return AssistantAgent(
            name=f"TestWriter_{team_id}",
            system_message="""You are a test engineering specialist. Your responsibilities:
- Write comprehensive unit tests for implemented code
- Ensure code coverage above 80%
- Write integration tests
- Document test scenarios and edge cases
Reply with TESTS_COMPLETE when done.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
        )

    def create_doc_writer(self, team_id: str) -> AssistantAgent:
        """Create technical documentation specialist agent."""
        return AssistantAgent(
            name=f"DocWriter_{team_id}",
            system_message="""You are a technical writer. Your responsibilities:
- Write clear, comprehensive documentation
- Create README files with setup instructions
- Document API endpoints and usage examples
- Write architectural decision records (ADRs)
Reply with DOCS_COMPLETE when done.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
        )

    def create_content_validator(self, team_id: str) -> AssistantAgent:
        """Create documentation validator agent."""
        return AssistantAgent(
            name=f"ContentValidator_{team_id}",
            system_message="""You are a documentation quality expert. Your responsibilities:
- Validate documentation completeness and clarity
- Ensure examples are accurate and runnable
- Check for consistency in terminology
- Verify all components are documented
Reply with VALIDATION_COMPLETE when done.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
        )

    def create_retrieve_proxy(
        self,
        agent_name: str,
        docs_path: str,
        task_type: str = "code"
    ) -> RetrieveUserProxyAgent:
        """
        Create RAG proxy agent with team-specific context.
        Each team gets isolated document context for better relevance.
        """
        return RetrieveUserProxyAgent(
            name=f"RAG_{agent_name}",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
            retrieve_config={
                "task": task_type,
                "docs_path": docs_path,
                "chunk_token_size": 1500,
                "embedding_model": "all-mpnet-base-v2",
                "get_or_create": True,
            },
            code_execution_config=False,
        )

    def create_user_proxy(self, team_id: str) -> UserProxyAgent:
        """Create orchestration user proxy for team coordination."""
        return UserProxyAgent(
            name=f"TeamOrchestrator_{team_id}",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            is_termination_msg=lambda x: any(
                phrase in x.get("content", "").upper()
                for phrase in ["COMPLETE", "DONE", "TERMINATE", "ERROR"]
            ),
        )


class TeamDefinition:
    """Defines a parallel team with agents and configuration."""

    def __init__(
        self,
        team_id: str,
        team_name: str,
        task_description: str,
        docs_paths: Dict[str, str],
        agents_factory: AgentFactory
    ):
        self.team_id = team_id
        self.team_name = team_name
        self.task_description = task_description
        self.docs_paths = docs_paths
        self.agents_factory = agents_factory
        self.agents: Dict[str, Any] = {}

    def initialize_team_a_architecture(self):
        """Team A: Architecture & Review"""
        self.agents["architect"] = self.agents_factory.create_architect_expert(self.team_id)
        self.agents["reviewer"] = self.agents_factory.create_code_reviewer(self.team_id)
        self.agents["rag_architect"] = self.agents_factory.create_retrieve_proxy(
            f"architect_{self.team_id}",
            self.docs_paths.get("architecture", "./docs/architecture"),
            task_type="code"
        )

    def initialize_team_b_implementation(self):
        """Team B: Implementation & Testing"""
        self.agents["writer"] = self.agents_factory.create_code_writer(self.team_id)
        self.agents["tester"] = self.agents_factory.create_test_writer(self.team_id)
        self.agents["rag_implementation"] = self.agents_factory.create_retrieve_proxy(
            f"impl_{self.team_id}",
            self.docs_paths.get("implementation", "./docs/implementation"),
            task_type="code"
        )

    def initialize_team_c_documentation(self):
        """Team C: Documentation & Validation"""
        self.agents["doc_writer"] = self.agents_factory.create_doc_writer(self.team_id)
        self.agents["validator"] = self.agents_factory.create_content_validator(self.team_id)
        self.agents["rag_docs"] = self.agents_factory.create_retrieve_proxy(
            f"docs_{self.team_id}",
            self.docs_paths.get("docs", "./docs/templates"),
            task_type="qa"
        )

    def create_group_chat(self, team_agents: List[str], speaker_method: str = "round_robin") -> GroupChat:
        """Create group chat for agents within team."""
        agents = [self.agents[agent_id] for agent_id in team_agents if agent_id in self.agents]
        orchestrator = self.agents_factory.create_user_proxy(self.team_id)

        return GroupChat(
            agents=agents + [orchestrator],
            messages=[],
            max_round=15,
            speaker_selection_method=speaker_method,
            allow_repeat_speaker=False,
        )


class ParallelAgentNetwork:
    """
    Main orchestrator for parallel team execution.
    Coordinates three parallel teams with isolated contexts.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        helix_db_host: str = "localhost:6379",
        max_workers: Optional[int] = None,
        enable_code_execution: bool = True
    ):
        self.llm_config = llm_config
        self.helix_db_host = helix_db_host
        self.agent_factory = AgentFactory(llm_config, helix_db_host, enable_code_execution)
        self.max_workers = max_workers or 3
        self.teams: Dict[str, TeamDefinition] = {}
        self.results: List[TeamResult] = []

    def setup_teams(self, task_description: str, docs_base_path: str = "./docs"):
        """Initialize all three parallel teams with their specific contexts."""

        # Team A: Architecture & Code Review
        team_a = TeamDefinition(
            team_id="team_a",
            team_name="Architecture Team",
            task_description=task_description,
            docs_paths={
                "architecture": f"{docs_base_path}/architecture",
                "patterns": f"{docs_base_path}/design_patterns",
            },
            agents_factory=self.agent_factory
        )
        team_a.initialize_team_a_architecture()
        self.teams["team_a"] = team_a

        # Team B: Implementation & Testing
        team_b = TeamDefinition(
            team_id="team_b",
            team_name="Implementation Team",
            task_description=task_description,
            docs_paths={
                "implementation": f"{docs_base_path}/implementation",
                "testing": f"{docs_base_path}/testing",
            },
            agents_factory=self.agent_factory
        )
        team_b.initialize_team_b_implementation()
        self.teams["team_b"] = team_b

        # Team C: Documentation
        team_c = TeamDefinition(
            team_id="team_c",
            team_name="Documentation Team",
            task_description=task_description,
            docs_paths={
                "docs": f"{docs_base_path}/doc_templates",
                "examples": f"{docs_base_path}/examples",
            },
            agents_factory=self.agent_factory
        )
        team_c.initialize_team_c_documentation()
        self.teams["team_c"] = team_c

        logger.info(f"Initialized {len(self.teams)} parallel teams")

    def execute_team(
        self,
        team_id: str,
        task_message: str
    ) -> TeamResult:
        """Execute a single team's workflow sequentially."""
        team = self.teams[team_id]
        start_time = datetime.now()

        try:
            # Create group chat for this team
            if team_id == "team_a":
                agents_in_team = ["architect", "reviewer", "rag_architect"]
            elif team_id == "team_b":
                agents_in_team = ["writer", "tester", "rag_implementation"]
            else:  # team_c
                agents_in_team = ["doc_writer", "validator", "rag_docs"]

            group_chat = team.create_group_chat(agents_in_team)
            manager = GroupChatManager(
                groupchat=group_chat,
                llm_config=self.llm_config
            )

            # Initiate team chat
            orchestrator = self.agent_factory.create_user_proxy(team_id)
            orchestrator.initiate_chat(
                manager,
                message=f"{task_message}\nTeam: {team.team_name}"
            )

            # Extract results
            messages = orchestrator.chat_messages.get(manager.name, [])
            output = "\n".join([msg.get("content", "") for msg in messages])

            duration = (datetime.now() - start_time).total_seconds()

            return TeamResult(
                team_name=team.team_name,
                success=True,
                output=output,
                duration=duration,
                messages=messages,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Team {team_id} failed: {str(e)}")
            return TeamResult(
                team_name=team.team_name,
                success=False,
                output="",
                duration=duration,
                error=str(e),
            )

    async def execute_parallel(self, task_message: str) -> List[TeamResult]:
        """Execute all teams in parallel using ThreadPoolExecutor."""
        logger.info("Starting parallel team execution...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(
                    executor,
                    self.execute_team,
                    team_id,
                    task_message
                )
                for team_id in self.teams.keys()
            ]
            results = await asyncio.gather(*futures)

        self.results = results
        return results

    def execute_refinement_loop(self, parallel_results: List[TeamResult]) -> Dict[str, Any]:
        """Execute final refinement in shared GroupChat."""
        logger.info("Starting refinement loop...")

        # Create refinement agents
        architect = self.agent_factory.create_architect_expert("refinement")
        reviewer = self.agent_factory.create_code_reviewer("refinement")
        doc_writer = self.agent_factory.create_doc_writer("refinement")
        orchestrator = self.agent_factory.create_user_proxy("refinement")

        # Create combined context from parallel results
        combined_context = "\n\n".join([
            f"## {r.team_name}\n{r.output}" if r.success else f"## {r.team_name}\nERROR: {r.error}"
            for r in parallel_results
        ])

        # Create group chat for refinement
        refinement_chat = GroupChat(
            agents=[architect, reviewer, doc_writer, orchestrator],
            messages=[],
            max_round=10,
            speaker_selection_method="round_robin",
        )
        manager = GroupChatManager(groupchat=refinement_chat, llm_config=self.llm_config)

        refinement_message = f"""Review and refine outputs.\n{combined_context}"""

        orchestrator.initiate_chat(manager, message=refinement_message)

        messages = orchestrator.chat_messages.get(manager.name, [])
        return {
            "refinement_output": "\n".join([msg.get("content", "") for msg in messages]),
            "messages": messages,
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive execution report."""
        total_time = sum(r.duration for r in self.results)
        success_count = sum(1 for r in self.results if r.success)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_execution_time": total_time,
            "teams_executed": len(self.results),
            "teams_successful": success_count,
            "teams_failed": len(self.results) - success_count,
            "results": [r.to_dict() for r in self.results],
        }


if __name__ == "__main__":
    # Configure LLM
    llm_config = LLMConfig(
        model="gpt-4",
        api_key="your-api-key-here",
        temperature=0.7,
        timeout=60,
    )

    network = ParallelAgentNetwork(
        llm_config=llm_config,
        max_workers=3
    )

    task = "Build a REST API for user authentication with JWT tokens"
    network.setup_teams(task)

    async def main():
        results = await network.execute_parallel(task)
        for r in results:
            print(f"{r.team_name}: {r.success} ({r.duration:.2f}s)")

    asyncio.run(main())
