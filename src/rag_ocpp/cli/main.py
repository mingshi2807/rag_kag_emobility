"""CLI entry point — typer app with ingest, query, eval commands."""

import typer

app = typer.Typer(
    name="rag",
    help="RAG/KAG pipeline CLI for OCPP 2.1 enterprise knowledge.",
    no_args_is_help=True,
)

from rag_ocpp.cli.ingest import ingest_command
from rag_ocpp.cli.query import query_command
from rag_ocpp.cli.eval import eval_retrieval
from rag_ocpp.cli.corpus import corpus_command, index_corpus_command

app.command(name="ingest")(ingest_command)
app.command(name="corpus")(corpus_command)
app.command(name="index-corpus")(index_corpus_command)
app.command(name="query")(query_command)
app.command(name="eval")(eval_retrieval)

if __name__ == "__main__":
    app()
