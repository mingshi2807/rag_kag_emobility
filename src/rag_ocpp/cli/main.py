"""CLI entry point — typer app with ingest, query, eval commands."""

import typer

from rag_ocpp.cli.corpus import (
    corpus_command,
    corpus_status_command,
    index_corpus_command,
)
from rag_ocpp.cli.db import migrate_command, migrate_status_command
from rag_ocpp.cli.eval import eval_answers_command, eval_quality_command, eval_retrieval
from rag_ocpp.cli.ingest import ingest_command
from rag_ocpp.cli.query import query_command

app = typer.Typer(
    name="rag",
    help="RAG/KAG pipeline CLI for OCPP 2.1 enterprise knowledge.",
    no_args_is_help=True,
)

app.command(name="ingest")(ingest_command)
app.command(name="corpus")(corpus_command)
app.command(name="corpus-status")(corpus_status_command)
app.command(name="index-corpus")(index_corpus_command)
app.command(name="migrate")(migrate_command)
app.command(name="migrate-status")(migrate_status_command)
app.command(name="query")(query_command)
app.command(name="eval")(eval_retrieval)
app.command(name="eval-quality")(eval_quality_command)
app.command(name="eval-answers")(eval_answers_command)

if __name__ == "__main__":
    app()
