import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from datetime import datetime, timedelta, date
import sys
import re

# =============================================================================
#  JAPANESE FONT AUTO-DETECTION
#  If the schedule file contains CJK characters, a CJK-capable font is used
#  for all text in the chart.  No manual configuration is needed.
# =============================================================================

_JP_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-DemiLight.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]

def _find_cjk_font():
    """Return the path of the first available CJK font, or None.
    Falls back to scanning the matplotlib font cache for any CJK-capable font.
    """
    import os
    # 1. Check known fixed paths
    for path in _JP_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    # 2. Search matplotlib font cache for any font whose name suggests CJK
    try:
        import matplotlib.font_manager as _fm
        cjk_keywords = ["cjk", "japanese", "gothic", "mincho", "noto", "ipa",
                         "meiryo", "yugothic", "hiragino"]
        for fe in _fm.fontManager.ttflist:
            name_lower = fe.name.lower()
            fname_lower = (fe.fname or "").lower()
            if any(k in name_lower or k in fname_lower for k in cjk_keywords):
                if os.path.exists(fe.fname):
                    return fe.fname
    except Exception:
        pass
    return None

def _has_cjk(text):
    """Return True if text contains any CJK characters."""
    return bool(re.search(r'[\u3000-\u9fff\uff00-\uffef]', text))

# Will be set to a FontProperties object once we know whether CJK is needed.
_FONT_PROP = None   # None -> use matplotlib default

def _fprop(**kwargs):
    """Return a dict of font kwargs for text/annotate calls."""
    if _FONT_PROP is not None:
        return dict(fontproperties=_FONT_PROP, **kwargs)
    return kwargs


# import  jpholiday

# =============================================================================
#  CONFIGURATION
# =============================================================================

# ── Schedule file & optional date override from command line ─────────────────
# Usage:
#   python gantt_chart.py                          # uses default "schedule.txt"
#   python gantt_chart.py myfile.txt               # explicit file, date from file header
#   python gantt_chart.py myfile.txt 2026-06-01    # file + date override
#
# The start date is read from a  "# startdate: YYYY-MM-DD"  line in the file.
# A command-line date overrides it when supplied.

import os as _os

DEFAULT_SCHEDULE_FILE  = "schedule.txt"
PROJECT_START_DATE     = None   # resolved after file is loaded
_proj_start_dt         = None
CHART_START_DATE       = None

_argv_rest = sys.argv[1:]
SCHEDULE_FILE      = DEFAULT_SCHEDULE_FILE
_CLI_DATE_OVERRIDE = None
for _arg in _argv_rest:
    try:
        datetime.strptime(_arg, "%Y-%m-%d")
        _CLI_DATE_OVERRIDE = _arg       # valid date string → override
    except ValueError:
        SCHEDULE_FILE = _arg            # not a date → treat as file path



# Set a fixed end date for the x-axis, or leave as None to auto-fit to the
# latest task end date (+ a small right-padding).
CHART_END_DATE = None          # e.g. "2024-04-30"  or  None
# CHART_END_DATE = "2024-10-01"

# Working-day mode:
#   1  →  Weekdays only              (Mon–Fri; Sat/Sun/holidays are non-working)
#   2  →  Weekdays + Saturdays       (Mon–Sat; Sun/holidays are non-working)
#   3  →  Weekdays + every 2nd Sat   (Mon–Fri always; Sat alternates; Sun/holidays non-working)
#   4  →  All days                   (Sat, Sun and holidays all count as working days)
WORK_MODE = 1

# Path to the Japanese public holiday CSV (syukujitsu.csv from the Cabinet Office).
# The file is Shift-JIS encoded with columns: date (YYYY/M/D), holiday name.
# Set to None to run with no holidays.
HOLIDAY_CSV_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "syukujitsu.csv")

# HOLIDAYS list is populated after the CSV is loaded (see load_holidays_csv below).
HOLIDAYS = []






