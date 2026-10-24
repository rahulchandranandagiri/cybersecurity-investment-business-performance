// Builds Highlights.docx, Supplementary_Material.docx and Cover_Letter.docx.
const fs = require('fs');
const L = require('./lib');
const { d, para, heading, table, caption, note, footer, styles, runs, FONT, SIZE } = L;
const { Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat, PageBreak } = d;
const M = require('./build_manuscript');
const T = JSON.parse(fs.readFileSync(__dirname + '/tables.json', 'utf8'));
const OUT = __dirname + '/out/';

const HIGHLIGHTS = [
  'Knowledge base maps 9,284 real incidents to nine cybersecurity control families',
  'Knowledge features lift out-of-time material-impact prediction to AUC 0.891',
  'Threat-count budgeting underperforms an equal split on business-impact risk',
  'KB-CIDS beats equal and threat-count budgets in all 18 sector-size profiles',
  'Impact alignment and recency drive gains; imputing unknown impacts does not',
];
module.exports.HIGHLIGHTS = HIGHLIGHTS;

const page = { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } };
const numbering = { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] };

function highlights() {
  const children = [
    new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: 'Highlights', font: FONT, size: 28, bold: true })] }),
    ...HIGHLIGHTS.map((h) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { line: 360, after: 120 },
      children: [new TextRun({ text: h, font: FONT, size: SIZE })] })),
  ];
  return new Document({ creator: 'Rahul Chandra Nandagiri', title: 'Highlights', styles: styles(), numbering,
    sections: [{ properties: { page }, children }] });
}

