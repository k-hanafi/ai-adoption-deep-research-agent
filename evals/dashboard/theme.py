"""Shared dark CSS tokens (Classifier Eval Suite visual language)."""

from __future__ import annotations

DARK_CSS = """
:root {
  --bg: #0d0f12;
  --bg-elevated: #151920;
  --border: #2a3140;
  --text: #e8eaed;
  --muted: #9aa3b2;
  --link: #6ea8ff;
  --link-hover: #9bc2ff;
  --chip-border: #3a4354;
  --accent: #6ea8ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.45;
}
a { color: var(--link); text-decoration: none; }
a:hover { color: var(--link-hover); text-decoration: underline; }
.wrap { max-width: 980px; margin: 0 auto; padding: 1.75rem 1.25rem 3rem; }
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  margin-bottom: 0.35rem;
}
h1 {
  font-size: 1.55rem;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.02em;
}
.subtitle { color: var(--muted); font-size: 0.95rem; margin: 0; }
.lede { color: var(--muted); font-size: 0.92rem; margin: 0.75rem 0 1.5rem; max-width: 52rem; }
.chip {
  display: inline-block;
  border: 1px solid var(--chip-border);
  color: var(--muted);
  padding: 0.12rem 0.45rem;
  border-radius: 3px;
  font-size: 0.75rem;
  letter-spacing: 0.02em;
}
.section { margin: 2rem 0 1.25rem; }
.section h2 {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0 0 0.65rem;
  font-weight: 600;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
th, td {
  text-align: left;
  padding: 0.7rem 0.85rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  font-size: 0.9rem;
}
th {
  color: var(--muted);
  font-weight: 500;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
tr:last-child td { border-bottom: none; }
.title-cell a { font-weight: 600; font-size: 0.95rem; }
.meta {
  display: block;
  margin-top: 0.2rem;
  color: var(--muted);
  font-size: 0.78rem;
}
.empty {
  color: var(--muted);
  font-size: 0.88rem;
  padding: 0.85rem;
  border: 1px dashed var(--border);
  border-radius: 6px;
  background: var(--bg-elevated);
}
.empty code {
  color: var(--text);
  font-size: 0.84rem;
}
.footer {
  margin-top: 2rem;
  color: var(--muted);
  font-size: 0.75rem;
}
.banner {
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  padding: 0.75rem 0.9rem;
  border-radius: 6px;
  color: var(--muted);
  font-size: 0.88rem;
  margin: 1rem 0 1.25rem;
}
pre {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  padding: 0.85rem;
  overflow: auto;
  border-radius: 6px;
  font-size: 0.82rem;
}
"""
