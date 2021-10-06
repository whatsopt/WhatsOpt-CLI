import click
from whatsopt import __version__
from .whatsopt_client import WhatsOpt, EXTRANET_SERVER_URL
from logging import error

DEFAULT_PUSH_DEPTH = 2


@click.group()
@click.version_option(__version__)
@click.option("--credentials", help="specify authentication information (API key)")
@click.option(
    "--url",
    help="specify WhatsOpt application server URL (default: {})".format(
        WhatsOpt(login=False).default_url
    ),
)
@click.pass_context
def cli(ctx, credentials, url):
    ctx.ensure_object(dict)  # create context dictionary ctx.obj ={}
    ctx.obj["api_key"] = credentials
    ctx.obj["url"] = url


@cli.command()
@click.argument("url")
@click.pass_context
def login(ctx, url):
    """Authenticate to the specified WhatsOpt server given its URL"""
    ctx.obj["url"] = url
    WhatsOpt(**ctx.obj).login(echo=True)


@cli.command()
def logout():
    """Deconnect from WhatsOpt server"""
    WhatsOpt(login=False).logout()


@cli.command()
@click.option(
    "-a", "--all", is_flag=True, default=False, help="list all analyses available"
)
@click.option(
    "-p",
    "--project-query",
    type=str,
    help="list all analyses available whose project name matches the given substring",
)
@click.pass_context
def list(ctx, all, project_query):
    """List analyses owned by the user"""
    WhatsOpt(**ctx.obj).list_analyses(all, project_query)


@cli.command()
@click.pass_context
def status(ctx):
    """List server connection and current pulled analysis status"""
    WhatsOpt(login=False).get_status()


@cli.command()
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="generate analysis push data without actually pushing",
)
@click.option(
    "--scalar/--no-scalar",
    default=True,
    help="manage (1,) shape variables as scalar variables",
)
@click.option(
    "--old",
    is_flag=True,
    default=False,
    help="use old push implementation",
)
@click.option("--name", help="find analysis with given name")
@click.option(
    "-c",
    "--component",
    help="push the specified OpenMDAO component importable from the given python file",
)
@click.option(
    "-d",
    "--depth",
    default=DEFAULT_PUSH_DEPTH,
    help="specify the max depth of the sub-analysis nesting (0 meaning no limit, default is 3)",
)
@click.option(
    "--json",
    is_flag=True,
    default=False,
    help="import analysis from file in WhatsOpt analysis json format (disable other options)",
)
@click.argument("filename")
@click.pass_context
def push(ctx, dry_run, scalar, old, name, component, depth, json, filename):
    """Push OpenMDAO problem or WhatsOpt analysis json from given FILENAME"""
    ctx.obj["login"] = not dry_run
    wop = WhatsOpt(**ctx.obj)
    options = {
        "--dry-run": dry_run,
        "--scalar": scalar,
        "--old": old,
        "--name": name,
        "--depth": depth,
    }
    if component:
        wop.push_component_cmd(filename, component, options)
    elif json:
        wop.push_json(filename)
        exit()
    else:
        wop.push_mda_cmd(filename, options)

    # if not exited successfully in execute
    if name:
        error("Analysis %s not found" % name)
    else:
        error("Analysis not found")
    exit(-1)


@cli.command()
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="print analysis pull infos without actually pulling",
)
@click.option(
    "-f", "--force", is_flag=True, default=False, help="overwrite existing files"
)
@click.option(
    "-s", "--server", is_flag=True, default=False, help="generate Thrift server as well"
)
@click.option("--egmdo", is_flag=True, default=False, help="generate EGMDO method code")
@click.option(
    "-r", "--run-ops", is_flag=True, default=False, help="update operation run scripts"
)
@click.option(
    "-t",
    "--test-units",
    is_flag=True,
    default=False,
    help="update discipline test scripts",
)
@click.option(
    "--json",
    is_flag=True,
    default=False,
    help="export analysis in json format on stdout (disable other options)",
)
@click.option(
    "-p",
    "--project-id",
    is_flag=True,
    default=False,
    help="export project in json format on stdout (works only with --json)",
)
@click.option(
    "--gemseo",
    is_flag=True,
    default=False,
    help="pull analysis as GEMSEO source code (default OpenMDAO)",
)
@click.argument("ident")
@click.pass_context
def pull(
    ctx,
    dry_run,
    force,
    server,
    egmdo,
    run_ops,
    test_units,
    json,
    project_id,
    gemseo,
    ident,
):
    """Pull analysis given its identifier"""
    options = {
        "--dry-run": dry_run,
        "--force": force,
        "--server": server,
        "--egmdo": egmdo,
        "--run-ops": run_ops,
        "--test-units": test_units,
        "--gemseo": gemseo,
        "--egmdo": egmdo,
    }
    if json:
        if project_id:
            WhatsOpt(**ctx.obj).pull_project_json(ident)
        else:
            WhatsOpt(**ctx.obj).pull_mda_json(ident)
    else:
        if project_id:
            error("Bad option --project-id which works only with option --json enabled")
            exit(-1)
        WhatsOpt(**ctx.obj).pull_mda(ident, options)


