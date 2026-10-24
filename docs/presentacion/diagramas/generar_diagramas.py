"""Genera D1 y D2: archivo .drawio (editable en draw.io) y SVG/PNG con la misma geometria.
Uso: python3 gen_diagrams.py <dir_salida>
"""
import sys, html
from xml.sax.saxutils import escape
import cairosvg

OUT = sys.argv[1]
W, H = 1776, 684  # area de contenido del layout CONTENIDO a 144 px/pulgada

TEAL, SOFT, TXT, MUTED, BORDER = "#0F766E", "#E6F4F1", "#0F1B2A", "#5B6B7D", "#E2E8F0"
FONT = "Calibri"
FS, FS_T = 36, 40  # 18 pt y 20 pt a 2 px por punto

AGENT = dict(fill=SOFT, stroke=TEAL, text=TXT, shape="rounded", sw=3)
DATA = dict(fill="#FFFFFF", stroke=BORDER, text=MUTED, shape="rounded", sw=3)
ACTOR = dict(fill="#FFFFFF", stroke=MUTED, text=TXT, shape="rounded", sw=2)
BAND = dict(fill=BORDER, stroke=BORDER, text=TXT, shape="rect", sw=1)
PROC = dict(fill="#FFFFFF", stroke=MUTED, text=TXT, shape="rounded", sw=3)
DEC = dict(fill="#FFFFFF", stroke=TEAL, text=TXT, shape="rhombus", sw=3)
TERM = dict(fill="#FFFFFF", stroke=MUTED, text=TXT, shape="stadium", sw=3)


def node(id, x, y, w, h, lines, kind, bold_first=True):
    return dict(id=id, x=x, y=y, w=w, h=h, lines=lines, kind=kind, bold_first=bold_first)


def edge(id, pts, src, tgt, color=MUTED, dashed=False, label=None, lpos=None, lanchor="middle"):
    return dict(id=id, pts=pts, src=src, tgt=tgt, color=color, dashed=dashed, label=label,
                lpos=lpos, lanchor=lanchor)


# ---------------- D1 arquitectura ----------------
AY, AH = 110, 160
d1_nodes = [
    node("n1", 0, 150, 170, 80, [("Médico", FS_T, False)], ACTOR),
    node("n2", 240, AY, 400, AH, [("Orquestador", FS_T, True), ("enruta cada mensaje", FS, False)], AGENT),
    node("n3", 720, AY, 340, AH, [("Monitor", FS_T, True), ("calcula", FS, False)], AGENT),
    node("n4", 1240, AY, 340, AH, [("Clínico", FS_T, True), ("interpreta", FS, False)], AGENT),
    node("n8", 240, 340, 1340, 60, [("Estado compartido de la sesión", FS, False)], BAND),
    node("n5", 740, 500, 300, 130, [("EHR y medicación", FS, False)], DATA),
    node("n6", 1080, 500, 400, 130, [("Historial de sesiones", FS, False), ("(SQLite)", FS, False)], DATA),
    node("n7", 1510, 500, 266, 130, [("Guías clínicas", FS, False), ("(ChromaDB)", FS, False)], DATA),
]
d1_edges = [
    edge("e1", [(170, 190), (240, 190)], "n1", "n2"),
    edge("e2", [(640, 190), (720, 190)], "n2", "n3"),
    edge("e3", [(1060, 190), (1240, 190)], "n3", "n4"),
    edge("e4", [(560, AY), (560, 40), (1410, 40), (1410, AY)], "n2", "n4"),
    edge("e5", [(890, 270), (890, 500)], "n3", "n5", dashed=True),
    edge("e6", [(1340, 270), (1340, 500)], "n4", "n6", dashed=True),
    edge("e7", [(1550, 270), (1550, 500)], "n4", "n7", dashed=True),
    # conectores cortos al estado compartido (sin flecha)
    edge("s2", [(300, 270), (300, 340)], "n2", "n8"),
    edge("s3", [(780, 270), (780, 340)], "n3", "n8"),
    edge("s4", [(1280, 270), (1280, 340)], "n4", "n8"),
]
NOARROW = {"s2", "s3", "s4"}

