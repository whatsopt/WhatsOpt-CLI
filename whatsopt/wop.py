import click
from whatsopt import __version__
from whatsopt.utils import get_analysis_id
from .whatsopt_client import WhatsOpt, EXTRANET_SERVER_URL
from logging import error

DEFAULT_PUSH_DEPTH = 2


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, "-v", "--version")
@click.option("--credentials", help="specify authentication information (API key)")
@click.option(
    "--url",
    help="specify WhatsOpt application server URL (default: {})".format(
        EXTRANET_SERVER_URL
    ),
)
@click.pass_context
def wop(ctx, credentials, url):
    ctx.ensure_object(dict)  # create context dictionary ctx.obj ={}
    ctx.obj["api_key"] = credentials
    ctx.obj["url"] = url


@wop.command()
@click.argument("url")
@click.pass_context
def login(ctx, url):
    """Authenticate to the specified WhatsOpt server given its URL."""
    ctx.obj["url"] = url
    WhatsOpt(**ctx.obj).login(echo=True)


@wop.command()
@click.option(
    "-l",
    "--list",
    is_flag=True,
    default=False,
    help="List login infos of known remote servers",
)
@click.option(
    "-a",
    "--all",
    is_flag=True,
    default=False,
    help="Remove login infos of known remote servers",
)
@click.option(
    "-r",
    "--remote",
    type=str,
    help="Remove login infos related to given remote server name",
)
def logout(list, all, remote):
    """Deconnect from WhatsOpt server."""
    WhatsOpt().logout(list, all, remote)


@wop.command()
@click.option(
    "-a", "--all", is_flag=True, default=False, help="list all analyses available"
)
@click.option(
    "-p",
    "--project-query",
    type=str,
    help="list all analyses available whose project name matches the given substring",
)
@click.option(
    "-r",
    "--remotes",
    is_flag=True,
    default=False,
    help="list all known remote servers",
)
@click.pass_context
def list(ctx, all, project_query, remotes):
    """List analyses owned by the user."""
    if remotes:
        WhatsOpt.list_remotes()
    else:
        WhatsOpt(**ctx.obj).login().list_analyses(all, project_query)


@wop.command()
@click.pass_context
def status(ctx):
    """List server connection and current pulled analysis status."""
    WhatsOpt(**ctx.obj).get_status()


@wop.command()
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
    help="specify the max depth of the sub-analysis nesting (0 meaning no limit, default is 2)",
)
@click.option(
    "--json",
    is_flag=True,
    default=False,
    help="import analysis from file in WhatsOpt analysis json format (disable other options)",
)
@click.argument("filename")
@click.pass_context
def push(ctx, dry_run, scalar, name, component, depth, json, filename):
    """Push OpenMDAO problem or WhatsOpt analysis json from given FILENAME."""
    wop = WhatsOpt(**ctx.obj)
    if not dry_run:
        wop.login()
    options = {
        "--dry-run": dry_run,
        "--scalar": scalar,
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


@wop.command()
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
    "--gemseo/--openmdao",
    default=False,
    help="pull analysis as GEMSEO source code (default OpenMDAO)",
)
@click.option(
    "--package/--plain",
    default=True,
    help="pull analysis as Python package (default) or plain mode (--plain)",
)
@click.argument("analysis_id")
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
    package,
    analysis_id,
):
    """Pull analysis given its identifier."""
    options = {
        "--dry-run": dry_run,
        "--force": force,
        "--server": server,
        "--egmdo": egmdo,
        "--run-ops": run_ops,
        "--test-units": test_units,
        "--gemseo": gemseo,
        "--package": package,
    }
    wop = WhatsOpt(**ctx.obj).login()
    if json:
        if project_id:
            wop.pull_project_json(analysis_id)
        else:
            wop.pull_mda_json(analysis_id)
    else:
        if project_id:
            error("Bad option --project-id which works only with option --json enabled")
            exit(-1)
        current_id = get_analysis_id()
        if current_id and analysis_id != current_id:
            wop.pull_source_mda(analysis_id, options)
        else:
            wop.pull_mda(analysis_id, options)


@wop.command()
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="print analysis update info without actually updating",
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
    """Update analysis connections."""
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
    WhatsOpt(**ctx.obj).login().update_mda(analysis_id, options)


@wop.command()
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
    """Upload data stored in given FILENAME results (sqlite, csv or hdf5 format) or mda init python file."""
    wop = WhatsOpt(**ctx.obj)
    if not dry_run:
        wop.login()
    wop.upload(
        filename,
        driver_kind,
        analysis_id,
        operation_id,
        dry_run,
        outvar_count,
        only_success,
        parallel,
    )


@wop.command()
@click.option(
    "-a",
    "--analysis-id",
    help="specify the id of the analysis available on the remote server",
)
@click.option(
    "-f", "--pbfile", help="specify the analysis given an OpenMDAO problem python file"
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
    help="specify the max depth of the sub-analysis nesting (0 meaning no limit, default is 2)",
)
@click.pass_context
def show(ctx, analysis_id, pbfile, name, outfile, batch, depth):
    """Show current analysis from pulled code or given its identifier (-a) on remote server
    or discovered in OpenMDAO problem file (-f)."""

    if pbfile is None:
        wop = WhatsOpt(**ctx.obj).login()
    else:
        ctx.obj["url"] = EXTRANET_SERVER_URL
        wop = WhatsOpt(**ctx.obj)
    wop.show_mda(analysis_id, pbfile, name, outfile, batch, depth)


@wop.command()
@click.pass_context
def version(ctx):
    """Show versions of WhatsOpt app and recommended wop command line."""
    WhatsOpt(**ctx.obj).login().check_versions()


@wop.command()
@click.option(
    "-p",
    "--port",
    default=31400,
    type=int,
    help="specify the listening port number of the analysis server.",
)
def serve(port):
    """Launch analysis server."""
    WhatsOpt().serve(port)


@wop.command()
@click.argument("sqlite_filename")
def convert(
    sqlite_filename,
):
    """Convert given sqlite file from OpenMDAO to csv file format."""
    WhatsOpt().convert(sqlite_filename)


@wop.command()
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="overwrite current published package anyway",
)
@click.pass_context
def publish(ctx, force):
    """Publish current analysis as Python package on WhatsOpt Package Store. Package mode is required."""
    WhatsOpt(**ctx.obj).login().publish(force)


@wop.command()
@click.pass_context
def build(ctx):
    """Build current analysis package. Package mode is required."""
    WhatsOpt(**ctx.obj).login().build()


@wop.command()
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="print analysis fetch info without actually fetching",
)
@click.option(
    "-f", "--force", is_flag=True, default=False, help="overwrite existing files"
)
@click.argument("source_id")
@click.pass_context
def fetch(ctx, source_id, dry_run, force):
    """Fetch package content of the given analysis specified by its identifier"""
    options = {"--dry-run": dry_run, "--force": force}
    WhatsOpt(**ctx.obj).login().fetch(source_id, options)


@wop.command()
@click.argument("analysis_id")
@click.pass_context
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="print analysis merge info without actually merging",
)
def merge(ctx, analysis_id, dry_run):
    """Merge the given analysis to the current one.
    All the disciplines of the to-be-merged analysis are imported. The command may fail
    if imported disciplines are not compatible (eg an output variable is already produced
    by a discipline of the current analysis)."""
    options = {"--dry-run": dry_run}
    WhatsOpt(**ctx.obj).login().merge(analysis_id, options)


if __name__ == "__main__":
    wop()
