# interface/theme.py
#
# Sistema visual de la interfaz (ADR-0021): tema de Gradio, tokens de color para modo claro y
# oscuro, tipografía embebida y el JS del selector de tema. Vive separado de app.py para que el
# layout y el wiring no se mezclen con ~400 líneas de estilos.
#
# - Tipografía: Plus Jakarta Sans (texto) y JetBrains Mono (código/logs), embebidas en base64 en
#   el CSS → la UI se ve igual sin internet. Cifras tabulares en tablas e indicadores.
# - Color: tokens --tp-* en :root (claro) y en .dark (oscuro). Gradio pone la clase `dark` en
#   <body>, así que los mismos tokens sirven para el tema de Gradio y para nuestros componentes.
# - Severidad: nunca solo por color; cada pill lleva su texto (accesibilidad y proyector).

from __future__ import annotations

import base64
import html
from pathlib import Path

import gradio as gr

_FONTS_DIR = Path(__file__).parent / "assets" / "fonts"

FONT_SANS = "Plus Jakarta Sans"
FONT_MONO = "JetBrains Mono"


def _font_face(family: str, filename: str, style: str = "normal", weights: str = "200 800") -> str:
    """@font-face con la fuente embebida en base64. Si falta el archivo, se usa la del sistema."""
    path = _FONTS_DIR / filename
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f"@font-face {{ font-family: '{family}'; font-style: {style}; font-display: swap; "
        f"font-weight: {weights}; src: url(data:font/woff2;base64,{data}) format('woff2'); }}\n"
    )


# -------------------------------------------------------------------
# Tema de Gradio (componentes nativos: inputs, botones, chat, tabs)
# -------------------------------------------------------------------
# Los colores replican los tokens --tp-* de abajo; la variante _dark es la del modo oscuro.
THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.teal,
    secondary_hue=gr.themes.colors.teal,
    neutral_hue=gr.themes.colors.slate,
    text_size=gr.themes.sizes.text_md,
    spacing_size=gr.themes.sizes.spacing_md,
    radius_size=gr.themes.sizes.radius_md,
    font=[gr.themes.Font(FONT_SANS), gr.themes.Font("ui-sans-serif"),
          gr.themes.Font("system-ui"), gr.themes.Font("sans-serif")],
    font_mono=[gr.themes.Font(FONT_MONO), gr.themes.Font("ui-monospace"),
               gr.themes.Font("Consolas"), gr.themes.Font("monospace")],
).set(
    body_background_fill="#F5F7FA",
    body_background_fill_dark="#0B1118",
    body_text_color="#0F1B2A",
    body_text_color_dark="#E6EDF3",
    body_text_color_subdued="#5B6B7D",
    body_text_color_subdued_dark="#93A4B5",
    background_fill_primary="#FFFFFF",
    background_fill_primary_dark="#111A24",
    background_fill_secondary="#F1F4F8",
    background_fill_secondary_dark="#172230",
    border_color_primary="#E2E8F0",
    border_color_primary_dark="#243243",
    block_background_fill="#FFFFFF",
    block_background_fill_dark="#111A24",
    block_border_color="#E2E8F0",
    block_border_color_dark="#243243",
    block_label_text_weight="600",
    block_title_text_weight="600",
    block_shadow="none",
    block_shadow_dark="none",
    input_background_fill="#FFFFFF",
    input_background_fill_dark="#0E1620",
    input_border_color="#D5DDE7",
    input_border_color_dark="#2A3A4D",
    input_border_color_focus="#0F766E",
    input_border_color_focus_dark="#2DD4BF",
    button_primary_background_fill="#0F766E",
    button_primary_background_fill_hover="#115E59",
    button_primary_background_fill_dark="#2DD4BF",
    button_primary_background_fill_hover_dark="#5EEAD4",
    button_primary_text_color="#FFFFFF",
    button_primary_text_color_dark="#042F2E",
    button_secondary_background_fill="#FFFFFF",
    button_secondary_background_fill_hover="#F1F4F8",
    button_secondary_background_fill_dark="#172230",
    button_secondary_background_fill_hover_dark="#1E2B3B",
    button_secondary_text_color="#0F1B2A",
    button_secondary_text_color_dark="#E6EDF3",
    button_secondary_border_color="#D5DDE7",
    button_secondary_border_color_dark="#2A3A4D",
    color_accent="#0F766E",
    color_accent_soft="#E6F4F1",
    color_accent_soft_dark="#123A38",
    table_border_color="#E2E8F0",
    table_border_color_dark="#243243",
    table_even_background_fill="#FFFFFF",
    table_even_background_fill_dark="#111A24",
    table_odd_background_fill="#FFFFFF",
    table_odd_background_fill_dark="#111A24",
    link_text_color="#0F766E",
    link_text_color_dark="#5EEAD4",
)


