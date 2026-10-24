SELECT substr(attendance_date,1,7) month, plant, SUM(status='Absent') absent_days, SUM(status NOT IN ('Weekly Off','Holiday','On Leave')) eligible_days FROM warehouse_attendance_daily GROUP BY 1,2;
