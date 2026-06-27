"""CLI: extract, evaluate, report."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from datasheet_extract.config import Config, DEFAULT_DEPLOYMENT
from datasheet_extract.emit import assemble_fields, emit_output, filter_raw_fields
from datasheet_extract.eval.metrics import (
    AggregateMetrics,
    compute_doc_metrics,
    extract_provenance_from_json,
    load_fields_from_json,
)
from datasheet_extract.eval.report import evaluate, format_aggregate_report, format_doc_report
from datasheet_extract.ground.provenance import ground_field
from datasheet_extract.ingest.layout_doc import LayoutDoc
from datasheet_extract.llm.extract import extract_fields
from datasheet_extract.model import FieldOut, Usage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

GOLDEN_DIR = Path("golden")
PDF_NAMES = ["pds-P718.pdf", "pds-P818.pdf", "pds-P300228.pdf", "pds-P600173.pdf"]


def run_pipeline(
    pdf_path: str | Path,
    config: Config,
    *,
    output_path: Path | None = None,
) -> tuple[list[FieldOut], LayoutDoc, Usage]:
    path = Path(pdf_path)
    doc = LayoutDoc.from_pdf(path)

    raw_fields, usage = extract_fields(doc, config)
    log.info("Extracted %d raw fields", len(raw_fields))

    raw_fields = filter_raw_fields(raw_fields, doc)
    provenances = [ground_field(rf, doc) for rf in raw_fields]
    fields = assemble_fields(raw_fields, provenances)

    if output_path:
        emit_output(doc.source_pdf, fields, output_path)

    return fields, doc, usage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Datasheet field extraction pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract fields from a PDF")
    p_extract.add_argument("pdf", type=Path, help="Path to datasheet PDF")
    p_extract.add_argument("-o", "--output", type=Path, help="Output JSON path")
    p_extract.add_argument("--model", default=DEFAULT_DEPLOYMENT, help="Azure OpenAI deployment name")
    p_extract.add_argument("--ingest-only", action="store_true", help="Skip LLM; dump ingest render only")

    p_eval = sub.add_parser("evaluate", help="Compare prediction JSON against golden")
    p_eval.add_argument("pred", type=Path, help="Prediction JSON")
    p_eval.add_argument("gold", type=Path, help="Golden JSON")

    p_report = sub.add_parser("report", help="Run extract + evaluate on all dev PDFs")
    p_report.add_argument("--pdf-dir", type=Path, default=Path("."), help="Directory containing PDFs")
    p_report.add_argument("-o", "--output-dir", type=Path, default=Path("out"), help="Output directory")
    p_report.add_argument("--model", default=DEFAULT_DEPLOYMENT, help="Azure OpenAI deployment name")

    args = parser.parse_args(argv)

    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "evaluate":
        return cmd_evaluate(args)
    if args.command == "report":
        return cmd_report(args)
    return 1


def cmd_extract(args) -> int:
    config = Config(deployment=args.model)
    out = args.output or Path("out") / f"{args.pdf.stem}.json"

    if args.ingest_only:
        doc = LayoutDoc.from_pdf(args.pdf)
        render = doc.render()
        dump_path = out.with_suffix(".render.txt")
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(render, encoding="utf-8")
        print(f"Ingest dump: {len(doc.words)} words, {len(doc.lines)} lines, {len(doc.sections)} sections")
        print(f"Render written to {dump_path}")
        return 0

    fields, doc, usage = run_pipeline(args.pdf, config, output_path=out)
    print(f"Extracted {len(fields)} fields → {out}")
    print(f"Tokens: {usage.prompt_tokens} in / {usage.completion_tokens} out (${usage.cost_usd(config.pricing()):.4f})")
    return 0


def cmd_evaluate(args) -> int:
    _, _, report = evaluate(args.pred, args.gold, Config())
    print(report)
    return 0


def cmd_report(args) -> int:
    config = Config(deployment=args.model)
    agg = AggregateMetrics()

    for pdf_name in PDF_NAMES:
        pdf_path = args.pdf_dir / pdf_name
        gold_path = GOLDEN_DIR / pdf_name.replace(".pdf", ".json")

        if not pdf_path.exists():
            log.warning("PDF not found: %s — skipping", pdf_path)
            continue
        if not gold_path.exists():
            log.warning("Golden not found: %s — skipping", gold_path)
            continue

        out_path = args.output_dir / f"{pdf_path.stem}.json"
        try:
            fields, doc, usage = run_pipeline(pdf_path, config, output_path=out_path)
        except Exception as e:
            log.error("Pipeline failed for %s: %s", pdf_name, e)
            continue

        with open(gold_path, encoding="utf-8") as f:
            gold_data = json.load(f)
        with open(out_path, encoding="utf-8") as f:
            pred_data = json.load(f)

        gold = load_fields_from_json(gold_data)
        pred = load_fields_from_json(pred_data)
        pred_prov = extract_provenance_from_json(pred_data)

        metrics, result = compute_doc_metrics(
            pred,
            gold,
            source=pdf_name,
            pred_provenance=pred_prov,
            usage=usage,
            pricing=config.pricing(),
        )
        agg.docs.append(metrics)
        print(format_doc_report(pred, gold, result, metrics, pred_prov))

    if agg.docs:
        print(format_aggregate_report(agg))

    return 0


if __name__ == "__main__":
    sys.exit(main())
