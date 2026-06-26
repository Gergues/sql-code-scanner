"""Grammar node-type and token-type constants that checks subscribe to.

These string values must match the rule names (and aliases) declared in
``pyzpa/grammar/plsql.lark`` and the token types produced by the lexer.
"""

from __future__ import annotations


class NodeType:
    # Program units
    ANONYMOUS_BLOCK = "anonymous_block"
    CREATE_PROCEDURE = "create_procedure"
    CREATE_FUNCTION = "create_function"
    NESTED_BLOCK = "nested_block"

    # Declarations
    DECLARE_SECTION = "declare_section"
    VARIABLE_DECLARATION = "variable_declaration"
    PARAMETER = "parameter"
    DATATYPE = "datatype"

    # Statements
    ASSIGNMENT_STATEMENT = "assignment_statement"
    IF_STATEMENT = "if_statement"
    ELSIF_CLAUSE = "elsif_clause"
    ELSE_CLAUSE = "else_clause"
    LOOP_STATEMENT = "loop_statement"
    NULL_STATEMENT = "null_statement"
    RETURN_STATEMENT = "return_statement"
    RAISE_STATEMENT = "raise_statement"
    CALL_STATEMENT = "call_statement"
    SELECT_STATEMENT = "select_statement"
    EXCEPTION_SECTION = "exception_section"
    EXCEPTION_HANDLER = "exception_handler"

    # SELECT internals
    SELECT_ALL_COLUMNS = "select_all_columns"
    SELECT_ITEM = "select_item"
    TABLE_REF = "table_ref"
    WHERE_CLAUSE = "where_clause"

    # Expressions
    EQ_COMPARISON = "eq_comparison"
    NEQ_COMPARISON = "neq_comparison"
    REL_COMPARISON = "rel_comparison"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    FUNCTION_CALL = "function_call"
    QUALIFIED_NAME = "qualified_name"
    NULL_LITERAL = "null_literal"
    NUMBER_LITERAL = "number_literal"
    STRING_LITERAL = "string_literal"

    # Tokens
    NAME = "NAME"


#: Node types that represent executable statements (used by metrics and checks).
STATEMENT_NODE_TYPES = frozenset(
    {
        NodeType.ASSIGNMENT_STATEMENT,
        NodeType.IF_STATEMENT,
        NodeType.LOOP_STATEMENT,
        NodeType.NULL_STATEMENT,
        NodeType.RETURN_STATEMENT,
        NodeType.RAISE_STATEMENT,
        NodeType.CALL_STATEMENT,
        NodeType.SELECT_STATEMENT,
        NodeType.NESTED_BLOCK,
    }
)

#: Node types that add a branch to cyclomatic complexity.
COMPLEXITY_NODE_TYPES = frozenset(
    {
        NodeType.IF_STATEMENT,
        NodeType.ELSIF_CLAUSE,
        NodeType.LOOP_STATEMENT,
        NodeType.EXCEPTION_HANDLER,
    }
)
