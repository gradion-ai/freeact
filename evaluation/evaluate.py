import asyncio
import json
import os
import shutil
import time
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Annotated, List

import datasets
import typer
from dotenv import load_dotenv
from tqdm import tqdm

from freeact import (
    Claude,
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModel,
    CodeActModelTurn,
    CodeExecution,
    DeepSeekR1,
    DeepSeekV3,
    Gemini,
    QwenCoder,
    execution_environment,
)

app = typer.Typer()

GAIA_NORMALIZATION_PROMPT = """
Finish your answer with the following template:
FINAL ANSWER: [YOUR FINAL ANSWER]. YOUR FINAL ANSWER should be a number OR as few words as possible OR a comma separated list of numbers and/or strings.
If you are asked for a number, don't use comma to write your number neither use units such as $ or percent sign unless specified otherwise.
If you are asked for a string, don't use articles, neither abbreviations (e.g. for cities), and write the digits in plain text unless specified otherwise.
If you are asked for a comma separated list, apply the above rules depending of whether the element to be put in the list is a number or a string.
"""

GSM8K_MATH_NORMALIZATION_PROMPT = """
Finish your answer with the following template:
FINAL ANSWER: [YOUR FINAL ANSWER]. YOUR FINAL ANSWER should only be a number. Don't use units such as $ or percent sign.
"""

SIMPLEQA_NORMALIZATION_PROMPT = """
Finish your answer with the following template:
FINAL ANSWER: [YOUR FINAL ANSWER]. YOUR FINAL ANSWER should be a number OR as few words as possible.
If you are asked for a number, use comma and decimal points to write your number but do not use use units such as $ or percent sign unless specified otherwise.
"""


class EvaluationSubset(StrEnum):
    GSM8K = "GSM8K"
    SIMPLEQA = "SimpleQA"
    GAIA = "GAIA"
    MATH = "MATH"


@app.command()
def main(
    run_id: str = typer.Option(..., help="Run ID"),
    model_name: str = typer.Option(..., help="Model name"),
    subset: Annotated[EvaluationSubset | None, typer.Option(help="Subset of the dataset to evaluate")] = None,
    debug: Annotated[bool, typer.Option(help="Debug mode")] = False,
    output_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("output", "evaluation"),
):
    asyncio.run(amain(**locals()))


async def amain(
    run_id: str,
    model_name: str,
    subset: EvaluationSubset | None,
    debug: bool,
    output_dir: Path,
):
    print(
        f"Starting evaluation run '{run_id}' of '{model_name}' on '{'full dataset' if subset is None else f'subset {subset}'}'"
    )
    prepare_workspace()

    output_run_dir = output_dir / run_id
    if not output_run_dir.exists():
        output_run_dir.mkdir(parents=True)

    print(f"Output directory: {output_run_dir.absolute()}")

    dataset = datasets.concatenate_datasets(
        [
            datasets.load_dataset("m-ric/agents_medium_benchmark_2")["train"],
            datasets.load_dataset("m-ric/smol_agents_benchmark")["test"].filter(
                lambda example: example["source"] == "MATH"
            ),
        ]
    )

    if subset is not None:
        _subset = str(subset)  # convert to string avoid datasets warning
        dataset = dataset.filter(lambda x: x["source"] == _subset)

    await evaluate_agent(
        dataset,
        output_dir=output_run_dir,
        model_name=model_name,
        debug=debug,
    )


def prepare_workspace():
    skills_source_path = Path("evaluation", "skills")
    skills_target_path = Path("workspace", "skills", "shared")

    if not skills_target_path.exists():
        skills_target_path.mkdir(parents=True, exist_ok=True)

    if not (skills_target_path / "google_search").exists():
        shutil.copytree(skills_source_path / "google_search", skills_target_path / "google_search")

    if not (skills_target_path / "visit_webpage").exists():
        shutil.copytree(skills_source_path / "visit_webpage", skills_target_path / "visit_webpage")


