# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""karta-status poll server: a live, karta-branded status page over the engine.

Zero dependencies — stdlib `http.server` only. Derives state fresh on every request
from the CWD's `.karta/binders` + git, so running it from a repo renders that repo.

  uv run --script serve_status.py                 # http://127.0.0.1:8765
  uv run --script serve_status.py --port 9000     # a different port
  uv run --script serve_status.py --key s3cret    # gate behind ?key=s3cret

Routes:
  GET /            the app HTML shell (a self-contained document; renders via Vue)
  GET /state.json  the enriched engine state as JSON (recomputed each request)
  GET /assets/<f>  the brand bytes + the vendored Vue (mascot.png, icon.png,
                   vendor/vue.global.prod.js) — same-origin only

The page is "Karta Watch": a read-only mirror of git. A thin stdlib server hands the
browser the current state inline (for a correct first paint, and so a file:// snapshot
works without a server) plus the vendored Vue app, which renders the whole design
reactively and — when not on file:// — polls /state.json every 2.6s as a live mirror.
The next action is the amber hero band ("YOU RUN NEXT"); the binder sequence is a card
column that ends at the gold star (main / the integration branch); the viewed binder's
work items are grouped by state with click-to-expand oracle detail. Light + dark ship
in one stylesheet via prefers-color-scheme; `?theme=light|dark` forces one (screenshots).
Self-contained: no CDN, no remote images, no remote fonts, no external JS — Vue is the
one vendored same-origin file.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# Import the sibling engine regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import karta_next  # noqa: E402

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# ---------------------------------------------------------------------------
# State + the data join (engine status  x  binder work_item detail)
# ---------------------------------------------------------------------------


def _enrich(state: dict, binders: list[dict]) -> dict:
    """Join each derived item (status only) back to its binder `work_item` so the
    renderers get desc/oracle/assert/cmd/deps. `derive_state` stays untouched."""
    wi_by_slug: dict[str, dict] = {}
    for b in binders:
        wi_by_slug[b["slug"]] = {it["id"]: it for it in b.get("work_items", [])}

    for ob in state["binders"]:
        items = wi_by_slug.get(ob["slug"], {})
        for d in ob["items"]["detail"]:
            wi = items.get(d["id"], {})
            oracle = wi.get("oracle", {}) or {}
            # an opt-out oracle is {opt_out: true, reason: ...}; treat type as "opt-out"
            if oracle.get("opt_out"):
                otype = "opt-out"
            else:
                otype = oracle.get("type", "unit")
            assertions = oracle.get("assertions") or []
            d["desc"] = wi.get("title", d["id"])
            d["oracle"] = otype
            d["assert"] = assertions[0] if assertions else None
            d["cmd"] = oracle.get("command")
            d["deps"] = wi.get("depends_on", []) or []
    return state


def current_state() -> dict:
    """Recompute the engine state from the CWD's .karta + git. Never cached.

    Returns the engine state with each item enriched (desc/oracle/assert/cmd/deps)
    by joining back to the binder `work_item` definitions."""
    binders = karta_next.load_binders()
    facts = karta_next.gather_git_facts(binders, karta_next._default_branch())
    state = karta_next.derive_state(binders, facts)
    return _enrich(state, binders)


# ---------------------------------------------------------------------------
# Icons — the design's ICONS() path data. Each value is a list of (tag, attrs)
# shapes. We hand the SAME data to the browser as `const ICONS = {...}` so the
# Vue app renders the identical inline <svg> shapes.
# ---------------------------------------------------------------------------