# -------------------------------------------------------------------
# CSS: tokens + layout + componentes propios
# -------------------------------------------------------------------
_TOKENS_CSS = """
:root {
  --tp-bg: #F5F7FA; --tp-surface: #FFFFFF; --tp-surface-2: #F1F4F8; --tp-border: #E2E8F0;
  --tp-border-strong: #CBD5E1; --tp-text: #0F1B2A; --tp-text-muted: #5B6B7D;
  --tp-accent: #0F766E; --tp-accent-strong: #115E59; --tp-accent-soft: #E6F4F1;
  --tp-on-accent: #FFFFFF;
  --tp-sev-high-fg: #B42318; --tp-sev-high-bg: #FEF3F2; --tp-sev-high-bd: #FECDCA;
  --tp-sev-mid-fg: #B54708;  --tp-sev-mid-bg: #FFF6E5;  --tp-sev-mid-bd: #FEDF89;
  --tp-sev-low-fg: #854D0E;  --tp-sev-low-bg: #FEFBE8;  --tp-sev-low-bd: #FDE68A;
  --tp-ok-fg: #067647; --tp-ok-bg: #ECFDF3; --tp-ok-bd: #ABEFC6;
  --tp-info-fg: #175CD3; --tp-info-bg: #EFF8FF; --tp-info-bd: #B2DDFF;
  --tp-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
  --tp-radius: 12px; --tp-radius-sm: 8px;
}
.dark {
  --tp-bg: #0B1118; --tp-surface: #111A24; --tp-surface-2: #172230; --tp-border: #243243;
  --tp-border-strong: #31445A; --tp-text: #E6EDF3; --tp-text-muted: #93A4B5;
  --tp-accent: #2DD4BF; --tp-accent-strong: #5EEAD4; --tp-accent-soft: #123A38;
  --tp-on-accent: #042F2E;
  --tp-sev-high-fg: #FDA29B; --tp-sev-high-bg: rgba(240, 68, 56, 0.14); --tp-sev-high-bd: rgba(240, 68, 56, 0.35);
  --tp-sev-mid-fg: #FEC84B;  --tp-sev-mid-bg: rgba(247, 144, 9, 0.14);  --tp-sev-mid-bd: rgba(247, 144, 9, 0.35);
  --tp-sev-low-fg: #FDE272;  --tp-sev-low-bg: rgba(234, 179, 8, 0.12);  --tp-sev-low-bd: rgba(234, 179, 8, 0.3);
  --tp-ok-fg: #75E0A7; --tp-ok-bg: rgba(23, 178, 106, 0.14); --tp-ok-bd: rgba(23, 178, 106, 0.35);
  --tp-info-fg: #84CAFF; --tp-info-bg: rgba(46, 144, 250, 0.14); --tp-info-bd: rgba(46, 144, 250, 0.35);
  --tp-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
"""

