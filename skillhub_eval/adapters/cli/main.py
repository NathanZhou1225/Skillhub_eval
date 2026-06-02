"""CLI entry point (expanded in Task 10)."""

import typer

app = typer.Typer(help="SkillHub Evaluation Engine CLI")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Show help when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
