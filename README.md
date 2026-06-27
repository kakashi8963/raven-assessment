# Datasheet Backend Assignment

A large part of working at Raven is to extract knowledge and insights from a factory plant's documentation. In this assignment, you are going to extract structured fields from process datasheets.

These structured fields can then be used for other applications like search, technical bid evaluation and more.

In this version of the assignment you are given the datasheets **and the expected structured fields** for each. Your job is to write code that reproduces those fields from the PDF, and to make that code **generic** - it should extend to other equipment types, layouts and companies, not be hard-coded to these four sheets. The four datasheets here are a development set, not the target.

## Context

A process datasheet is a structured technical document that spells out what the equipment does and under what conditions (flows, temperatures, pressures, materials, etc). See the PDF files in the repo.

You can imagine a search agent using the knowledge in form of queries:
- What is the material for impeller in pump P300228?
- For P300228, what fluid is pumped, and what are the nominal and maximum flow rates?
- For P300228, whether the pump will corrode / erode over time?
- For P600173, what estimated efficiency of the motor?

Extracting process datasheets requires a few challenges: handling complex layouts, performance curves and more. In this assignment, you are going to work with a few simplified datasheets to extract relevant information.

## Inputs Provided

Four datasheets, each paired with its expected structured fields:

| Datasheet | Expected fields |
|---|---|
| `pds-P718.pdf` | `golden/pds-P718.json` |
| `pds-P818.pdf` | `golden/pds-P818.json` |
| `pds-P300228.pdf` | `golden/pds-P300228.json` |
| `pds-P600173.pdf` | `golden/pds-P600173.json` |

Each `golden/*.json` is the expected output for its PDF. Use these files as the schema, by example - read a couple to see the shape your extractor should produce:

```json
{
  "source_pdf": "pds-P300228.pdf",
  "fields": [
    { "name": "Nominal Flow", "value": "3.35", "unit": "m3/h", "section": "CONDITIONS OPERATOIRES / OPERATING CONDITIONS", "context": "nominal flow" },
    { "name": "Coupling Type", "value": null, "unit": null, "section": null, "context": null }
  ]
}
```

Each field carries:
- `name` - the field label as it reads on the sheet.
- `value` - the extracted value, or `null` when the field is present on the sheet but has no value. `null` is a correct answer, not a miss.
- `unit` - the unit of measurement, or `null` when there is none.
- `section` - the section heading the field sits under, or `null`.
- `context` - a short disambiguator when the name alone is ambiguous (e.g. which column or operating condition), or `null`.

## What You'll Build

An extraction pipeline - a CLI or a function - that takes a datasheet PDF and produces structured fields in the shape shown above. Run it over the four PDFs and compare your output against the `golden/` files.

Think about how you would measure your own accuracy (coverage and value/unit correctness), and how your output ties each field back to where it came from in the PDF.

## Logistics

- **Time:** 24 hours.
- **Tools:** Anything.
- **Stack:** Anything.
- **Submission:** Create a private fork of this github repo, and share it with the evaluator at the end of the task. Include a short note on your approach, the trade-offs you made, how you evaluated accuracy, and what you would improve with more time.

If you are unsure, ask questions to clarify whether something is allowed.

## Evaluation Criteria

You will be evaluated on the following:
- **Quality** - how well your output reproduces the expected fields: coverage and value/unit correctness.
- **Generality** - whether the approach extends beyond these four sheets to other equipment types, layouts and companies. A solution that hard-codes these sheets (e.g. a per-sheet lookup) will be marked down.
- **Provenance** - whether your output ties each field back to where it appears in the source PDF. We are specifically looking for word-level bounding boxes: for each field's label and its value, the page and the coordinates of the exact word(s) on that page they were read from, so a reviewer can highlight the precise text on the page rather than just the region or row it came from.
- **Cost** - cost per document, and your understanding of where and why the pipeline fails.

We are not expecting production-grade accuracy or model training. We care most about engineering judgment, system design, reliability, evaluation, and thoughtful trade-offs.

## What We're Not Looking For

Do not invest effort in:
- Deployment
- A user interface
# raven-assessment