_LAYOUT_CSS = """
/* ===== Barra superior ===== */
.tp2-appbar-wrap { padding: 0 !important; border: none !important; background: transparent !important; }
/* 2px a los lados: el contenedor del gr.HTML recorta, y el borde del botón de tema quedaba cortado. */
.tp2-appbar { display: flex; align-items: center; gap: 16px; padding: 18px 2px 14px;
  border-bottom: 1px solid var(--tp-border); }
.tp2-brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
/* Proporciones del logo: radio 26% del lado y el glifo ocupando todo el cuadro (su escala viene en el SVG). */
.tp2-logo { width: 38px; height: 38px; border-radius: 26%; flex: none; display: grid;
  place-items: center; background: var(--tp-accent); color: var(--tp-on-accent); }
.tp2-logo svg { width: 38px; height: 38px; display: block; }
/* Gradio le fuerza `color` a los SVG: sin esto el glifo salía del color del texto y no contrastaba con el cuadro. */
.tp2-logo svg, .tp2-logo svg * { color: var(--tp-on-accent) !important; }
.tp2-brand-text { min-width: 0; }
.tp2-brand-name { margin: 0; font-size: 1.15rem; font-weight: 700; letter-spacing: -0.01em;
  color: var(--tp-text); line-height: 1.2; }
.tp2-brand-sub { margin: 2px 0 0; font-size: 0.85rem; color: var(--tp-text-muted); }
.tp2-appbar-actions { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.tp2-status { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px;
  font-size: 0.8rem; font-weight: 600; border-radius: 999px; border: 1px solid var(--tp-border);
  background: var(--tp-surface); color: var(--tp-text); white-space: nowrap; max-width: 420px;
  overflow: hidden; text-overflow: ellipsis; }
.tp2-status-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.tp2-status.is-ok .tp2-status-dot { background: #12B76A; box-shadow: 0 0 0 3px rgba(18, 183, 106, 0.18); }
.tp2-status.is-warn .tp2-status-dot { background: #F79009; box-shadow: 0 0 0 3px rgba(247, 144, 9, 0.2); }
/* padding/min-width en 0: Gradio le pone 8px 16px a todo <button> y descentraba el icono. */
.tp2-icon-btn { width: 36px; height: 36px; flex: none; padding: 0 !important; min-width: 0 !important;
  display: grid; place-items: center; cursor: pointer; line-height: 0;
  border-radius: 10px; border: 1px solid var(--tp-border); background: var(--tp-surface);
  color: var(--tp-text); transition: background 0.15s ease, border-color 0.15s ease; }
.tp2-icon-btn:hover { background: var(--tp-surface-2); border-color: var(--tp-border-strong); }
.tp2-icon-btn:focus-visible { outline: 2px solid var(--tp-accent); outline-offset: 2px; }
.tp2-icon-btn svg { width: 18px; height: 18px; }
.tp2-icon-btn .tp2-ic-sun { display: none; }
.dark .tp2-icon-btn .tp2-ic-sun { display: block; }
.dark .tp2-icon-btn .tp2-ic-moon { display: none; }
.tp2-notice { display: flex; align-items: center; gap: 8px; margin: 12px 0 4px;
  font-size: 0.82rem; color: var(--tp-text-muted); }
.tp2-notice svg { width: 15px; height: 15px; flex: none; color: var(--tp-text-muted); }

/* ===== Pestañas ===== */
.tp2-tabs { margin-top: 4px; }
.tp2-tabs > .tab-wrapper, .tp2-tabs [role="tablist"] { border-bottom: 1px solid var(--tp-border); }
.tp2-tabs button[role="tab"] { font-size: 0.92rem; font-weight: 600; color: var(--tp-text-muted);
  padding: 10px 14px; }
.tp2-tabs button[role="tab"][aria-selected="true"] { color: var(--tp-text); }

/* ===== Tarjetas ===== */
.tp2-card { background: var(--tp-surface) !important; border: 1px solid var(--tp-border) !important;
  border-radius: var(--tp-radius) !important; padding: 18px 20px !important;
  box-shadow: var(--tp-shadow); gap: 12px !important; }
.tp2-card > .form, .tp2-card .block { border: none !important; box-shadow: none !important; }
.tp2-card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.tp2-card-title { margin: 0; font-size: 0.98rem; font-weight: 700; color: var(--tp-text);
  letter-spacing: -0.005em; }
.tp2-card-meta { font-size: 0.8rem; color: var(--tp-text-muted); }
.tp2-eyebrow { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--tp-text-muted); margin: 0; }
.tp2-sidebar, .tp2-chat-col { gap: 16px !important; }
.tp2-chat-col { position: sticky; top: 12px; align-self: flex-start; }
.tp2-primary-btn { font-weight: 700 !important; letter-spacing: 0.005em; min-height: 44px; }

/* ===== Tipografía del contenido (reporte, chat) ===== */
.gradio-container .prose { font-size: 0.95rem; line-height: 1.65; color: var(--tp-text); }
.gradio-container .prose h1 { font-size: 1.3rem; font-weight: 700; letter-spacing: -0.01em; margin: 0.1em 0 0.5em; }
.gradio-container .prose h2 { font-size: 1.08rem; font-weight: 700; margin: 1.3em 0 0.5em;
  padding-bottom: 6px; border-bottom: 1px solid var(--tp-border); }
.gradio-container .prose h3 { font-size: 0.98rem; font-weight: 700; margin: 1.1em 0 0.4em; }
.gradio-container .prose p { margin: 0.5em 0; }
.gradio-container .prose ul, .gradio-container .prose ol { margin: 0.35em 0 0.75em; padding-left: 1.3em; }
.gradio-container .prose li { margin: 0.2em 0; }
.gradio-container .prose strong { font-weight: 650; }
.gradio-container .prose hr { border: none; height: 1px; margin: 1.2em 0; background: var(--tp-border); }
.gradio-container .prose blockquote { margin: 0.8em 0; padding: 10px 14px; border-radius: var(--tp-radius-sm);
  border: 1px solid var(--tp-border); border-left: 3px solid var(--tp-accent);
  background: var(--tp-surface-2); color: var(--tp-text-muted); font-style: normal; }
.gradio-container .prose code, .gradio-container code { font-family: var(--font-mono);
  font-size: 0.86em; padding: 1px 5px; border-radius: 5px; background: var(--tp-surface-2); }
.gradio-container .prose pre code { padding: 0; background: transparent; }
.gradio-container .prose table { border-collapse: collapse; width: 100%; font-size: 0.88rem;
  margin: 0.5rem 0 1rem; font-variant-numeric: tabular-nums; }
.gradio-container .prose th { text-align: left; font-weight: 600; color: var(--tp-text-muted);
  background: var(--tp-surface-2); padding: 8px 10px; border-bottom: 1px solid var(--tp-border); }
.gradio-container .prose td { padding: 8px 10px; border-bottom: 1px solid var(--tp-border); vertical-align: top; }

/* ===== Estado vacío ===== */
.tp2-empty-state { text-align: center; padding: 36px 16px; color: var(--tp-text-muted); }
.tp2-empty-state svg { width: 36px; height: 36px; margin: 0 auto 12px; display: block;
  color: var(--tp-border-strong); }
.tp2-empty-state h4 { margin: 0 0 6px; font-size: 0.98rem; font-weight: 700; color: var(--tp-text); }
.tp2-empty-state p { margin: 0; font-size: 0.88rem; }
.tp2-steps { display: inline-flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 16px; padding: 0; list-style: none; }
.tp2-steps li { display: inline-flex; align-items: center; gap: 8px; font-size: 0.82rem;
  padding: 6px 12px; border: 1px solid var(--tp-border); border-radius: 999px; background: var(--tp-surface-2); }
.tp2-steps b { display: inline-grid; place-items: center; width: 18px; height: 18px; font-size: 0.72rem;
  border-radius: 50%; background: var(--tp-accent); color: var(--tp-on-accent); }
.tp2-muted { color: var(--tp-text-muted); font-size: 0.88rem; margin: 0; }

/* ===== Perfil del paciente ===== */
.tp2-patient-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.tp2-avatar { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
  font-weight: 700; font-size: 0.85rem; background: var(--tp-accent-soft); color: var(--tp-accent-strong); flex: none; }
.dark .tp2-avatar { color: var(--tp-accent); }
.tp2-patient-id { margin: 0; font-size: 1.05rem; font-weight: 700; color: var(--tp-text); }
.tp2-patient-sub { margin: 1px 0 0; font-size: 0.84rem; color: var(--tp-text-muted); }
.tp2-kv { display: grid; grid-template-columns: minmax(96px, auto) 1fr; gap: 8px 14px; margin: 0; font-size: 0.86rem; }
.tp2-kv dt { color: var(--tp-text-muted); }
.tp2-kv dd { margin: 0; color: var(--tp-text); font-weight: 500; font-variant-numeric: tabular-nums; }
.tp2-kv dd small { color: var(--tp-text-muted); font-weight: 400; }
.tp2-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.tp2-chip { font-size: 0.78rem; font-weight: 500; padding: 2px 9px; border-radius: 999px;
  border: 1px solid var(--tp-border); background: var(--tp-surface-2); color: var(--tp-text); }

/* ===== Indicadores (resumen del análisis) ===== */
.tp2-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); gap: 12px; }
.tp2-kpis.is-empty .tp2-kpi-value { color: var(--tp-border-strong); }
.tp2-kpi { background: var(--tp-surface); border: 1px solid var(--tp-border); border-radius: var(--tp-radius);
  padding: 14px 16px; box-shadow: var(--tp-shadow); min-width: 0; }
.tp2-kpi-label { margin: 0; font-size: 0.78rem; font-weight: 600; color: var(--tp-text-muted); }
.tp2-kpi-value { margin: 6px 0 2px; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em;
  color: var(--tp-text); font-variant-numeric: tabular-nums; line-height: 1.15; }
.tp2-kpi-value small { font-size: 0.8rem; font-weight: 600; color: var(--tp-text-muted); margin-left: 3px; letter-spacing: 0; }
.tp2-kpi-foot { margin: 0; font-size: 0.78rem; color: var(--tp-text-muted); display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.tp2-trend { font-weight: 600; }
.tp2-kpi.is-high { border-color: var(--tp-sev-high-bd); }
.tp2-kpi.is-high .tp2-kpi-value { color: var(--tp-sev-high-fg); }
.tp2-kpi.is-ok .tp2-kpi-value { color: var(--tp-ok-fg); }

/* ===== Pills de severidad / estado ===== */
.tp2-pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 9px; border-radius: 999px;
  font-size: 0.76rem; font-weight: 600; border: 1px solid transparent; white-space: nowrap; }
.tp2-pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.tp2-pill.sev-severa { color: var(--tp-sev-high-fg); background: var(--tp-sev-high-bg); border-color: var(--tp-sev-high-bd); }
.tp2-pill.sev-moderada { color: var(--tp-sev-mid-fg); background: var(--tp-sev-mid-bg); border-color: var(--tp-sev-mid-bd); }
.tp2-pill.sev-leve { color: var(--tp-sev-low-fg); background: var(--tp-sev-low-bg); border-color: var(--tp-sev-low-bd); }
.tp2-pill.is-ok { color: var(--tp-ok-fg); background: var(--tp-ok-bg); border-color: var(--tp-ok-bd); }
.tp2-pill.is-info { color: var(--tp-info-fg); background: var(--tp-info-bg); border-color: var(--tp-info-bd); }
.tp2-pill.is-neutral { color: var(--tp-text-muted); background: var(--tp-surface-2); border-color: var(--tp-border); }

/* ===== Tablas de datos (alertas, tendencias) ===== */
.tp2-table-wrap { overflow-x: auto; border: 1px solid var(--tp-border) !important; border-radius: var(--tp-radius-sm); }
.tp2-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; font-variant-numeric: tabular-nums;
  border: none !important; margin: 0 !important; }
/* Gradio dibuja bordes verticales gruesos en toda tabla: acá solo filetes horizontales. */
.tp2-table th, .tp2-table td, .gradio-container .prose th, .gradio-container .prose td {
  border-left: none !important; border-right: none !important; border-top: none !important; }
.tp2-table thead, .tp2-table tr, .gradio-container .prose thead, .gradio-container .prose tr {
  border-color: var(--tp-border) !important; }
.tp2-table td.period { white-space: normal; min-width: 120px; }
.gradio-container .prose table { border: 1px solid var(--tp-border) !important; border-radius: var(--tp-radius-sm); }
.tp2-table th { text-align: left; font-weight: 600; font-size: 0.76rem; color: var(--tp-text-muted);
  background: var(--tp-surface-2); padding: 9px 12px; border-bottom: 1px solid var(--tp-border); white-space: nowrap; }
.tp2-table td { padding: 10px 12px; border-bottom: 1px solid var(--tp-border); color: var(--tp-text); vertical-align: top; }
.tp2-table tr:last-child td { border-bottom: none; }
.tp2-table tbody tr:hover td { background: var(--tp-surface-2); }
.tp2-table .num { text-align: right; white-space: nowrap; }
.tp2-table th.num { text-align: right; }
.tp2-table .metric { font-weight: 600; white-space: nowrap; }
.tp2-table .unit { color: var(--tp-text-muted); font-weight: 400; font-size: 0.78rem; margin-left: 4px; }
.tp2-table .desc { color: var(--tp-text-muted); min-width: 160px; }
.tp2-table .id { font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600; color: var(--tp-text-muted); }
.tp2-disclosure { margin-top: 12px; }
.tp2-disclosure > summary { cursor: pointer; font-size: 0.85rem; font-weight: 600; color: var(--tp-accent);
  padding: 4px 0; list-style: none; }
.tp2-disclosure > summary::-webkit-details-marker { display: none; }
.tp2-disclosure > summary::before { content: "\\203A"; display: inline-block; width: 14px;
  transition: transform 0.15s ease; }
.tp2-disclosure[open] > summary::before { transform: rotate(90deg); }
.tp2-disclosure[open] > summary { margin-bottom: 8px; }
.tp2-table .na { color: var(--tp-text-muted); }
.tp2-dir { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; font-weight: 500; }
.tp2-dir.up { color: var(--tp-sev-mid-fg); }
.tp2-dir.down { color: var(--tp-info-fg); }
.tp2-dir.flat { color: var(--tp-text-muted); }
.tp2-callout { display: flex; gap: 10px; align-items: flex-start; margin-top: 12px; padding: 10px 14px;
  border-radius: var(--tp-radius-sm); font-size: 0.86rem; border: 1px solid var(--tp-sev-mid-bd);
  background: var(--tp-sev-mid-bg); color: var(--tp-text); }
.tp2-callout ul { margin: 4px 0 0; padding-left: 1.1em; }
.tp2-callout.is-ok { border-color: var(--tp-ok-bd); background: var(--tp-ok-bg); }
.tp2-callout.is-neutral { border-color: var(--tp-border); background: var(--tp-surface-2); color: var(--tp-text-muted); }

/* ===== Chat ===== */
.tp2-chat-col .bubble-wrap, .tp2-chat-col [role="log"] { background: transparent !important; }
.tp2-chat-col .message { font-size: 0.9rem; line-height: 1.55; }
.tp2-chat-actions { gap: 8px !important; }

/* ===== Visor de logs (Observabilidad) ===== */
.tp2-logs { font-family: var(--font-mono); font-size: 12px; max-height: 560px; overflow-y: auto;
  border: 1px solid var(--tp-border); border-radius: var(--tp-radius-sm); background: var(--tp-surface); }
.tp2-head, .tp2-cells { display: grid; gap: 10px; align-items: center;
  grid-template-columns: 104px 96px 170px 1fr; padding: 7px 12px; }
.tp2-head { position: sticky; top: 0; z-index: 1; font-family: var(--font-sans, inherit); font-size: 0.74rem;
  font-weight: 600; color: var(--tp-text-muted); background: var(--tp-surface-2); border-bottom: 1px solid var(--tp-border); }
.tp2-row { border-bottom: 1px solid var(--tp-border); }
.tp2-row > summary { cursor: pointer; list-style: none; }
.tp2-row > summary::-webkit-details-marker { display: none; }
.tp2-row > summary:hover { background: var(--tp-surface-2); }
.tp2-ts { color: var(--tp-text-muted); }
.tp2-ts::before { content: "\\203A  "; color: var(--tp-text-muted); }
.tp2-row[open] > summary .tp2-ts::before { content: "\\2304  "; }
.tp2-nm, .tp2-sm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--tp-text); }
.tp2-ev { justify-self: start; font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 5px;
  background: var(--tp-surface-2); color: var(--tp-text-muted); border: 1px solid var(--tp-border); }
.tp2-ev.ev-llm { color: var(--tp-info-fg); background: var(--tp-info-bg); border-color: var(--tp-info-bd); }
.tp2-ev.ev-tool { color: var(--tp-accent-strong); background: var(--tp-accent-soft); border-color: transparent; }
.dark .tp2-ev.ev-tool { color: var(--tp-accent); }
.tp2-ev.ev-error { color: var(--tp-sev-high-fg); background: var(--tp-sev-high-bg); border-color: var(--tp-sev-high-bd); }
.tp2-raw { margin: 0; padding: 10px 14px; white-space: pre-wrap; word-break: break-word;
  font-size: 11.5px; background: var(--tp-surface-2); color: var(--tp-text); }
.tp2-empty { padding: 18px; color: var(--tp-text-muted); font-family: inherit; }

/* ===== Evaluación ===== */
.tp2-eval-panel { height: 100%; }
.tp2-eval-expected, .tp2-eval-obtained { max-height: 560px; overflow-y: auto; }

/* ===== Responsive ===== */
@media (max-width: 1100px) { .tp2-chat-col { position: static; } }
@media (max-width: 720px) {
  .tp2-appbar { flex-wrap: wrap; gap: 12px; padding-top: 14px; }
  .tp2-appbar-actions { margin-left: 0; width: 100%; justify-content: space-between; }
  .tp2-status { max-width: calc(100% - 48px); }
  .tp2-brand-sub { font-size: 0.8rem; }
  .tp2-card { padding: 14px 14px !important; }
  .tp2-tabs button[role="tab"] { padding: 8px 10px; }
  .tp2-kpi-value { font-size: 1.35rem; }
}
"""

