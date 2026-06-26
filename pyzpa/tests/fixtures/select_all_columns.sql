BEGIN
  SELECT * INTO v_row FROM employees WHERE id = 1;  -- Noncompliant
  SELECT name, salary INTO v_name, v_sal FROM employees WHERE id = 2;
END;
