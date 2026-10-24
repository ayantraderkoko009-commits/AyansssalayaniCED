-- SQLite constraints applied by run_pipeline.py after each rebuild.
-- UNIQUE indexes enforce primary-key uniqueness. Triggers enforce foreign-key lookups.
CREATE UNIQUE INDEX ux_dim_employee_sk ON warehouse_employees(employee_sk);
CREATE UNIQUE INDEX ux_dim_department_id ON warehouse_departments(dept_id);
CREATE UNIQUE INDEX ux_dim_shift_code ON warehouse_shifts(shift_code);
CREATE UNIQUE INDEX ux_dim_date_key ON warehouse_date(date_key);
CREATE UNIQUE INDEX ux_fact_attendance_emp_date ON warehouse_attendance_daily(emp_id, attendance_date);
CREATE UNIQUE INDEX ux_fact_payroll_line ON warehouse_payroll_line(line_id);
CREATE UNIQUE INDEX ux_fact_overtime_request ON warehouse_overtime_approved(request_id);
CREATE UNIQUE INDEX ux_monthly_employee_month ON warehouse_monthly_employee(emp_id, payroll_month);

CREATE TRIGGER fk_attendance_insert BEFORE INSERT ON warehouse_attendance_daily
WHEN NOT EXISTS (SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk)
 OR NOT EXISTS (SELECT 1 FROM warehouse_shifts WHERE shift_code=NEW.shift_code)
 OR (NEW.dept_id<>'' AND NOT EXISTS (SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id))
 OR NOT EXISTS (SELECT 1 FROM warehouse_date WHERE date=NEW.attendance_date)
BEGIN SELECT RAISE(ABORT, 'attendance dimension reference missing'); END;

CREATE TRIGGER fk_leave_insert BEFORE INSERT ON warehouse_leave_day
WHEN NOT EXISTS (SELECT 1 FROM staging_employees WHERE emp_id=NEW.emp_id)
 OR NOT EXISTS (SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk)
 OR NOT EXISTS (SELECT 1 FROM warehouse_date WHERE date_key=NEW.date_key)
 OR (NEW.dept_id<>'' AND NOT EXISTS (SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id))
BEGIN SELECT RAISE(ABORT, 'leave dimension reference missing'); END;

CREATE TRIGGER fk_payroll_insert BEFORE INSERT ON warehouse_payroll_line
WHEN NOT EXISTS (SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk)
 OR NOT EXISTS (SELECT 1 FROM warehouse_date WHERE date_key=NEW.date_key)
 OR (NEW.dept_id<>'' AND NOT EXISTS (SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id))
BEGIN SELECT RAISE(ABORT, 'payroll employee reference missing'); END;

CREATE TRIGGER fk_overtime_insert BEFORE INSERT ON warehouse_overtime_approved
WHEN NOT EXISTS (SELECT 1 FROM warehouse_employees WHERE employee_sk=NEW.employee_sk)
 OR NOT EXISTS (SELECT 1 FROM warehouse_date WHERE date_key=NEW.date_key)
 OR (NEW.dept_id<>'' AND NOT EXISTS (SELECT 1 FROM warehouse_departments WHERE dept_id=NEW.dept_id))
BEGIN SELECT RAISE(ABORT, 'overtime employee reference missing'); END;