SAT_COLOR     = "#F5F0FF"   # light lavender  – Saturday (non-working)
SUN_COLOR     = "#FFF0F0"   # light rose      – Sunday
HOLIDAY_COLOR = "#FFF3CC"   # light amber     – Holiday
WORKDAY_COLOR = "#F0FFF0"   # light mint      – working Saturday (mode 3)

COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
]

BAR_HEIGHT  = 0.30
PLAN_OFFSET =  0.18
ACT_OFFSET  = -0.18

MODE_LABELS = {
    1: "Weekdays only (Mon–Fri)",
    2: "Weekdays + Saturdays (Mon–Sat)",
    3: "Weekdays + every 2nd Saturday",
    4: "All days (Mon–Sun incl. holidays)",
}

_OUT_DIR = _os.path.dirname(_os.path.abspath(SCHEDULE_FILE)) if SCHEDULE_FILE != "schedule.txt" else "."
OUT_PNG = _os.path.join(_OUT_DIR, "gantt_chart.png")
OUT_SVG = _os.path.join(_OUT_DIR, "gantt_chart.svg")

# =============================================================================
#  WORKING-DAY CALENDAR HELPERS
#  (defined here so _d() can call them at load time when parsing the schedule)
# =============================================================================

def _first_saturday_on_or_after(d: date) -> date:
    days_ahead = (5 - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


def _is_working_sat_mode3(d: date, first_sat: date) -> bool:
    """Every other Saturday starting from first_sat is a working day."""
    if d.weekday() != 5:
        return False
    weeks_since = (d - first_sat).days // 7
    return weeks_since % 2 == 0


def is_working_day(d: date, mode: int, holiday_dates: set, first_sat: date) -> bool:
    """Return True if date d counts as a working day under the given mode."""
    wd         = d.weekday()
    is_sat     = wd == 5
    is_sun     = wd == 6
    is_holiday = d in holiday_dates

    if mode == 1:
        return not is_sat and not is_sun and not is_holiday
    elif mode == 2:
        return not is_sun and not is_holiday
    elif mode == 3:
        if is_sun or is_holiday:
            return False
        if is_sat:
            return _is_working_sat_mode3(d, first_sat)
        return True
    elif mode == 4:
        return True
    else:
        raise ValueError(f"Unknown WORK_MODE: {mode}")


def add_working_days(start_dt: datetime, working_days: int,
                     mode: int, holiday_dates: set, first_sat: date) -> datetime:
    """Return the calendar end-date after `working_days` working days from start_dt."""
    d       = start_dt.date()
    counted = 0
    while counted < working_days:
        if is_working_day(d, mode, holiday_dates, first_sat):
            counted += 1
        if counted < working_days:
            d += timedelta(days=1)
    return datetime.combine(d + timedelta(days=1), datetime.min.time())


# =============================================================================
#  INPUT DATA  — loaded from a schedule text file
# =============================================================================
# File format (lines starting with # are comments and are ignored):
#
#   project name | plan_segments | actual_segments
#
# Each segment list is:  start+duration, start+duration, ...
#   where start    = working-day offset from day 1 (the project start day)
#         duration = number of working days
#
# actual_segments column is optional; omit it (or leave blank) for plan-only rows.
#
# Example line:
#   python coding | 14+10,52+10 | 14+12,53+11
#
# Usage:
#   python gantt_chart.py 2025-06-01 schedule.txt
#   python gantt_chart.py 2025-06-01          # uses DEFAULT_SCHEDULE_FILE
#   python gantt_chart.py                     # uses default date + default file


def _d(working_day_offset: int) -> str:
    """Return the calendar date that is (working_day_offset - 1) WORKING DAYS
    after the first working day on or after PROJECT_START_DATE.
    offset=1  →  first working day on/after PROJECT_START_DATE.
    offset=2  →  the next working day, etc.
    If PROJECT_START_DATE itself is a non-working day it is skipped and the
    walk begins from the next working day.
    """
    _hd = {datetime.strptime(d, "%Y-%m-%d").date() for d in HOLIDAYS}
    _fs = _first_saturday_on_or_after(_proj_start_dt.date())

    # Step 1: advance to the first working day on or after _proj_start_dt
    d = _proj_start_dt.date()
    while not is_working_day(d, WORK_MODE, _hd, _fs):
        d += timedelta(days=1)

    # Step 2: walk forward (working_day_offset - 1) more working days
    counted = 0
    while counted < working_day_offset - 1:
        d += timedelta(days=1)
        if is_working_day(d, WORK_MODE, _hd, _fs):
            counted += 1
    return d.strftime("%Y-%m-%d")


def _parse_segments(seg_str: str, row_name: str = "?", col: str = "?"):
    """Parse 'start+dur,start+dur,...' into a list of (start_offset, duration) tuples.

    Malformed tokens are skipped with a WARNING rather than crashing.
    row_name and col are used only for the warning message.
    """
    seg_str = seg_str.strip()
    if not seg_str:
        return []
    result = []
    for token in seg_str.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split("+")
        if len(parts) != 2:
            print(f"WARNING: [{row_name}] {col} — skipping malformed segment "
                  f"'{token}' (expected 'start+duration').")
            continue
        try:
            s, d = int(parts[0]), int(parts[1])
        except ValueError:
            print(f"WARNING: [{row_name}] {col} — skipping non-integer segment "
                  f"'{token}' (both values must be whole numbers).")
            continue
        if s < 1:
            print(f"WARNING: [{row_name}] {col} — start offset {s} is < 1; "
                  f"segment '{token}' skipped.")
            continue
        if d < 1:
            print(f"WARNING: [{row_name}] {col} — duration {d} is < 1; "
                  f"segment '{token}' skipped.")
            continue
        result.append((s, d))
    return result


def load_holidays_csv(filepath: str, start_year: int) -> list:
    """Load Japanese public holidays from the Cabinet Office CSV (syukujitsu.csv).

    The file is Shift-JIS encoded.  Each data row has two columns:
        YYYY/M/D , holiday name in Japanese

    Only holidays within [start_year - 10, start_year] are loaded.

    Returns a sorted list of 'YYYY-MM-DD' strings.
    """
    if filepath is None:
        print("Holiday CSV: none configured — no holidays will be marked.")
        return [], None

    import os
    if not os.path.exists(filepath):
        print(f"WARNING: Holiday CSV '{filepath}' not found — no holidays will be marked.")
        return [], None

    holidays = []
    try:
        with open(filepath, "r", encoding="shift_jis") as f:
            lines = f.readlines()
    except PermissionError:
        print(f"WARNING: Permission denied reading '{filepath}' — no holidays will be marked.")
        return [], None
    except UnicodeDecodeError as e:
        print(f"WARNING: Could not decode '{filepath}' as Shift-JIS: {e} — no holidays will be marked.")
        return [], None
    except OSError as e:
        print(f"WARNING: Could not read '{filepath}': {e} — no holidays will be marked.")
        return [], None

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date_str = parts[0].strip()
        # Skip header row(s) — header contains non-numeric characters before the first "/"
        if not re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", date_str):
            continue
        try:
            dt = datetime.strptime(date_str, "%Y/%m/%d")
        except ValueError:
            print(f"WARNING: Holiday CSV line {lineno}: unrecognised date '{date_str}' — skipped.")
            continue
        if (start_year - 7) <= dt.year <= (start_year + 3):
            holidays.append(dt.strftime("%Y-%m-%d"))

    holidays = sorted(set(holidays))
    max_year = max(datetime.strptime(d, "%Y-%m-%d").year for d in holidays) if holidays else None
    print(f"Holiday CSV loaded: '{filepath}'  "
          f"(years {start_year - 7}–{start_year + 3}, {len(holidays)} entries)")
    return holidays, max_year


def load_schedule(filepath: str) -> tuple:
    """Pass 1 — read the file, extract startdate/workday-mode headers and raw segment data.

    Returns (raw_rows, startdate_str_or_None, workday_mode_or_None) where raw_rows is a
    list of (name, plan_segs, actual_segs) tuples with integer offsets/durations.
    Call build_projects(raw_rows) AFTER _proj_start_dt is set.
    """
    raw_rows       = []
    file_date      = None
    file_work_mode = None
    file_holidays  = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"ERROR: Schedule file '{filepath}' not found.")
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: Permission denied reading '{filepath}'. "
              f"Check that the file is readable by the current user.")
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(f"ERROR: '{filepath}' is not valid UTF-8 and could not be decoded.\n"
              f"  Detail: {e}\n"
              f"  Tip: re-save the file with UTF-8 encoding.")
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: Could not read '{filepath}': {e}")
        sys.exit(1)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = re.match(r"#\s*startdate:\s*(\S+)", line, re.IGNORECASE)
            if m:
                try:
                    datetime.strptime(m.group(1), "%Y-%m-%d")
                    file_date = m.group(1)
                except ValueError:
                    print(f"WARNING: Invalid startdate in file: '{m.group(1)}' — ignored.")
            m2 = re.match(r"#\s*workday-mode:\s*(\d+)", line, re.IGNORECASE)
            if m2:
                mode_val = int(m2.group(1))
                if mode_val in (1, 2, 3, 4):
                    file_work_mode = mode_val
                else:
                    print(f"WARNING: Invalid workday-mode in file: '{mode_val}' — ignored (must be 1–4).")
            m3 = re.match(r"#\s*holiday:\s*(\S+)", line, re.IGNORECASE)
            if m3:
                try:
                    datetime.strptime(m3.group(1), "%Y-%m-%d")
                    file_holidays.append(m3.group(1))
                except ValueError:
                    print(f"WARNING: Invalid holiday date in file: '{m3.group(1)}' — ignored (expected YYYY-MM-DD).")
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        name        = parts[0]
        plan_segs   = _parse_segments(parts[1], row_name=name, col="plan")
        actual_segs = _parse_segments(parts[2], row_name=name, col="actual") if len(parts) >= 3 else []
        if plan_segs or actual_segs:
            raw_rows.append((name, plan_segs, actual_segs))

    if not raw_rows:
        print(f"ERROR: No valid project rows found in '{filepath}'.")
        sys.exit(1)

    return raw_rows, file_date, file_work_mode, file_holidays


