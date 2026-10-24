# Paper

**Aligning cybersecurity investment with business-impact risk: A knowledge-based AI
decision-support model evaluated on real-world incident data**
Rahul Chandra Nandagiri, Midwest University, Wentzville, Missouri, United States

Short Communication submitted to *Knowledge-Based Systems* (Elsevier) on 24 October 2026.
The files here are the submitted version (preprint), not a peer-reviewed or published version.

**Read the paper: [Manuscript.pdf](Manuscript.pdf)**

| File | Contents |
|---|---|
| [`Manuscript.pdf`](Manuscript.pdf) | The paper (17 pages) |
| [`Manuscript.docx`](Manuscript.docx) | Editable Word version, as submitted |
| [`Supplementary_Material.pdf`](Supplementary_Material.pdf) / `.docx` | Supplementary tables S1-S10 |
| [`Highlights.pdf`](Highlights.pdf) / `.docx` | The five journal highlights |
| [`../results/figures/`](../results/figures) | Figure 1, Figure 2 and the graphical abstract (PNG 600 dpi and PDF) |
| [`../results/tables/`](../results/tables) | Table 1, Table 2 and the supplementary tables as CSV |
| [`submission/Cover_Letter.pdf`](submission/Cover_Letter.pdf) / `.docx` | Cover letter to the editor |
| [`submission/Submission_Readiness_Report.pdf`](submission/Submission_Readiness_Report.pdf) / `.docx` | Journal-compliance checklist, figure and table checks, reference verification |
| [`build/`](build) | Scripts that generate all of the Word files above from `results/` |

## Rebuild the documents

Every number in the paper is read from `results/`, and `verify.py` checks each quoted number
against `results/summary.json` and the result tables (81 checks).

```bash
# from the repository root: regenerate results/ (see the main README)
python run_experiment.py

# then build the Word files
cd paper/build
npm install          # installs docx 9.8.1
npm run build        # writes out/*.docx and runs the 81 checks (needs pandas and pandoc)

# optional: PDFs with LibreOffice
soffice --headless --convert-to pdf --outdir out out/*.docx
```

`npm run build` runs, in order: `export_tables.py` (writes `tables.json`),
`build_manuscript.js`, `build_extras.js` (highlights, supplementary material, cover letter),
`verify.py` (writes `verification.json`) and `build_report.js` (readiness report).