async def evaluate_agent(
    dataset,
    output_dir: Path,
    model_name: str,
    debug: bool,
):
    answered_questions = []
    for file in output_dir.glob("*.json"):
        with open(file, "r") as f:
            example = json.load(f)
            answered_questions.append(example["question"])

    for _, example in tqdm(enumerate(dataset), total=len(dataset)):
        output_file = output_dir / f"{example['source']}_{uuid.uuid4().hex[:4]}.json"

        question = example["question"]
        if question in answered_questions:
            continue

        source = example["source"]
        try:
            if source in ["GSM8K", "MATH"]:
                normalization_prompt = GSM8K_MATH_NORMALIZATION_PROMPT
            elif source == "GAIA":
                normalization_prompt = GAIA_NORMALIZATION_PROMPT
            elif source == "SimpleQA":
                normalization_prompt = SIMPLEQA_NORMALIZATION_PROMPT
            else:
                raise ValueError(f"Unknown dataset: {source}")

            start_time = time.time()
            agent_steps, answer = await run_agent(
                model_name,
                question,
                normalization_prompt,
                debug,
            )
            answer = extract_normalized_answer(answer)
            end_time = time.time()

            save_example(
                output_file=output_file,
                example=example,
                model_name=model_name,
                answer=answer,
                agent_steps=agent_steps,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as e:
            print(f"Failed: {e} (output file: '{output_file}')")
            save_example(
                output_file=output_file,
                example=example,
                model_name=model_name,
                answer="",
                is_error=True,
                error_message=str(e),
            )


def extract_normalized_answer(answer: str) -> str:
    if "FINAL ANSWER: " in answer:
        return answer[answer.rindex("FINAL ANSWER: ") + len("FINAL ANSWER: ") :].strip()
    return answer


def save_example(
    output_file: Path,
    example: dict,
    model_name: str,
    answer: str,
    agent_steps: list[str] | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    is_error: bool = False,
    error_message: str | None = None,
):
    evaluated_example = {
        "model_name": model_name,
        "question": example["question"],
        "answer": answer,
        "true_answer": example["true_answer"],
        "source": example["source"],
        "steps": agent_steps or [],
        "start_time": start_time,
        "end_time": end_time,
        "is_error": is_error,
        "error_message": error_message,
    }
    with open(output_file, "w") as f:
        json.dump(evaluated_example, f, indent=4)


async def run_agent(
    model_name: str,
    question: str,
    normalization_prompt: str,
    debug: bool,
) -> tuple[list[str], str]:
    async with execution_environment(
        executor_key="agent-evaluation",
        ipybox_tag="ghcr.io/gradion-ai/ipybox:eval",
        log_file=Path("logs", "agent-evaluation.log"),
    ) as env:
        skill_sources = await env.executor.get_module_sources(
            ["google_search.api", "visit_webpage.api"],
        )

        run_kwargs = {}
        model: CodeActModel

        if model_name in ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]:
            model = Claude(model_name=model_name, logger=env.logger)  # type: ignore
            run_kwargs["skill_sources"] = skill_sources
        elif model_name == "gemini-2.0-flash-exp":
            model = Gemini(
                model_name=model_name,  # type: ignore
                skill_sources=skill_sources,
                max_tokens=8096,
            )
        elif model_name == "qwen2p5-coder-32b-instruct":
            model = QwenCoder(
                api_key=os.getenv("FIREWORKS_API_KEY"),
                base_url="https://api.fireworks.ai/inference/v1",
                model_name=f"accounts/fireworks/models/{model_name}",
                skill_sources=skill_sources,
            )
        elif model_name == "deepseek-v3":
            # was used for earlier evaluation runs
            from freeact.model.qwen.model import (
                EXECUTION_ERROR_TEMPLATE,
                EXECUTION_OUTPUT_TEMPLATE,
                SYSTEM_TEMPLATE,
            )

            model = DeepSeekV3(
                api_key=os.getenv("FIREWORKS_API_KEY"),
                base_url="https://api.fireworks.ai/inference/v1",
                model_name=f"accounts/fireworks/models/{model_name}",
                skill_sources=skill_sources,
                system_template=SYSTEM_TEMPLATE,
                execution_output_template=EXECUTION_OUTPUT_TEMPLATE,
                execution_error_template=EXECUTION_ERROR_TEMPLATE,
            )
        elif model_name == "deepseek-r1":
            model = DeepSeekR1(
                api_key=os.getenv("FIREWORKS_API_KEY"),
                base_url="https://api.fireworks.ai/inference/v1",
                model_name=f"accounts/fireworks/models/{model_name}",
                skill_sources=skill_sources,
                instruction_extension="Important: never pass a PDF file as argument to visit_webpage.",
            )
            run_kwargs |= {"max_tokens": 16384}
        else:
            raise ValueError(f"Unknown model: {model_name}")

        agent = CodeActAgent(model=model, executor=env.executor)

        agent_turn = agent.run(question, **run_kwargs)
        agent_output = await collect_output(agent_turn, debug=debug)

        normalization_turn = agent.run(normalization_prompt, **run_kwargs)
        normalization_output = await collect_output(normalization_turn, debug=debug)

        normalized_answer = normalization_output[-1].replace("[agent ]", "").strip()
        return agent_output + normalization_output, normalized_answer


async def collect_output(agent_turn: CodeActAgentTurn, debug: bool = True) -> List[str]:
    output = []
    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as model_turn:
                if debug:
                    async for chunk in model_turn.stream():
                        print(chunk, end="", flush=True)
                    print()

                model_response = await model_turn.response()
                output.append("[agent ] " + model_response.text)

                if model_response.code:
                    output.append("[python] " + model_response.code)
                    if debug:
                        print("\n```python")
                        print(model_response.code)
                        print("```\n")

            case CodeExecution() as execution:
                execution_result = await execution.result()
                if execution_result.text is not None:
                    output.append("[result] " + execution_result.text)
                if debug:
                    print("Execution result:")
                    print(execution_result.text)

    return output


if __name__ == "__main__":
    load_dotenv()
    app()
