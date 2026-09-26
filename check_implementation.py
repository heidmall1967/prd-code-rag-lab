import ast
from pathlib import Path

repo = Path(__file__).resolve().parent / "data/httpx"

config = ast.parse((repo / "httpx/_config.py").read_text())
assignment = next(
    node for node in config.body
    if isinstance(node, ast.Assign)
    and any(
        isinstance(target, ast.Name)
        and target.id == "DEFAULT_TIMEOUT_CONFIG"
        for target in node.targets
    )
)

call = assignment.value
timeout_value = next(
    keyword.value for keyword in call.keywords
    if keyword.arg == "timeout"
)

if not (
    isinstance(call, ast.Call)
    and isinstance(call.func, ast.Name)
    and call.func.id == "Timeout"
    and isinstance(timeout_value, ast.Constant)
    and timeout_value.value == 5.0
):
    raise SystemExit("The default constant is not Timeout(timeout=5.0).")

print("Verified: DEFAULT_TIMEOUT_CONFIG assigns 5.0")

client_tree = ast.parse((repo / "httpx/_client.py").read_text())

for class_name in ("Client", "AsyncClient"):
    client_class = next(
        node for node in client_tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    constructor = next(
        node for node in client_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    defaults = dict(zip(
        (argument.arg for argument in constructor.args.kwonlyargs),
        constructor.args.kw_defaults,
    ))
    timeout_default = defaults.get("timeout")

    if not (
        isinstance(timeout_default, ast.Name)
        and timeout_default.id == "DEFAULT_TIMEOUT_CONFIG"
    ):
        raise SystemExit(f"{class_name} does not use the default constant.")

    print(f"Verified: {class_name} uses DEFAULT_TIMEOUT_CONFIG")
