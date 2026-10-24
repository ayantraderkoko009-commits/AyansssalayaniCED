"""Business-query outputs and pipeline data-quality reports."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import pandas as pd

if not __package__:
    raise SystemExit(
        "This is a helper module. From the SMiT PROJECT folder, run "
        "python run_pipeline.py --input-dir \"C:\\Users\\Lenovo\\Downloads\" instead."
    )

from pipeline.quality import write_quality


def write_outputs(context):
    """Write Q1-Q10 outputs, SQL companions, audits, and DQ results."""
    OUT = context["OUT"]
    monthly = context["monthly"]
    emp = context["emp"]
    month_department = context["month_department"]
    emap = context["emap"]
    deptinfo = context["deptinfo"]
    att = context["att"]
    monthly_att = context["monthly_att"]
    paycost = context["paycost"]
    ld = context["ld"]
    dept = context["dept"]
    conn = context["conn"]
    rowlog = context["rowlog"]
    d_emp = context["d_emp"]
    payroll = context["payroll"]
    ot = context["ot"]
    roster = context["roster"]
    dm = context["dm"]
    hol = context["hol"]
    raw = context["raw"]
    mapped_punch_count = context["mapped_punch_count"]
    punches = context["punches"]
    punch_duplicate_count = context["punch_duplicate_count"]
    ot_fact = context["ot_fact"]
    leave_rows = context["leave_rows"]
    approvals = context["approvals"]
    history_dedup_audit = context["history_dedup_audit"]
    dedup_audit = context["dedup_audit"]
    deviations = context["deviations"]
    offsets = context["offsets"]
    payroll_fact = context["payroll_fact"]
    d_date = context["d_date"]
    d_shift = context["d_shift"]
    d_dept = context["d_dept"]
    hist = context["hist"]
    shifts = context["shifts"]
    rejected = context["rejected"]
    emp_raw = context["emp_raw"]

    # Query answers as CSVs. Queries are also saved as SQL in analytics/.
    qdir=OUT/"analytics"; resdir=qdir/"results"; qdir.mkdir(exist_ok=True); resdir.mkdir(exist_ok=True)
    # Compact result sets built from trusted monthly and daily tables.
    q1=monthly.groupby(["payroll_month","plant","department"],as_index=False).month_end_headcount.sum().rename(columns={"payroll_month":"month","department":"department","month_end_headcount":"headcount"})
    sep_rows=[]
    for r in emp.to_dict("records"):
        if r["separation_date"]:
            m=r["separation_date"][:7]
            if "2026-04"<=m<="2026-09":
                d=month_department(r["emp_id"],pd.to_datetime(r["separation_date"]).date())
                sep_rows.append({"month":m,"emp_id":r["emp_id"],"dept_id":d})
    sepdf=pd.DataFrame(sep_rows)
    head=monthly.groupby(["payroll_month","dept_id"],as_index=False).month_end_headcount.sum().rename(columns={"payroll_month":"month","month_end_headcount":"hc"})
    if len(sepdf): sepagg=sepdf.groupby(["month","dept_id"],as_index=False).emp_id.nunique().rename(columns={"emp_id":"separations"})
    else: sepagg=pd.DataFrame(columns=["month","dept_id","separations"])
    # Average monthly headcount uses opening and closing headcount by the department held on each date.
    q2rows=[]
    for _,hr in head.iterrows():
        pm=hr["month"]; begin=pd.Period(pm).start_time.date()-timedelta(days=1)
        opening=0
        for eid,e in emap.items():
            hire=pd.to_datetime(e["hire_date"],errors="coerce"); sep=pd.to_datetime(e["separation_date"],errors="coerce")
            if pd.notna(hire) and hire.date()<=begin and (pd.isna(sep) or sep.date()>begin) and month_department(eid,begin)==hr["dept_id"]: opening+=1
        nsep=int(sepagg[(sepagg.month==pm)&(sepagg.dept_id==hr["dept_id"])].separations.sum()) if len(sepagg) else 0
        avg=(opening+int(hr["hc"]))/2
        q2rows.append({"month":pm,"dept_id":hr["dept_id"],"dept_name":deptinfo.get(hr["dept_id"],{}).get("dept_name",""),"opening_headcount":opening,"closing_headcount":int(hr["hc"]),"average_headcount":avg,"separations":nsep,"attrition_rate":nsep/avg if avg else None})
    q2=pd.DataFrame(q2rows)
    q3=att.assign(month=att.attendance_date.str.slice(0,7),workday=~att.status.isin(["Weekly Off","Holiday","On Leave"])).groupby(["month","plant"],as_index=False).agg(absent_days=("status",lambda s:int((s=="Absent").sum())),eligible_days=("workday","sum")); q3["absenteeism_rate"]=q3.absent_days/q3.eligible_days.replace(0,pd.NA)
    q4=att[att.late_minutes>0].groupby("emp_id",as_index=False).agg(late_arrivals=("late_minutes","size"),late_minutes=("late_minutes","sum")); q4=q4.merge(emp[["emp_id","full_name"]],on="emp_id",how="left"); q4["dept_id"]=[month_department(e,"2026-09-30") for e in q4.emp_id]; q4=q4.merge(dept[["dept_id","dept_name"]],on="dept_id",how="left").sort_values(["late_arrivals","late_minutes"],ascending=False).head(10)
    q5=monthly.groupby(["payroll_month","department"],as_index=False).agg(punch_overtime_hours=("punch_ot_hours","sum"),approved_overtime_hours=("approved_ot_hours","sum"),paid_overtime_hours=("paid_ot_hours","sum")); q5=q5.rename(columns={"payroll_month":"month"})
    q6=q5.copy(); q6["paid_vs_computed_pct"]=(q6.paid_overtime_hours-q6.punch_overtime_hours)/q6.punch_overtime_hours.replace(0,pd.NA); q6=q6[q6.paid_vs_computed_pct>0.15]
    attmonth=set(zip(monthly_att.emp_id,monthly_att.payroll_month)); paid=set(zip(paycost.emp_id,paycost.payroll_month)); q7=pd.DataFrame([{"emp_id":e,"month":m} for e,m in paid if (e,m) not in attmonth]); q7=q7.merge(emp[["emp_id","full_name"]],on="emp_id",how="left") if len(q7) else q7
    q8=paycost.merge(emp[["emp_id","separation_date"]],on="emp_id",how="left"); q8=q8[(q8.separation_date!="")&(q8.apply(lambda r:r.payroll_month>r.separation_date[:7],axis=1))][["emp_id","payroll_month","payroll_cost","separation_date"]]
    q9=monthly.groupby(["payroll_month","department"],as_index=False).agg(payroll_cost=("payroll_cost","sum"),employees=("emp_id","nunique")); q9["cost_per_employee"]=q9.payroll_cost/q9.employees.replace(0,pd.NA); q9=q9.sort_values(["department","payroll_month"]); q9["mom_change_pct"]=q9.groupby("department").cost_per_employee.pct_change()
    ann=ld[ld.leave_type.str.casefold().eq("annual")].groupby("emp_id",as_index=False).leave_date.nunique().rename(columns={"leave_date":"approved_annual_days"}); q10=ann.merge(emp[["emp_id","full_name","annual_leave_entitlement"]],on="emp_id",how="left"); q10=q10[pd.to_numeric(q10.annual_leave_entitlement,errors="coerce")<q10.approved_annual_days]
    results=[q1,q2,q3,q4,q5,q6,q7,q8,q9,q10]
    for i,df in enumerate(results,1): df.to_csv(resdir/f"q{i:02d}_result.csv",index=False)
    # SQL companion files document the logic against the query-ready warehouse tables.
    queries={
    1:"SELECT payroll_month AS month, plant, department, SUM(month_end_headcount) AS headcount FROM warehouse_monthly_employee GROUP BY 1,2,3 ORDER BY 1,2,3;",
    2:"WITH months AS (SELECT DISTINCT payroll_month month FROM warehouse_monthly_employee), head AS (SELECT payroll_month month,dept_id,SUM(month_end_headcount) closing_headcount FROM warehouse_monthly_employee GROUP BY 1,2), opening AS (SELECT m.month,d.dept_id,COUNT(h.emp_id) opening_headcount FROM months m CROSS JOIN warehouse_departments d LEFT JOIN staging_employees e ON e.hire_date<=date(m.month||'-01','-1 day') AND (e.separation_date='' OR e.separation_date>date(m.month||'-01','-1 day')) LEFT JOIN warehouse_employees h ON h.emp_id=e.emp_id AND h.valid_from<=date(m.month||'-01','-1 day') AND (h.valid_to='' OR h.valid_to>=date(m.month||'-01','-1 day')) AND h.dept_id=d.dept_id GROUP BY 1,2), sep AS (SELECT substr(e.separation_date,1,7) month,h.dept_id,COUNT(DISTINCT e.emp_id) separations FROM staging_employees e JOIN warehouse_employees h ON h.emp_id=e.emp_id AND h.valid_from<=e.separation_date AND (h.valid_to='' OR h.valid_to>=e.separation_date) WHERE e.separation_date<>'' GROUP BY 1,2) SELECT h.month,d.dept_name,o.opening_headcount,h.closing_headcount,(o.opening_headcount+h.closing_headcount)/2.0 average_headcount,COALESCE(s.separations,0) separations,COALESCE(s.separations,0)/NULLIF((o.opening_headcount+h.closing_headcount)/2.0,0) attrition_rate FROM head h JOIN opening o ON o.month=h.month AND o.dept_id=h.dept_id JOIN warehouse_departments d ON d.dept_id=h.dept_id LEFT JOIN sep s ON s.month=h.month AND s.dept_id=h.dept_id ORDER BY 1,2;",
    3:"SELECT substr(attendance_date,1,7) month, plant, SUM(status='Absent') absent_days, SUM(status NOT IN ('Weekly Off','Holiday','On Leave')) eligible_days FROM warehouse_attendance_daily GROUP BY 1,2;",
    4:"WITH late AS (SELECT emp_id,SUM(CASE WHEN late_minutes>0 THEN 1 ELSE 0 END) late_arrivals,SUM(late_minutes) late_minutes FROM warehouse_attendance_daily GROUP BY emp_id), ref AS (SELECT e.emp_id,e.full_name,CASE WHEN e.separation_date<>'' AND e.separation_date<'2026-09-30' THEN e.separation_date ELSE '2026-09-30' END asof_date FROM staging_employees e) SELECT l.emp_id,l.late_arrivals,l.late_minutes,r.full_name,d.dept_id,d.dept_name FROM late l JOIN ref r USING(emp_id) LEFT JOIN warehouse_employees h ON h.emp_id=l.emp_id AND h.valid_from<=r.asof_date AND (h.valid_to='' OR h.valid_to>=r.asof_date) LEFT JOIN warehouse_departments d ON d.dept_id=h.dept_id WHERE l.late_arrivals>0 ORDER BY l.late_arrivals DESC,l.late_minutes DESC LIMIT 10;",
    5:"SELECT payroll_month AS month, department, SUM(punch_ot_hours) punch_overtime_hours, SUM(approved_ot_hours) approved_overtime_hours, SUM(paid_ot_hours) paid_overtime_hours FROM warehouse_monthly_employee GROUP BY 1,2;",
    6:"WITH x AS (SELECT payroll_month,department,SUM(punch_ot_hours) punch_overtime_hours,SUM(approved_ot_hours) approved_overtime_hours,SUM(paid_ot_hours) paid_overtime_hours FROM warehouse_monthly_employee GROUP BY 1,2) SELECT *, (paid_overtime_hours-punch_overtime_hours)/punch_overtime_hours paid_vs_computed_pct FROM x WHERE punch_overtime_hours>0 AND (paid_overtime_hours-punch_overtime_hours)/punch_overtime_hours>0.15;",
    7:"SELECT DISTINCT p.emp_id,p.payroll_month,e.full_name FROM warehouse_payroll_line p JOIN staging_employees e USING(emp_id) LEFT JOIN warehouse_attendance_daily a ON a.emp_id=p.emp_id AND substr(a.attendance_date,1,7)=p.payroll_month WHERE p.component_type='EARNING' GROUP BY 1,2,3 HAVING COUNT(a.attendance_date)=0;",
    8:"SELECT p.emp_id,p.payroll_month,SUM(p.amount_num) payroll_cost,e.separation_date FROM warehouse_payroll_line p JOIN staging_employees e USING(emp_id) WHERE p.component_type='EARNING' AND e.separation_date<>'' AND p.payroll_month>substr(e.separation_date,1,7) GROUP BY 1,2,4;",
    9:"WITH totals AS (SELECT payroll_month,department,SUM(payroll_cost) payroll_cost,COUNT(DISTINCT emp_id) employees,SUM(payroll_cost)/COUNT(DISTINCT emp_id) cost_per_employee FROM warehouse_monthly_employee GROUP BY 1,2) SELECT *,cost_per_employee/NULLIF(LAG(cost_per_employee) OVER(PARTITION BY department ORDER BY payroll_month),0)-1 AS mom_change_pct FROM totals ORDER BY department,payroll_month;",
    10:"SELECT l.emp_id,COUNT(DISTINCT l.leave_date) approved_annual_days,e.annual_leave_entitlement FROM warehouse_leave_day l JOIN staging_employees e USING(emp_id) WHERE lower(l.leave_type)='annual' GROUP BY 1,3 HAVING COUNT(DISTINCT l.leave_date)>CAST(e.annual_leave_entitlement AS INTEGER);"
    }
    for i,q in enumerate(queries.values(),1): (qdir/f"q{i:02d}.sql").write_text(q+"\n",encoding="utf-8")
    quality_context = dict(context)
    quality_context.update(locals())
    return write_quality(quality_context)
    print(write_quality)
