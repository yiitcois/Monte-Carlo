import os, json, pandas as pd
from ingest import detect_format, READERS

def ingest_one(in_path: str):
    fmt = detect_format(in_path)
    df, calendars = READERS[fmt](in_path)
    return df, calendars

def write_outputs(df: pd.DataFrame, calendars: list, out_dir="examples"):
    os.makedirs(out_dir, exist_ok=True)
    # tasks.csv
    out_cols = ["task_id","task_name","predecessors",
                "d_min","d_most_likely","d_max",
                "d_optimistic","d_likely","d_pessimistic",
                "calendar_id","milestone_flag","owner","anchor","offset","relative_to","work_package",
                "fixed_date","constraint","wbs_code","resource_id","cost_rate"]
    for c in out_cols:
        if c not in df.columns: df[c]=""
    df[out_cols].to_csv(os.path.join(out_dir,"tasks.csv"), index=False)
    # risks.csv (boş)
    pd.DataFrame(columns=["risk_id","risk_name","probability","impact_type","impact_target","impact_model","correlation_group","activation_logic"]).to_csv(os.path.join(out_dir,"risks.csv"), index=False)
    # calendars.json
    with open(os.path.join(out_dir,"calendars.json"),"w",encoding="utf-8") as f:
        json.dump(calendars, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    import sys
    if len(sys.argv)<2:
        print("Kullanım: python ingest_project.py <dosya1> [<dosya2> ...] [--out examples]")
        sys.exit(1)
    out = "examples"
    paths=[]
    for a in sys.argv[1:]:
        if a=="--out":
            # next token
            pass
    args = sys.argv[1:]
    if "--out" in args:
        i = args.index("--out")
        out = args[i+1]
        paths = args[0:i]
    else:
        paths = args
    # tek dosya veya birden çok dosya; birleştir
    frames=[]; cals=[]
    for p in paths:
        df, cal = ingest_one(p)
        frames.append(df); cals.extend(cal)
    big = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["task_id"], keep="first")
    if not cals:
        cals = [{"calendar_id":"TR_Factory_ShiftA","workdays":["Mon","Tue","Wed","Thu","Fri"],"work_hours_per_day":8,"holidays":[]}]
    write_outputs(big, cals, out_dir=out)
    print(f"Yazıldı → {out}/tasks.csv, {out}/risks.csv, {out}/calendars.json")
