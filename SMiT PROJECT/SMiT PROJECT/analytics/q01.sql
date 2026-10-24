SELECT payroll_month AS month, plant, department, SUM(month_end_headcount) AS headcount FROM warehouse_monthly_employee GROUP BY 1,2,3 ORDER BY 1,2,3;
