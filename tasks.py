from sys import platform

from invoke import task


@task
def precommit_install(c):
    c.run("pre-commit install")


@task(aliases=["cc"])
def code_check(c):
    c.run("pre-commit run --all-files")


@task
def build_docs(c):
    c.run("mkdocs build")


@task
def serve_docs(c):
    c.run("mkdocs serve -a 0.0.0.0:8001")


@task
def deploy_docs(c):
    c.run("mkdocs gh-deploy --force")


@task
def test(c, cov=False, cov_report=None):
    _run_pytest(c, "tests", cov, cov_report)


@task(aliases=["ut"])
def unit_test(c, cov=False, cov_report=None):
    _run_pytest(c, "tests/unit", cov, cov_report)


@task(aliases=["it"])
def integration_test(c, cov=False, cov_report=None):
    _run_pytest(c, "tests/integration", cov, cov_report)


def _run_pytest(c, test_dir, cov=False, cov_report=None):
    c.run(f"pytest {test_dir} {_pytest_cov_options(cov, cov_report)} --no-flaky-report", pty=_use_pty())


def _use_pty():
    return platform != "win32"


def _pytest_cov_options(use_cov: bool, cov_reports: str | None):
    if not use_cov:
        return ""

    cov_report_types = cov_reports.split(",") if cov_reports else []
    cov_report_types = ["term"] + cov_report_types
    cov_report_params = [f"--cov-report {r}" for r in cov_report_types]
    return f"--cov {' '.join(cov_report_params)}"