# ---------------- D2 flujo ----------------
RY, RH = 250, 120  # fila principal
CY = RY + RH // 2
d2_nodes = [
    node("f1", 0, 260, 190, 100, [("Mensaje", FS, False), ("del médico", FS, False)], ACTOR, False),
    node("f2", 240, RY, 260, RH, [("Orquestador", FS_T, True)], AGENT),
    node("f3", 640, RY, 220, RH, [("Monitor", FS_T, True)], AGENT),
    node("f4", 960, RY, 220, RH, [("Clínico", FS_T, True)], AGENT),
    node("f5", 1230, 190, 400, 240, [("¿Información", FS, False), ("suficiente?", FS, False)], DEC, False),
    node("f6", 250, 520, 220, 90, [("Guardado", FS, False)], PROC, False),
    node("f7", 1600, 470, 176, 140, [("Fin", FS_T, True)], TERM),
]
d2_edges = [
    edge("g1", [(190, CY), (240, CY)], "f1", "f2"),
    edge("g2", [(500, CY), (640, CY)], "f2", "f3", label=["nuevo", "análisis"], lpos=(570, 185)),
    edge("g3", [(500, 350), (520, 350), (520, 450), (1070, 450), (1070, 370)], "f2", "f4",
         label=["seguimiento"], lpos=(795, 500)),
    edge("g4", [(320, 370), (320, 520)], "f2", "f6", label=["confirmar", "guardado"], lpos=(338, 420), lanchor="start"),
    edge("g5", [(240, 350), (215, 350), (215, 664), (1690, 664), (1690, 610)], "f2", "f7",
         label=["cancelar"], lpos=(1000, 642)),
    edge("g6", [(860, CY), (960, CY)], "f3", "f4"),
    edge("g7", [(680, RY), (680, 40), (1720, 40), (1720, 470)], "f3", "f7",
         label=["sin datos del paciente"], lpos=(700, 26), lanchor="start"),
    edge("g8", [(1180, CY), (1230, CY)], "f4", "f5"),
    edge("g9", [(1430, 190), (1430, 140), (820, 140), (820, RY)], "f5", "f3", color=TEAL,
         label=["no: vuelve al Monitor (máximo 3 ciclos)"], lpos=(1125, 124)),
    edge("g10", [(1430, 430), (1430, 520), (1600, 520)], "f5", "f7",
         label=["sí: reporte"], lpos=(1410, 490), lanchor="end"),
    edge("g11", [(470, 575), (1600, 575)], "f6", "f7"),
]


# ---------------- salida SVG ----------------
def svg_shape(n):
    k = n["kind"]; x, y, w, h = n["x"], n["y"], n["w"], n["h"]
    a = f'fill="{k["fill"]}" stroke="{k["stroke"]}" stroke-width="{k["sw"]}"'
    if k["shape"] == "rhombus":
        pts = f'{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}'
        s = f'<polygon points="{pts}" {a}/>'
    else:
        r = {"rounded": 16, "rect": 0, "stadium": h / 2}[k["shape"]]
        s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" {a}/>'
    lines = n["lines"]
    total = sum(l[1] * 1.15 for l in lines)
    cy = y + h / 2 - total / 2
    for i, (t, size, bold) in enumerate(lines):
        cy += size * 1.15
        wt = "700" if bold else "400"
        col = k["text"]
        s += (f'<text x="{x+w/2}" y="{cy - size*0.28:.1f}" font-family="Carlito, Calibri, sans-serif" '
              f'font-size="{size}" font-weight="{wt}" fill="{col}" text-anchor="middle">{escape(t)}</text>')
    return s


def svg_edge(e):
    p = " ".join(f"{a},{b}" for a, b in e["pts"])
    dash = ' stroke-dasharray="10 8"' if e["dashed"] else ""
    marker = "" if e["id"] in NOARROW else f' marker-end="url(#a{e["color"][1:]})"'
    s = f'<polyline points="{p}" fill="none" stroke="{e["color"]}" stroke-width="3"{dash}{marker}/>'
    if e["label"]:
        lx, ly = e["lpos"]
        col = e["color"] if e["color"] == TEAL else MUTED
        for i, t in enumerate(e["label"]):
            s += (f'<text x="{lx}" y="{ly + i*FS*1.1:.1f}" font-family="Carlito, Calibri, sans-serif" font-size="{FS}" '
                  f'fill="{col}" text-anchor="{e["lanchor"]}">{escape(t)}</text>')
    return s


def to_svg(nodes, edges, label):
    defs = "".join(
        f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in (MUTED, TEAL))
    band = [n for n in nodes if n["kind"] is BAND]
    rest = [n for n in nodes if n["kind"] is not BAND]
    body = "".join(svg_edge(e) for e in edges) + "".join(svg_shape(n) for n in band) + "".join(svg_shape(n) for n in rest)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" aria-label="{label}">'
            f'<defs>{defs}</defs><rect width="{W}" height="{H}" fill="#FFFFFF"/>{body}</svg>')