function supplementary() {
  const S = T.sup; const c = [];
  const sp = (t) => c.push(para(t, { indent: false, line: 300, after: 120 }));
  c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Supplementary material', font: FONT, size: 28, bold: true })] }));
  c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120, line: 300 }, children: runs(M.TITLE, { italics: true }) }));
  c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: runs('Rahul Chandra Nandagiri') }));
  sp('All tables below are produced by run_experiment.py in the public repository (https://github.com/rahulchandranandagiri/cybersecurity-investment-business-performance) and are also provided there as CSV files in results/tables/. Unless stated otherwise, decision results use the reference budget (B = 9, α = β = 1) and the 18 sector–size profiles of the 2017–2026 evaluation period.');

  c.push(caption('Table S1.', 'Knowledge base: production rules mapping VERIS incident patterns to control families (R1–R22) and expert consequence rules (C1–C3). An incident’s family weights are the normalized counts of the rules it triggers.', { keepNext: true, line: 276 }));
  c.push(table(['Rule', 'Scope', 'Condition', 'Family / consequence'], S.S1, [700, 1300, 5660, 1700]));
  c.push(note('Source: decision_intelligence.py (RULES, family_weights, consequence_rules).'));
  c.push(caption('Table S1b.', 'Control families and their alignment with CIS Critical Security Controls v8 and NIST CSF 2.0 categories.', { keepNext: true, line: 276 }));
  c.push(table(['Family', 'Name', 'CIS v8 / NIST CSF 2.0'], S.S1b, [900, 4260, 4200]));
  c.push(note(''));
  c.push(caption('Table S2.', 'Business-impact risk reduction (BIRR) by profile at the reference budget.', { keepNext: true, line: 276 }));
  c.push(table(['Profile', 'Equal', 'Threat freq. (context)', 'Impact-aligned (pooled)', 'KB-CIDS w/o AI imputation', 'KB-CIDS', 'Oracle'], S.S2, [2560, 900, 1200, 1200, 1300, 1000, 1200]));
  c.push(note(''));
  c.push(caption('Table S3.', 'Weighting parameters selected on the inner validation split (training up to 2014, validation 2015–2016) and the corresponding validation BIRR.', { keepNext: true, line: 276 }));
  c.push(table(['Strategy', 'λ_{s}', 'λ_{g}', 'Half-life *h* (years)', 'Validation BIRR'], S.S3, [3660, 1100, 1300, 1700, 1600]));
  c.push(note('∞ denotes no weighting on that dimension (pooled context or no recency discount). The full grid is in S3_validation_tuning.csv.'));
  c.push(caption('Table S4.', 'Mean BIRR across profiles as a function of the budget relative to the reference budget.', { keepNext: true, line: 276 }));
  c.push(table(['*B* / *B*_{ref}', 'Equal', 'Threat freq. (context)', 'Impact-aligned (pooled)', 'KB-CIDS', 'Oracle'], S.S4, [1360, 1400, 1700, 1700, 1600, 1600]));
  c.push(note(''));
  c.push(caption('Table S5.', 'Sensitivity of mean BIRR to the Gordon–Loeb parameters α and β at the reference budget.', { keepNext: true, line: 276 }));
  c.push(table(['α', 'β', 'Equal', 'Threat freq. (context)', 'KB-CIDS', 'Oracle', 'KB-CIDS gap closed (%)'], S.S5, [800, 800, 1300, 1700, 1300, 1300, 2160]));
  c.push(note(''));
  c.push(caption('Table S6.', 'Robustness of the decision results to alternative specifications (each specification re-tunes on its own inner validation split).', { keepNext: true, line: 276 }));
  c.push(table(['Specification', 'Profiles', 'Equal', 'Threat freq.', 'Impact pooled', 'w/o AI imp.', 'KB-CIDS', 'Oracle', 'Gap closed (%)', 'p vs threat freq.'], S.S6, [1900, 750, 700, 850, 850, 850, 850, 800, 900, 910], { size: 16 }));
  c.push(note('p from two-sided Wilcoxon signed-rank tests of KB-CIDS against context-weighted threat-frequency allocation.'));
  c.push(caption('Table S7.', 'Permutation importance of the KB-CIDS materiality model on the evaluation period (mean drop in ROC-AUC over 10 repeats; top 15 features).', { keepNext: true, line: 276 }));
  c.push(table(['Feature', 'Mean ΔAUC', 'SD'], S.S7, [5360, 2000, 2000]));
  c.push(note('kb_F1–kb_F9 are knowledge-base family weights; kr_disrupt, kr_mass and kr_contained are expert consequence-rule flags.'));
  c.push(caption('Table S8.', 'Allocation rationale for small healthcare organizations: the threat patterns contributing most of each family’s business-impact risk (development-period evidence, KB-CIDS weights).', { keepNext: true, line: 276 }));
  c.push(table(['Family', 'Threat pattern', 'Share of family risk (%)'], S.S8, [1200, 5560, 2600]));
  c.push(note(''));
  c.push(caption('Table S9.', 'Mean budget shares (%) by control family across the 18 profiles, compared with the realized shares of material-impact risk in 2017–2026.', { keepNext: true, line: 276 }));
  c.push(table(['Allocation', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9'], S.S9, [2880, 720, 720, 720, 720, 720, 720, 720, 720, 720]));
  c.push(note(''));
  c.push(caption('Table S10.', 'Out-of-time predictive metrics with 95% bootstrap confidence intervals (2,000 resamples).', { keepNext: true, line: 276 }));
  c.push(table(['Model', 'PR-AUC [95% CI]', 'Brier [95% CI]', 'ECE [95% CI]'], S.S10, [3060, 2100, 2100, 2100]));
  c.push(note(''));
  return new Document({ creator: 'Rahul Chandra Nandagiri', title: 'Supplementary material', styles: styles(),
    sections: [{ properties: { page }, footers: { default: footer() }, children: c }] });
}

function coverLetter() {
  const c = [];
  const p = (t, o = {}) => c.push(para(t, { indent: false, line: 300, after: 160, align: AlignmentType.LEFT, ...o }));
  p('Rahul Chandra Nandagiri');
  p('Doctor of Business Administration Program, Midwest University, Wentzville, Missouri, United States');
  p('E-mail: chandrarahul416@gmail.com');
  p('The Editor-in-Chief, Knowledge-Based Systems');
  p('Dear Editor,');
  p(`Please consider the enclosed Short Communication, “${M.TITLE},” for publication in Knowledge-Based Systems.`);
  p('The paper presents KB-CIDS, a knowledge-based decision-support model that couples an explicit production-rule knowledge base (22 rules mapping incident patterns to nine control families aligned with CIS Controls v8 and NIST CSF 2.0), a calibrated machine-learning model of material business impact, and a Gordon–Loeb budget-allocation layer. Using 9,284 public incidents from the VERIS Community Database, all components were developed on incidents up to 2016 and evaluated out of time on 2017–2026. Business-impact-aligned allocation outperformed both undifferentiated and threat-frequency budgeting in all 18 sector–size profiles and closed 56% of the gap to an ex-post oracle, whereas threat-frequency allocation performed worse than an equal split. A component ablation is reported openly, including a negative result for imputing unknown impacts.');
  p('The work fits the journal’s aims of supporting human decision-making through knowledge-based and data-science techniques with applications in business, and its leading topics of intelligent decision support systems, knowledge representation and data-driven optimization.');
  p('The manuscript is original, has not been published previously and is not under consideration elsewhere. The data are public (CC BY-SA 4.0), and the complete code, derived data, figures and tables are openly available for reproduction. The use of generative AI tools in preparing the manuscript is declared in the dedicated section, and the author declares no competing interests.');
  p('Thank you for your consideration.');
  p('Sincerely,');
  p('Rahul Chandra Nandagiri');
  return new Document({ creator: 'Rahul Chandra Nandagiri', title: 'Cover letter', styles: styles(), sections: [{ properties: { page }, children: c }] });
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  for (const [name, doc] of [['Highlights.docx', highlights()], ['Supplementary_Material.docx', supplementary()], ['Cover_Letter.docx', coverLetter()]]) {
    fs.writeFileSync(OUT + name, await Packer.toBuffer(doc)); console.log('wrote', name);
  }
})();
