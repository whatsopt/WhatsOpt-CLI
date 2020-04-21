import click

DEBUG = False


def log(*args, **kwargs):
    click.echo(click.style(*args, **kwargs))


def info(msg, **kwargs):
    kwargs.update(fg="green")
    log(msg, **kwargs)


def warn(msg, **kwargs):
    kwargs.update(fg="yellow")
    log(msg, **kwargs)


def error(msg, **kwargs):
    kwargs.update(fg="red")
    log("Error: {}".format(msg), **kwargs)


def debug(msg):
    if DEBUG:
        print("DEBUG ********************************")
        print(msg)
