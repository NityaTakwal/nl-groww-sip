"""Lean-Month Planner on Streamlit.  Run from 06_mvp/:  ../.venv/bin/streamlit run streamlit_app.py

Renders the same phone UI as the FastAPI app (app/static) inside a Streamlit component.
The page's fetch("/api/...") calls are bridged to Python, which calls the same handlers as app/main.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # shared `common` package
sys.path.insert(0, str(HERE))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from app import main  # noqa: E402

STATIC = HERE / "app" / "static"
BUILD = HERE / ".st_component"

# Replaces window.fetch for /api/* with a round trip through Streamlit's component messages.
BRIDGE = """<script>
(function () {
  const pending = {}, queue = [];
  let seq = 0, ready = false, scenarios = null;
  const send = (type, data) => window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, data), "*");
  // body, not documentElement: the latter never shrinks below the iframe's own height, so it ratchets up
  const setHeight = () => send("streamlit:setFrameHeight", { height: document.body.scrollHeight });
  window.addEventListener("message", (e) => {
    const d = e.data;
    if (!d || d.type !== "streamlit:render") return;
    const args = d.args || {};
    if (!ready) {
      ready = true; scenarios = args.scenarios;
      queue.splice(0).forEach((f) => f());
    }
    const res = args.response;
    if (res && pending[res.id]) { pending[res.id](res.body); delete pending[res.id]; }
    setHeight();
  });
  window.fetch = (url, opts) => new Promise((resolve) => {
    const reply = (body) => resolve({ json: async () => body });
    const run = () => {
      if (url === "/api/scenarios") return reply(scenarios);
      const id = Date.now() + "-" + (++seq);
      pending[id] = reply;
      send("streamlit:setComponentValue", { value: { id, path: url, body: JSON.parse(opts.body) }, dataType: "json" });
    };
    ready ? run() : queue.push(run);
  });
  new ResizeObserver(setHeight).observe(document.body);
  send("streamlit:componentReady", { apiVersion: 1 });
})();
</script>"""


def build_component() -> Path:
    """Inline style.css + app.js into one index.html so app/static stays the single source."""
    html = (STATIC / "index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="/static/style.css">',
                        f"<style>{(STATIC / 'style.css').read_text()}</style>")
    html = html.replace('<script src="/static/app.js"></script>',
                        f"{BRIDGE}\n<script>{(STATIC / 'app.js').read_text()}</script>")
    BUILD.mkdir(exist_ok=True)
    (BUILD / "index.html").write_text(html)
    return BUILD


def handle(req: dict):
    body = req.get("body") or {}
    if req["path"] == "/api/assist":
        return main.assist(main.AssistIn(**body))
    if req["path"] == "/api/action":
        return main.action(main.ActionIn(**body))
    return {"error": "unknown path"}


st.set_page_config(page_title="Lean-Month Planner · Groww SIP (MVP)", page_icon="📅", layout="wide")
st.markdown("""<style>
  header[data-testid="stHeader"], footer, #MainMenu { display: none; }
  .block-container { padding: 0 !important; max-width: 100% !important; }
  iframe { border: 0; }
</style>""", unsafe_allow_html=True)

planner = components.declare_component("lean_month_planner", path=str(build_component()))
req = planner(scenarios=main.scenarios(), response=st.session_state.get("response"), key="planner", default=None)

if req and req["id"] != st.session_state.get("handled"):
    st.session_state.handled = req["id"]
    st.session_state.response = {"id": req["id"], "body": handle(req)}
    st.rerun()
