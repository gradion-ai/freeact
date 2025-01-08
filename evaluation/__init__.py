from pathlib import Path

EVAL_SKILLS_SOURCE_PATH = Path("evaluation/skills")
EVAL_WORKSPACE_PATH = Path("workspace")
EVAL_WORKSPACE_SKILLS_PATH = EVAL_WORKSPACE_PATH / "skills" / "shared"

EVAL_EXECUTOR_KEY = "agent-evaluation"
EVAL_IPYBOX_TAG = "ghcr.io/gradion-ai/ipybox:eval"
EVAL_LOG_FILE = Path("logs/agent-evaluation.log")
EVAL_OUTPUT_DIR = Path("output/evaluation")
EVAL_RESULTS_FILE = Path("output/evaluation-results.csv")
