"""Biometric cleaning, leave expansion, and daily attendance calculations."""
from datetime import date, datetime, time, timedelta
import pandas as pd


def build_attendance(context):
    """Clean punches and produce leave-day and daily attendance records."""
    punches=context["punches"]
    rejected=context["rejected"]
    mapped_punch_count=context["mapped_punch_count"]
    emp=context["emp"]
    emap=context["emap"]
    shift_for=context["shift_for"]
    shifts=context["shifts"]
    hist=context["hist"]
    dept=context["dept"]
    roster=context["roster"]
    raw=context["raw"]
    dt=context["dt"]
    pd=context["pd"]
    date=context["date"]
    datetime=context["datetime"]
    time=context["time"]
    timedelta=context["timedelta"]

    # Estimate per-device clock offset from first punches vs the employee's rostered shift start.
    punches["calendar_date"]=punches.timestamp.dt.date
    firsts=punches.sort_values("timestamp").groupby(["emp_id","calendar_date"],as_index=False).first()
    deviations={}
    for row in firsts.itertuples():
        e=emap.get(row.emp_id)
        if not e: continue
        day=row.calendar_date
        code=shift_for(row.emp_id,day)
        sh=shifts.get(code,shifts["GEN"])
        expected=datetime.combine(day,time.fromisoformat(sh["start_time"]))
        actual=row.timestamp.to_pydatetime()
        delta=(actual-expected).total_seconds()/60
        # For night shifts a first punch after midnight is associated with previous day's night.
        if code=="NIGHT" and actual.hour<12:
            expected-=timedelta(days=1); delta=(actual-expected).total_seconds()/60
        deviations.setdefault(row.device_id,[]).append(delta)
    offsets={}
    for dev,vals in deviations.items():
        med=float(pd.Series(vals).median())
        offsets[dev]=int(round(med/60))*60 if abs(med)>=35 and abs(med)<=85 else 0
    punches["clock_offset_minutes"]=punches.device_id.map(offsets).fillna(0).astype(int)
    punches["corrected_time"]=punches.timestamp-pd.to_timedelta(punches.clock_offset_minutes,unit="m")
    punches=punches.sort_values(["emp_id","corrected_time"])
    # Remove any same-employee punch within two minutes of the prior retained punch.
    kept=[]; previous={}
    for r in punches.itertuples():
        prev=previous.get(r.emp_id)
        if prev is not None and (r.corrected_time-prev).total_seconds()<=120: continue
        kept.append(r.Index); previous[r.emp_id]=r.corrected_time
    punches=punches.loc[kept].copy()
    punch_duplicate_count=mapped_punch_count-len(punches)
    # Assign punch to a shift date, evaluating the current and previous calendar date against shift windows.
    def assign_shift_date(eid, ts):
        ts=ts.to_pydatetime(); candidates=[]
        for d in [ts.date()-timedelta(days=1),ts.date(),ts.date()+timedelta(days=1)]:
            code=shift_for(eid,d); sh=shifts.get(code,shifts["GEN"])
            start=datetime.combine(d,time.fromisoformat(sh["start_time"]))
            end=datetime.combine(d+(timedelta(days=1) if sh["crosses_midnight"] else timedelta()),time.fromisoformat(sh["end_time"]))
            dist=0 if start<=ts<=end+timedelta(hours=8) else min(abs((ts-start).total_seconds()),abs((ts-end).total_seconds()))
            candidates.append((dist,d,code))
        _,d,code=min(candidates,key=lambda x:x[0]); return d,code
    asn=[assign_shift_date(r.emp_id,r.corrected_time) for r in punches.itertuples()]
    punches["shift_date"]=[x[0].isoformat() for x in asn]; punches["shift_code"]=[x[1] for x in asn]
    grouped={}
    for (eid,sd),g in punches.groupby(["emp_id","shift_date"]):
        ts=sorted(g.corrected_time.tolist()); grouped[(eid,sd)]=ts

    hol=raw["holidays.csv"].copy(); hol["holiday_date"]=dt(hol.holiday_date).dt.strftime("%Y-%m-%d")
    plantcode={"Head Office":"HO","Korangi Plant":"KOR","SITE Plant":"SITE","Faisalabad Plant":"FSD"}
    holidays={(r.holiday_date,r.scope) for r in hol.itertuples()}
    # Expand approved leave excluding Sundays and relevant plant holidays.
    leave_raw=raw["leave_requests.json"]; leave_rows=[]; approvals=[]; leave_days=[]
    for req in leave_raw:
        approvals_for=req.get("approvals",[])
        for a in approvals_for: approvals.append({"request_id":req.get("request_id"),**a})
        acts={a.get("approver_role"):a.get("action") for a in approvals_for}
        approved=(acts.get("Manager")=="Approved" and acts.get("HR")=="Approved" and not req.get("cancelled_at"))
        l=req.get("leave",{}); e=req.get("employee",{})
        start=pd.to_datetime(l.get("from"),errors="coerce"); end=pd.to_datetime(l.get("to"),errors="coerce")
        leave_rows.append({"request_id":req.get("request_id"),"emp_id":e.get("emp_id"),"plant":e.get("plant"),"leave_type":l.get("type"),"from_date":start.strftime("%Y-%m-%d") if pd.notna(start) else "","to_date":end.strftime("%Y-%m-%d") if pd.notna(end) else "","approved":int(approved),"cancelled_at":req.get("cancelled_at") or ""})
        if approved and pd.notna(start) and pd.notna(end):
            for d in pd.date_range(start,end):
                ds=d.strftime("%Y-%m-%d"); code=plantcode.get(e.get("plant"),"")
                if d.weekday()==6 or (ds,"ALL") in holidays or (ds,code) in holidays: continue
                leave_days.append({"request_id":req.get("request_id"),"emp_id":e.get("emp_id"),"leave_date":ds,"leave_type":l.get("type")})
    ld=pd.DataFrame(leave_days,columns=["request_id","emp_id","leave_date","leave_type"])
    leave_set={(r.emp_id,r.leave_date) for r in ld.itertuples()}
    leave_type_by={(r.emp_id,r.leave_date):r.leave_type for r in ld.itertuples()}

    # Department validity is sourced from employment history.
    deptinfo=dept.set_index("dept_id").to_dict("index")
    hist_by_emp={eid:g.sort_values("valid_from").to_dict("records") for eid,g in hist.groupby("emp_id")}
    def hist_on(eid, ds):
        if isinstance(ds,(date,datetime)): ds=ds.strftime("%Y-%m-%d")
        for row in reversed(hist_by_emp.get(eid,[])):
            if row["valid_from"]<=ds and (not row["valid_to"] or row["valid_to"]>=ds): return row
        return None
    def month_department(eid, month_end):
        if isinstance(month_end,str): month_end=pd.to_datetime(month_end).date()
        e=emap[eid]; sep=e["separation_date"]
        sep_date=pd.to_datetime(sep,errors="coerce").date() if sep else None
        d=min(month_end,sep_date) if sep_date else month_end
        h=hist_on(eid,d)
        if h and h["dept_id"] in deptinfo: return h["dept_id"]
        return next((k for k,v in deptinfo.items() if v["dept_name"].casefold()==str(e["department"]).casefold()),"")
    # Attendance daily, for employed dates in the six-month case window.
    attendance=[]
    for eid,e in emap.items():
        hire=pd.to_datetime(e["hire_date"],errors="coerce"); sep=pd.to_datetime(e["separation_date"],errors="coerce")
        if pd.isna(hire): continue
        lo=max(hire.date(),date(2026,4,1)); hi=min(sep.date() if pd.notna(sep) else date(2026,9,30),date(2026,9,30))
        if lo>hi: continue
        d=lo
        while d<=hi:
            ds=d.isoformat(); code=shift_for(eid,d); sh=shifts.get(code,shifts["GEN"])
            p=grouped.get((eid,ds),[])
            plant=e["plant"]; hday=(ds,"ALL") in holidays or (ds,plantcode.get(plant,"")) in holidays
            if d.weekday()==6 and not p: status="Weekly Off"
            elif hday and not p: status="Holiday"
            elif (eid,ds) in leave_set: status="On Leave"
            elif len(p)>=2: status="Present"
            elif len(p)==1: status="Missing Punch"
            else: status="Absent"
            if p:
                checkin=p[0]; checkout=p[-1] if len(p)>=2 else None
                start=datetime.combine(d,time.fromisoformat(sh["start_time"]))
                end=datetime.combine(d+(timedelta(days=1) if sh["crosses_midnight"] else timedelta()),time.fromisoformat(sh["end_time"]))
                work=max(0,(checkout-checkin).total_seconds()/3600) if checkout else 0
                working_present=(status=="Present" and d.weekday()!=6 and not hday)
                late=max(0,(checkin.to_pydatetime()-start).total_seconds()/60-10) if working_present else 0
                early=max(0,(end-checkout.to_pydatetime()).total_seconds()/60-10) if checkout and working_present else 0
                if d.weekday()==6 or hday: otmins=(checkout-checkin).total_seconds()/60 if checkout else 0
                elif status=="Present": otmins=max(0,(checkout.to_pydatetime()-end).total_seconds()/60)
                else: otmins=0
                overtime=(int(otmins//30)*0.5)
            else: checkin=checkout=None; work=late=early=overtime=0
            h=hist_on(eid,ds); deptid=h["dept_id"] if h else ""
            attendance.append({"emp_id":eid,"attendance_date":ds,"plant":plant,"dept_id":deptid,"shift_code":code,"status":status,"check_in":checkin.isoformat(sep=" ") if checkin else "","check_out":checkout.isoformat(sep=" ") if checkout else "","worked_hours":round(work,2),"late_minutes":round(late,1),"early_departure_minutes":round(early,1),"overtime_hours":overtime})
            d+=timedelta(days=1)
    att=pd.DataFrame(attendance)
    state = locals()
    return {name: state[name] for name in ['punches', 'rejected', 'mapped_punch_count', 'deviations', 'offsets', 'punch_duplicate_count', 'grouped', 'hol', 'plantcode', 'holidays', 'leave_rows', 'approvals', 'leave_days', 'ld', 'leave_set', 'leave_type_by', 'deptinfo', 'hist_by_emp', 'hist_on', 'month_department', 'attendance', 'att']}