def build_projects(raw_rows: list) -> list:
    """Pass 2 — convert raw (offset, duration) tuples to date strings.
    Must be called after _proj_start_dt has been set.
    """
    projects = []
    for name, plan_segs, actual_segs in raw_rows:
        n = max(len(plan_segs), len(actual_segs))
        subtasks = []
        for i in range(n):
            task = {}
            if i < len(plan_segs):
                ps, pd = plan_segs[i]
                task["start"]    = _d(ps)
                task["duration"] = pd
            if i < len(actual_segs):
                as_, ad = actual_segs[i]
                task["actual_start"]    = _d(as_)
                task["actual_duration"] = ad
            if task:
                subtasks.append(task)
        if len(subtasks) == 1:
            entry = {"name": name, **subtasks[0]}
        else:
            entry = {"name": name, "subtasks": subtasks}
        projects.append(entry)
        print(f"  Loaded: {name!r}  ({len(subtasks)} segment(s))")
    return projects


# ── Pass 1: read file, extract startdate, workday-mode and raw rows ──────────
print(f"Loading schedule from: {SCHEDULE_FILE}")
_raw_rows, _file_date, _file_work_mode, _file_holidays = load_schedule(SCHEDULE_FILE)

# ── Resolve WORK_MODE ─────────────────────────────────────────────────────────
# Priority: file header > hardcoded default (no CLI override for mode currently)
if _file_work_mode is not None:
    WORK_MODE = _file_work_mode
    print(f"Working-day mode (from file): {WORK_MODE} — {MODE_LABELS[WORK_MODE]}")
