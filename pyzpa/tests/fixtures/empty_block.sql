BEGIN
  BEGIN  -- Noncompliant
    NULL;
  END;
  BEGIN
    do_work();
  END;
END;
