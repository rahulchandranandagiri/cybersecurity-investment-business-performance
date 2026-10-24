// Shared helpers for building the submission documents with docx-js.
const fs = require('fs');
const d = require('docx');
const {
  Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle,
  ImageRun, Footer, PageNumber, TabStopType, HeadingLevel,
  MathRun, MathSubScript, MathSuperScript, MathSubSuperScript, MathFraction, MathSum,
  MathRoundBrackets, MathSquareBrackets, MathCurlyBrackets,
} = d;

const FONT = 'Times New Roman';
const SIZE = 24;          // 12 pt
const TSIZE = 19;         // 9.5 pt for tables
const DOUBLE = 480;
const TEXT_WIDTH = 9360;  // 6.5 in at 1 in margins (US Letter)

// Inline markup: *italic*, **bold**, _{sub}, ^{sup}
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]*\}|\^\{[^}]*\})/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size: SIZE, ...base }));
    const t = m[0];
    if (t.startsWith('**')) out.push(new TextRun({ text: t.slice(2, -2), font: FONT, size: SIZE, ...base, bold: true }));
    else if (t.startsWith('*')) out.push(new TextRun({ text: t.slice(1, -1), font: FONT, size: SIZE, ...base, italics: true }));
    else if (t.startsWith('_{')) out.push(new TextRun({ text: t.slice(2, -1), font: FONT, size: SIZE, ...base, subScript: true }));
    else out.push(new TextRun({ text: t.slice(2, -1), font: FONT, size: SIZE, ...base, superScript: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: SIZE, ...base }));
  return out;
}

function para(text, opt = {}) {
  const { align = AlignmentType.JUSTIFIED, line = DOUBLE, indent = true, before = 0, after = 0, base = {}, keepNext = false } = opt;
  return new Paragraph({
    alignment: align, keepNext,
    spacing: { line, before, after },
    indent: indent ? { firstLine: 360 } : undefined,
    children: runs(text, base),
  });
}

function heading(text, level = 1) {
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    keepNext: true,
    spacing: { line: DOUBLE, before: level === 1 ? 240 : 120, after: 0 },
    children: [new TextRun({ text, font: FONT, size: SIZE, bold: level === 1, italics: level === 2 })],
  });
}

// ---- Office Math helpers
const arr = (x) => (Array.isArray(x) ? x : [x]).map((e) => (typeof e === 'string' ? new MathRun(e) : e));
const mr = (t) => new MathRun(t);
const up = (t) => new MathRun({ text: t, style: 'plain' });
const sb = (b, s) => new MathSubScript({ children: arr(b), subScript: arr(s) });
const sp = (b, s) => new MathSuperScript({ children: arr(b), superScript: arr(s) });
const sbsp = (b, s, u) => new MathSubSuperScript({ children: arr(b), subScript: arr(s), superScript: arr(u) });
const fr = (n, m) => new MathFraction({ numerator: arr(n), denominator: arr(m) });
const sum = (s, u, body) => new MathSum({ children: arr(body), subScript: s ? arr(s) : undefined, superScript: u ? arr(u) : undefined });
const rb = (c) => new MathRoundBrackets({ children: arr(c) });
const qb = (c) => new MathSquareBrackets({ children: arr(c) });
const cb = (c) => new MathCurlyBrackets({ children: arr(c) });

function mathParts(children) {
  const parts = []; let cur = [];
  for (const c of children) {
    if (c && typeof c === 'object' && c.plain !== undefined) {
      if (cur.length) { parts.push(new d.Math({ children: arr(cur) })); cur = []; }
      parts.push(new TextRun({ text: c.plain, font: FONT, size: SIZE }));
    } else cur.push(c);
  }
  if (cur.length) parts.push(new d.Math({ children: arr(cur) }));
  return parts;
}

function equation(children, number) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.CENTER, position: TEXT_WIDTH / 2 }, { type: TabStopType.RIGHT, position: TEXT_WIDTH }],
    spacing: { line: 240, lineRule: 'auto', before: 160, after: 160 },
    children: [new TextRun({ children: [new d.Tab()], font: FONT, size: SIZE }), ...mathParts(children),
      new TextRun({ children: [new d.Tab(), `(${number})`], font: FONT, size: SIZE })],
  });
}

// ---- booktabs-style table (no vertical rules, no shading)
const NONE = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const RULE = (sz) => ({ style: BorderStyle.SINGLE, size: sz, color: '000000' });
function table(header, rows, widths, opt = {}) {
  const { bold = [], firstColLeft = true, size = TSIZE } = opt;
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cells, isHeader, isLast, rowIdx) => new TableRow({
    tableHeader: isHeader, cantSplit: true,
    children: cells.map((c, j) => new TableCell({
      width: { size: widths[j], type: WidthType.DXA },
      margins: { top: 30, bottom: 30, left: 70, right: 70 },
      borders: {
        top: isHeader ? RULE(8) : NONE,
        bottom: isHeader ? RULE(4) : (isLast ? RULE(8) : NONE),
        left: NONE, right: NONE,
      },
      children: [new Paragraph({
        alignment: j === 0 && firstColLeft ? AlignmentType.LEFT : AlignmentType.CENTER,
        spacing: { line: 240 },
        children: runs(String(c), { size, bold: isHeader || bold.includes(rowIdx) }),
      })],
    })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: [mk(header, true, false, -1), ...rows.map((r, i) => mk(r, false, i === rows.length - 1, i))],
  });
}

function caption(label, text, opt = {}) {
  return new Paragraph({
    alignment: AlignmentType.LEFT, keepNext: !!opt.keepNext,
    spacing: { line: opt.line || 360, before: opt.before ?? 120, after: opt.after ?? 60 },
    children: [new TextRun({ text: label + ' ', font: FONT, size: opt.size || 22, bold: true }), ...runs(text, { size: opt.size || 22 })],
  });
}

function note(text) {
  return new Paragraph({ spacing: { line: 276, before: 40, after: 160 }, children: runs(text, { size: 18 }) });
}

function figure(file, widthPx = 624) {
  const buf = fs.readFileSync(file);
  // PNG header: width at byte 16, height at byte 20
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return new Paragraph({
    alignment: AlignmentType.CENTER, keepNext: true, spacing: { line: 240, lineRule: 'auto', before: 120, after: 0 },
    children: [new ImageRun({ type: 'png', data: buf, transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })],
  });
}

function footer() {
  return new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })] })] });
}

function styles() {
  return {
    default: { document: { run: { font: FONT, size: SIZE }, paragraph: { spacing: { line: DOUBLE } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: SIZE, bold: true }, paragraph: { spacing: { before: 240, after: 0, line: DOUBLE }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: SIZE, italics: true }, paragraph: { spacing: { before: 120, after: 0, line: DOUBLE }, outlineLevel: 1 } },
    ],
  };
}

module.exports = { d, FONT, SIZE, DOUBLE, TEXT_WIDTH, runs, para, heading, equation, table, caption, note, figure, footer, styles,
  mr, up, sb, sp, sbsp, fr, sum, rb, qb, cb };