else:
    print(f"Working-day mode (default)  : {WORK_MODE} — {MODE_LABELS[WORK_MODE]}")

# ── Resolve PROJECT_START_DATE ────────────────────────────────────────────────
# Priority: CLI override > file header > error
if _CLI_DATE_OVERRIDE:
    PROJECT_START_DATE = _CLI_DATE_OVERRIDE
    print(f"Start date (CLI override): {PROJECT_START_DATE}")
elif _file_date:
    PROJECT_START_DATE = _file_date
    print(f"Start date (from file)   : {PROJECT_START_DATE}")
else:
    print("ERROR: No start date found. Add  '# startdate: YYYY-MM-DD'  to the "
          "schedule file, or pass the date as a command-line argument.")
    sys.exit(1)

_proj_start_dt   = datetime.strptime(PROJECT_START_DATE, "%Y-%m-%d")
CHART_START_DATE = (_proj_start_dt - timedelta(days=3)).strftime("%Y-%m-%d")

# ── Load holidays from CSV (project start year and prior 10 years) ───────────
HOLIDAYS, _HOLIDAY_MAX_YEAR = load_holidays_csv(HOLIDAY_CSV_FILE, start_year=_proj_start_dt.year)

# ── Merge any # holiday: entries from the schedule file ──────────────────────
if _file_holidays:
    print(f"Extra holidays from schedule file: {len(_file_holidays)} entries")
    HOLIDAYS = sorted(set(HOLIDAYS) | set(_file_holidays))

