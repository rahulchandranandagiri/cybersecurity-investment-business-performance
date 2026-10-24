# Paper

**Aligning cybersecurity investment with business-impact risk: A knowledge-based AI
decision-support model evaluated on real-world incident data**
Rahul Chandra Nandagiri, Midwest University, Wentzville, Missouri, United States

Short Communication submitted to *Knowledge-Based Systems* (Elsevier) on 24 October 2026.
The files here are the submitted version (preprint), not a peer-reviewed or published version.

**Read the paper: [Manuscript.pdf](Manuscript.pdf)**

| File | Contents |
|---|---|
| [`Manuscript.pdf`](Manuscript.pdf) / [`.docx`](Manuscript.docx) | The paper (17 pages), as submitted |
| [`Supplementary_Material.pdf`](Supplementary_Material.pdf) / `.docx` | Supplementary tables S1-S10 |
| [`Highlights.pdf`](Highlights.pdf) / `.docx` | The five journal highlights |
| [`Cover_Letter.pdf`](Cover_Letter.pdf) / `.docx` | Cover letter to the editor |
| [`Submission_Readiness_Report.pdf`](Submission_Readiness_Report.pdf) / `.docx` | Journal-compliance checklist, figure and table checks, reference verification |
| [`verify_manuscript.py`](verify_manuscript.py) | Checks the manuscript against the experiment outputs |
| [`../results/figures/`](../results/figures) | Figure 1, Figure 2 and the graphical abstract (PNG 600 dpi and PDF) |
| [`../results/tables/`](../results/tables) | Table 1, Table 2 and the supplementary tables as CSV |

## Check the paper against the results

```bash
python run_experiment.py              # regenerates results/ (see the main README)
python paper/verify_manuscript.py     # 81 checks
```

`verify_manuscript.py` reads the Word files directly and checks the journal limits (abstract
length, keywords, highlights), that all 36 references are cited in order, that every table,
figure, equation and supplementary table referred to exists, and that every number quoted in
the text equals the value in `results/summary.json` and the result tables. It exits with an
error if any check fails.
