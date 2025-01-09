from pathlib import Path
from typing import Annotated

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import typer

from evaluation import EVAL_RESULTS_FILE

OUTPUT_PATH = Path("output/evaluation-report")

app = typer.Typer()


@app.command()
def performance():
    df = read_evaluation_results()
    df["source_protocol"] = df.apply(
        lambda row: f"{row['source']} ({row['eval_protocol']})",
        axis=1,
    )

    create_barplot(
        data=df,
        figsize=(10, 6),
        palette="Blues_d",
        hue="source_protocol",
        hue_order=["GAIA (exact_match)", "GSM8K (exact_match)", "SimpleQA (exact_match)", "SimpleQA (llm_as_judge)"],
        title="freeact performance on m-ric/agents_medium_benchmark_2",
        output_file=OUTPUT_PATH / "plot.png",
    )

    print("Results:")
    print(df.drop(columns=["source_protocol"]))


def read_evaluation_results() -> pd.DataFrame:
    if not EVAL_RESULTS_FILE.exists():
        raise FileNotFoundError(f"Evaluation results file not found at {EVAL_RESULTS_FILE}")

    return pd.read_csv(EVAL_RESULTS_FILE).reset_index(drop=True)


def create_barplot(
    data: pd.DataFrame,
    figsize: tuple[int, int],
    palette: str,
    hue: str,
    hue_order: list[str],
    title: str,
    output_file: Path,
):
    sns.set_style("whitegrid")
    plt.figure(figsize=figsize)

    ax = sns.barplot(
        data=data,
        x="model_id",
        y="correct",
        hue=hue,
        hue_order=hue_order,
        palette=palette,
        width=0.8,
        capsize=0.1,
        err_kws={"linewidth": 2},
    )
    ax.set_xlabel("")
    ax.set_ylabel("% Correct")
    ax.spines["top"].set_visible(False)

    plt.title(title)
    plt.legend(fontsize=10, bbox_to_anchor=(1.05, 0.5), loc="center left")
    plt.xticks(rotation=0, fontsize=8)

    if not output_file.parent.exists():
        output_file.parent.mkdir(parents=True)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()


@app.command()
def comparison_plot(
    reference_results: Annotated[
        Path, typer.Option(..., help="Path to CSV file with reference results for comparison")
    ],
):
    df = read_evaluation_results()
    df = df[df["model_id"] == "claude-3-5-sonnet-20241022"]
    df = df[df["eval_protocol"] == "exact_match"]

    reference_data = pd.read_csv(reference_results)
    df = pd.concat([df.assign(model_id=lambda x: "freeact (zero-shot)"), reference_data]).reset_index(drop=True)

    create_barplot(
        data=df,
        figsize=(8, 6),
        palette="Blues_d",
        hue="source",
        hue_order=["GAIA", "GSM8K", "SimpleQA"],
        title="freeact vs. smolagents performance on m-ric/agents_medium_benchmark_2\n(model = claude-3-5-sonnet-20241022, eval protocol = exact_match)",
        output_file=OUTPUT_PATH / "plot-comparison.png",
    )

    print("Results:")
    print(df)


if __name__ == "__main__":
    app()