# Reglas sobre el contenedor de Gradio y sus ancestros. Van por `head` y no por `css` porque Gradio
# prefija TODO el `css` con `.gradio-container… .contain`, así que una regla sobre `.gradio-container`,
# `.main` o `footer` nunca matchea desde ahí.
HEAD = """<link rel="icon" type="image/svg+xml" href="/favicon.ico">
<style>
.gradio-container, .gradio-container * { -webkit-font-smoothing: antialiased; }
footer { display: none !important; }
@media (max-width: 720px) {
  /* En celular, 24px del contenedor + 32px de .main comían casi un tercio de la pantalla. */
  .gradio-container { padding-left: 12px !important; padding-right: 12px !important; }
  .gradio-container .main { padding-left: 0 !important; padding-right: 0 !important; }
}
</style>"""

CSS = (
    _font_face(FONT_SANS, "plus-jakarta-sans-latin-wght-normal.woff2")
    + _font_face(FONT_SANS, "plus-jakarta-sans-latin-wght-italic.woff2", style="italic")
    + _font_face(FONT_MONO, "jetbrains-mono-latin-wght-normal.woff2", weights="100 800")
    + _TOKENS_CSS
    + _LAYOUT_CSS
)


# -------------------------------------------------------------------
# Selector de tema claro / oscuro
# -------------------------------------------------------------------
# Corre en el js_on_load del header (gr.HTML): aplica la preferencia guardada (si la hay) y
# alterna la clase `dark` de <body>, que es la que usa Gradio para su propio modo oscuro.
# La preferencia vive en localStorage del navegador; sin ella manda la del sistema operativo.
THEME_TOGGLE_JS = """
const KEY = 'tp2-theme';
const apply = (mode) => document.body.classList.toggle('dark', mode === 'dark');
try { const saved = localStorage.getItem(KEY); if (saved) apply(saved); } catch (e) {}
const btn = element.querySelector('[data-theme-toggle]');
const sync = () => btn && btn.setAttribute('aria-pressed', String(document.body.classList.contains('dark')));
sync();
if (btn) btn.addEventListener('click', () => {
  const mode = document.body.classList.contains('dark') ? 'light' : 'dark';
  apply(mode);
  try { localStorage.setItem(KEY, mode); } catch (e) {}
  sync();
});
"""

