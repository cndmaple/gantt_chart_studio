# 工程計画 / Gantt Chart App

An interactive project schedule editor + Gantt chart generator, deployable on **Streamlit Community Cloud** via GitHub.

---

## Repository structure

```
├── app.py               ← Streamlit app (entry point)
├── gantt_core.py        ← Chart generation engine (matplotlib)
├── gantt_editor.html    ← Interactive HTML/JS Gantt editor
├── syukujitsu.csv       ← Japanese public holiday schedule (Cabinet Office, 1955–2027)
├── requirements.txt     ← Python dependencies
└── README.md
```

---

## How to deploy on Streamlit Community Cloud

### 1 — Push this repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2 — Connect to Streamlit Community Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
2. Click **"New app"**
3. Select your repository, branch (`main`), and set **Main file path** to `app.py`
4. Click **"Deploy"**

Streamlit Cloud installs dependencies from `requirements.txt` automatically.

---

## How to use the app

### Tab 1 — Schedule Editor
1. Edit your project schedule in the interactive Gantt editor
2. Set start date, working-day mode, and any extra holidays
3. Click **💾 Save** (or **💾 保存**) — your browser downloads `schedule.txt`
4. Upload that file using the upload panel below the editor
5. The chart is generated **automatically** on upload — no extra button click needed

### Tab 2 — Generate Chart
- The chart appears automatically after upload
- Click **▶ Re-generate Chart** to regenerate at any time
- Download the result as **PNG** or **SVG**

---

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Notes

- `schedule.txt` is **not stored in the repo** — it lives in browser session memory only, so each new session starts fresh. Re-upload your file when you open a new browser session.
- The holiday CSV (`syukujitsu.csv`) is sourced from the **official Japanese Cabinet Office (内閣府)**:
  - URL: https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv
  - Encoding: Shift_JIS
  - Data range: 1955/1/1 to 2027/9/23 (as of the 2026/2027 update)
  - A warning banner appears in the chart if your schedule extends beyond that range — beyond that range, only Saturdays and Sundays are counted as non-working days (public holidays are not recognised).
- Working-day mode and start date are read from the `# startdate:` and `# workday-mode:` header lines inside `schedule.txt`.
