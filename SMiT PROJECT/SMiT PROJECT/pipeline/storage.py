"""SQLite persistence for staging, warehouse tables, and key constraints."""
import pandas as pd


def persist_tables(context):
    """Write standardized tables and warehouse key/reference constraints."""
    conn = context["conn"]
    emp = context["emp"]
    hist = context["hist"]
    dept = context["dept"]
    rejected = context["rejected"]
    punches = context["punches"]
    leave_rows = context["leave_rows"]
    approvals = context["approvals"]
    ld = context["ld"]
    att = context["att"]
    d_emp = context["d_emp"]
    d_dept = context["d_dept"]
    d_shift = context["d_shift"]
    d_date = context["d_date"]
    ot_fact = context["ot_fact"]
    payroll_fact = context["payroll_fact"]
    monthly = context["monthly"]
    raw = context["raw"]
    sql_write = context["sql_write"]

    # Persist staging/warehouse tables.
    sql_write(conn,"employees",emp.drop(columns=["updated_dt"],errors="ignore")); sql_write(conn,"employment_history",hist.drop(columns=["effective_from_dt","_source_order"],errors="ignore")); sql_write(conn,"departments",dept); sql_write(conn,"rejected_punches",rejected); sql_write(conn,"punches_clean",punches.drop(columns=["timestamp","calendar_date"],errors="ignore")); sql_write(conn,"leave_requests",pd.DataFrame(leave_rows)); sql_write(conn,"leave_approval_steps",pd.DataFrame(approvals)); sql_write(conn,"leave_days",ld); sql_write(conn,"attendance_daily",att); sql_write(conn,"employees",d_emp,schema="warehouse"); sql_write(conn,"departments",d_dept,schema="warehouse"); sql_write(conn,"shifts",d_shift,schema="warehouse"); sql_write(conn,"date",d_date,schema="warehouse"); sql_write(conn,"attendance_daily",att,schema="warehouse"); sql_write(conn,"leave_day",ld,schema="warehouse"); sql_write(conn,"overtime_approved",ot_fact,schema="warehouse"); sql_write(conn,"payroll_line",payroll_fact,schema="warehouse"); sql_write(conn,"monthly_employee",monthly,schema="warehouse"); sql_write(conn,"applications",raw["applications.csv"],schema="staging")
    # SQLite unique indexes enforce dimension and fact keys; triggers enforce the warehouse references.
    for sql in [
        "CREATE UNIQUE INDEX ux_dim_employee_sk ON warehouse_employees(employee_sk)",
        "CREATE UNIQUE INDEX ux_dim_department_id ON warehouse_departments(dept_id)",
        "CREATE UNIQUE INDEX ux_dim_shift_code ON warehouse_shifts(shift_code)",
        "CREATE UNIQUE INDEX ux_dim_date_key ON warehouse_date(date_key)",
        "CREATE UNIQUE INDEX ux_fact_attendance_emp_date ON warehouse_attendance_daily(emp_id,attendance_date)",
        "CREATE UNIQUE INDEX ux_fact_payroll_line ON warehouse_payroll_line(line_id)",
        "CREATE UNIQUE INDEX ux_fact_overtime_request ON warehouse_overtime_approved(request_id)",
        "CREATE UNIQUE INDEX ux_monthly_employee_month ON warehouse_monthly_employee(emp_id,payroll_month)",
        "CREATE TRIGGER fk_attendance_insert BEFORE INSERT ON warehouse_attendance_daily WHEN NOT EXISTS(SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk) OR NOT EXISTS(SELECT 1 FROM warehouse_shifts WHERE shift_code=NEW.shift_code) OR (NEW.dept_id<>'' AND NOT EXISTS(SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id)) OR NOT EXISTS(SELECT 1 FROM warehouse_date WHERE date=NEW.attendance_date) BEGIN SELECT RAISE(ABORT,'attendance dimension reference missing'); END",
        "CREATE TRIGGER fk_attendance_update BEFORE UPDATE ON warehouse_attendance_daily WHEN NOT EXISTS(SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk) OR NOT EXISTS(SELECT 1 FROM warehouse_shifts WHERE shift_code=NEW.shift_code) OR (NEW.dept_id<>'' AND NOT EXISTS(SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id)) OR NOT EXISTS(SELECT 1 FROM warehouse_date WHERE date=NEW.attendance_date) BEGIN SELECT RAISE(ABORT,'attendance dimension reference missing'); END",
        "CREATE TRIGGER fk_leave_insert BEFORE INSERT ON warehouse_leave_day WHEN NOT EXISTS(SELECT 1 FROM staging_employees WHERE emp_id=NEW.emp_id) OR NOT EXISTS(SELECT 1 FROM warehouse_date WHERE date=NEW.leave_date) BEGIN SELECT RAISE(ABORT,'leave dimension reference missing'); END",
        "CREATE TRIGGER fk_leave_dim_insert BEFORE INSERT ON warehouse_leave_day WHEN NOT EXISTS(SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk) OR NOT EXISTS(SELECT 1 FROM warehouse_date WHERE date_key=NEW.date_key) OR (NEW.dept_id<>'' AND NOT EXISTS(SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id)) BEGIN SELECT RAISE(ABORT,'leave warehouse reference missing'); END",
        "CREATE TRIGGER fk_payroll_insert BEFORE INSERT ON warehouse_payroll_line WHEN NOT EXISTS(SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk) OR NOT EXISTS(SELECT 1 FROM warehouse_date WHERE date_key=NEW.date_key) OR (NEW.dept_id<>'' AND NOT EXISTS(SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id)) BEGIN SELECT RAISE(ABORT,'payroll warehouse reference missing'); END",
        "CREATE TRIGGER fk_overtime_insert BEFORE INSERT ON warehouse_overtime_approved WHEN NOT EXISTS(SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk) OR NOT EXISTS(SELECT 1 FROM warehouse_date WHERE date_key=NEW.date_key) OR (NEW.dept_id<>'' AND NOT EXISTS(SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id)) BEGIN SELECT RAISE(ABORT,'overtime warehouse reference missing'); END"
    ]: conn.execute(sql)

