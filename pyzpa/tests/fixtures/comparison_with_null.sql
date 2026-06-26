BEGIN
  IF x = NULL THEN  -- Noncompliant
    NULL;
  END IF;
  IF y <> NULL THEN  -- Noncompliant
    NULL;
  END IF;
  IF z IS NULL THEN
    NULL;
  END IF;
  IF w = 10 THEN
    NULL;
  END IF;
END;
