"""
Gantt Chart Streamlit App
Two tabs: Schedule Editor | Generate Chart
Language toggle above tabs (EN/JA).
"""

import streamlit as st
import sys
import subprocess
import tempfile
import shutil
import hashlib
from pathlib import Path
from datetime import date

APP_DIR     = Path(__file__).parent
HTML_FILE   = APP_DIR / "gantt_editor.html"
CORE_PY     = APP_DIR / "gantt_core.py"
HOLIDAY_CSV = APP_DIR / "syukujitsu.csv"

st.set_page_config(
    page_title="工程計画 / Project Schedule",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
  iframe { border: none !important; }
  .sbox {
    padding: 11px 15px; border-radius: 7px; margin: 8px 0;
    font-family: monospace; font-size: 13px; line-height: 1.6;
  }
  .ok   { background:#e8f5e9; border:1px solid #66bb6a; color:#1b5e20; }
  .warn { background:#fff3e0; border:1px solid #ffa726; color:#e65100; }
  .err  { background:#ffebee; border:1px solid #ef5350; color:#b71c1c; }
</style>
""", unsafe_allow_html=True)

# ── i18n strings ───────────────────────────────────────────────────────────────
T = {
    "en": {
        "lang_btn":         "日本語",
        "tab_editor":       "📝 Schedule Editor",
        "tab_chart":        "📊 Generate Chart",
        "desc_editor":      (
            "Edit your schedule below. "
            "Click **💾 Save** inside the editor to download `schedule.txt`, "
            "then go to the **Generate Chart** tab to upload it."
        ),
        "desc_chart_s1":    "**Step 1:** Click 💾 Save inside the editor — browser downloads `schedule.txt`",
        "desc_chart_s2":    "**Step 2:** Upload it here — the chart generates automatically",
        "uploader":         "📂 Upload schedule.txt",
        "spinner":          "Generating chart...",
        "success":          "Chart generated!",
        "err_failed":       "Chart generation failed. See console output below.",
        "info_waiting":     "Upload `schedule.txt` above to generate the chart.",
        "dl_png":           "Download PNG",
        "dl_svg":           "Download SVG",
        "expander_console": "Console output",
        "expander_preview": "Preview schedule.txt",
        "paper_label":      "Paper size",
        "paper_a4":         "A4 Landscape",
        "paper_a3":         "A3 Landscape",
        "paper_free":       "Auto",
    },
    "ja": {
        "lang_btn":         "English",
        "tab_editor":       "📝 スケジュール エディタ",
        "tab_chart":        "📊 チャートを生成",
        "desc_editor":      (
            "下のエディタでスケジュールを編集してください。"
            "エディタ内の **💾 保存** をクリックすると `schedule.txt` がダウンロードされます。"
            "その後、**チャートを生成** タブでファイルをアップロードしてください。"
        ),
        "desc_chart_s1":    "**ステップ 1:** エディタで 💾 保存 をクリック — `schedule.txt` がダウンロードされます",
        "desc_chart_s2":    "**ステップ 2:** ここにアップロード — チャートが自動生成されます",
        "uploader":         "📂 schedule.txt をアップロード",
        "spinner":          "チャートを生成中...",
        "success":          "チャートが生成されました！",
        "err_failed":       "チャートの生成に失敗しました。下のコンソール出力を確認してください。",
        "info_waiting":     "上から `schedule.txt` をアップロードするとチャートが生成されます。",
        "dl_png":           "PNG をダウンロード",
        "dl_svg":           "SVG をダウンロード",
        "expander_console": "コンソール出力",
        "expander_preview": "schedule.txt のプレビュー",
        "paper_label":      "用紙サイズ",
        "paper_a4":         "A4 横",
        "paper_a3":         "A3 横",
        "paper_free":       "自動",
    },
}

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [
    ("lang",           "ja"),
    ("schedule_text",  None),
    ("png_bytes",      None),
    ("svg_bytes",      None),
    ("run_log",        ""),
    ("run_ok",         None),
    ("last_file_hash", None),
    ("paper_size",     "auto"),
]:
    if k not in st.session_state:
        st.session_state[k] = v

lang = st.session_state.lang


def t(key):
    return T[lang][key]


# ── Helpers ────────────────────────────────────────────────────────────────────
def fix_schedule(text):
    today = date.today().strftime("%Y-%m-%d")
    fixed = []
    for line in text.splitlines():
        if line.strip().lower().startswith("# startdate:"):
            val = line.split(":", 1)[-1].strip()
            if not val or val.lower() == "none":
                line = "# startdate: " + today
        fixed.append(line)
    return "\n".join(fixed)


def run_chart(schedule_text, paper_size="auto"):
    schedule_text = fix_schedule(schedule_text)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "schedule.txt").write_text(schedule_text, encoding="utf-8")
        if HOLIDAY_CSV.exists():
            shutil.copy(HOLIDAY_CSV, tmp / "syukujitsu.csv")

        cmd = [sys.executable, str(CORE_PY), str(tmp / "schedule.txt")]
        if paper_size in ("A4", "A3"):
            cmd.append(f"--paper={paper_size}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(tmp),
        )

        log = result.stdout
        if result.stderr.strip():
            log = log + "\n" + result.stderr
        st.session_state.run_log = log

        png_path = tmp / "gantt_chart.png"
        svg_path = tmp / "gantt_chart.svg"

        if result.returncode == 0 and png_path.exists():
            st.session_state.png_bytes = png_path.read_bytes()
            st.session_state.svg_bytes = svg_path.read_bytes() if svg_path.exists() else None
            st.session_state.run_ok    = True
        else:
            st.session_state.run_ok = False


# ── Header: title + language toggle ───────────────────────────────────────────
col_title, col_btn = st.columns([5, 1], vertical_alignment="bottom")
with col_title:
    st.markdown("## " + ("工程計画 / Project Schedule" if lang == "ja" else "Project Schedule / 工程計画"))
with col_btn:
    st.markdown("<div style='margin-top:32px'></div>", unsafe_allow_html=True)
    if st.button(t("lang_btn"), use_container_width=True):
        st.session_state.lang = "ja" if lang == "en" else "en"
        st.rerun()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs([t("tab_editor"), t("tab_chart")])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — SCHEDULE EDITOR
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(t("desc_editor"))
    html_src = HTML_FILE.read_text(encoding="utf-8")
    st.components.v1.html(html_src, height=820, scrolling=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — UPLOAD & GENERATE CHART
#  (uploader AND results are both here so they render in the same pass)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(t("desc_chart_s1") + "  \n" + t("desc_chart_s2"))

    # Paper size selector
    _paper_options = {"auto": t("paper_free"), "A4": t("paper_a4"), "A3": t("paper_a3")}
    _paper_keys    = list(_paper_options.keys())
    _paper_labels  = list(_paper_options.values())
    _paper_idx     = _paper_keys.index(st.session_state.paper_size)
    _paper_choice  = st.radio(t("paper_label"), _paper_labels, index=_paper_idx, horizontal=True)
    st.session_state.paper_size = _paper_keys[_paper_labels.index(_paper_choice)]

    uploaded = st.file_uploader(t("uploader"), type=["txt"])

    if uploaded is not None:
        raw   = uploaded.read()
        fhash = hashlib.md5(raw).hexdigest()
        if fhash != st.session_state.last_file_hash:
            text = raw.decode("utf-8")
            st.session_state.schedule_text  = text
            st.session_state.last_file_hash = fhash
            with st.spinner(t("spinner")):
                run_chart(text, paper_size=st.session_state.paper_size)

    # Results — same tab, same render pass as the uploader
    if st.session_state.run_ok is True:
        st.success(t("success"))

        # Reserve the button slot BEFORE the image so it renders above it
        btn_slot = st.container()
        st.image(st.session_state.png_bytes, use_container_width=True)

        # Now fill the reserved slot with the download buttons
        with btn_slot:
            c1, c2, _ = st.columns([1, 1, 4])
            with c1:
                st.download_button(
                    t("dl_png"),
                    data=st.session_state.png_bytes,
                    file_name="gantt_chart.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with c2:
                if st.session_state.svg_bytes:
                    st.download_button(
                        t("dl_svg"),
                        data=st.session_state.svg_bytes,
                        file_name="gantt_chart.svg",
                        mime="image/svg+xml",
                        use_container_width=True,
                    )

    elif st.session_state.run_ok is False:
        st.error(t("err_failed"))

    else:
        st.info(t("info_waiting"))

    if st.session_state.run_log:
        with st.expander(t("expander_console"), expanded=(st.session_state.run_ok is False)):
            st.code(st.session_state.run_log, language="text")

    if st.session_state.schedule_text:
        with st.expander(t("expander_preview")):
            st.code(st.session_state.schedule_text, language="text")
