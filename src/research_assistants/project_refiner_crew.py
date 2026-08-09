from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

@CrewBase
class ProjectRefiner():
    """ProjectRefiner crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = 'config/project_refiner_agents.yaml'
    tasks_config = 'config/project_refiner_tasks.yaml'


    llm = LLM(model="groq/openai/gpt-oss-20b",
                #model="huggingface/meta-llama/Llama-3.1-8B-Instruct:fastest",
              #temperature=0.5,
              max_tokens=4096,
              num_retries=3
              )

    @agent
    def experimenter(self) -> Agent:
        return Agent(
            config=self.agents_config['experimenter'], # type: ignore[index]
            verbose=True,
            llm=self.llm
        )
    
    @task
    def hypothesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['hypothesis_task'], # type: ignore[index]
            output_file='{run_dir}/final_hypothesis.md',
            human_input=True
            #tools=[TavilySearchTool()]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the ProjectRefiner crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True
        )
    