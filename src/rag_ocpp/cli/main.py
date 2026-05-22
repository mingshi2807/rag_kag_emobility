"""CLI entry point — typer app with ingest, query subcommands."""

import typer

app = typer.Typer(
    name="rag",
    help="RAG/KAG pipeline CLI for OCPP 2.1 enterprise knowledge.",
    no_args_is_help=True,
)

from rag_ocpp.cli.ingest import ingest_app
from rag_ocpp.cli.query import query_app
from rag_ocpp.cli.eval import eval_app

app.add_typer(ingest_app, name="ingest", help="Ingest documents into the knowledge base")
app.add_typer(query_app, name="query", help="Query the knowledge base")
app.add_typer(eval_app, name="eval", help="Evaluate retrieval quality")

if __name__ == "__main__":
    app()
