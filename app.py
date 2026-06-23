
from datetime import date

from flask import Flask, render_template, request, abort

from database import get_connection

app = Flask(__name__)
TODAY = date(2026, 6, 22)

# Thresholds (hours / days) for the readiness coloring of an upcoming item.
HRS_RED, HRS_AMBER = 50, 200
DAYS_RED, DAYS_AMBER = 14, 30



# helpers
def _urgency(hours_left, days_left):
    """Classify an upcoming item as due / soon / ok for color coding."""
    over = (hours_left is not None and hours_left <= 0) or \
           (days_left is not None and days_left <= 0)
    if over:
        return "due"
    red = (hours_left is not None and hours_left <= HRS_RED) or \
          (days_left is not None and days_left <= DAYS_RED)
    if red:
        return "due"
    amber = (hours_left is not None and hours_left <= HRS_AMBER) or \
            (days_left is not None and days_left <= DAYS_AMBER)
    return "soon" if amber else "ok"


def _days_until(iso_date):
    if not iso_date:
        return None
    return (date.fromisoformat(iso_date) - TODAY).days


def upcoming_for_aircraft(conn, aircraft_id, ac_row):
    """Combines time tracked components and scheduled inspections, computes
    remaining flt hrs and days. returns list sorted by soonest.
    """
    rate_per_day = ac_row["avg_monthly_hours"] / 30.0 if ac_row["avg_monthly_hours"] else None
    af_hours = ac_row["airframe_hours"]
    items = []

    # 1) Time/life-limited components
    comp_rows = conn.execute(
        """SELECT co.component_name, co.category, ac.serial_number,
                  ac.hours_since_new, ac.life_limit_hours
           FROM aircraft_components ac
           JOIN components co ON co.component_id = ac.component_id
           WHERE ac.aircraft_id = ?""",
        (aircraft_id,),
    ).fetchall()
    for r in comp_rows:
        hours_left = round(r["life_limit_hours"] - r["hours_since_new"], 1)
        days_left = round(hours_left / rate_per_day) if rate_per_day else None
        items.append({
            "item": r["component_name"],
            "detail": f"{r['category']} · S/N {r['serial_number']} · life {r['life_limit_hours']:.0f} hr",
            "kind": "Component life",
            "hours_left": hours_left,
            "days_left": days_left,
            "urgency": _urgency(hours_left, days_left),
        })

    # 2) Scheduled inspections (hours and/or calendar driven)
    insp_rows = conn.execute(
        """SELECT inspection_type, interval_hours, hours_at_last,
                  interval_days, date_last
           FROM inspections WHERE aircraft_id = ?""",
        (aircraft_id,),
    ).fetchall()
    for r in insp_rows:
        hours_left = None
        days_left = None
        detail_bits = []
        if r["interval_hours"] is not None and r["hours_at_last"] is not None:
            hours_left = round(r["hours_at_last"] + r["interval_hours"] - af_hours, 1)
            detail_bits.append(f"every {r['interval_hours']:.0f} hr")
        if r["interval_days"] is not None and r["date_last"]:
            due_in = _days_until(r["date_last"]) + r["interval_days"]
            days_left = due_in
            detail_bits.append(f"every {r['interval_days']} days")
        # if only hours-driven, project days from utilization
        if days_left is None and hours_left is not None and rate_per_day:
            days_left = round(hours_left / rate_per_day)
        items.append({
            "item": r["inspection_type"],
            "detail": " · ".join(detail_bits),
            "kind": "Inspection",
            "hours_left": hours_left,
            "days_left": days_left,
            "urgency": _urgency(hours_left, days_left),
        })

    # sort by soonest: prefer days_left, fall back to hours_left
    def sort_key(it):
        d = it["days_left"]
        return d if d is not None else (it["hours_left"] or 1e9)

    items.sort(key=sort_key)
    return items


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Fleet overview + aircraft search."""
    q = request.args.get("q", "").strip()
    conn = get_connection()

    if q:
        rows = conn.execute(
            """SELECT aircraft_id, tail_number, model, unit, status,
                      airframe_hours
               FROM aircraft
               WHERE tail_number LIKE ? OR model LIKE ? OR unit LIKE ?
               ORDER BY tail_number""",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT aircraft_id, tail_number, model, unit, status,
                      airframe_hours
               FROM aircraft ORDER BY tail_number""",
        ).fetchall()

    # fleet readiness summary
    summary = conn.execute(
        """SELECT status, COUNT(*) AS n FROM aircraft GROUP BY status"""
    ).fetchall()
    summary = {r["status"]: r["n"] for r in summary}
    total = sum(summary.values())
    conn.close()
    return render_template("index.html", aircraft=rows, q=q,
                           summary=summary, total=total)