_ICONS: dict[str, list[tuple[str, dict]]] = {
    "done": [("circle", {"cx": 12, "cy": 12, "r": 10}),
             ("path", {"d": "m8.5 12 2.4 2.4 4.6-5"})],
    "building": [("path", {"d": "M21 12a9 9 0 1 1-6.219-8.56"})],
    "ready": [("circle", {"cx": 12, "cy": 12, "r": 10}),
              ("polygon", {"points": "10 8 16 12 10 16"})],
    "blocked": [("rect", {"x": 3, "y": 11, "width": 18, "height": 10, "rx": 2}),
                ("path", {"d": "M7 11V7a5 5 0 0 1 10 0v4"})],
    "unit": [("path", {"d": "M14 2v6l5.5 9.5a2 2 0 0 1-1.7 3H6.2a2 2 0 0 1-1.7-3L10 8V2"}),
             ("path", {"d": "M8.5 2h7"}),
             ("path", {"d": "M7 16h10"})],
    "integration": [("circle", {"cx": 18, "cy": 18, "r": 3}),
                    ("circle", {"cx": 6, "cy": 6, "r": 3}),
                    ("path", {"d": "M6 21V9a9 9 0 0 0 9 9"})],
    "e2e": [("circle", {"cx": 6, "cy": 19, "r": 3}),
            ("path", {"d": "M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"}),
            ("circle", {"cx": 18, "cy": 5, "r": 3})],
    "smoke": [("path", {"d": "M22 12h-4l-3 9L9 3l-3 9H2"})],
    "visual": [("path", {"d": "M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"}),
               ("circle", {"cx": 12, "cy": 12, "r": 3})],
    "binder": [("path", {"d": "M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"}),
               ("path", {"d": "m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"}),
               ("path", {"d": "m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"})],
    "branch": [("line", {"x1": 6, "x2": 6, "y1": 3, "y2": 15}),
               ("circle", {"cx": 18, "cy": 6, "r": 3}),
               ("circle", {"cx": 6, "cy": 18, "r": 3}),
               ("path", {"d": "M18 9a9 9 0 0 1-9 9"})],
    "star": [("polygon", {"points": "12 2 15 8.5 22 9.3 17 14 18.3 21 12 17.5 5.7 21 7 14 2 9.3 9 8.5"})],
    "arrow": [("path", {"d": "m9 18 6-6-6-6"})],
    "play": [("polygon", {"points": "6 3 20 12 6 21 6 3"})],
    "copy": [("rect", {"x": 9, "y": 9, "width": 12, "height": 12, "rx": 2}),
             ("path", {"d": "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"})],
    "sun": [("circle", {"cx": 12, "cy": 12, "r": 4}), ("path", {"d": "M12 2v2"}), ("path", {"d": "M12 20v2"}), ("path", {"d": "m4.93 4.93 1.41 1.41"}), ("path", {"d": "m17.66 17.66 1.41 1.41"}), ("path", {"d": "M2 12h2"}), ("path", {"d": "M20 12h2"}), ("path", {"d": "m6.34 17.66-1.41 1.41"}), ("path", {"d": "m19.07 4.93-1.41 1.41"})],
    "moon": [("path", {"d": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"})],
    "eye": [("path", {"d": "M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"}), ("circle", {"cx": 12, "cy": 12, "r": 3})],
    "eye-off": [("path", {"d": "m15 18-.722-3.25"}), ("path", {"d": "M2 8a10.645 10.645 0 0 0 20 0"}), ("path", {"d": "m20 15-1.726-2.05"}), ("path", {"d": "m4 15 1.726-2.05"}), ("path", {"d": "m9 18 .722-3.25"})],
}


# ---------------------------------------------------------------------------
# State metadata — color + soft + icon + label per item/binder state.
# Mirrors the design's stateMeta, extended to cover the engine's `built`/`failed`
# so those surface instead of breaking the page. Shipped to JS verbatim.
# ---------------------------------------------------------------------------

_STATE = {
    "done":     {"color": "var(--green)", "soft": "var(--green-soft)", "icon": "done",     "label": "done"},
    "building": {"color": "var(--amber)", "soft": "var(--amber-soft)", "icon": "building", "label": "building"},
    "ready":    {"color": "var(--steel)", "soft": "var(--steel-soft)", "icon": "ready",    "label": "ready"},
    "blocked":  {"color": "var(--block)", "soft": "var(--block-soft)", "icon": "blocked",  "label": "blocked"},
    # engine-only states the design never showed — keep the page from breaking:
    "built":    {"color": "var(--steel)", "soft": "var(--steel-soft)", "icon": "ready",    "label": "built"},
    "failed":   {"color": "var(--block)", "soft": "var(--block-soft)", "icon": "blocked",  "label": "failed"},
}

# binder.status -> the kind used to colour its card / stage label
_BINDER_KIND = {"merged": "done", "in_flight": "building", "not_started": "ready"}
_STAGE_LABEL = {"merged": "merged into main", "in_flight": "building", "not_started": "not started"}

# oracle.type -> icon name (the design only carries these; fall back to unit)
_ORACLE_ICON = {"unit": "unit", "integration": "integration", "e2e": "e2e",
                "smoke": "smoke", "visual": "visual", "opt-out": "smoke"}

# the work-item groups, in display order (engine-only states tail the list)
_GROUP_DEFS = [
    {"key": "building", "label": "Building", "sub": "in a worktree now"},
    {"key": "ready", "label": "Ready", "sub": "queued · dependencies met"},
    {"key": "blocked", "label": "Blocked", "sub": "waiting on a dependency"},
    {"key": "done", "label": "Done", "sub": "merged into the branch"},
    {"key": "built", "label": "Built", "sub": "committed · awaiting merge"},
    {"key": "failed", "label": "Failed", "sub": "the check did not pass"},
]

# the state-word order for the legend (the four the design shows)
_LEGEND_KEYS = ["done", "building", "ready", "blocked"]


# ---------------------------------------------------------------------------
# The two design palettes, ported verbatim from the design's vars().
# ---------------------------------------------------------------------------

_DARK_VARS = (
    "--bg:#14161e;--panel:#1f2530;--panel-2:#191e27;--line:rgba(255,255,255,0.07);"
    "--ink:#e8e5dd;--mut:#8b8f9a;--amber:#d9a94a;--amber-soft:rgba(217,169,74,0.13);"
    "--green:#74a583;--green-soft:rgba(116,165,131,0.13);--steel:#8e96a8;"
    "--steel-soft:rgba(142,150,168,0.14);--block:#c2876a;--block-soft:rgba(194,135,106,0.13);"
    "--star:#d9b455;--banner:linear-gradient(180deg,#ddae50,#cf9e3e);--banner-ink:#352809;"
    "--chip:rgba(0,0,0,0.22);--live:#74a583;"
)
_LIGHT_VARS = (
    "--bg:#efece4;--panel:#ffffff;--panel-2:#f6f3ec;--line:rgba(40,30,10,0.12);"
    "--ink:#2a2d36;--mut:#797d88;--amber:#b1832c;--amber-soft:rgba(177,131,44,0.12);"
    "--green:#4e885c;--green-soft:rgba(78,136,92,0.12);--steel:#5e6985;"
    "--steel-soft:rgba(94,105,133,0.12);--block:#a9633f;--block-soft:rgba(169,99,63,0.12);"
    "--star:#b8902c;--banner:linear-gradient(180deg,#e7c25f,#dcb24a);--banner-ink:#3c2d0b;"
    "--chip:rgba(0,0,0,0.06);--live:#4e885c;"
)


# ---------------------------------------------------------------------------
# CSS — "Karta Watch". The two design themes as custom properties; dark default,
# light via ?theme=light. Both via data-theme AND prefers-color-scheme. Sharp
# corners, terminal feel, system font stack (NO remote fonts). The component
# styles that used to be inline Python strings now live here as real classes —
# this is where the maintenance complexity drops.
# ---------------------------------------------------------------------------

_CSS = ("""
:root{__DARK__}
@media (prefers-color-scheme: light){ :root{__LIGHT__} }
:root[data-theme="dark"]{__DARK__}
:root[data-theme="light"]{__LIGHT__}

*{box-sizing:border-box}
html,body{margin:0}
:root{
  --mono:ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Menlo, Consolas, monospace;
  --sans:system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
body{
  background:var(--bg); color:var(--ink);
  font-family:var(--sans); font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
  padding:28px 24px 40px;
  display:flex; flex-direction:column; align-items:center;
  min-height:100vh;
}
.mono{ font-family:var(--mono); }
.wrap{ width:100%; max-width:1020px; display:flex; flex-direction:column; gap:16px; }
main{ display:flex; flex-direction:column; gap:16px; }

@keyframes karta-spin{ to{ transform:rotate(360deg); } }
@keyframes karta-fade{ from{ opacity:0; transform:translateY(4px); } to{ opacity:1; transform:none; } }

/* header */
.top{ display:flex; justify-content:space-between; align-items:center; gap:16px; }
.brand{ display:flex; align-items:center; gap:13px; min-width:0; }
.brand__mascot{ width:40px; height:40px; border-radius:0; flex:none; display:block; }
.brand__txt{ min-width:0; }
.brand__row{ display:flex; align-items:center; gap:10px; }
.brand__word{ font-family:var(--mono); font-weight:700; font-size:21px; letter-spacing:-0.5px; }
.brand__branch{
  display:flex; align-items:center; gap:5px;
  font-family:var(--mono); font-size:12px;
  padding:3px 9px 3px 7px; border-radius:0;
  background:var(--chip); color:var(--mut);
}
.brand__sub{ font-size:12px; color:var(--mut); margin-top:2px; }
.live{
  display:flex; align-items:center; gap:8px; flex:none;
  color:var(--mut); font-family:var(--sans); font-size:12px; padding:4px;
}
.live--recon{ color:var(--amber); }
.timer{
  width:18px; height:18px; border-radius:0; border:1.5px solid var(--line);
  position:relative; overflow:hidden; flex:none; display:block;
}
.timer__sweep{
  position:absolute; inset:-1px; border-radius:0; display:block;
  background:conic-gradient(from 0deg, var(--live) 0deg, var(--live) 35deg, transparent 150deg, transparent 360deg);
  animation:karta-spin 2.6s linear infinite;
}
.timer--recon .timer__sweep{
  background:conic-gradient(from 0deg, var(--amber) 0deg, var(--amber) 35deg, transparent 150deg, transparent 360deg);
  animation:karta-spin .85s linear infinite;
}
.timer__hole{ position:absolute; inset:4px; border-radius:0; background:var(--bg); display:block; }

/* header right cluster: hide-done + theme toggles, then the live indicator */
.hdr-right{ display:flex; align-items:center; gap:10px; flex:none; }
.hctl{
  display:inline-flex; align-items:center; gap:6px;
  font-family:var(--mono); font-size:12px; line-height:1;
  padding:6px 9px; border-radius:0; border:1px solid var(--line);
  background:transparent; color:var(--mut); cursor:pointer;
  transition:color .2s, border-color .2s, background .2s;
}
.hctl:hover{ color:var(--ink); border-color:var(--mut); }
.hctl--icon{ padding:6px; }
.hctl--on{
  border-color:var(--amber); background:var(--amber-soft); color:var(--amber);
}
.hctl--on:hover{ color:var(--amber); border-color:var(--amber); }
.hctl__l{ display:inline-block; }

/* hero — YOU RUN NEXT */
.hero{ background:var(--banner); color:var(--banner-ink); border-radius:0; padding:15px 20px; }
.hero__row{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.hero__glyph{
  display:flex; align-items:center; justify-content:center;
  width:22px; height:22px; border-radius:0; background:rgba(0,0,0,0.16); flex:none;
}
.hero__label{ font-family:var(--mono); font-weight:700; font-size:11px; letter-spacing:2px; }
.hero__cmd{
  font-family:var(--mono); font-weight:600; font-size:14px;
  padding:6px 12px; border-radius:0; background:rgba(0,0,0,0.16);
}
.hero__dollar{ opacity:.5; }
.hero__copy{
  display:flex; align-items:center; gap:6px;
  font-family:var(--mono); font-size:12px; padding:6px 11px;
  border-radius:0; border:none; cursor:pointer;
  background:rgba(255,255,255,0.32); color:var(--banner-ink);
}
.hero__copy:hover{ background:rgba(255,255,255,0.45); }
.hero__aside{ font-size:11.5px; opacity:.7; }
.hero__sub{ font-size:12.5px; margin-top:9px; opacity:.82; }

/* panels */
.panel{ background:var(--panel); border:1px solid var(--line); border-radius:0; padding:20px 22px 22px; }
.panel--wi{ padding-bottom:18px; }
.panel__head{ display:flex; align-items:center; gap:9px; margin-bottom:3px; }
.panel__hicon{ display:flex; }
.panel__title{ font-weight:600; font-size:15px; }
.panel__meta{ font-size:12px; color:var(--mut); }
.panel__chip{
  margin-left:auto; font-size:12px; padding:4px 11px;
  background:var(--chip); color:var(--mut);
}
.panel__lede{ font-size:12.5px; color:var(--mut); margin:0 0 20px; }
.panel__lede--wi{ margin-bottom:18px; line-height:1.65; }
.panel__lede b{ color:var(--ink); font-weight:600; }

/* binders panel: card column + star endpoint */
.bgrid{ display:flex; align-items:stretch; }
.bcol{ flex:1; display:flex; flex-direction:column; gap:11px; min-width:0; }
.bhidden{ font-family:var(--mono); font-size:11px; color:var(--mut); margin:0; opacity:.85; }
.brow{ display:flex; align-items:center; gap:11px; }
.brow__ord{
  flex:none; width:14px; text-align:center;
  font-family:var(--mono); font-size:11px; color:var(--mut);
}
.bcard{
  flex:1; min-width:0; border:1px solid var(--line); padding:11px 13px;
  background:var(--panel-2); cursor:pointer; text-decoration:none; color:inherit;
  transition:background .2s, border-color .2s; display:block;
}
.bcard:hover{ border-color:var(--mut); }
.bcard--sel{ border-color:var(--amber); background:var(--amber-soft); }
.bcard__top{ display:flex; align-items:center; gap:9px; }
.bcard__icon{ display:flex; flex:none; }
.bcard__slug{
  font-family:var(--mono); font-weight:600; font-size:13px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; min-width:0;
}
.bcard__state{ display:flex; flex:none; }
.bcard__stage{ font-size:10.5px; color:var(--mut); flex:none; }
.bcard__bot{ display:flex; align-items:center; gap:9px; margin-top:9px; }
.bcard__bar{
  flex:1; height:6px; background:var(--panel-2); overflow:hidden;
  border:1px solid var(--line); display:block;
}
.bcard__fill{ display:block; height:100%; transition:width .5s ease; }
.bcard__count{ font-size:11px; color:var(--mut); flex:none; }
.brow__conn{ flex:none; width:26px; height:2px; background:var(--mut); opacity:.35; }
.bstar{ flex:none; width:104px; position:relative; display:flex; align-items:center; justify-content:center; }
.bstar__line{ position:absolute; left:0; top:16px; bottom:16px; width:2px; background:var(--mut); opacity:.35; }
.bstar__node{
  position:relative; z-index:1; display:flex; flex-direction:column;
  align-items:center; gap:5px; background:var(--panel); padding:10px 6px;
}
.bstar__icon{ display:flex; }
.bstar__name{ font-family:var(--mono); font-size:12px; font-weight:600; }
.bstar__sub{
  font-size:9.5px; color:var(--mut); text-transform:uppercase;
  letter-spacing:0.5px; text-align:center; line-height:1.4;
}

/* work items panel */
.branch-chip{
  display:inline-flex; align-items:center; gap:5px;
  font-family:var(--mono); font-weight:600; color:var(--ink);
  padding:2px 8px; background:var(--steel-soft); border:1px solid var(--line);
  vertical-align:middle;
}
.branch-chip .mono{ font-weight:600; }
.wgroups{ display:flex; flex-direction:column; gap:18px; }
.wgroup__head{ display:flex; align-items:center; gap:8px; margin-bottom:11px; }
.wgroup__icon{ display:flex; }
.wgroup__label{ font-weight:600; font-size:13px; }
.wgroup__sub{ font-size:11.5px; color:var(--mut); }
.wgroup__count{ font-size:11.5px; color:var(--mut); margin-left:auto; }
.wgrid{ display:grid; grid-template-columns:repeat(auto-fill, minmax(290px, 1fr)); gap:11px; }

.wi{
  display:flex; border:1px solid var(--line); background:var(--panel-2);
  cursor:pointer; min-width:0;
}
.wi__rail{
  flex:none; width:46px; align-self:stretch;
  display:flex; align-items:center; justify-content:center;
  border-right:1px solid var(--line);
}
.wi__body{ flex:1; min-width:0; padding:12px 14px; display:block; }
.wi__head{ display:flex; align-items:baseline; gap:10px; }
.wi__id{ font-family:var(--mono); font-weight:600; font-size:13.5px; }
.wi__word{
  margin-left:auto; font-family:var(--mono); font-size:10px; font-weight:600;
  letter-spacing:1.5px; flex:none;
}
.wi__desc{ display:block; font-size:12.5px; color:var(--ink); opacity:.78; margin-top:4px; }
.wi__oracle{ display:flex; align-items:center; gap:6px; margin-top:9px; color:var(--mut); flex-wrap:wrap; }
.wi__oracle-i{ display:flex; }
.wi__oracle-l{ font-size:11.5px; }
.wi__dep{ display:flex; align-items:center; gap:4px; font-size:11px; color:var(--block); margin-left:4px; }
.wi__detail{
  display:block; margin-top:11px; padding-top:10px; border-top:1px solid var(--line);
  animation:karta-fade .2s ease;
}
.wi__assert{ display:block; font-size:11.5px; color:var(--ink); opacity:.82; }
.wi__assert-k{ color:var(--mut); }
.wi__cmd{
  display:block; font-family:var(--mono); font-size:11px; color:var(--mut);
  margin-top:7px; padding:6px 9px; background:var(--bg);
}
.wempty{ font-size:12.5px; color:var(--mut); margin:0; }

/* legend */
.legend{
  display:flex; flex-wrap:wrap; gap:7px 16px; margin-top:20px;
  padding-top:14px; border-top:1px solid var(--line);
}
.leg{ display:flex; align-items:center; gap:6px; font-size:11.5px; color:var(--mut); }
.leg__i{ display:flex; }

/* empty state */
.empty{ text-align:center; }
.empty__mascot{ width:80px; height:80px; opacity:.85; margin-bottom:6px; }
.empty__title{ font-weight:600; font-size:15px; margin-bottom:6px; }
.empty__hint{ font-size:12.5px; color:var(--mut); margin:0 auto; max-width:46ch; }

/* footer */
.foot{ text-align:center; font-size:12.5px; color:var(--mut); padding-top:4px; }

@media (prefers-reduced-motion: reduce){
  .timer__sweep, .karta-spin{ animation:none !important; }
}
@media (max-width:640px){
  .wgrid{ grid-template-columns:1fr; }
  .bstar{ width:80px; }
}
"""
        .replace("__DARK__", _DARK_VARS)
        .replace("__LIGHT__", _LIGHT_VARS)
        .strip())


# ---------------------------------------------------------------------------
# The Vue 3 app. Uses the vendored global build (Vue.createApp), an in-document
# template (no build step). Mounts from the inlined initial state for a correct
# first paint, then — only off file:// — polls /state.json every 2.6s as the live
# mirror. All interaction (binder selection, expand, copy, theme) is client state,
# so none of it needs a server round-trip. This is the complexity win: the design
# is one declarative template instead of ~500 lines of Python string assembly.
# ---------------------------------------------------------------------------

_APP_JS = """
const { createApp } = Vue;

// icon path data + state metadata, handed over from Python verbatim.
const ICONS = __ICONS__;
const STATE_META = __STATE__;
const BINDER_KIND = __BINDER_KIND__;
const STAGE_LABEL = __STAGE_LABEL__;
const ORACLE_ICON = __ORACLE_ICON__;
const GROUP_DEFS = __GROUP_DEFS__;
const LEGEND_KEYS = __LEGEND_KEYS__;
const POLL_MS = 2600;

// A render helper for inline <svg> icons, matching the design's icon() factory.
const Icon = {
  name: 'KartaIcon',
  props: {
    name: { type: String, required: true },
    size: { type: Number, default: 16 },
    color: { type: String, default: 'currentColor' },
    fill: { type: String, default: 'none' },
    sw: { type: Number, default: 2 },
    spin: { type: Boolean, default: false },
  },
  render() {
    const defs = ICONS[this.name] || [];
    const kids = defs.map((d, i) =>
      Vue.h(d[0], Object.assign({ key: i }, d[1]))
    );
    return Vue.h('svg', {
      width: this.size, height: this.size, viewBox: '0 0 24 24',
      fill: this.fill, stroke: this.color, 'stroke-width': this.sw,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      class: this.spin ? 'karta-spin' : null,
      style: 'display:block;' + (this.spin ? 'animation:karta-spin 2.6s linear infinite;' : ''),
    }, kids);
  },
};

function metaFor(status) { return STATE_META[status] || STATE_META.ready; }
function doneCount(b) { return b.items.done; }

const app = createApp({
  components: { Icon },
  data() {
    return {
      state: window.__KARTA_STATE__ || { binders: [], repo: { default_branch: 'main' }, next_action: {} },
      viewSlug: null,
      expanded: {},      // work-item id -> bool
      copied: false,
      reconnecting: false,
      hideDone: localStorage.getItem('karta-hide-done') === '1',
      theme: localStorage.getItem('karta-theme')
        || window.__KARTA_THEME__ || 'dark',
      _copyTimer: null,
      _pollTimer: null,
    };
  },
  computed: {
    binders() { return this.state.binders || []; },
    hasBinders() { return this.binders.length > 0; },
    activeBinder() { return this.binders.find(b => b.status === 'in_flight') || null; },
    // the integration-branch chip / header slug
    activeSlug() {
      return this.activeBinder ? this.activeBinder.slug
        : (this.state.repo && this.state.repo.default_branch) || 'main';
    },
    // the binder whose work items show: explicit selection, else in_flight, else first
    viewedSlug() {
      if (!this.binders.length) return '';
      const slugs = this.binders.map(b => b.slug);
      if (this.viewSlug && slugs.includes(this.viewSlug)) return this.viewSlug;
      const active = this.activeBinder;
      return active ? active.slug : this.binders[0].slug;
    },
    viewedBinder() {
      return this.binders.find(b => b.slug === this.viewedSlug) || this.binders[0] || null;
    },
    nextAction() { return this.state.next_action || {}; },
    binderCards() {
      return this.binders.map((b, i) => {
        const kind = BINDER_KIND[b.status] || 'ready';
        const m = metaFor(kind);
        const total = b.items.total;
        const done = doneCount(b);
        return {
          slug: b.slug, ordinal: i + 1, status: b.status, color: m.color, icon: m.icon,
          stateIcon: m.icon, spin: kind === 'building',
          stage: STAGE_LABEL[b.status] || 'not started',
          pct: total ? Math.round(done / total * 100) : 0,
          countLabel: done + '/' + total + ' items',
          selected: b.slug === this.viewedSlug,
        };
      });
    },
    // the cards actually rendered in the column: drop merged ones when hiding
    // completed binders. Ordinals stay tied to full-sequence position (no renumber).
    visibleBinderCards() {
      if (!this.hideDone) return this.binderCards;
      return this.binderCards.filter(c => c.status !== 'merged');
    },
    // how many merged binders exist (for the collapsed-hint count).
    mergedBinderCount() {
      return this.binderCards.filter(c => c.status === 'merged').length;
    },
    // how many cards are actually hidden right now (0 unless hiding is on).
    hiddenBinderCount() {
      return this.hideDone ? this.mergedBinderCount : 0;
    },
    groups() {
      const vb = this.viewedBinder;
      const items = vb ? vb.items.detail : [];
      return GROUP_DEFS.map(g => {
        const members = items.filter(d => d.status === g.key);
        const m = metaFor(g.key);
        return {
          key: g.key, label: g.label, sub: g.sub,
          color: m.color, icon: m.icon, spin: g.key === 'building',
          count: members.length + (members.length === 1 ? ' item' : ' items'),
          items: members,
        };
      }).filter(g => g.items.length > 0);
    },
    legend() {
      return LEGEND_KEYS.map(k => {
        const m = metaFor(k);
        return { key: k, label: m.label, color: m.color, icon: m.icon };
      });
    },
  },
  methods: {
    metaFor,
    railStyle(d) {
      const m = metaFor(d.status);
      return 'background:' + m.soft + ';color:' + m.color + ';';
    },
    oracleIconName(d) { return ORACLE_ICON[d.oracle] || 'unit'; },
    oracleLabel(d) { return (d.oracle || 'unit') + ' check'; },
    blockedDep(d) {
      const arr = d.blocked_by || d.deps || [];
      return arr.length ? arr[0] : '';
    },
    isExpanded(d) { return !!this.expanded[d.id]; },
    toggle(d) { this.expanded = Object.assign({}, this.expanded, { [d.id]: !this.expanded[d.id] }); },
    selectBinder(slug) { this.viewSlug = slug; },
    toggleHideDone() {
      this.hideDone = !this.hideDone;
      try { localStorage.setItem('karta-hide-done', this.hideDone ? '1' : '0'); } catch (e) {}
    },
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = this.theme;
      try { localStorage.setItem('karta-theme', this.theme); } catch (e) {}
    },
    copyCmd() {
      const cmd = this.nextAction.command || '';
      const done = () => {
        this.copied = true;
        clearTimeout(this._copyTimer);
        this._copyTimer = setTimeout(() => { this.copied = false; }, 1300);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cmd).then(done, () => {});
      } else {
        try {
          const ta = document.createElement('textarea');
          ta.value = cmd; document.body.appendChild(ta);
          ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
          done();
        } catch (e) {}
      }
    },
    poll() {
      fetch('/state.json', { cache: 'no-store' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(s => { this.state = s; this.reconnecting = false; })
        .catch(() => { this.reconnecting = true; });
    },
  },
  mounted() {
    // Apply the resolved theme (a stored preference overrides the server default
    // baked into data-theme on reload). CSS keys off :root[data-theme=...].
    document.documentElement.dataset.theme = this.theme;
    // The live mirror: only poll when actually served over http(s). A file://
    // snapshot keeps the inlined first-paint state and never tries to fetch.
    if (location.protocol !== 'file:') {
      this._pollTimer = setInterval(() => this.poll(), POLL_MS);
    }
  },
  beforeUnmount() {
    clearInterval(this._pollTimer);
    clearTimeout(this._copyTimer);
  },
  template: `
<div class="wrap">
  <header class="top">
    <div class="brand">
      <img class="brand__mascot" src="/assets/mascot.png" alt="karta mascot" width="40" height="40">
      <div class="brand__txt">
        <div class="brand__row">
          <span class="brand__word">karta</span>
          <span class="brand__branch"><icon name="branch" :size="12" color="var(--mut)" />{{ activeSlug }}</span>
        </div>
        <div class="brand__sub">watching a binder sequence build · read-only mirror of git</div>
      </div>
    </div>
    <div class="hdr-right">
      <button type="button" class="hctl" :class="{ 'hctl--on': hideDone }"
        @click="toggleHideDone"
        :title="hideDone ? 'show all binders' : 'hide completed binders'"
        :aria-pressed="hideDone ? 'true' : 'false'">
        <icon :name="hideDone ? 'eye-off' : 'eye'" :size="14" color="currentColor" />
        <span class="hctl__l">{{ hideDone ? 'show all' : 'hide done' }}</span>
      </button>
      <button type="button" class="hctl hctl--icon"
        @click="toggleTheme"
        :title="theme === 'dark' ? 'switch to light mode' : 'switch to dark mode'"
        aria-label="toggle theme">
        <icon :name="theme === 'dark' ? 'sun' : 'moon'" :size="14" color="currentColor" />
      </button>
      <div class="live" :class="{ 'live--recon': reconnecting }">
        <span class="timer" :class="{ 'timer--recon': reconnecting }" aria-hidden="true">
          <span class="timer__sweep"></span>
          <span class="timer__hole"></span>
        </span>
        <span class="live__label">{{ reconnecting ? 'reconnecting…' : 'live' }}</span>
      </div>
    </div>
  </header>

  <main>
    <template v-if="hasBinders">
      <!-- hero: YOU RUN NEXT -->
      <section class="hero" aria-label="next action">
        <div class="hero__row">
          <span class="hero__glyph" aria-hidden="true"><icon name="play" :size="11" color="var(--banner-ink)" fill="var(--banner-ink)" /></span>
          <span class="hero__label">YOU RUN NEXT</span>
          <template v-if="nextAction.command">
            <span class="hero__cmd"><span class="hero__dollar">$ </span>{{ nextAction.command }}</span>
            <button type="button" class="hero__copy" @click="copyCmd" aria-label="copy command">
              <icon name="copy" :size="13" color="var(--banner-ink)" />
              <span class="hero__copy-l">{{ copied ? 'copied' : 'copy' }}</span>
            </button>
            <span class="hero__aside">run this in your terminal — karta only watches</span>
          </template>
          <span v-else class="hero__aside">nothing to run — karta only watches</span>
        </div>
        <div class="hero__sub">{{ nextAction.human }}</div>
      </section>

      <!-- binders: card column ending at the star -->
      <section class="panel" aria-label="binders">
        <div class="panel__head">
          <span class="panel__hicon" style="color:var(--amber)"><icon name="binder" :size="17" color="var(--amber)" /></span>
          <span class="panel__title">Binders</span>
          <span class="panel__meta">{{ binders.length }} · each merges to main on its own</span>
        </div>
        <p class="panel__lede">A <b>binder</b> is one self-sufficient stage. Each merges into
          <span class="mono">main</span> independently — the numbering is karta's
          <b>suggested</b> order, not a dependency.</p>
        <div class="bgrid">
          <div class="bcol">
            <div class="brow" v-for="c in visibleBinderCards" :key="c.slug">
              <span class="brow__ord">{{ c.ordinal }}</span>
              <a class="bcard" :class="{ 'bcard--sel': c.selected }" href="#" @click.prevent="selectBinder(c.slug)">
                <div class="bcard__top">
                  <span class="bcard__icon" :style="{ color: c.color }"><icon name="binder" :size="17" :color="c.color" /></span>
                  <span class="bcard__slug">{{ c.slug }}</span>
                  <span class="bcard__state" :style="{ color: c.color }"><icon :name="c.stateIcon" :size="15" :color="c.color" :spin="c.spin" /></span>
                  <span class="bcard__stage">{{ c.stage }}</span>
                </div>
                <div class="bcard__bot">
                  <span class="bcard__bar"><span class="bcard__fill" :style="{ width: c.pct + '%', background: c.color }"></span></span>
                  <span class="bcard__count">{{ c.countLabel }}</span>
                </div>
              </a>
              <span class="brow__conn" aria-hidden="true"></span>
            </div>
            <p class="bhidden" v-if="hiddenBinderCount > 0">+ {{ hiddenBinderCount }} completed binder{{ hiddenBinderCount === 1 ? '' : 's' }} hidden</p>
          </div>
          <div class="bstar">
            <span class="bstar__line" aria-hidden="true"></span>
            <div class="bstar__node">
              <span class="bstar__icon"><icon name="star" :size="20" color="var(--star)" fill="var(--star)" /></span>
              <span class="bstar__name">main</span>
              <span class="bstar__sub">integration<br>branch</span>
            </div>
          </div>
        </div>
      </section>

      <!-- work items: grouped by state -->
      <section class="panel panel--wi" aria-label="work items">
        <div class="panel__head">
          <span class="panel__hicon" style="color:var(--steel)"><icon name="branch" :size="16" color="var(--steel)" /></span>
          <span class="panel__title">Work items</span>
          <span class="panel__chip" v-if="viewedBinder">{{ doneCountOf(viewedBinder) }}/{{ viewedBinder.items.total }} done</span>
        </div>
        <p class="panel__lede panel__lede--wi">Each <b>work item</b> builds in its own git
          worktree, passes its check, then integrates into
          <span class="branch-chip"><icon name="branch" :size="12" color="var(--steel)" /><span class="mono">{{ viewedSlug }}</span></span>
          — the binder's integration branch, which then merges into <span class="mono">main</span>.</p>

        <div class="wgroups">
          <div class="wgroup" v-for="g in groups" :key="g.key">
            <div class="wgroup__head">
              <span class="wgroup__icon" :style="{ color: g.color }"><icon :name="g.icon" :size="16" :color="g.color" :spin="g.spin" /></span>
              <span class="wgroup__label">{{ g.label }}</span>
              <span class="wgroup__sub">{{ g.sub }}</span>
              <span class="wgroup__count">{{ g.count }}</span>
            </div>
            <div class="wgrid">
              <div class="wi" v-for="d in g.items" :key="d.id" @click="toggle(d)">
                <span class="wi__rail" :style="railStyle(d)">
                  <icon :name="metaFor(d.status).icon" :size="18" :color="metaFor(d.status).color" :spin="d.status === 'building'" />
                </span>
                <span class="wi__body">
                  <span class="wi__head">
                    <span class="wi__id">{{ d.id }}</span>
                    <span class="wi__word" :style="{ color: metaFor(d.status).color }">{{ metaFor(d.status).label.toUpperCase() }}</span>
                  </span>
                  <span class="wi__desc">{{ d.desc || d.id }}</span>
                  <span class="wi__oracle">
                    <span class="wi__oracle-i"><icon :name="oracleIconName(d)" :size="14" color="var(--mut)" /></span>
                    <span class="wi__oracle-l">{{ oracleLabel(d) }}</span>
                    <span class="wi__dep" v-if="d.status === 'blocked'">
                      <icon name="blocked" :size="12" color="var(--block)" /><span>waiting on {{ blockedDep(d) }}</span>
                    </span>
                  </span>
                  <span class="wi__detail" v-if="isExpanded(d) && (d.assert || d.cmd)">
                    <span class="wi__assert" v-if="d.assert"><span class="wi__assert-k">must pass — </span>{{ d.assert }}</span>
                    <span class="wi__cmd" v-if="d.cmd">$ {{ d.cmd }}</span>
                  </span>
                </span>
              </div>
            </div>
          </div>
          <p class="wempty" v-if="!groups.length">no work items in this binder.</p>
        </div>

        <div class="legend">
          <span class="leg" v-for="L in legend" :key="L.key">
            <span class="leg__i" :style="{ color: L.color }"><icon :name="L.icon" :size="14" :color="L.color" /></span>{{ L.label }}
          </span>
        </div>
      </section>
    </template>

    <!-- empty state -->
    <section class="panel empty" aria-label="no binders" v-else>
      <img class="empty__mascot" src="/assets/mascot.png" alt="" width="80" height="80">
      <div class="empty__title">no binders planned yet</div>
      <p class="empty__hint">add a binder under <span class="mono">.karta/binders/</span>
        (try <span class="mono">karta-plan</span>) and the sequence will chart itself here.</p>
    </section>
  </main>

  <footer class="foot">karta · derived fresh from git every poll · read-only</footer>
</div>
`,
});

// expose a tiny helper used in-template for the done chip
app.config.globalProperties.doneCountOf = doneCount;

app.mount('#app');
""".strip()


def _theme_attr(theme: str | None) -> str:
    return theme if theme in ("light", "dark") else "dark"


def _build_app_js(state: dict) -> str:
    """Substitute the Python-owned data tables into the Vue app source."""
    return (
        _APP_JS
        .replace("__ICONS__", json.dumps(_ICONS, separators=(",", ":")))
        .replace("__STATE__", json.dumps(_STATE, separators=(",", ":")))
        .replace("__BINDER_KIND__", json.dumps(_BINDER_KIND, separators=(",", ":")))
        .replace("__STAGE_LABEL__", json.dumps(_STAGE_LABEL, separators=(",", ":")))
        .replace("__ORACLE_ICON__", json.dumps(_ORACLE_ICON, separators=(",", ":")))
        .replace("__GROUP_DEFS__", json.dumps(_GROUP_DEFS, separators=(",", ":")))
        .replace("__LEGEND_KEYS__", json.dumps(_LEGEND_KEYS, separators=(",", ":")))
    )


def render_app_html(state: dict, theme: str | None = None) -> str:
    """One self-contained document: the theme CSS, the inlined initial state (for a
    correct first paint and file:// snapshots), the vendored Vue, and the app. No
    external URLs — only same-origin /assets and /state.json."""
    theme_attr = _theme_attr(theme)
    # `</script>` inside a JSON string would close the inline <script>; escape it.
    state_json = json.dumps(state, separators=(",", ":")).replace("</", "<\\/")
    app_js = _build_app_js(state)
    return (
        "<!doctype html>"
        f'<html lang="en" data-theme="{theme_attr}">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Karta Watch</title>"
        '<link rel="icon" type="image/png" href="/assets/mascot.png">'
        f"<style>{_CSS}</style>"
        "</head>"
        "<body>"
        '<div id="app"></div>'
        "<script>"
        f"window.__KARTA_STATE__ = {state_json};"
        f'window.__KARTA_THEME__ = "{theme_attr}";'
        "</script>"
        '<script src="/assets/vendor/vue.global.prod.js"></script>'
        f"<script>{app_js}</script>"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Asset content types
# ---------------------------------------------------------------------------


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".js":
        return "text/javascript"
    return "application/octet-stream"


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    server_version = "karta-status/2.0"
    required_key: str | None = None  # set on the class at boot

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, ctype: str, *, cache: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", "public, max-age=86400")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _text(self, code: int, text: str, ctype: str) -> None:
        self._send(code, text.encode("utf-8"), f"{ctype}; charset=utf-8")

    def _key_ok(self, qs: dict) -> bool:
        if not self.required_key:
            return True
        return qs.get("key", [None])[0] == self.required_key

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        path = parts.path
        qs = parse_qs(parts.query)

        # assets are public (the favicon/mascot/vendor JS must load even pre-auth).
        if path.startswith("/assets/"):
            return self._serve_asset(path)

        if not self._key_ok(qs):
            return self._text(403, "forbidden — add ?key=<token>", "text/plain")

        theme = qs.get("theme", [None])[0]
        theme = theme if theme in ("light", "dark") else None

        if path == "/state.json":
            return self._text(200, json.dumps(current_state()), "application/json")

        if path in ("/", "/index.html"):
            return self._text(200, render_app_html(current_state(), theme), "text/html")

        return self._text(404, "not found", "text/plain")

    def _serve_asset(self, path: str) -> None:
        # resolve relative to the assets dir; allow one nested level (vendor/<f>).
        rel = path[len("/assets/"):]
        target = (ASSETS_DIR / rel).resolve()
        # confine to the assets dir
        if (target != ASSETS_DIR and ASSETS_DIR not in target.parents) or not target.is_file():
            return self._text(404, "not found", "text/plain")
        try:
            data = target.read_bytes()
        except OSError:
            return self._text(404, "not found", "text/plain")
        self._send(200, data, _content_type(target), cache=True)


def _run_self_test() -> int:
    """Render a fixture through the real engine+enrich pipeline (no repo needed) and
    assert the page's invariants: it renders, inlines its state, vendors Vue
    same-origin, and ships NO external URLs (self-contained)."""
    def _u(assertion, otype="unit"):
        return {"type": otype, "assertions": [assertion], "command": "npm run lint && npm test"}
    binders = [
        {"slug": "s-new", "motivation": "x", "scope": {"included": ["x"]},
         "work_items": [{"id": "a", "title": "A item", "oracle": _u("a is asserted")}]},
        {"slug": "s-edit", "after": ["s-new"], "motivation": "x", "scope": {"included": ["x"]},
         "work_items": [
             {"id": "api", "title": "Wire the API", "oracle": _u("editing sends the request", "integration")},
             {"id": "doc", "title": "Document it", "depends_on": ["api"], "oracle": _u("usage is documented")}]},
        {"slug": "s-del", "after": ["s-edit"], "motivation": "x", "scope": {"included": ["x"]},
         "work_items": [{"id": "r", "title": "Remove legacy", "oracle": _u("legacy is gone")}]},
    ]
    facts = {"default_branch": "main", "binders": {
        "s-new": {"items": {"a": {"done": True, "done_in_default": True}}},
        "s-edit": {"integration_exists": True,
                   "items": {"api": {"done": True, "done_in_default": False}, "doc": {}}},
        "s-del": {"items": {"r": {}}},
    }}
    state = _enrich(karta_next.derive_state(binders, facts), binders)

    checks: list[tuple[str, bool]] = []
    try:
        json.dumps(state)
        checks.append(("state is JSON-serializable (served as /state.json)", True))
    except TypeError:
        checks.append(("state is JSON-serializable (served as /state.json)", False))
    for theme in ("dark", "light"):
        h = render_app_html(state, theme)
        checks += [
            (f"{theme}: renders a real document", len(h) > 8000),
            (f"{theme}: NO external URLs (self-contained)", "http://" not in h and "https://" not in h),
            (f"{theme}: inlines first-paint state", "window.__KARTA_STATE__" in h),
            (f"{theme}: vendors Vue same-origin", "/assets/vendor/vue.global.prod.js" in h),
            (f"{theme}: carries the binder + next action", "s-edit" in h and "karta-deliver" in h),
            (f"{theme}: carries joined oracle detail", "integration" in h and "documented" in h),
        ]
    failures = sum(1 for _, ok in checks if not ok)
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="karta-status live poll server")
    ap.add_argument("--port", type=int, default=8765, help="port to bind (default 8765)")
    ap.add_argument("--key", type=str, default=None, help="if set, require ?key=TOKEN")
    ap.add_argument("--root", type=str, default=None,
                    help="repo root to serve (chdir here so .karta/binders + git resolve); default CWD")
    ap.add_argument("--self-test", action="store_true", help="render fixtures, check invariants, exit 0/1")
    args = ap.parse_args()

    if args.self_test:
        return _run_self_test()

    if args.root:
        import os
        os.chdir(args.root)

    _Handler.required_key = args.key
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"karta-status serving {url}")
    print(f"  state:    {url}state.json")
    if args.key:
        print(f"  guarded:  append ?key={args.key}")
    print("  (Ctrl-C to stop; this is read-only and derives from git every request)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nkarta-status stopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
