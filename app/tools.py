"""Tool definitions + dispatch for the chat tool-calling loop (Step 6, Part B).

Tools are safe by construction:
- `calculator` only evaluates arithmetic via the `ast` module — never `eval()`.
- `search_project_files` reads only the project's own embedded chunks.

The model may request at most MAX_TOOL_TURNS rounds before the endpoint gives up.
"""

import ast
import operator

from app.rag import RETRIEVAL_LIMIT, embed_query, search_chunks

MAX_TOOL_TURNS = 4

_MAX_EXPONENT = 512

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate_expression(expression: str) -> str:
    """Safely evaluate an arithmetic expression, returning a string result.

    Only numeric literals and the binary/unary operators in _BINOPS/_UNARY_OPS
    are accepted. Anything else raises ValueError.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {exc.msg}") from exc
    value = _eval_node(tree.body)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _eval_node(node) -> int | float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("Only numeric literals are allowed")
    if isinstance(node, ast.BinOp):
        op = type(node.op)
        if op not in _BINOPS:
            raise ValueError(f"Operator not allowed: {node.op.__class__.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op is ast.Pow and abs(right) > _MAX_EXPONENT:
            raise ValueError("Exponent too large")
        return _BINOPS[op](left, right)
    if isinstance(node, ast.UnaryOp):
        op = type(node.op)
        if op not in _UNARY_OPS:
            raise ValueError(f"Operator not allowed: {node.op.__class__.__name__}")
        return _UNARY_OPS[op](_eval_node(node.operand))
    raise ValueError("Unsupported expression")


def execute_tool(name: str, arguments: dict, db, project_id, embedder) -> str:
    """Dispatch a tool call to its implementation and return the result text.

    Raises ValueError only for unknown tool names; individual tool failures are
    returned as an "Error: ..." string so the model can recover mid-loop.
    """
    if name == "calculator":
        expression = (arguments.get("expression") or "").strip()
        try:
            return evaluate_expression(expression)
        except Exception as exc:
            return f"Error: {exc}"
    if name == "search_project_files":
        query = (arguments.get("query") or "").strip()
        if not query:
            return "Error: query must be a non-empty string"
        query_vector = embed_query(embedder, query)
        chunks = search_chunks(db, project_id, query_vector, limit=RETRIEVAL_LIMIT)
        if not chunks:
            return "No relevant content found in the project files."
        return "\n\n---\n\n".join(chunks)
    raise ValueError(f"Unknown tool: {name}")


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a safe arithmetic expression and return the numeric result. "
                "Supports +, -, *, /, %, **, unary plus/minus, parentheses and numeric "
                "literals. Use whenever the answer requires arithmetic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": 'The arithmetic expression to evaluate, e.g. "17 * 23 + 4".',
                    }
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_project_files",
            "description": (
                "Search the project's uploaded files for content relevant to a query and "
                f"return up to {RETRIEVAL_LIMIT} matching snippets. Use it when the answer "
                "should be grounded in the documents uploaded to this project."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query describing the information to find.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]