@cli.command()
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="print analysis update infos without actually updating",
)
@click.option(
    "-a",
    "--analysis-id",
    help="specify the analysis to update from (otherwise guessed from current files)",
)
@click.option(
    "-f", "--force", is_flag=True, default=False, help="overwrite existing files"
)
@click.option(
    "-s", "--server", is_flag=True, default=False, help="update Thrift server as well"
)
@click.option("--egmdo", is_flag=True, default=False, help="update EGMDO code as well")
@click.option(
    "-r", "--run-ops", is_flag=True, default=False, help="update operation run scripts"
)
@click.option(
    "-t",
    "--test-units",
    is_flag=True,
    default=False,
    help="update discipline test scripts",
)
@click.option(
    "--gemseo",
    is_flag=True,
    default=False,
    help="update analysis as GEMSEO source code (otherwise OpenMDAO)",
)
@click.option(
    "--openmdao",
    is_flag=True,
    default=False,
    help="update analysis as OpenMDAO source code (to be used when GEMSEO code has been pulled)",
)
@click.pass_context
def update(
    ctx,
    dry_run,
    analysis_id,
    force,
    server,
    egmdo,
    run_ops,
    test_units,
    gemseo,
    openmdao,
):
    """Update analysis connections"""
    options = {
        "--dry-run": dry_run,
        "--force": force,
        "--server": server,
        "--egmdo": egmdo,
        "--run-ops": run_ops,
        "--test-units": test_units,
        "--gemseo": gemseo,
        "--openmdao": openmdao,
    }
    WhatsOpt(**ctx.obj).update_mda(analysis_id, options)


@cli.command()
@click.argument("filename")
@click.option(
    "-k",
    "--driver-kind",
    type=click.Choice(["doe", "optimizer", "screening"]),
    help="used with csv data upload to specify driver kind",
)
@click.option(
    "-a",
    "--analysis-id",
    help="specify the analysis to create a new operation otherwise use default analysis",
)
@click.option(
    "-o", "--operation-id", help="specify the operation to be updated with new cases"
)
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="parse data file and display content without uploading",
)
@click.option(
    "-c",
    "--outvar-count",
    type=int,
    default=1,
    help="number of output variable (>0) only used when uploading csv file",
)
@click.option(
    "-x",
    "--only-success",
    is_flag=True,
    default=False,
    help="keep only data from successful executions",
)
@click.option(
    "-p", "--parallel", is_flag=True, default=False, help="use filename as first"
)
@click.pass_context
def upload(
    ctx,
    filename,
    driver_kind,
    analysis_id,
    operation_id,
    dry_run,
    outvar_count,
    only_success,
    parallel,
):
    """Upload data stored in given FILENAME being in results in sqlite or csv format or run parameters file"""
    ctx.obj["login"] = not dry_run
    WhatsOpt(**ctx.obj).upload(
        filename,
        driver_kind,
        analysis_id,
        operation_id,
        dry_run,
        outvar_count,
        only_success,
        parallel,
    )


@cli.command()
@click.option(
    "-a",
    "--analysis-id",
    help="specify the id of the analysis available on the remote server",
)
@click.option(
    "-f", "--pbfile", help="specify the analysis given an OpenMDAO problem python file"
)
@click.option(
    "--old",
    is_flag=True,
    default=False,
    help="use old push implementation",
)
@click.option(
    "--name", help="find analysis with given name (only used with pbfile option)"
)
@click.option(
    "-o", "--outfile", default="xdsm.html", help="specify output filename to store html"
)
@click.option(
    "-b",
    "--batch",
    is_flag=True,
    default=False,
    help="batch mode: do not launch browser",
)
@click.option(
    "-d",
    "--depth",
    default=DEFAULT_PUSH_DEPTH,
    help="specify the max depth of the sub-analysis nesting (0 meaning no limit, default is 3)",
)
@click.pass_context
def show(ctx, analysis_id, pbfile, old, name, outfile, batch, depth):
    """Show current analysis from pulled code or given its identifier (-a) on remote server
    or discovered in OpenMDAO problem file (-f)"""
    if pbfile is None:
        ctx.obj["login"] = True
    else:
        ctx.obj["login"] = False
        ctx.obj["url"] = EXTRANET_SERVER_URL
    WhatsOpt(**ctx.obj).show_mda(analysis_id, pbfile, old, name, outfile, batch, depth)


@cli.command()
@click.pass_context
def version(ctx):
    """Show versions of WhatsOpt app and recommended wop command line"""
    WhatsOpt(**ctx.obj).check_versions()


@cli.command()
@click.option(
    "-p",
    "--port",
    default=31400,
    type=int,
    help="specify the listening port number of the analysis server",
)
def serve(port):
    """Launch analysis server"""
    WhatsOpt(login=False).serve(port)


@cli.command()
@click.argument("sqlite_filename")
def convert(
    sqlite_filename,
):
    """Convert given sqlite file from OpenMDAO to csv file format"""
    WhatsOpt(login=False).convert(sqlite_filename)


if __name__ == "__main__":
    cli()
