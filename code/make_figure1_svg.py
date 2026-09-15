# -*- coding: utf-8 -*-
"""Generate the IEEE-style concept schematic used as Figure 1.

The source is deliberately plain SVG: square modules, thin rules, serif type,
and a restrained blue/orange signal language.  This keeps the figure legible
at two-column width and makes every element editable.
"""
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "result" / "figs"


def make_svg(path: Path) -> None:
    # Fireworks Tech Graph list method: one SVG element per explicit line.
    lines = []
    add = lines.append
    add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 650" width="1200" height="650">')
    add('  <style>')
    add("    text { font-family:'Times New Roman',Times,'Liberation Serif',serif; fill:#111111; }")
    add('    .section { font-size:19px; font-weight:700; letter-spacing:.35px; }')
    add('    .head { font-size:17px; font-weight:700; }')
    add('    .label { font-size:15px; font-weight:700; }')
    add('    .body { font-size:14px; }')
    add('    .small { font-size:12.5px; }')
    add('    .math { font-size:18px; font-style:italic; }')
    add('  </style>')
    add('  <defs>')
    add('    <marker id="blue-arrow" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">')
    add('      <polygon points="0,0 9,3.5 0,7" fill="#2d63b8"/>')
    add('    </marker>')
    add('    <marker id="orange-arrow" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">')
    add('      <polygon points="0,0 9,3.5 0,7" fill="#e56b21"/>')
    add('    </marker>')
    add('  </defs>')
    add('  <rect data-graph-role="background" width="1200" height="650" fill="#ffffff"/>')

    # I. BLACK-BOX EXTRACTION
    add('  <text x="600" y="27" text-anchor="middle" class="section">BLACK-BOX EXTRACTION</text>')
    add('  <rect data-graph-role="container" x="18" y="38" width="1164" height="158" fill="#ffffff" stroke="#222222" stroke-width="1.5"/>')
    add('  <rect data-graph-role="node" x="38" y="60" width="190" height="112" fill="#ffffff" stroke="#222222" stroke-width="1.3"/>')
    add('  <rect x="38" y="60" width="190" height="27" fill="#edf3fb" stroke="#222222" stroke-width="1.1"/>')
    add('  <text x="133" y="79" text-anchor="middle" class="label">Input document</text>')
    add('  <path d="M68,101 H106 L118,113 V153 H68 Z" fill="#ffffff" stroke="#555555" stroke-width="1.1"/>')
    add('  <path d="M106,101 V113 H118" fill="none" stroke="#555555" stroke-width="1.1"/>')
    add('  <line x1="78" y1="121" x2="106" y2="121" stroke="#777777"/>')
    add('  <line x1="78" y1="131" x2="106" y2="131" stroke="#777777"/>')
    add('  <line x1="78" y1="141" x2="99" y2="141" stroke="#777777"/>')
    add('  <text x="136" y="120" class="body">unlabelled text</text>')
    add('  <text x="136" y="143" class="small" fill="#555555">no gold annotations</text>')

    add('  <line data-graph-role="edge" x1="228" y1="116" x2="307" y2="116" stroke="#2d63b8" stroke-width="2.2" marker-end="url(#blue-arrow)"/>')
    add('  <polygon points="307,116 297,111 297,121" fill="#2d63b8"/>')
    add('  <text x="267" y="105" text-anchor="middle" class="small" fill="#2d63b8">prompt</text>')

    add('  <rect data-graph-role="node" x="316" y="60" width="212" height="112" fill="#ffffff" stroke="#222222" stroke-width="1.3"/>')
    add('  <rect x="316" y="60" width="212" height="27" fill="#edf3fb" stroke="#222222" stroke-width="1.1"/>')
    add('  <text x="422" y="79" text-anchor="middle" class="label">Black-box LLM</text>')
    add('  <rect x="350" y="102" width="144" height="37" fill="#222222" stroke="#222222"/>')
    add('  <text x="422" y="126" text-anchor="middle" font-size="15" font-weight="700" style="fill:#ffffff">ONE DECODE</text>')
    add('  <text x="422" y="157" text-anchor="middle" class="small" fill="#555555">no logits or internals</text>')

    add('  <line data-graph-role="edge" x1="528" y1="116" x2="607" y2="116" stroke="#2d63b8" stroke-width="2.2" marker-end="url(#blue-arrow)"/>')
    add('  <polygon points="607,116 597,111 597,121" fill="#2d63b8"/>')
    add('  <text x="567" y="105" text-anchor="middle" class="small" fill="#2d63b8">extract</text>')

    add('  <rect data-graph-role="node" x="616" y="60" width="546" height="112" fill="#ffffff" stroke="#222222" stroke-width="1.3"/>')
    add('  <rect x="616" y="60" width="546" height="27" fill="#edf3fb" stroke="#222222" stroke-width="1.1"/>')
    add('  <text x="889" y="79" text-anchor="middle" class="label">Typed extraction</text>')
    add('  <text x="636" y="109" class="body"><tspan font-weight="700">Entities:</tspan> Olympics:MISC, Mediaș:LOC, medal:MISC, China:LOC,</text>')
    add('  <text x="700" y="130" class="body">IOC:ORG, 1894:TIME</text>')
    add('  <text x="636" y="155" class="body"><tspan font-weight="700">Relations:</tspan> located-in, capital-of, date-of-birth, …</text>')

    # Downstream direction from extraction into the certificate pipeline.
    add('  <path data-graph-role="edge" d="M889,172 V211 H276 V232" fill="none" stroke="#2d63b8" stroke-width="2.2" marker-end="url(#blue-arrow)"/>')
    add('  <polygon points="276,232 271,222 281,222" fill="#2d63b8"/>')

    # II-A. TYPE-SIGNATURE CHECK
    add('  <rect data-graph-role="container" x="18" y="232" width="516" height="398" fill="#ffffff" stroke="#222222" stroke-width="1.5"/>')
    add('  <rect x="18" y="232" width="516" height="34" fill="#edf3fb" stroke="#222222" stroke-width="1.1"/>')
    add('  <text x="276" y="255" text-anchor="middle" class="head">(a) TYPE-SIGNATURE CHECK</text>')
    add('  <text x="276" y="286" text-anchor="middle" class="small">Hard schema signatures are checked against the emitted types</text>')

    def entity_box(x, y, name, typ, bad=False):
        stroke = '#e56b21' if bad else '#333333'
        add(f'  <rect data-graph-role="node" x="{x}" y="{y}" width="132" height="54" fill="#ffffff" stroke="{stroke}" stroke-width="{2.0 if bad else 1.2}"/>')
        add(f'  <text x="{x + 66}" y="{y + 22}" text-anchor="middle" class="label">{name}</text>')
        add(f'  <text x="{x + 66}" y="{y + 42}" text-anchor="middle" class="small" fill="{stroke}">[{typ}]</text>')

    rows = [
        (310, 'Olympics', 'MISC', 'located-in', 'Mediaș', 'LOC'),
        (405, 'medal', 'MISC', 'capital-of', 'China', 'LOC'),
        (500, 'IOC', 'ORG', 'date-of-birth', '1894', 'TIME'),
    ]
    for y, left, ltyp, rel, right, rtyp in rows:
        entity_box(42, y, left, ltyp, True)
        entity_box(378, y, right, rtyp, False)
        add(f'  <line data-graph-role="edge" x1="174" y1="{y + 27}" x2="369" y2="{y + 27}" stroke="#e56b21" stroke-width="2.1" marker-end="url(#orange-arrow)"/>')
        add(f'  <polygon points="369,{y + 27} 359,{y + 22} 359,{y + 32}" fill="#e56b21"/>')
        add(f'  <rect x="205" y="{y + 10}" width="132" height="23" fill="#ffffff"/>')
        add(f'  <text x="271" y="{y + 27}" text-anchor="middle" font-size="13.5" font-weight="700" fill="#b74c13">×  {rel}</text>')
    add('  <line x1="42" y1="584" x2="73" y2="584" stroke="#e56b21" stroke-width="2.1"/>')
    add('  <text x="82" y="589" class="small" fill="#b74c13">schema violation</text>')
    add('  <text x="509" y="611" text-anchor="end" class="small" font-style="italic">3 violated constraints</text>')

    # A -> B
    add('  <line data-graph-role="edge" x1="534" y1="431" x2="558" y2="431" stroke="#2d63b8" stroke-width="2.2" marker-end="url(#blue-arrow)"/>')
    add('  <polygon points="558,431 548,426 548,436" fill="#2d63b8"/>')

    # II-B. CONFLICT HYPERGRAPH AND DISJOINT PACKING
    add('  <rect data-graph-role="container" x="562" y="232" width="336" height="398" fill="#ffffff" stroke="#222222" stroke-width="1.5"/>')
    add('  <rect x="562" y="232" width="336" height="34" fill="#edf3fb" stroke="#222222" stroke-width="1.1"/>')
    add('  <text x="730" y="255" text-anchor="middle" class="head">(b) HYPEREDGE PACKING</text>')
    add('  <text x="730" y="283" text-anchor="middle" class="small">Each enclosure is a conflict hyperedge;</text>')
    add('  <text x="730" y="299" text-anchor="middle" class="small">at least one enclosed item must be wrong</text>')

    for cx, eid, top, bottom in [
        (620, '1', 'Olympics', 'located-in'),
        (730, '2', 'medal', 'capital-of'),
        (840, '3', 'IOC', 'date-of-birth'),
    ]:
        add(f'  <rect data-graph-role="container" x="{cx - 43}" y="307" width="86" height="212" fill="#f7faff" stroke="#7fa3d8" stroke-width="1.1"/>')
        add(f'  <line data-graph-role="edge" x1="{cx}" y1="370" x2="{cx}" y2="392" stroke="#e56b21" stroke-width="2.5"/>')
        add(f'  <line data-graph-role="edge" x1="{cx}" y1="428" x2="{cx}" y2="450" stroke="#e56b21" stroke-width="2.5"/>')
        add(f'  <circle data-graph-role="node" cx="{cx}" cy="352" r="16" fill="#ffffff" stroke="#333333" stroke-width="1.4"/>')
        add(f'  <circle data-graph-role="node" cx="{cx}" cy="410" r="16" fill="#ffffff" stroke="#333333" stroke-width="1.4"/>')
        add(f'  <circle data-graph-role="node" cx="{cx}" cy="468" r="16" fill="#ffffff" stroke="#333333" stroke-width="1.4"/>')
        add(f'  <text x="{cx}" y="357" text-anchor="middle" class="label">H<tspan baseline-shift="sub" font-size="10">{eid}</tspan></text>')
        add(f'  <text x="{cx}" y="415" text-anchor="middle" class="label">T<tspan baseline-shift="sub" font-size="10">{eid}</tspan></text>')
        add(f'  <text x="{cx}" y="473" text-anchor="middle" class="label">R<tspan baseline-shift="sub" font-size="10">{eid}</tspan></text>')
        add(f'  <text x="{cx}" y="323" text-anchor="middle" class="small">{top}</text>')
        add(f'  <text x="{cx}" y="506" text-anchor="middle" class="small">{bottom}</text>')
    add('  <path d="M588,540 V552 H872 V540" fill="none" stroke="#2d63b8" stroke-width="1.6"/>')
    add('  <text x="730" y="577" text-anchor="middle" class="math">maximum disjoint packing  |M| = 3</text>')
    add('  <text x="730" y="605" text-anchor="middle" class="small" fill="#2d63b8">three vertex-disjoint conflict hyperedges</text>')

    # B -> C
    add('  <line data-graph-role="edge" x1="898" y1="431" x2="922" y2="431" stroke="#2d63b8" stroke-width="2.2" marker-end="url(#blue-arrow)"/>')
    add('  <polygon points="922,431 912,426 912,436" fill="#2d63b8"/>')

    # II-C. CERTIFICATE
    add('  <rect data-graph-role="container" x="926" y="232" width="256" height="398" fill="#ffffff" stroke="#222222" stroke-width="1.5"/>')
    add('  <rect x="926" y="232" width="256" height="34" fill="#edf3fb" stroke="#222222" stroke-width="1.1"/>')
    add('  <text x="1054" y="255" text-anchor="middle" class="head">(c) CERTIFICATE</text>')
    add('  <text x="1054" y="291" text-anchor="middle" class="math">|M| ≤ #errors</text>')
    add('  <line x1="950" y1="306" x2="1158" y2="306" stroke="#777777" stroke-width="1"/>')
    add('  <rect data-graph-role="node" x="949" y="325" width="210" height="76" fill="#fff4ed" stroke="#e56b21" stroke-width="2"/>')
    add('  <text x="1054" y="350" text-anchor="middle" class="small" fill="#b74c13">CONDITIONAL LOWER BOUND</text>')
    add('  <text x="1054" y="383" text-anchor="middle" font-size="25" font-weight="700" fill="#b74c13">#errors ≥ 3</text>')

    def guarantee(y, title, detail):
        add(f'  <rect x="949" y="{y}" width="210" height="52" fill="#f7faff" stroke="#7fa3d8" stroke-width="1.1"/>')
        add(f'  <rect x="949" y="{y}" width="28" height="52" fill="#2d63b8"/>')
        add(f'  <path d="M956,{y + 27} l5,5 l9,-12" fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
        add(f'  <text x="988" y="{y + 21}" class="label">{title}</text>')
        add(f'  <text x="988" y="{y + 41}" class="small" fill="#555555">{detail}</text>')

    guarantee(424, 'Sound', 'every flagged set has an error')
    guarantee(487, 'Gold-free', 'no labels or reference output')
    guarantee(550, 'Single pass', 'one deterministic decode')
    add('</svg>')
    path.write_text('\n'.join(lines), encoding='utf-8')


def write_assets(out_dir: Path = OUT) -> None:
    """Write the editable SVG plus print and preview exports."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / 'F1_concept.svg'
    make_svg(svg_path)
    try:
        import cairosvg
    except (ImportError, OSError):
        cairosvg = None

    if cairosvg is not None:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(out_dir / 'F1_concept.pdf'))
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(out_dir / 'F1_concept.png'),
            output_width=2400,
            output_height=1300,
        )
        return

    # CairoSVG needs a system Cairo library on macOS. svglib/reportlab keeps
    # the publication PDF vector instead of silently degrading it to a bitmap.
    try:
        from reportlab.graphics import renderPDF
        from svglib.svglib import svg2rlg
    except ImportError:
        renderPDF = None

    if renderPDF is not None:
        drawing = svg2rlg(str(svg_path))
        if drawing is None:
            raise RuntimeError(f"Could not parse {svg_path} for vector export.")
        renderPDF.drawToFile(drawing, str(out_dir / 'F1_concept.pdf'))

        sips = shutil.which('sips')
        if not sips:
            raise RuntimeError("The PNG preview export needs the macOS sips utility.")
        subprocess.run(
            [sips, '-s', 'format', 'png', str(out_dir / 'F1_concept.pdf'),
             '--out', str(out_dir / 'F1_concept.png')],
            check=True,
            capture_output=True,
        )
        return

    raise RuntimeError(
        "Figure 1 vector export needs CairoSVG with Cairo, or svglib/reportlab."
    )


if __name__ == '__main__':
    write_assets()
    print(OUT / 'F1_concept.svg')