# ── Pass 2: convert offsets to real dates now that _proj_start_dt is set ─────
projects = build_projects(_raw_rows)

# ── Activate CJK font if any project name contains Japanese/CJK characters ──
_all_names = " ".join(p["name"] for p in projects)
if _has_cjk(_all_names):
    _cjk_path = _find_cjk_font()
    if _cjk_path:
        _FONT_PROP = fm.FontProperties(fname=_cjk_path)
        print(f"CJK characters detected — using font: {_cjk_path}")
    else:
        print("WARNING: CJK characters detected but no CJK font found. Labels may show boxes.")















# =============================================================================
#  CHART HELPERS
# =============================================================================

def parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def iter_segments(proj, mode, holiday_dates, first_sat):
    """Yield (plan_start, plan_end, act_start|None, act_end|None, plan_wd, act_wd|None)."""
    tasks = proj.get("subtasks") or [proj]
    for t in tasks:
        ps = parse(t["start"])
        pe = add_working_days(ps, t["duration"], mode, holiday_dates, first_sat)
        if "actual_start" in t:
            as_ = parse(t["actual_start"])
            ae  = add_working_days(as_, t["actual_duration"], mode, holiday_dates, first_sat)
            act_wd = t["actual_duration"]
        else:
            as_ = ae = act_wd = None
        yield ps, pe, as_, ae, t["duration"], act_wd


def draw_bar(ax, y_centre, offset, start_dt, end_dt, working_days, color, alpha, zorder,
             mode, holiday_dates, first_sat):
    """Draw a bar day-by-day so non-working day slices appear lighter.

    Working-day slices  → full alpha (as supplied).
    Non-working slices  → alpha reduced to 25 % of the supplied alpha,
                          giving a clearly faded appearance while keeping
                          the bar shape intact across the whole calendar span.
    The duration label (working days from the input file) is drawn once,
    centred over the full bar.
    """
    cal_width = (end_dt - start_dt).days
    y_bar     = y_centre + offset
    left_num  = mdates.date2num(start_dt)

    # Draw one 1-day rectangle per calendar day
    d = start_dt.date()
    for _ in range(cal_width):
        day_left  = mdates.date2num(datetime.combine(d, datetime.min.time()))
        working   = is_working_day(d, mode, holiday_dates, first_sat)
        day_alpha = alpha if working else alpha * 0.25
        ax.barh(
            y_bar, 1, left=day_left,
            height=BAR_HEIGHT,
            color=color, edgecolor="white", linewidth=0.6,
            alpha=day_alpha, zorder=zorder,
        )
        d += timedelta(days=1)




