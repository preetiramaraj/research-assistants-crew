from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import RagTool, TavilySearchTool, ArxivPaperTool
from pathlib import Path
from typing import List
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class ResearchAssistants():
    """ResearchAssistants crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    arxiv_dir = (Path(__file__).resolve().parents[2] / "arxiv_pdfs").resolve()
    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    arxiv_tool = ArxivPaperTool(
        download_pdfs=True,
        save_dir=str(arxiv_dir),
        use_title_as_filename=True
        )
    arxiv_tool_no_download = ArxivPaperTool(
        download_pdfs=False
    )
    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'], # type: ignore[index]
            verbose=True,
            tools=[TavilySearchTool(), self.arxiv_tool_no_download]
        )

    @agent
    def literature_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config['literature_reviewer'], # type: ignore[index]
            verbose=True,
            tools=[TavilySearchTool(), self.arxiv_tool]
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def research_problem_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_problem_task'], # type: ignore[index]
            output_file='results/research_problem.md'
        )

    @task
    def identify_novel_project_task(self) -> Task:
        return Task(
            config=self.tasks_config['identify_novel_project_task'], # type: ignore[index]
            output_file='results/identify_novel_project.md'
        )

    @task
    def literature_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['literature_review_task'], # type: ignore[index]
            tools=[TavilySearchTool(), self.arxiv_tool],
            output_file='results/literature_review.md'
        )
    # @task
    # def reporting_task(self) -> Task:
    #     return Task(
    #         config=self.tasks_config['reporting_task'], # type: ignore[index]
    #         output_file='report.md'
    #     )

    @crew
    def crew(self) -> Crew:
        """Creates the ResearchAssistants crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
