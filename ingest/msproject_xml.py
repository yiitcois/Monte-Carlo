import xml.etree.ElementTree as ET
import pandas as pd
from .normalize import mk_predecessor_link, ensure_task_columns, synthesize_distributions

TYPE_MAP = {"1":"FF","2":"FS","3":"SF","4":"SS"}

def parse_duration_text(txt: str) -> float:
    # MS Project XML duration strings like "PT32H0M0S" (ISO8601). Convert to working DAYS with 8h assumption here.
    # You can improve by reading HoursPerDay from Calendar; fallback 8h
    if not txt: return 0.0
    h = 0
    import re
    m = re.search(r"PT(\d+)H", txt)
    if m:
        h = int(m.group(1))
    return round(h / 8.0, 3)

def read(path: str):
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"ms":"http://schemas.microsoft.com/project"}
    # Tasks
    rows = []
    for t in root.findall("ms:Tasks/ms:Task", ns):
        uid = (t.findtext("ms:UID", default="", namespaces=ns) or "").strip()
        name = (t.findtext("ms:Name", default="", namespaces=ns) or "").strip()
        is_ms = (t.findtext("ms:Milestone", default="0", namespaces=ns) or "0").strip() in ("1","true","True")
        dur = parse_duration_text(t.findtext("ms:Duration", default="", namespaces=ns))
        cal_uid = (t.findtext("ms:CalendarUID", default="", namespaces=ns) or "").strip()
        const_type = (t.findtext("ms:ConstraintType", default="", namespaces=ns) or "").strip()
        const_date = (t.findtext("ms:ConstraintDate", default="", namespaces=ns) or "").strip()
        # predecessors
        preds=[]
        for pl in t.findall("ms:PredecessorLink", ns):
            pid = (pl.findtext("ms:PredecessorUID", default="", namespaces=ns) or "").strip()
            ltype = TYPE_MAP.get((pl.findtext("ms:Type", default="", namespaces=ns) or "").strip(), "FS")
            lag_dur = parse_duration_text(pl.findtext("ms:LinkLag", default="", namespaces=ns))
            preds.append(mk_predecessor_link(pid, ltype, lag_dur))
        rows.append({
            "task_id": uid, "task_name": name, "predecessors": ",".join(preds),
            "calendar_id": cal_uid if cal_uid else "TR_Factory_ShiftA",
            "milestone_flag": bool(is_ms),
            "base_duration_days": dur,
            "constraint": const_type, "fixed_date": const_date
        })
    df = pd.DataFrame(rows)
    df = ensure_task_columns(df)
    df = synthesize_distributions(df, duration_field="base_duration_days")
    # Calendars (optional minimal)
    cals = [{"calendar_id":"TR_Factory_ShiftA","workdays":["Mon","Tue","Wed","Thu","Fri"],"work_hours_per_day":8,"holidays":[]}]
    return df, cals
