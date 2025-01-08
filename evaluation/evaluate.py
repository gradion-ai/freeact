import asyncio
import json
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

from evaluation import (
    EVAL_EXECUTOR_KEY,
    EVAL_IPYBOX_TAG,
    EVAL_LOG_FILE,
    EVAL_OUTPUT_DIR,
    EVAL_SKILLS_SOURCE_PATH,
    EVAL_WORKSPACE_PATH,
    EVAL_WORKSPACE_SKILLS_PATH,
)
from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModelTurn,
    CodeExecution,
    execution_environment,
)
from freeact.cli.__main__ import ModelName
from freeact.cli.utils import dotenv_variables
from freeact.model.claude.model import Claude
from freeact.model.gemini.model.chat import Gemini

app = typer.Typer()

GAIA_NORMALIZATION_PROMPT = """
Finish your answer with the following template:
FINAL ANSWER: [YOUR FINAL ANSWER]. YOUR FINAL ANSWER should be a number OR as few words as possible OR a comma separated list of numbers and/or strings.
If you are asked for a number, don't use comma to write your number neither use units such as $ or percent sign unless specified otherwise.
If you are asked for a string, don't use articles, neither abbreviations (e.g. for cities), and write the digits in plain text unless specified otherwise.
If you are asked for a comma separated list, apply the above rules depending of whether the element to be put in the list is a number or a string.
"""

GSM8K_NORMALIZATION_PROMPT = """
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


@app.command()
def main(
    run_id: str = typer.Option(..., help="Run ID"),
    model_name: ModelName = ModelName.CLAUDE_3_5_SONNET_20241022,
    subset: Annotated[EvaluationSubset | None, typer.Option(help="Subset of the dataset to evaluate")] = None,
    debug: Annotated[bool, typer.Option(help="Debug mode")] = False,
):
    asyncio.run(amain(**locals()))


async def amain(
    run_id: str,
    model_name: ModelName,
    subset: EvaluationSubset | None,
    debug: bool,
):
    print(
        f"Starting evaluation run '{run_id}' of '{model_name}' on '{'full dataset' if subset is None else f'subset {subset}'}'"
    )
    prepare_workspace()

    output_run_dir = EVAL_OUTPUT_DIR / run_id
    if not output_run_dir.exists():
        output_run_dir.mkdir(parents=True)

    print(f"Output directory: {output_run_dir.absolute()}")

    dataset = datasets.load_dataset("m-ric/agents_medium_benchmark_2")
    dataset = dataset["train"]

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
    if not EVAL_WORKSPACE_SKILLS_PATH.exists():
        EVAL_WORKSPACE_SKILLS_PATH.mkdir(parents=True)

    if not (EVAL_WORKSPACE_SKILLS_PATH / "google_search").exists():
        shutil.copytree(EVAL_SKILLS_SOURCE_PATH / "google_search", EVAL_WORKSPACE_SKILLS_PATH / "google_search")

    if not (EVAL_WORKSPACE_SKILLS_PATH / "visit_webpage").exists():
        shutil.copytree(EVAL_SKILLS_SOURCE_PATH / "visit_webpage", EVAL_WORKSPACE_SKILLS_PATH / "visit_webpage")


async def evaluate_agent(
    dataset,
    output_dir: Path,
    model_name: ModelName,
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
            if source == "GSM8K":
                normalization_prompt = GSM8K_NORMALIZATION_PROMPT
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
    model_name: ModelName,
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
    model_name: ModelName,
    question: str,
    normalization_prompt: str,
    debug: bool,
) -> tuple[list[str], str]:
    async with execution_environment(
        executor_key=EVAL_EXECUTOR_KEY,
        ipybox_tag=EVAL_IPYBOX_TAG,
        workspace_path=EVAL_WORKSPACE_PATH,
        log_file=EVAL_LOG_FILE,
        env_vars=dotenv_variables(),
    ) as env:
        skill_sources = await env.executor.get_module_sources(
            ["google_search.api", "visit_webpage.api"],
        )
        if model_name in [ModelName.CLAUDE_3_5_SONNET_20241022, ModelName.CLAUDE_3_5_HAIKU_20241022]:
            model = Claude(model_name=model_name, logger=env.logger)  # type: ignore
        elif model_name == ModelName.GEMINI_2_0_FLASH_EXP:
            model = Gemini(
                model_name=model_name,  # type: ignore
                skill_sources=skill_sources,
                temperature=0.0,
                max_tokens=8096,
            )
        else:
            raise ValueError(f"Unknown model: {model_name}")

        agent = CodeActAgent(model=model, executor=env.executor)

        agent_turn = agent.run(question, skill_sources=skill_sources)
        agent_output = await collect_output(agent_turn, debug=debug)

        normalization_turn = agent.run(normalization_prompt, skill_sources=skill_sources)
        normalization_output = await collect_output(normalization_turn, debug=debug)

        normalized_answer = normalization_output[-1].replace("[agent ]", "").strip()
        return agent_output + normalization_output, normalized_answer


async def collect_output(agent_turn: CodeActAgentTurn, debug: bool = True) -> List[str]:
    output = []
    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as model_turn:
                model_response = await model_turn.response()
                # TODO: rename to [model] (extra blank?)
                output.append("[agent ] " + model_response.text)
                if debug:
                    # TODO: rename to "Model response:"
                    print("Agent response:")
                    print(model_response.text)

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
