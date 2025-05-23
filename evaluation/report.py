from pathlib import Path
from typing import Annotated, Literal

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import typer

from evaluation.score import RESULTS_FILE

OUTPUT_DIR = Path("output", "evaluation-report")

app = typer.Typer()


@app.command()
def performance(
    results_file: Annotated[
        Path,
        typer.Option(help="Path to results file"),
    ] = RESULTS_FILE,
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory"),
    ] = OUTPUT_DIR,
    benchmark_display_name: Annotated[
        str,
        typer.Option(help="Display name of the dataset"),
    ] = "\nm-ric/agents_medium_benchmark_2 (GAIA, GSM8K, SimpleQA)\nm-ric/smol_agents_benchmark (MATH)",
):
    df = read_evaluation_results(results_file)
    df["source_protocol"] = df.apply(
        lambda row: f"{row['source']} ({row['eval_protocol']})",
        axis=1,
    )

    hue_order = df["model_id"].unique().tolist()

    create_barplot(
        data=df,
        figsize=(10, 6),
        palette="coolwarm",
        hue="model_id",
        hue_order=hue_order,
        title=f"freeact performance on {benchmark_display_name}",
        output_file=output_dir / "eval-plot.png",
        legend_location="top",
    )

    print("Results:")
    print(df.drop(columns=["source_protocol"]))


def read_evaluation_results(results_file: Path) -> pd.DataFrame:
    if not results_file.exists():
        raise FileNotFoundError(f"Evaluation results file not found at {results_file}")

    return pd.read_csv(results_file).reset_index(drop=True)


def create_barplot(
    data: pd.DataFrame,
    figsize: tuple[int, int],
    palette: str | list[str],
    hue: str,
    hue_order: list[str],
    title: str,
    output_file: Path,
    legend_location: Literal["top", "right"] = "right",
):
    sns.set_style("whitegrid")
    plt.figure(figsize=figsize)

    ax = sns.barplot(
        data=data,
        x="source_protocol",
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

    if legend_location == "top":
        plt.title(title, pad=70)
        plt.legend(fontsize=10, bbox_to_anchor=(0.5, 1.10), loc="center", ncol=2)
    else:
        plt.title(title)
        plt.legend(fontsize=10, bbox_to_anchor=(1.05, 0.5), loc="center left")

    plt.xticks(rotation=0, fontsize=8)

    if not output_file.parent.exists():
        output_file.parent.mkdir(parents=True)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()


@app.command()
def performance_comparison(
    reference_results_file: Annotated[
        Path, typer.Option(..., help="Path to CSV file with reference results for comparison")
    ],
    results_file: Annotated[
        Path,
        typer.Option(help="Path to results file"),
    ] = RESULTS_FILE,
    model_name: Annotated[
        str,
        typer.Option(help="Model name"),
    ] = "claude-3-5-sonnet-20241022",
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory"),
    ] = OUTPUT_DIR,
    benchmark_display_name: Annotated[
        str,
        typer.Option(help="Display name of the dataset"),
    ] = "m-ric/agents_medium_benchmark_2",
):
    eval_protocol = "exact_match"

    df_ref = pd.read_csv(reference_results_file)
    df_ref = df_ref[df_ref["model_id"] == model_name]
    df_ref = df_ref[df_ref["eval_protocol"] == eval_protocol]

    df = read_evaluation_results(results_file)
    df = df[df["model_id"] == model_name]
    df = df[df["eval_protocol"] == eval_protocol]
    df = df[df["source"].isin(["GAIA", "GSM8K", "SimpleQA"])]

    df = pd.concat(
        [
            df.assign(model_id=lambda x: "freeact (zero-shot)"),
            df_ref.assign(model_id=lambda x: "smolagents (few-shot)"),
        ]
    ).reset_index(drop=True)

    df["source_protocol"] = df.apply(
        lambda row: f"{row['source']}",
        axis=1,
    )

    create_barplot(
        data=df,
        figsize=(6, 6),
        palette=["#8099e1", "#ec9381"],
        hue="model_id",
        hue_order=["freeact (zero-shot)", "smolagents (few-shot)"],
        title=f"freeact vs. smolagents performance on\n{benchmark_display_name}\n\n(model = {model_name}\neval_protocol = {eval_protocol})",
        output_file=output_dir / f"eval-plot-comparison-{model_name}.png",
    )

    print("Results:")
    print(df.drop(columns=["source_protocol"]))


if __name__ == "__main__":
    app()
