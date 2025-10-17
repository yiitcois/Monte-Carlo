import pandas as pd
from .normalize import ensure_task_columns, synthesize_distributions

def read(path: str):
    df = pd.read_csv(path)
    # Expect at least task_id, task_name; others optional
    if "task_id" not in df.columns or "task_name" not in df.columns:
        raise ValueError("CSV en azından task_id ve task_name içermeli.")
    if "calendar_id" not in df.columns:
        df["calendar_id"] = "TR_Factory_ShiftA"
    if "predecessors" not in df.columns:
        df["predecessors"] = ""
    if "milestone_flag" in df.columns:
        df["milestone_flag"] = df["milestone_flag"].astype(str).str.lower().isin(["1","true","evet","yes","y"])
    else:
        df["milestone_flag"] = False
    if "base_duration_days" not in df.columns:
        # try duration columns
        for c in ["duration","dur_days","dur"]:
            if c in df.columns:
                df["base_duration_days"] = pd.to_numeric(df[c], errors="coerce").fillna(0); break
        else:
            df["base_duration_days"] = 0
    df = ensure_task_columns(df)
    df = synthesize_distributions(df, duration_field="base_duration_days")
    cals = [{"calendar_id":"TR_Factory_ShiftA","workdays":["Mon","Tue","Wed","Thu","Fri"],"work_hours_per_day":8,"holidays":[]}]
    return df, cals