# ---------------- salida draw.io ----------------
def drawio(nodes, edges, name):
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    late = []
    for n in nodes:
        k = n["kind"]
        shape = {"rounded": "rounded=1;arcSize=10;", "rect": "rounded=0;", "rhombus": "rhombus;",
                 "stadium": "rounded=1;arcSize=50;"}[k["shape"]]
        parts = []
        for i, (t, size, bold) in enumerate(n["lines"]):
            t = html.escape(t)
            st = f'font-size:{size}px;' + ('font-weight:bold;' if bold else '')
            parts.append(f'<span style="{st}">{t}</span>')
        val = html.escape("<br>".join(parts), quote=True)
        style = (f"{shape}whiteSpace=wrap;html=1;fillColor={k['fill']};strokeColor={k['stroke']};"
                 f"strokeWidth={k['sw']};fontColor={k['text']};fontFamily={FONT};fontSize={FS};shadow=0;")
        (late if k is BAND else cells).append(f'<mxCell id="{n["id"]}" value="{val}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry"/></mxCell>')
    for e in edges:
        arrow = "endArrow=none;" if e["id"] in NOARROW else "endArrow=block;endFill=1;"
        dash = "dashed=1;dashPattern=10 8;" if e["dashed"] else ""
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={e['color']};strokeWidth=3;"
                 f"{arrow}{dash}fontFamily={FONT};fontSize={FS};fontColor={e['color'] if e['color']==TEAL else MUTED};")
        (sx, sy), (tx, ty) = e["pts"][0], e["pts"][-1]
        pts = "".join(f'<mxPoint x="{a}" y="{b}"/>' for a, b in e["pts"][1:-1])
        arr = f'<Array as="points">{pts}</Array>' if pts else ""
        cells.append(f'<mxCell id="{e["id"]}" style="{style}" edge="1" parent="1" source="{e["src"]}" target="{e["tgt"]}">'
                     f'<mxGeometry relative="1" as="geometry"><mxPoint x="{sx}" y="{sy}" as="sourcePoint"/>'
                     f'<mxPoint x="{tx}" y="{ty}" as="targetPoint"/>{arr}</mxGeometry></mxCell>')
        if e["label"]:
            lx, ly = e["lpos"]
            text = html.escape("<br>".join(e["label"]), quote=True)
            align = {"middle": "center", "start": "left", "end": "right"}[e["lanchor"]]
            wlab = max(len(t) for t in e["label"]) * 19 + 20
            hlab = len(e["label"]) * 42
            x0 = lx - wlab / 2 if align == "center" else (lx if align == "left" else lx - wlab)
            cells.append(f'<mxCell id="{e["id"]}l" value="{text}" style="text;html=1;align={align};verticalAlign=top;'
                         f'fontFamily={FONT};fontSize={FS};fontColor={e["color"] if e["color"]==TEAL else MUTED};'
                         f'strokeColor=none;fillColor=none;" vertex="1" parent="1">'
                         f'<mxGeometry x="{x0:.0f}" y="{ly-34}" width="{wlab}" height="{hlab}" as="geometry"/></mxCell>')
    cells += late
    model = (f'<mxGraphModel dx="{W}" dy="{H}" grid="0" page="1" pageWidth="{W}" pageHeight="{H}" background="#FFFFFF">'
             f'<root>{"".join(cells)}</root></mxGraphModel>')
    return (f'<mxfile host="Claude" type="device"><diagram id="{name}" name="{name}">{model}</diagram></mxfile>', model)


for name, nodes, edges, label in [
    ("d1-arquitectura", d1_nodes, d1_edges, "Arquitectura: Orquestador, Monitor y Clínico con sus fuentes de datos"),
    ("d2-flujo", d2_nodes, d2_edges, "Flujo de una consulta: enrutamiento y ciclo de refinamiento"),
]:
    svg = to_svg(nodes, edges, label)
    open(f"{OUT}/{name}.svg", "w").write(svg)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=f"{OUT}/{name}.png", scale=2)
    f, model = drawio(nodes, edges, name)
    open(f"{OUT}/{name}.drawio", "w").write(f)
    open(f"{OUT}/{name}.model.xml", "w").write(model)
print("ok")
