import click

DEBUG = False


def log(*args, **kwargs):
    click.echo(click.style(*args, **kwargs))


def info(*args, **kwargs):
    kwargs.update(fg="green")
    log(*args, **kwargs)


def warn(*args, **kwargs):
    kwargs.update(fg="yellow")
    log(*args, **kwargs)


def error(*args, **kwargs):
    kwargs.update(fg="red")
    log(*args, **kwargs)


def debug(*args, **kwargs):
    if DEBUG:
        print("DEBUG ********************************")
        print(*args, **kwargs)
