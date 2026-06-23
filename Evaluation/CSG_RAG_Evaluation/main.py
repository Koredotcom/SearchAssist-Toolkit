from __future__ import annotations

import click
from rich.console import Console

from db.database import freeze_golden_set, init_db
from pipeline.evaluate import run_evaluation_pipeline
from pipeline.generate import run_generation_pipeline
from pipeline.import_gt import run_import_gt_pipeline

console = Console()


@click.group()
def cli() -> None:
    """RAG Evaluation Framework for Kore.ai SearchAI."""
    init_db()


@cli.command()
@click.option("--version", required=True, help="Golden set version, e.g. 1.0.0")
@click.option("--max-docs", default=10, show_default=True, help="Max documents to sample")
@click.option("--freeze", is_flag=True, help="Freeze golden set after generation")
def generate(version: str, max_docs: int, freeze: bool) -> None:
    """Fetch documents, run Agents 1-3, and build the golden test set."""
    stats = run_generation_pipeline(
        golden_set_version=version,
        max_docs=max_docs,
    )
    if freeze:
        freeze_golden_set(version)
        console.print(f"[bold green]Golden set {version} frozen.[/bold green]")


@cli.command()
@click.option("--version", required=True, help="Golden set version to evaluate against")
@click.option("--rag-version", default="unknown", show_default=True)
@click.option("--trigger", default="manual", type=click.Choice(["manual", "ci", "cron"]))
def evaluate(version: str, rag_version: str, trigger: str) -> None:
    """Query the RAG system with the golden set and judge the results."""
    run_evaluation_pipeline(
        golden_set_version=version,
        rag_version=rag_version,
        trigger=trigger,
    )


@cli.command()
@click.option("--version", required=True)
def freeze(version: str) -> None:
    """Freeze a golden set version so it cannot be modified."""
    freeze_golden_set(version)
    console.print(f"[bold green]Golden set {version} frozen.[/bold green]")


@cli.command("import-gt")
@click.option("--version", required=True, help="Golden set version, e.g. 1.0.0")
@click.option("--gt-path", multiple=True, required=True, help="Path to GT CSV file (repeat for multiple)")
@click.option("--notes", default="", help="Optional notes for this golden set")
@click.option("--freeze", is_flag=True, help="Freeze golden set after import")
def import_gt(version: str, gt_path: tuple[str, ...], notes: str, freeze: bool) -> None:
    """Import externally-generated ground truth CSVs into the golden set."""
    stats = run_import_gt_pipeline(list(gt_path), version, notes)
    console.print(f"[bold green]Imported {stats['imported']} test cases from {stats['files']} file(s).[/bold green]")
    if freeze:
        freeze_golden_set(version)
        console.print(f"[bold green]Golden set {version} frozen.[/bold green]")


if __name__ == "__main__":
    cli()