# Isotipo (monograma "MC" con línea de tendencia), el mismo glifo que interface/assets/logo.svg pero
# sin fondo ni <style>: el cuadrado lo pone .tp2-logo y el color sale de currentColor, así sigue al
# selector de tema (el <style> del archivo sería CSS global en la página y responde al sistema operativo).
_ICON_LOGO = (
    "<svg viewBox='0 0 24 24' aria-hidden='true'>"
    "<g transform='translate(1.8, 1.8) scale(0.85)' fill='none' stroke='currentColor' stroke-width='2.2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M18.7 6A9 9 0 1 0 18.7 18'/>"
    "<path d='M8 15L10.3 9.8L12.8 13.5L15.4 8.5L17.6 12.2'/>"
    "<circle cx='18.3' cy='13.4' r='1.5' fill='currentColor' stroke='none'/></g></svg>"
)

LOGO_PATH = Path(__file__).parent / "assets" / "logo.svg"
_ICON_MOON = (
    "<svg class='tp2-ic-moon' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<path d='M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z'/></svg>"
)
_ICON_SUN = (
    "<svg class='tp2-ic-sun' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='12' cy='12' r='4'/><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4"
    "M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/></svg>"
)
_ICON_INFO = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='12' cy='12' r='10'/><path d='M12 16v-4M12 8h.01'/></svg>"
)


