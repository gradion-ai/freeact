import json
from enum import Enum
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from tqdm import tqdm

from evaluation import EVAL_RESULTS_FILE
from evaluation.scoring.gaia import get_question_score_gaia
from evaluation.scoring.gsm8k import get_question_score_gsm8k
from evaluation.scoring.simpleqa import SimpleQAScorer

app = typer.Typer()


class EvalProtocol(Enum):
    LLM_AS_JUDGE = "llm_as_judge"
    EXACT_MATCH = "exact_match"


@app.command()
def score(
    evaluation_dir: Annotated[
        list[Path], typer.Option(..., help="Paths to directories containing model evaluation results")
    ] = [],
):
    all_dfs = []
    model_ids = []
    for results_dir in evaluation_dir:
        df = pd.concat(
            [
                score_dataset(results_dir, "GAIA", EvalProtocol.EXACT_MATCH),
                score_dataset(results_dir, "SimpleQA", EvalProtocol.LLM_AS_JUDGE),
                score_dataset(results_dir, "SimpleQA", EvalProtocol.EXACT_MATCH),
                score_dataset(results_dir, "GSM8K", EvalProtocol.EXACT_MATCH),
            ]
        )
        all_dfs.append(df)
        model_ids.extend(df["model_id"].unique())

    df = pd.concat(all_dfs)
    df_stats = (df.groupby(["model_id", "source", "eval_protocol"])[["correct"]].mean() * 100).round(1).reset_index()

    df_stats["model_id"] = pd.Categorical(df_stats["model_id"], categories=model_ids, ordered=True)
    df_stats = df_stats.sort_values("model_id")
    df_stats["model_id"] = df_stats["model_id"].astype(str)

    print("Results:")
    print(df_stats)

    if not EVAL_RESULTS_FILE.parent.exists():
        EVAL_RESULTS_FILE.parent.mkdir(parents=True)

    df_stats.to_csv(EVAL_RESULTS_FILE, index=False)


def score_dataset(
    eval_results_dir,
    source: str,
    eval_protocol: EvalProtocol = EvalProtocol.LLM_AS_JUDGE,
) -> pd.DataFrame:
    _ids = []
    _model_id = []
    _correct = []
    _source = []
    _true_answer = []
    _answer = []
    _error_message = []

    simpleqa_scorer = SimpleQAScorer()

    files = list(eval_results_dir.glob("*.json"))

    for file in tqdm(files, desc=f"Scoring {source} results"):
        with open(file, "r") as f:
            example = json.load(f)

        if example["source"] != source:
            continue

        if "is_error" in example and example["is_error"]:
            if is_api_overload_error(example["error_message"]):
                raise ValueError(f"API rate limit exceeded for {file}. Please rerun the evaluation for this example.")
            else:
                print(
                    f"WARNING: Error in {file}: {example['error_message']}. This example will be counted as an incorrect result in the final statistics."
                )

        _ids.append(file.name)
        _model_id.append(example["model_name"])
        _source.append(example["source"])
        _correct.append(is_correct(example, simpleqa_scorer, eval_protocol))
        _true_answer.append(example["true_answer"])
        _answer.append(example["answer"])
        _error_message.append(example["error_message"] if "error_message" in example else None)

    return pd.DataFrame(
        {
            "id": _ids,
            "model_id": _model_id,
            "source": _source,
            "eval_protocol": [eval_protocol.value] * len(_ids),
            "correct": _correct,
            "true_answer": _true_answer,
            "answer": _answer,
            "error_message": _error_message,
        }
    )


def is_correct(example, simpleqa_scorer: SimpleQAScorer, eval_protocol: EvalProtocol):
    if "is_error" in example and example["is_error"]:
        return False

    answer = str(example["answer"])
    true_answer = str(example["true_answer"])
    question = str(example["question"])

    match example["source"]:
        case "GSM8K":
            return get_question_score_gsm8k(answer, true_answer)
        case "SimpleQA" if eval_protocol == EvalProtocol.LLM_AS_JUDGE:
            return simpleqa_scorer.score(question, answer, true_answer)
        case "SimpleQA" if eval_protocol == EvalProtocol.EXACT_MATCH:
            return get_question_score_gaia(answer, true_answer)
        case "GAIA":
            return get_question_score_gaia(answer, true_answer)
        case _:
            raise ValueError(f"Unknown dataset: {example['source']}")


def is_api_overload_error(error_message: str) -> bool:
    return "429 RESOURCE_EXHAUSTED" in error_message or "overloaded_error" in error_message


if __name__ == "__main__":
    app()
