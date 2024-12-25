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
