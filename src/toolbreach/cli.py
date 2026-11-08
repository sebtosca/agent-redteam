"""Command-line entry point. Fleshed out in P1.T7."""

import typer

app = typer.Typer(
    name="toolbreach",
    help="Red-team your own tool-using LLM agents.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Red-team your own authorized tool-using LLM agents in CI."""


@app.command()
def version() -> None:
    """Print the installed toolbreach version."""
    from toolbreach import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
