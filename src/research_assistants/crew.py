from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import TavilySearchTool
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

    llm = LLM(model="groq/openai/gpt-oss-20b",
              #temperature=0.5,
              max_tokens=2048,
              num_retries=3
              )

    llm2 = LLM(model="groq/openai/gpt-oss-20b",
              #temperature=0.5,
              max_tokens=2048,
              num_retries=3
              )

    
    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools


    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'], # type: ignore[index]
            verbose=True,
            llm=self.llm
        )

    @agent
    def literature_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config['literature_reviewer'], # type: ignore[index]
            verbose=True,
            llm=self.llm2
        )


    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def research_problem_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_problem_task'], # type: ignore[index]
            output_file='{run_dir}/research_problem.md',
            human_input=True
            #tools=[TavilySearchTool()]
        )

    @task
    def create_search_queries_task(self) -> Task:
        return Task(
            config=self.tasks_config['create_search_queries_task'], # type: ignore[index]
            human_input=True,
            output_file='{run_dir}/search_queries.md'
        )


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