def shade_day(ax, d: date, mode: int, holiday_dates: set, first_sat: date):
    """Paint a background column for non-working / special days."""
    is_holiday = d in holiday_dates
    is_sat     = d.weekday() == 5
    is_sun     = d.weekday() == 6
    working    = is_working_day(d, mode, holiday_dates, first_sat)

    if is_holiday:
        color = HOLIDAY_COLOR
    elif is_sat and mode == 3 and working:
        color = WORKDAY_COLOR
    elif is_sat:
        color = SAT_COLOR
    elif is_sun:
        color = SUN_COLOR
    else:
        return  # regular weekday – no shading

    x_left = mdates.date2num(datetime.combine(d, datetime.min.time()))
    ax.axvspan(x_left, x_left + 1, ymin=0, ymax=1,
               color=color, zorder=0, linewidth=0)


def build_legend(ax, mode):
    """Add the legend with planned/actual swatches and day-type shading keys."""
    handles = [
        mpatches.Patch(color="#555555", alpha=0.88, label="Planned"),
        mpatches.Patch(color="#555555", alpha=0.40, label="Actual"),
        mpatches.Patch(facecolor=SAT_COLOR,     edgecolor="#CCCCCC", lw=0.5,
                       label="Saturday (non-working)"),
        mpatches.Patch(facecolor=SUN_COLOR,     edgecolor="#CCCCCC", lw=0.5,
                       label="Sunday"),
        mpatches.Patch(facecolor=HOLIDAY_COLOR, edgecolor="#CCCCCC", lw=0.5,
                       label="Holiday"),
    ]
    if mode == 3:
        handles.append(
            mpatches.Patch(facecolor=WORKDAY_COLOR, edgecolor="#CCCCCC", lw=0.5,
                           label="Working Saturday")
        )
    ax.legend(handles=handles, loc="lower right", fontsize=8.5,
              frameon=True, framealpha=0.95, edgecolor="#CCCCCC", ncol=2)

# =============================================================================
#  MAIN
# =============================================================================

