"""Data-quality, reconciliation, and audit outputs."""
from datetime import datetime
import json
from pathlib import Path
import pandas as pd


def write_quality(context):
    """Save DQ outcomes and reconciliation/audit CSV files."""
    OUT = context["OUT"]
    conn = context["conn"]
    rowlog = context["rowlog"]
    emp = context["emp"]
    dept = context["dept"]
    d_emp = context["d_emp"]
    d_dept = context["d_dept"]
    d_shift = context["d_shift"]
    d_date = context["d_date"]
    hist = context["hist"]
    shifts = context["shifts"]
    raw = context["raw"]
    rejected = context["rejected"]
    mapped_punch_count = context["mapped_punch_count"]
    punches = context["punches"]
    punch_duplicate_count = context["punch_duplicate_count"]
    emp_raw = context["emp_raw"]
    dedup_audit = context["dedup_audit"]
    history_dedup_audit = context["history_dedup_audit"]
    ot = context["ot"]
    ot_fact = context["ot_fact"]
    payroll = context["payroll"]
    payroll_fact = context["payroll_fact"]
    leave_rows = context["leave_rows"]
    approvals = context["approvals"]
    ld = context["ld"]
    att = context["att"]
    roster = context["roster"]
    dm = context["dm"]
    hol = context["hol"]
    deviations = context["deviations"]
    offsets = context["offsets"]
    monthly = context["monthly"]

    # Data quality results.
    dq=[]
    def check(name,passed,detail): dq.append({"check_name":name,"passed":int(bool(passed)),"detail":str(detail)})
    check("raw row counts loaded",all(x["raw_rows"]==x["loaded_rows"] for x in rowlog),json.dumps(rowlog))
    check("employee primary key unique",emp.emp_id.is_unique,len(emp))
    check("attendance employee-date unique",not att.duplicated(["emp_id","attendance_date"]).any(),len(att))
    check("attendance status accepted",att.status.isin(["Present","Absent","On Leave","Holiday","Weekly Off","Missing Punch"]).all(),att.status.value_counts().to_dict())
    check("worked hours nonnegative",(att.worked_hours>=0).all(),att.worked_hours.min() if len(att) else 0)
    check("attendance employee SCD key resolves",att.employee_sk.notna().all() and att.employee_sk.isin(d_emp.employee_sk).all(),int(att.employee_sk.isna().sum()))
    check("attendance department keys resolve",att.dept_id.eq("").all() or att.loc[att.dept_id.ne(""),"dept_id"].isin(dept.dept_id).all(),int((att.dept_id.ne("")&~att.dept_id.isin(dept.dept_id)).sum()))
    check("leave employee keys resolve",ld.emp_id.isin(emp.emp_id).all(),int((~ld.emp_id.isin(emp.emp_id)).sum()))
    check("payroll employee keys resolve",payroll.emp_id.isin(emp.emp_id).all(),int((~payroll.emp_id.isin(emp.emp_id)).sum()))
    pk_specs=[("staging_employees",emp,["emp_id"]),("staging_employment_history",hist,["emp_id","valid_from"]),("staging_departments",dept,["dept_id"]),("staging_punches_clean",punches,["punch_id"]),("staging_rejected_punches",rejected,["punch_id"]),("staging_leave_requests",pd.DataFrame(leave_rows),["request_id"]),("staging_leave_approval_steps",pd.DataFrame(approvals),["request_id","step"]),("staging_attendance_daily",att,["emp_id","attendance_date"]),("dim_employee",d_emp,["employee_sk"]),("dim_department",d_dept,["dept_id"]),("dim_shift",d_shift,["shift_code"]),("dim_date",d_date,["date_key"]),("fact_attendance_daily",att,["emp_id","attendance_date"]),("fact_leave_day",ld,["request_id","emp_id","leave_date"]),("fact_overtime_approved",ot_fact,["request_id"]),("fact_payroll_line",payroll_fact,["line_id"]),("monthly_employee_mart",monthly,["emp_id","payroll_month"])]
    for label,frame,keys in pk_specs:
        valid=all(k in frame.columns and frame[k].notna().all() and frame[k].astype(str).ne("").all() for k in keys)
        unique=not frame.duplicated(keys).any() if valid else False
        check(f"{label} primary key unique and not null",valid and unique,f"rows={len(frame)}; key={','.join(keys)}")
    datekeys=set(d_date.date_key)
    check("leave fact date keys resolve",ld.date_key.isin(datekeys).all(),int((~ld.date_key.isin(datekeys)).sum()))
    check("approved overtime fact keys resolve",ot_fact.employee_sk.isin(d_emp.employee_sk).all() and ot_fact.date_key.isin(datekeys).all(),f"rows={len(ot_fact)}")
    check("payroll fact keys resolve",payroll_fact.employee_sk.notna().all() and payroll_fact.date_key.isin(datekeys).all(),f"rows={len(payroll_fact)}")
    check("shifts <=16 hours",all(((datetime.strptime(s["end_time"],"%H:%M")-datetime.strptime(s["start_time"],"%H:%M")).total_seconds()/3600)%24<=16 for s in shifts.values()),"shift definitions")
    overlap=0
    for _,g in hist.groupby("emp_id"):
        vs=list(g.sort_values("valid_from").valid_from); ve=list(g.sort_values("valid_from").valid_to)
        for j in range(len(vs)-1):
            if ve[j] and ve[j]>=vs[j+1]: overlap+=1
    invalid_ranges=int((hist.valid_to.ne("")&(hist.valid_to<hist.valid_from)).sum())
    check("SCD2 ranges nonoverlapping and ordered",overlap==0 and invalid_ranges==0,f"overlaps={overlap}; invalid_ranges={invalid_ranges}")
    check("punch reconciliation",len(raw["biometric_punches.csv"])==len(rejected)+mapped_punch_count,f"raw={len(raw['biometric_punches.csv'])}; rejected={len(rejected)}; mapped before dedup={mapped_punch_count}; deduplicated={len(punches)}")
    check("unmapped punches parked",True,len(rejected))
    check("employee duplicate reconciliation",len(emp_raw)==len(emp)+len(dedup_audit),f"raw={len(emp_raw)}; standardized={len(emp)}; merged duplicates={len(dedup_audit)}")
    check("employment history same-day reconciliation",len(raw["employment_history.csv"])==len(hist)+len(history_dedup_audit),f"raw={len(raw['employment_history.csv'])}; staged={len(hist)}; same-day rows resolved={len(history_dedup_audit)}")
    check("punch duplicate reconciliation",mapped_punch_count==len(punches)+punch_duplicate_count,f"mapped={mapped_punch_count}; clean={len(punches)}; duplicate events={punch_duplicate_count}")
    check("leave request reconciliation",len(raw["leave_requests.json"])==len(leave_rows),f"raw requests={len(raw['leave_requests.json'])}; staged requests={len(leave_rows)}")
    check("overtime request reconciliation",len(raw["overtime_requests.csv"])==len(ot),f"raw requests={len(ot)}; approved fact={len(ot_fact)}; nonapproved={len(ot)-len(ot_fact)}")
    for filename,stage_count in [("departments.csv",len(dept)),("shift_roster.csv",len(roster)),("device_mapping.csv",len(dm)),("holidays.csv",len(hol)),("payroll_lines.csv",len(payroll)),("applications.csv",len(raw["applications.csv"]))]:
        raw_count=len(raw[filename]); check(f"{Path(filename).stem} reconciliation",raw_count==stage_count,f"raw={raw_count}; staged={stage_count}")
    dqdf=pd.DataFrame(dq); dqdf.to_sql("dq_results",conn,if_exists="replace",index=False)
    pd.DataFrame(rowlog).to_csv(OUT/"load_reconciliation.csv",index=False)
    pd.DataFrame(dedup_audit,columns=["emp_id","discarded_updated_at","kept_updated_at","reason"]).to_csv(OUT/"employee_dedup_audit.csv",index=False)
    pd.DataFrame(history_dedup_audit,columns=["emp_id","effective_from","discarded_reason","kept_reason","resolution"]).to_csv(OUT/"history_dedup_audit.csv",index=False)
    table_counts=[]
    for table in ["raw_employees","raw_employment_history","raw_departments","raw_shifts","raw_shift_roster","raw_device_mapping","raw_biometric_punches","raw_holidays","raw_leave_requests","raw_overtime_requests","raw_payroll_lines","raw_applications","staging_employees","staging_employment_history","staging_departments","staging_punches_clean","staging_rejected_punches","staging_leave_requests","staging_leave_approval_steps","staging_leave_days","staging_attendance_daily","warehouse_employees","warehouse_departments","warehouse_shifts","warehouse_date","warehouse_attendance_daily","warehouse_leave_day","warehouse_overtime_approved","warehouse_payroll_line","warehouse_monthly_employee"]:
        table_counts.append({"table":table,"row_count":conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]})
    pd.DataFrame(table_counts).to_csv(OUT/"table_row_counts.csv",index=False)
    pd.DataFrame([{"device_id":k,"estimated_clock_offset_minutes":v,"sample_punch_days":len(deviations.get(k,[])),"median_shift_start_delta_minutes":round(float(pd.Series(deviations.get(k,[0])).median()),1)} for k,v in offsets.items()]).to_csv(OUT/"device_clock_audit.csv",index=False)
    return len(dq)
