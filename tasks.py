from invoke import task


@task
def precommit_install(c):
    c.run("pre-commit install")


@task(aliases=["cc"])
def code_check(c):
    c.run("pre-commit run --all-files")