def main():
    # ── Derived constants ────────────────────────────────────────────────────
    holiday_dates = {datetime.strptime(d, "%Y-%m-%d").date() for d in HOLIDAYS}
    chart_start   = parse(CHART_START_DATE)
    first_sat     = _first_saturday_on_or_after(chart_start.date())

    # ── Warn if project start date is a non-working day ──────────────────────
    supplied = _proj_start_dt.date()
    if not is_working_day(supplied, WORK_MODE, holiday_dates, first_sat):
        effective = datetime.strptime(_d(1), "%Y-%m-%d").date()
        print(f"WARNING: {supplied} ({supplied.strftime('%A')}) is a non-working day. "
              f"First task starts on {effective} ({effective.strftime('%A')}) instead.")

    # ── Compute x-axis range ─────────────────────────────────────────────────
    all_ends = []
    for proj in projects:
        for ps, pe, as_, ae, *_ in iter_segments(proj, WORK_MODE, holiday_dates, first_sat):
            all_ends.append(pe)
            if ae:
                all_ends.append(ae)

    if CHART_END_DATE is not None:
        chart_end = parse(CHART_END_DATE) + timedelta(days=1)  # inclusive of end date
    else:
        chart_end = max(all_ends) + timedelta(days=3)          # auto-fit + padding

    total_days = (chart_end - chart_start).days

    # ── Figure setup ─────────────────────────────────────────────────────────
    n          = len(projects)
    fig_width  = max(14, total_days * 0.28)
    fig_height = max(4, n * 1.0 + 1.8)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # ── Shade weekends & holidays ─────────────────────────────────────────────
    current  = chart_start.date()
    end_date = chart_end.date()
    while current < end_date:
        shade_day(ax, current, WORK_MODE, holiday_dates, first_sat)
        current += timedelta(days=1)

    # ── Draw project bars ─────────────────────────────────────────────────────
    y_positions = list(range(n - 1, -1, -1))
    for i, (proj, y) in enumerate(zip(projects, y_positions)):
        color = COLORS[i % len(COLORS)]
        for ps, pe, as_, ae, plan_wd, act_wd in iter_segments(
                proj, WORK_MODE, holiday_dates, first_sat):
            draw_bar(ax, y, PLAN_OFFSET, ps, pe, plan_wd, color, alpha=0.88, zorder=3, mode=WORK_MODE, holiday_dates=holiday_dates, first_sat=first_sat)
            if as_ is not None:
                draw_bar(ax, y, ACT_OFFSET, as_, ae, act_wd, color, alpha=0.40, zorder=3, mode=WORK_MODE, holiday_dates=holiday_dates, first_sat=first_sat)

    # ── Horizontal lines between projects ───────────────────────────────────
    for y in y_positions:
        ax.axhline(y - 0.5, color="#CCCCCC", linewidth=0.7, zorder=2)

    # ── X-axis ────────────────────────────────────────────────────────────────
    ax.set_xlim(mdates.date2num(chart_start), mdates.date2num(chart_end))
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="left", **_fprop(fontsize=8.5))
    ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))
    ax.xaxis.grid(True, which="minor", color="#E8E8E8", linewidth=0.4, zorder=1)
    ax.xaxis.grid(True, which="major", color="#BBBBBB", linewidth=0.8, zorder=1)
    ax.yaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", which="both", length=0)

    # ── Y-axis ────────────────────────────────────────────────────────────────
    ax.set_yticks(y_positions)
    labels = [p["name"] for p in projects]
    ax.set_yticklabels(labels, **_fprop(fontsize=10))
    ax.yaxis.set_tick_params(length=0)
    ax.set_ylim(-0.65, n - 0.35)

    for spine in ["left", "right", "bottom"]:
        ax.spines[spine].set_visible(False)
    ax.spines["top"].set_color("#CCCCCC")

    # ── Legend ────────────────────────────────────────────────────────────────
    build_legend(ax, WORK_MODE)

    # ── Holiday coverage warning ─────────────────────────────────────────────
    _chart_end_year = chart_end.year
    _holiday_warning = (
        _HOLIDAY_MAX_YEAR is not None and _chart_end_year > _HOLIDAY_MAX_YEAR
    )
    if _holiday_warning:
        _warn_msg = (
            f"⚠  Holiday data only covers up to {_HOLIDAY_MAX_YEAR}. "
            f"Dates beyond {_HOLIDAY_MAX_YEAR} treat holidays as working days."
        )
        print(f"WARNING: {_warn_msg}")

        # Draw a prominent warning banner across the top of the axes
        ax.annotate(
            _warn_msg,
            xy=(0.5, 1.0),
            xycoords="axes fraction",
            xytext=(0, 36),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=8.5, fontweight="bold", color="#7a0000",
            bbox=dict(
                boxstyle="round,pad=0.45",
                facecolor="#FFF0B0",
                edgecolor="#CC8800",
                linewidth=1.5,
                alpha=0.97,
            ),
            zorder=50,
        )

        # Also draw a vertical red dashed boundary at Jan 1 of the first uncovered year
        _boundary = datetime(year=_HOLIDAY_MAX_YEAR + 1, month=1, day=1)
        if chart_start <= _boundary <= chart_end:
            ax.axvline(
                mdates.date2num(_boundary),
                color="#CC0000", linewidth=1.2,
                linestyle="--", alpha=0.7, zorder=6,
            )
            ax.annotate(
                f"← holidays known    unknown →",
                xy=(mdates.date2num(_boundary), n - 0.35),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=7, color="#CC0000",
                zorder=7,
            )

    plt.tight_layout(rect=[0, 0, 1, 1.0])

    # ── Save ──────────────────────────────────────────────────────────────────
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor="white")
    plt.savefig(OUT_SVG, bbox_inches="tight", facecolor="white")
    print(f"Saved: {OUT_PNG}")
    print(f"Saved: {OUT_SVG}")


if __name__ == "__main__":
    main()