def appbar_html(status_text: str, status_ok: bool, status_detail: str = "") -> str:
    """Barra superior: marca, estado del LLM, selector de tema y aviso clínico permanente."""
    status_cls = "is-ok" if status_ok else "is-warn"
    status = html.escape(status_text)
    detail = html.escape(status_detail or status_text)
    return (
        "<header class='tp2-appbar'>"
        "<div class='tp2-brand'>"
        f"<div class='tp2-logo'>{_ICON_LOGO}</div>"
        "<div class='tp2-brand-text'>"
        "<p class='tp2-brand-name'>Monitor Clínico</p>"
        "<p class='tp2-brand-sub'>Seguimiento de diabetes tipo 2 · sistema multiagente</p>"
        "</div></div>"
        "<div class='tp2-appbar-actions'>"
        f"<span class='tp2-status {status_cls}' title=\"{detail}\">"
        f"<span class='tp2-status-dot'></span>{status}</span>"
        "<button type='button' class='tp2-icon-btn' data-theme-toggle aria-pressed='false' "
        "aria-label='Alternar modo claro u oscuro' title='Modo claro / oscuro'>"
        f"{_ICON_MOON}{_ICON_SUN}</button>"
        "</div></header>"
        f"<p class='tp2-notice'>{_ICON_INFO}"
        "Herramienta de soporte a la decisión clínica. No emite diagnósticos: "
        "el criterio es siempre del médico tratante.</p>"
    )


def card_head(title: str, meta: str = "") -> str:
    """Encabezado de tarjeta (título + metadato opcional a la derecha)."""
    meta_html = f"<span class='tp2-card-meta'>{meta}</span>" if meta else ""
    return f"<div class='tp2-card-head'><h3 class='tp2-card-title'>{title}</h3>{meta_html}</div>"
