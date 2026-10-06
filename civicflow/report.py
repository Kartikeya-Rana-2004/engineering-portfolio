"""Export an offline, dependency-free dashboard from the warehouse."""
import argparse
import html
from pathlib import Path
import sqlite3


def render(db, output):
    with sqlite3.connect(f"file:{Path(db).resolve()}?mode=ro", uri=True) as connection:
        total, closed, hours = connection.execute("SELECT count(*),sum(closed_date IS NOT NULL),avg(resolution_hours) FROM requests").fetchone()
        boroughs = connection.execute("SELECT borough,count(*) FROM requests GROUP BY borough ORDER BY count(*) DESC").fetchall()
        groups = connection.execute("SELECT day,borough,agency,complaint_type,request_count,closed_count,avg_resolution_hours FROM daily_service_metrics ORDER BY day DESC,request_count DESC LIMIT 100").fetchall()
        runs = connection.execute("SELECT count(*),sum(quarantined) FROM runs").fetchone()
    bars = ""
    maximum = max((count for _, count in boroughs), default=1)
    for borough, count in boroughs:
        bars += f'<div class="bar-row"><span>{html.escape(borough)}</span><div class="bar" style="width:{100*count/maximum:.1f}%"></div><b>{count:,}</b></div>'
    table = "".join("<tr>" + "".join(f"<td>{html.escape(str(round(v, 2) if isinstance(v, float) else v if v is not None else '—'))}</td>" for v in row) + "</tr>" for row in groups)
    hours_display = f"{hours:.1f}" if hours is not None else "Unavailable"
    text = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CivicFlow | Service operations</title><style>
body{{font:16px system-ui;margin:0;background:#101820;color:#e8f0f4}}main{{max-width:1100px;margin:50px auto;padding:24px}}h1{{font-size:42px;margin-bottom:8px}}p{{color:#b3c4cd;line-height:1.6}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:28px 0}}.card{{padding:24px;background:#1d2c36;border-radius:12px}}.card b{{display:block;font-size:32px;color:#70dfc1}}.bar-row{{display:grid;grid-template-columns:150px 1fr 90px;align-items:center;margin:18px 0;gap:12px}}.bar{{height:16px;background:#70dfc1;border-radius:5px}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #30424e}}.scroll{{overflow:auto}}small{{color:#b3c4cd}}
</style><main><small>PUBLIC DATA ENGINEERING / NYC 311</small><h1>CivicFlow</h1><p>Service request operations from the loaded batch. This is a bounded sample, not a citywide performance assessment.</p>
<div class="cards"><div class="card">Requests<b>{total:,}</b></div><div class="card">With a closure date<b>{closed or 0:,}</b></div><div class="card">Mean closure hours<b>{hours_display}</b></div><div class="card">Successful loads<b>{runs[0]}</b></div></div>
<h2>Request distribution</h2>{bars}<h2>Daily service metrics</h2><p>Mean closure time includes only records with a closure date; unresolved requests are excluded. Differences in case mix and sampling limit comparisons.</p><div class="scroll"><table><thead><tr><th>Day</th><th>Borough</th><th>Agency</th><th>Type</th><th>Requests</th><th>Closed</th><th>Mean hours</th></tr></thead><tbody>{table}</tbody></table></div></main></html>'''
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/warehouse.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("data/dashboard.html"))
    args = parser.parse_args()
    render(args.db, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
