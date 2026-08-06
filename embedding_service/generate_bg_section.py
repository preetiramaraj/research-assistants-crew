
from groq import Groq
from run_paths import latest_run_dir

run_dir = latest_run_dir()

research_problem = (run_dir / 'research_problem.md').read_text(encoding='utf-8').strip()
chunks = sorted(run_dir.glob('bg_chunks_*.txt'))[-1].read_text(encoding='utf-8').strip()

prompt = f"""You are a research assistant writing a background section for an academic paper.

Research problem: {research_problem}

Relevant literature excerpts:
{chunks}

Write a coherent background section that synthesizes the key themes, methods, and a bullet list of gaps from the literature above. You must ground every claim in the provided literature excerpts. Do not use general knowledge."""

(run_dir / 'background_section_prompt.txt').write_text(prompt, encoding='utf-8')

client = Groq()

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[{"role": "user", "content": prompt}]
)

(run_dir / 'background_section.txt').write_text(response.choices[0].message.content, encoding='utf-8')
