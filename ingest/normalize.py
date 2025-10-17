import re
import pandas as pd

def mk_predecessor_link(pred_id: str, link_type: str, lag_days: float) -> str:
    # link_type: FS/SS/FF/SF
    lag_sign = "+" if lag_days >= 0 else "-"
    lag_abs = abs(lag_days)
    return f"{pred_id} {link_type}{lag_sign}{int(lag_abs)}d"

def ensure_task_columns(df: pd.DataFrame) -> pd.DataFrame:
    need = ["task_id","task_name","predecessors","calendar_id","milestone_flag",
            "d_min","d_most_likely","d_max","d_optimistic","d_likely","d_pessimistic",
            "owner","work_package","fixed_date","constraint","wbs_code","resource_id","cost_rate",
            "anchor","offset","relative_to"]
    for c in need:
        if c not in df.columns:
            df[c] = ""
    return df

def synthesize_distributions(df: pd.DataFrame, duration_field="base_duration_days",
                             rule=(0.8,1.0,1.5)):
    # For tasks that have no distribution info, build triangular from deterministic base
    dmin, dml, dmax = rule
    base = pd.to_numeric(df.get(duration_field, 0), errors="coerce").fillna(0)
    tri_missing = (df[["d_min","d_most_likely","d_max"]].replace("", pd.NA).isna().all(axis=1))
    df.loc[tri_missing & (base>0), "d_min"] = (base * dmin).round(2)
    df.loc[tri_missing & (base>0), "d_most_likely"] = (base * dml).round(2)
    df.loc[tri_missing & (base>0), "d_max"] = (base * dmax).round(2)
    # Milestones -> 0,0,0
    ms = df["milestone_flag"] == True
    df.loc[ms, ["d_min","d_most_likely","d_max","d_optimistic","d_likely","d_pessimistic"]] = 0
    return df
