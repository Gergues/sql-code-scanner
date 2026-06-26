"""Parser-level smoke tests."""

from __future__ import annotations

from pyzpa.api.nodes import NodeType
from pyzpa.parser.parser import PlSqlParser

PROCEDURE = """
CREATE OR REPLACE PROCEDURE greet(p_name IN VARCHAR2) IS
  v_msg VARCHAR2(100);
BEGIN
  v_msg := 'hello';
  IF p_name IS NULL THEN
    RETURN;
  END IF;
END greet;
"""


def test_parse_procedure_builds_ast():
    result = PlSqlParser().parse(PROCEDURE)
    assert result.ok, result.error
    assert result.ast is not None

    procs = list(result.ast.descendants_of_type(NodeType.CREATE_PROCEDURE))
    assert len(procs) == 1

    assigns = list(result.ast.descendants_of_type(NodeType.ASSIGNMENT_STATEMENT))
    assert len(assigns) == 1
    assert assigns[0].line == 5


def test_parse_reports_error_for_garbage():
    result = PlSqlParser().parse("BEGIN this is not valid")
    assert not result.ok
    assert result.error is not None


def test_comments_extracted():
    result = PlSqlParser().parse("BEGIN NULL; END; -- trailing")
    assert any("trailing" in c.text for c in result.comments)
