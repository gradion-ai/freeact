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
def test(c, cov=False):
    _run_pytest(c, "tests", cov)


@task(aliases=["ut"])
def unit_test(c, cov=False):
    _run_pytest(c, "tests/unit", cov)


@task(aliases=["it"])
def integration_test(c, cov=False):
    _run_pytest(c, "tests/integration", cov)


def _run_pytest(c, test_dir, cov=False):
    c.run(f"pytest -xsv {test_dir} {_pytest_cov_options(cov)}", pty=_use_pty())


def _use_pty():
    return platform != "win32"


def _pytest_cov_options(use_cov: bool):
    if not use_cov:
        return ""
    return "--cov=freeact --cov-report=term"
