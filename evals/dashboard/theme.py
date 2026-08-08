"""Shared CSS for the Eval Suite GUI (ported from Classifier Eval Suite)."""

from __future__ import annotations

# Visual language copied from ai-startups-taxonomy-research
# (`build_eval_dashboard.py` STYLE + archive index tokens).
SUITE_CSS = """
:root {
  --bg: #0a0a0a;
  --surface: #111111;
  --surface-muted: #161616;
  --border: #2a2a2a;
  --border-strong: #333333;
  --text: #e8e8ea;
  --text2: #a8abb0;
  --muted: #7a7e85;
  --accent: #5b8fc4;
  --accent-bg: #152033;
  --pass: #3fb950;
  --pass-bg: #0f1f14;
  --fail: #f85149;
  --fail-bg: #2a1210;
  --pending: #8b9096;
  --pending-bg: #1a1a1a;
  --winner: #c9944f;
  --winner-bg: #241c10;
  --sans: "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.55;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code {
  font-family: var(--mono);
  font-size: 0.92em;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  padding: 0.05em 0.35em;
}

.appbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 24px;
  border-bottom: 1px solid var(--border);
  padding: 18px 36px;
}
.brand {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--text);
}
.brand small {
  margin-left: 0;
  font-size: 12px;
  font-weight: 400;
  color: var(--muted);
}
.appbar-meta {
  font-size: 12px;
  font-family: var(--mono);
  color: var(--muted);
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  padding: 0 36px;
}
.tab {
  appearance: none;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  padding: 13px 14px;
  font: inherit;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text2);
  cursor: pointer;
}
.tab:hover { color: var(--text); background: var(--surface-muted); }
.tab.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}

.content {
  max-width: 1160px;
  margin: 0 auto;
  padding: 28px 36px 72px;
}
.panel { display: none; }
.panel.active { display: block; }
.tab-lead {
  margin-bottom: 24px;
  max-width: 860px;
}
.tab-lead h2 {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.015em;
  margin-bottom: 4px;
}
.tab-lead p { font-size: 13.5px; color: var(--text2); }

.notice {
  display: flex;
  align-items: baseline;
  gap: 12px;
  border: 1px solid var(--border);
  border-left: 2px solid var(--border-strong);
  background: var(--surface-muted);
  padding: 10px 14px;
  margin: 16px 36px 0;
  font-size: 12.5px;
  color: var(--text2);
  line-height: 1.5;
}
.notice.scored { border-left-color: var(--accent); }
.notice.dry { border-left-color: var(--pending); }
.notice .tag {
  flex: 0 0 auto;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--pending);
  border: 1px solid var(--border-strong);
  padding: 2px 7px;
  background: var(--surface);
}
.notice.scored .tag { color: var(--accent); }
.notice .run-headline {
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
}
.notice .run-meta {
  display: block;
  margin-top: 3px;
  font-family: var(--mono);
  font-size: 11.5px;
  color: var(--muted);
}

.check {
  border: 1px solid var(--border);
  margin-bottom: 16px;
  background: var(--surface);
}
.check-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.check-head h3 {
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.check-body { padding: 14px 18px 16px; }
.check-meaning {
  font-size: 13px;
  color: var(--text2);
  max-width: 820px;
  margin-bottom: 14px;
}
.check-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  border: 1px solid var(--border);
  margin-bottom: 14px;
  width: fit-content;
}
.stat {
  padding: 8px 18px;
  border-right: 1px solid var(--border);
  min-width: 130px;
}
.stat:last-child { border-right: none; }
.stat-label {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 1px;
}
.stat-value {
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
}
.check-footnote {
  font-size: 12px;
  color: var(--muted);
  max-width: 720px;
  margin-top: 12px;
}
table.mini {
  border-collapse: collapse;
  font-size: 12.5px;
  min-width: 420px;
}
table.mini th, table.mini td {
  text-align: left;
  padding: 6px 16px 6px 0;
  border-bottom: 1px solid var(--border);
}
table.mini th {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
}
table.mini tr:last-child td { border-bottom: none; }
table.mini td.mono { font-family: var(--mono); font-size: 12px; }
table.mini td.num { font-family: var(--mono); text-align: right; }
.mini-status {
  font-family: var(--mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.mini-status.pass { color: var(--pass); }
.mini-status.fail { color: var(--fail); }
.mini-status.pending { color: var(--pending); }
.mini-status.winner { color: var(--winner); }

.filter-shell {
  border-bottom: 1px solid var(--border);
  padding: 14px 36px 10px;
  background: var(--bg);
}
.filter-shell[hidden] { display: none !important; }
.filter-shell-inner { max-width: 1160px; margin: 0 auto; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding-bottom: 10px;
}
.toolbar-hint {
  width: 100%;
  font-size: 11.5px;
  color: var(--muted);
  margin-bottom: 4px;
}
.toolbar-left, .toolbar-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.toolbar-right { margin-left: auto; }
.toolbar-label {
  font-size: 11px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 500;
  margin-right: 2px;
}
.toolbar-count {
  font-size: 12px;
  font-family: var(--mono);
  color: var(--muted);
  white-space: nowrap;
}
.chip {
  appearance: none;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text2);
  padding: 5px 11px;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}
.chip:hover { border-color: var(--border-strong); color: var(--text); }
.chip.active {
  background: var(--accent-bg);
  border-color: var(--accent);
  color: var(--accent);
}
.btn-ghost {
  appearance: none;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text2);
  padding: 5px 11px;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}
.btn-ghost:hover { background: var(--surface-muted); color: var(--text); }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 18px 20px 10px;
  margin-bottom: 20px;
}
.card-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
  margin-bottom: 3px;
}
.card-desc {
  font-size: 12.5px;
  color: var(--muted);
  margin-bottom: 10px;
  max-width: 860px;
}
.chart { width: 100%; height: 340px; }
.chart.short { height: 260px; }

.table-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  overflow-x: auto;
  margin-bottom: 20px;
}
table.grid {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
table.grid th {
  text-align: left;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-strong);
  background: var(--surface-muted);
  white-space: nowrap;
}
table.grid th.num, table.grid td.num { text-align: right; }
table.grid td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  vertical-align: middle;
}
table.grid tr:last-child td { border-bottom: none; }
table.grid tbody tr:hover { background: var(--surface-muted); }
table.grid tbody tr.winner-row { background: var(--winner-bg); }
table.grid tbody tr.winner-row:hover { background: #2c2214; }
table.grid td.mono { font-family: var(--mono); font-size: 12.5px; }
.name-cell { font-weight: 600; letter-spacing: -0.01em; }
.sub-cell { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
.score-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
}
.score-val {
  font-family: var(--mono);
  font-size: 12.5px;
  font-weight: 500;
  min-width: 3.2rem;
  text-align: right;
}
.score-bar {
  width: 84px;
  height: 5px;
  background: var(--surface-muted);
  border: 1px solid var(--border);
}
.score-bar > span {
  display: block;
  height: 100%;
  background: var(--accent);
}
.badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-family: var(--mono);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  vertical-align: middle;
  border: 1px solid var(--border);
  color: var(--muted);
}
.badge.winner {
  color: var(--winner);
  border-color: var(--winner);
  background: var(--winner-bg);
}
.badge.fail {
  color: var(--fail);
  border-color: var(--fail);
  background: var(--fail-bg);
}
.badge.pass {
  color: var(--pass);
  border-color: var(--pass);
  background: var(--pass-bg);
}

.empty {
  padding: 44px 20px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
  border: 1px dashed var(--border);
  background: var(--surface-muted);
}

/* Archive landing (taxonomy eval_instances/index.html) */
main.archive {
  padding: 28px 36px 48px;
  max-width: 1100px;
}
.lede { color: var(--text2); max-width: 70ch; margin-bottom: 24px; }
.section { margin: 2rem 0 1.25rem; }
.section h2 {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0 0 0.65rem;
  font-weight: 600;
}
table.archive-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 8px;
}
table.archive-table th, table.archive-table td {
  text-align: left;
  padding: 11px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
table.archive-table th {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}
table.archive-table tr:last-child td { border-bottom: none; }
table.archive-table td.num {
  font-family: var(--mono);
  color: var(--text2);
  white-space: nowrap;
}
table.archive-table .meta {
  display: block;
  margin-top: 2px;
  color: var(--text2);
  font-size: 12px;
}
.tag-inline {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
  border: 1px solid var(--border);
  padding: 1px 6px;
  margin-left: 8px;
}

footer.page-footer {
  margin-top: 44px;
  padding-top: 18px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
  line-height: 1.7;
}

@media (max-width: 720px) {
  .appbar, .tabs, .filter-shell { padding-left: 18px; padding-right: 18px; }
  .notice { margin: 14px 18px 0; }
  .content, main.archive { padding: 20px 18px 56px; }
  .appbar-meta { white-space: normal; }
  .tabs { flex-wrap: wrap; }
  .tab { padding: 10px 10px; font-size: 12.5px; }
  .toolbar-right { width: 100%; margin-left: 0; }
  .chart, .chart.short { height: 240px; }
}
"""

# Back-compat alias used by older imports.
DARK_CSS = SUITE_CSS