@app.route("/aircraft/<int:aircraft_id>")
def aircraft_detail(aircraft_id):
    conn = get_connection()
    ac = conn.execute(
        "SELECT * FROM aircraft WHERE aircraft_id = ?", (aircraft_id,)
    ).fetchone()
    if ac is None:
        conn.close()
        abort(404)

    # rollups
    stats = conn.execute(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(downtime_hours),0) AS downtime,
                  SUM(CASE WHEN status='Open' THEN 1 ELSE 0 END) AS open_cnt
           FROM discrepancies WHERE aircraft_id = ?""",
        (aircraft_id,),
    ).fetchone()

    common_fault = conn.execute(
        """SELECT discrepancy_text, COUNT(*) AS n
           FROM discrepancies WHERE aircraft_id = ?
           GROUP BY discrepancy_text ORDER BY n DESC LIMIT 1""",
        (aircraft_id,),
    ).fetchone()

    history = conn.execute(
        """SELECT d.date, c.component_name, d.discrepancy_text,
                  d.corrective_action, d.downtime_hours, d.status
           FROM discrepancies d
           JOIN components c ON c.component_id = d.component_id
           WHERE d.aircraft_id = ?
           ORDER BY d.date DESC LIMIT 50""",
        (aircraft_id,),
    ).fetchall()

    upcoming = upcoming_for_aircraft(conn, aircraft_id, ac)
    conn.close()
    return render_template("aircraft.html", ac=ac, stats=stats,
                           common_fault=common_fault, history=history,
                           upcoming=upcoming)


@app.route("/analytics")
def analytics():
    conn = get_connection()
    top_faults = conn.execute(
        """SELECT discrepancy_text, COUNT(*) AS n
           FROM discrepancies GROUP BY discrepancy_text
           ORDER BY n DESC LIMIT 10"""
    ).fetchall()

    top_components = conn.execute(
        """SELECT c.component_name, c.category, COUNT(*) AS n
           FROM discrepancies d JOIN components c
             ON c.component_id = d.component_id
           GROUP BY c.component_name ORDER BY n DESC LIMIT 10"""
    ).fetchall()

    top_downtime = conn.execute(
        """SELECT a.tail_number, a.model, a.aircraft_id,
                  ROUND(SUM(d.downtime_hours),1) AS downtime
           FROM discrepancies d JOIN aircraft a
             ON a.aircraft_id = d.aircraft_id
           GROUP BY a.aircraft_id ORDER BY downtime DESC LIMIT 10"""
    ).fetchall()

    repeats = conn.execute(
        """SELECT a.tail_number, c.component_name, COUNT(*) AS n
           FROM discrepancies d
           JOIN aircraft a   ON a.aircraft_id = d.aircraft_id
           JOIN components c  ON c.component_id = d.component_id
           GROUP BY d.aircraft_id, d.component_id
           HAVING n > 5 ORDER BY n DESC LIMIT 15"""
    ).fetchall()
    conn.close()
    return render_template("analytics.html", top_faults=top_faults,
                           top_components=top_components,
                           top_downtime=top_downtime, repeats=repeats)


@app.route("/search")
def keyword_search():
    """Keyword search across the discrepancy log."""
    kw = request.args.get("kw", "").strip()
    results = []
    conn = get_connection()
    if kw:
        results = conn.execute(
            """SELECT d.date, a.tail_number, c.component_name,
                      d.discrepancy_text, d.corrective_action,
                      d.downtime_hours, d.status, a.aircraft_id
               FROM discrepancies d
               JOIN aircraft a   ON a.aircraft_id = d.aircraft_id
               JOIN components c  ON c.component_id = d.component_id
               WHERE d.discrepancy_text LIKE ?
               ORDER BY d.date DESC LIMIT 200""",
            (f"%{kw}%",),
        ).fetchall()
    conn.close()
    return render_template("search.html", kw=kw, results=results)


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    # host=0.0.0.0 so it is reachable by others on the intranet
    app.run(host="0.0.0.0", port=5000, debug=True)
