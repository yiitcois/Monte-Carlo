import pandas as pd
from .normalize import ensure_task_columns, synthesize_distributions

def parse_xer(path: str):
    # Minimal XER parser: read sections into dataframes
    tables = {}
    current = None
    cols = []
    data = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line=line.rstrip("\n")
            if line.startswith("%T"):
                if current and data:
                    tables[current] = pd.DataFrame(data, columns=cols)
                current = line.split("\t")[1]
                cols=[]; data=[]
            elif line.startswith("%F"):
                cols = line.split("\t")[1:]
            elif line.startswith("%R"):
                vals = line.split("\t")[1:]
                data.append(vals)
        if current and data:
            tables[current] = pd.DataFrame(data, columns=cols)
    return tables

def read(path: str):
    tables = parse_xer(path)
    act = tables.get("TASK", pd.DataFrame())
    preds = tables.get("TASKPRED", pd.DataFrame())
    # Build tasks
    rows=[]
    if not act.empty:
        for _,r in act.iterrows():
            tid = str(r.get("task_id") or r.get("taskid") or r.get("task_id", ""))
            name = str(r.get("task_name") or r.get("taskname") or "")
            dur = float(r.get("orig_dur_hr", 0) or 0)/8.0
            cal = str(r.get("clndr_id") or "") or "TR_Factory_ShiftA"
            is_ms = str(r.get("milestone_flag") or r.get("milestone_flag", "0")).lower() in ("1","y","yes","true")
            rows.append({"task_id":tid,"task_name":name,"base_duration_days":dur,"calendar_id":cal,"milestone_flag":is_ms})
    df = pd.DataFrame(rows)
    # Predecessors
    if not preds.empty and not df.empty:
        mapping={}
        for _,r in preds.iterrows():
            succ = str(r.get("task_id") or r.get("taskid") or "")
            pred = str(r.get("pred_task_id") or r.get("predtaskid") or "")
            typ  = str(r.get("pred_type") or "FS").upper()
            lagh = float(r.get("lag_hr_cnt",0) or 0)/8.0
            link = f"{pred} {typ}{'+' if lagh>=0 else '-'}{int(abs(lagh))}d"
            mapping.setdefault(succ, []).append(link)
        if "predecessors" not in df.columns: df["predecessors"]=""
        df["predecessors"] = df["task_id"].map(lambda x: ",".join(mapping.get(str(x), [])))
    # Normalize
    from .normalize import ensure_task_columns, synthesize_distributions
    df = ensure_task_columns(df)
    df = synthesize_distributions(df, duration_field="base_duration_days")
    cals = [{"calendar_id":"TR_Factory_ShiftA","workdays":["Mon","Tue","Wed","Thu","Fri"],"work_hours_per_day":8,"holidays":[]}]
    return df, cals
