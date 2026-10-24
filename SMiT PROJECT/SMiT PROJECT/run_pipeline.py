#!/usr/bin/env python3
"""Build the Indus Weave HR SQLite warehouse and analysis outputs.

The script reads the twelve case-study exports from ``--input-dir`` and writes
the rebuilt database beside this file (or to ``--db``). Database replacement
is atomic: a failed build leaves the previous database in place.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, sqlite3, bisect
from pathlib import Path
from datetime import date, datetime, time, timedelta
import pandas as pd
from pipeline.analytics import write_outputs
from pipeline.attendance import build_attendance
from pipeline.storage import persist_tables

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = Path(r"C:\Users\Lenovo\Downloads")
OUT = ROOT
DB = OUT / "indus_weave_hr.sqlite"
MONTHS = pd.period_range("2026-04", "2026-09", freq="M")

FILES = ["employees.csv", "employment_history.csv", "departments.csv", "shifts.json",
         "shift_roster.csv", "device_mapping.csv", "biometric_punches.csv", "holidays.csv",
         "leave_requests.json", "overtime_requests.csv", "payroll_lines.csv", "applications.csv"]

def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)

def dt(s):
    formats=("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S")
    def parse_one(v):
        if v is None or str(v).strip()=="": return pd.NaT
        value=str(v).strip()
        for fmt in formats:
            try: return pd.Timestamp(datetime.strptime(value,fmt))
            except ValueError: pass
        return pd.NaT
    return s.map(parse_one) if hasattr(s,"map") else parse_one(s)

def norm(s):
    return str(s).strip()

def load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def sha_row(values):
    return hashlib.sha256("\x1f".join(map(str, values)).encode()).hexdigest()

def sql_write(conn, name, frame, schema="staging", if_exists="replace"):
    frame.to_sql(f"{schema}_{name}", conn, if_exists=if_exists, index=False)

def main():
    ap=argparse.ArgumentParser(
        description="Build the HR warehouse, data-quality checks, SQL, and CSV results."
    )
    ap.add_argument(
        "--input-dir", default=str(DEFAULT_INPUT),
        help=f"folder containing the 12 source files (default: {DEFAULT_INPUT})",
    )
    ap.add_argument(
        "--db", default=str(DB),
        help=f"destination SQLite database (default: {DB})",
    )
    args=ap.parse_args()
    src=Path(args.input_dir).expanduser()
    db=Path(args.db).expanduser()
    db.parent.mkdir(parents=True, exist_ok=True)
    missing=[f for f in FILES if not (src/f).exists()]
    if missing:
        raise SystemExit(f"Missing input files in {src}: "+", ".join(missing))
    if not src.is_dir():
        raise SystemExit(f"Input path is not a folder: {src}")

    # Build beside the destination, then replace it only after a successful
    # commit. This protects the last good database if processing fails.
    build_db=db.with_name(f".{db.stem}.building{db.suffix or '.sqlite'}")
    if build_db.exists():
        build_db.unlink()
    conn=sqlite3.connect(build_db)
    conn.execute("PRAGMA foreign_keys=ON")
    rowlog=[]; raw={}
    for f in FILES:
        path=src/f
        if f.endswith(".csv"):
            frame=read_csv(path); raw[f]=frame
            rawname="raw_"+Path(f).stem
            cols=list(frame.columns)+["_source_file","_loaded_at","_row_hash"]
            conn.execute(f'CREATE TABLE "{rawname}" ('+', '.join('"'+c+'" TEXT' for c in cols)+')')
            stamp=datetime.now().isoformat(timespec="seconds")
            vals=[]
            for tup in frame.itertuples(index=False,name=None):
                vals.append(tuple(tup)+(f,stamp,sha_row(tup)))
            conn.executemany(f'INSERT INTO "{rawname}" VALUES ('+','.join('?' for _ in cols)+')', vals)
            rowlog.append({"file":f,"raw_rows":len(frame),"loaded_rows":len(vals),"rejected_rows":0})
        else:
            obj=load_json(path)
            if f=="leave_requests.json": raw[f]=obj
            else: raw[f]=obj
            rows=obj if isinstance(obj,list) else obj.get("shifts",[])
            rawname="raw_"+Path(f).stem
            # Preserve JSON rows without flattening their nested fields.
            conn.execute(f'CREATE TABLE "{rawname}" (payload TEXT, _source_file TEXT, _loaded_at TEXT, _row_hash TEXT)')
            stamp=datetime.now().isoformat(timespec="seconds")
            vals=[(json.dumps(x,ensure_ascii=False),f,stamp,sha_row([json.dumps(x,sort_keys=True)])) for x in rows]
            conn.executemany(f'INSERT INTO "{rawname}" VALUES (?,?,?,?)',vals)
            rowlog.append({"file":f,"raw_rows":len(rows),"loaded_rows":len(vals),"rejected_rows":0})

    emp_raw=raw["employees.csv"].copy()
    emp=emp_raw.copy()
    emp["updated_dt"]=dt(emp.updated_at)
    dedup_audit=[]
    for eid,g in emp.sort_values(["emp_id","updated_dt"]).groupby("emp_id"):
        if len(g)>1:
            kept=g.iloc[-1]
            for _,drop in g.iloc[:-1].iterrows(): dedup_audit.append({"emp_id":eid,"discarded_updated_at":drop["updated_at"],"kept_updated_at":kept["updated_at"],"reason":"Duplicate emp_id; retained latest updated_at"})
    emp=emp.sort_values(["emp_id","updated_dt"]).drop_duplicates("emp_id",keep="last")
    for c in ["hire_date","separation_date","date_of_birth"]: emp[c]=dt(emp[c]).dt.strftime("%Y-%m-%d").fillna("")
    for c in ["plant","department","designation","grade","employment_type","status"]: emp[c]=emp[c].map(lambda x:norm(x))
    emp["department_norm"]=emp.department.str.strip().str.casefold()

    dept=raw["departments.csv"].copy()
    for c in ["dept_name","plant","previous_name"]: dept[c]=dept[c].map(lambda x:norm(x))
    dept_lookup={}
    for r in dept.to_dict("records"):
        for n in [r["dept_name"],r["previous_name"]]:
            if n: dept_lookup[(r["plant"].casefold(),n.casefold())]=r["dept_id"]
    # match department text using normalized names, then employment history's dept_id is authoritative
    hist=raw["employment_history.csv"].copy()
    hist["effective_from_dt"]=dt(hist.effective_from)
    hist["_source_order"]=range(len(hist))
    history_dedup_audit=[]
    for (eid,eff),g in hist.groupby(["emp_id","effective_from_dt"],dropna=False):
        if len(g)>1:
            keep=g.iloc[-1]
            for _,drop in g.iloc[:-1].iterrows(): history_dedup_audit.append({"emp_id":eid,"effective_from":str(eff.date()) if pd.notna(eff) else "","discarded_reason":drop["change_reason"],"kept_reason":keep["change_reason"],"resolution":"Same employee and effective date; retained last source row because no intra-day sequence is supplied"})
    hist=hist.sort_values("_source_order").drop_duplicates(["emp_id","effective_from_dt"],keep="last")
    hist=hist.sort_values(["emp_id","effective_from_dt"])
    hist["valid_from"]=hist.effective_from_dt.dt.strftime("%Y-%m-%d")
    hist["valid_to"]=""
    for _,ix in hist.groupby("emp_id").groups.items():
        ids=list(ix)
        for j,i in enumerate(ids[:-1]): hist.loc[i,"valid_to"]=(hist.loc[ids[j+1],"effective_from_dt"]-pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    hist["basic_salary_num"]=pd.to_numeric(hist.basic_salary,errors="coerce")

    shifts_obj=raw["shifts.json"]; shifts={x["shift_code"]:x for x in shifts_obj["shifts"]}
    roster=raw["shift_roster.csv"].copy(); roster["week_start"]=dt(roster.week_start).dt.date
    roster=roster.drop_duplicates(["emp_id","week_start"],keep="last")
    rmap={(r.emp_id,r.week_start):r.shift_code for r in roster.itertuples()}
    roster_by_emp={}
    for eid,g in roster.groupby("emp_id"):
        roster_by_emp[eid]=sorted((r.week_start,r.shift_code) for r in g.itertuples())
    emap=emp.set_index("emp_id").to_dict("index")
    def shift_for(eid, d):
        monday=d-timedelta(days=d.weekday())
        code=rmap.get((eid,monday))
        if code: return code
        # carry forward the most recent rostered shift, including before a missing week
        weeks=roster_by_emp.get(eid,[]); i=bisect.bisect_left([x[0] for x in weeks],monday)-1
        return weeks[i][1] if i>=0 else "GEN"
    dm=raw["device_mapping.csv"].copy()
    dm["device_user_id"]=dm.device_user_id.astype(str)
    dmap={(r.device_id,str(r.device_user_id)):r.emp_id for r in dm.itertuples()}
    punches=raw["biometric_punches.csv"].copy()
    punches["device_user_id"]=punches.device_user_id.astype(str)
    punches["emp_id"]=[dmap.get((r.device_id,str(r.device_user_id)),"") for r in punches.itertuples()]
    punches["timestamp"]=pd.to_datetime(punches.punch_time,errors="coerce")
    rejected=punches[punches.emp_id.eq("")].copy(); rejected["reason"]="No device_id + device_user_id mapping"
    punches=punches[punches.emp_id.ne("") & punches.timestamp.notna()].copy()
    mapped_punch_count=len(punches)
    attendance_context = locals().copy()
    attendance_context.update({"pd": pd, "dt": dt, "date": date, "datetime": datetime, "time": time, "timedelta": timedelta})
    attendance_state = build_attendance(attendance_context)
    punches=attendance_state["punches"]
    rejected=attendance_state["rejected"]
    mapped_punch_count=attendance_state["mapped_punch_count"]
    deviations=attendance_state["deviations"]
    offsets=attendance_state["offsets"]
    punch_duplicate_count=attendance_state["punch_duplicate_count"]
    grouped=attendance_state["grouped"]
    hol=attendance_state["hol"]
    plantcode=attendance_state["plantcode"]
    holidays=attendance_state["holidays"]
    leave_rows=attendance_state["leave_rows"]
    approvals=attendance_state["approvals"]
    leave_days=attendance_state["leave_days"]
    ld=attendance_state["ld"]
    leave_set=attendance_state["leave_set"]
    leave_type_by=attendance_state["leave_type_by"]
    deptinfo=attendance_state["deptinfo"]
    hist_by_emp=attendance_state["hist_by_emp"]
    hist_on=attendance_state["hist_on"]
    month_department=attendance_state["month_department"]
    attendance=attendance_state["attendance"]
    att=attendance_state["att"]

    # Warehouse dimensions and facts.
    # Employee dimension SCD2 from complete history, with surrogate key.
    d_emp=hist.merge(emp[["emp_id","full_name","plant","hire_date","separation_date","annual_leave_entitlement"]],on="emp_id",how="left")
    d_emp=d_emp.merge(dept[["dept_id","dept_name","plant","cost_center"]],on="dept_id",how="left",suffixes=("_employee","_department"))
    d_emp=d_emp.reset_index(drop=True); d_emp["employee_sk"]=d_emp.index+1
    d_emp=d_emp.rename(columns={"basic_salary":"basic_salary_raw"})
    d_dept=dept.drop_duplicates("dept_id").copy()
    d_shift=pd.DataFrame([{"shift_code":k,**v} for k,v in shifts.items()])
    d_date=pd.DataFrame([{"date_key":d.strftime("%Y%m%d"),"date":d.strftime("%Y-%m-%d"),"year":d.year,"month":d.month,"month_name":d.strftime("%B"),"day":d.day,"weekday":d.strftime("%A"),"is_sunday":int(d.weekday()==6)} for d in pd.date_range("2026-01-01","2026-12-31")])
    sk_by_emp={eid:g.sort_values("valid_from").to_dict("records") for eid,g in d_emp.groupby("emp_id")}
    def employee_sk(eid, ds):
        for row in reversed(sk_by_emp.get(eid,[])):
            if row["valid_from"]<=ds and (not row["valid_to"] or row["valid_to"]>=ds): return int(row["employee_sk"])
        return None
    att["employee_sk"]=[employee_sk(r.emp_id,r.attendance_date) for r in att.itertuples()]
    att["date_key"]=att.attendance_date.str.replace("-","",regex=False)
    ld["employee_sk"]=[employee_sk(r.emp_id,r.leave_date) for r in ld.itertuples()]
    ld["dept_id"]=[(hist_on(r.emp_id,r.leave_date) or {}).get("dept_id","") for r in ld.itertuples()]
    ld["date_key"]=ld.leave_date.str.replace("-","",regex=False)
    payroll=raw["payroll_lines.csv"].copy(); payroll["amount_num"]=pd.to_numeric(payroll.amount,errors="coerce").fillna(0); payroll["units_num"]=pd.to_numeric(payroll.units,errors="coerce")
    ot=raw["overtime_requests.csv"].copy(); ot["approved_hours_num"]=pd.to_numeric(ot.approved_hours,errors="coerce").fillna(0); ot["requested_hours_num"]=pd.to_numeric(ot.requested_hours,errors="coerce").fillna(0)
    payroll_fact=payroll.copy()
    payroll_refs={}
    for eid,pm in payroll_fact[["emp_id","payroll_month"]].drop_duplicates().itertuples(index=False,name=None):
        me=pd.Period(pm).end_time.date(); se=pd.to_datetime(emap[eid]["separation_date"],errors="coerce")
        ref=min(me,se.date()) if pd.notna(se) else me; ref_s=ref.strftime("%Y-%m-%d")
        h=hist_on(eid,ref_s); payroll_refs[(eid,pm)]={"employee_sk":employee_sk(eid,ref_s),"dept_id":h["dept_id"] if h else "","plant":deptinfo.get(h["dept_id"],{}).get("plant",emap[eid]["plant"]) if h else emap[eid]["plant"]}
    payroll_fact["employee_sk"]=[payroll_refs[(r.emp_id,r.payroll_month)]["employee_sk"] for r in payroll_fact.itertuples()]
    payroll_fact["dept_id"]=[payroll_refs[(r.emp_id,r.payroll_month)]["dept_id"] for r in payroll_fact.itertuples()]
    payroll_fact["plant"]=[payroll_refs[(r.emp_id,r.payroll_month)]["plant"] for r in payroll_fact.itertuples()]
    payroll_fact["date_key"]=[(pd.Period(pm).end_time.strftime("%Y%m%d")) for pm in payroll_fact.payroll_month]
    ot_fact=ot[ot.status.str.casefold().eq("approved")].copy()
    ot_fact["employee_sk"]=[employee_sk(r.emp_id,r.ot_date) for r in ot_fact.itertuples()]
    ot_fact["dept_id"]=[(hist_on(r.emp_id,r.ot_date) or {}).get("dept_id","") for r in ot_fact.itertuples()]
    ot_fact["date_key"]=ot_fact.ot_date.str.replace("-","",regex=False)
    # Query-ready monthly consolidated table derived from the warehouse facts.
    pay_ot=payroll[payroll.component.str.upper().eq("OVERTIME")].groupby(["emp_id","payroll_month"],as_index=False).agg(paid_ot_hours=("units_num","sum"),paid_ot_amount=("amount_num","sum"))
    paycost=payroll[payroll.component_type.str.upper().eq("EARNING")].groupby(["emp_id","payroll_month"],as_index=False).agg(payroll_cost=("amount_num","sum"))
    appr=ot[ot.status.str.casefold().eq("approved")].groupby(["emp_id",ot.ot_date.str.slice(0,7)],as_index=False).approved_hours_num.sum().rename(columns={"ot_date":"payroll_month","approved_hours_num":"approved_ot_hours"})
    monthly_att=att.assign(payroll_month=att.attendance_date.str.slice(0,7)).groupby(["emp_id","payroll_month"],as_index=False).agg(punch_ot_hours=("overtime_hours","sum"),attendance_days=("status",lambda s:int((s=="Present").sum())),late_arrivals=("late_minutes",lambda s:int((s>0).sum())))
    # Add monthly plant and department keys based on month-end/last day worked.
    months=[]
    for eid,e in emap.items():
        for pm in map(str,MONTHS):
            me=(pd.Period(pm).end_time.date())
            hire=pd.to_datetime(e["hire_date"],errors="coerce"); sep=pd.to_datetime(e["separation_date"],errors="coerce")
            if pd.isna(hire) or hire.date()>me or (pd.notna(sep) and sep.date()<pd.Period(pm).start_time.date()): continue
            deptid=month_department(eid,me); dinfo=deptinfo.get(deptid,{})
            at_month_end=(pd.isna(sep) or sep.date()>me)
            months.append({"emp_id":eid,"payroll_month":pm,"plant":dinfo.get("plant",e["plant"]),"dept_id":deptid,"department":dinfo.get("dept_name",e["department"]),"month_end_headcount":int(at_month_end)})
    monthly=pd.DataFrame(months)
    for x in [monthly_att,pay_ot,paycost,appr]:
        if "payroll_month" not in x.columns and "ot_date" in x.columns: x["payroll_month"]=x["ot_date"].str.slice(0,7)
    monthly=monthly.merge(monthly_att,on=["emp_id","payroll_month"],how="left").merge(pay_ot,on=["emp_id","payroll_month"],how="left").merge(paycost,on=["emp_id","payroll_month"],how="left").merge(appr,on=["emp_id","payroll_month"],how="left")
    for c in ["punch_ot_hours","attendance_days","late_arrivals","paid_ot_hours","paid_ot_amount","payroll_cost","approved_ot_hours"]: monthly[c]=monthly[c].fillna(0)

    storage_context = locals().copy()
    storage_context["sql_write"] = sql_write
    persist_tables(storage_context)
    analysis_context = locals().copy()
    analysis_context["OUT"] = OUT
    dq_count = write_outputs(analysis_context)
    conn.commit()
    conn.close()
    build_db.replace(db)
    print(f"Built {db}; attendance rows={len(att):,}; rejected punches={len(rejected):,}; DQ checks={dq_count}")

if __name__=="__main__": main()
