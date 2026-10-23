
import ast
import sys
from pathlib import Path


def analyze(root, entry="app.py"):
    root = Path(root)
    classes = {}
    imports = {}

    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        module = ".".join(relative.with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))

        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    imports[(module, alias.asname or alias.name)] = (
                        node.module, alias.name
                    )

            if isinstance(node, ast.ClassDef):
                classes[(module, node.name)] = {
                    item.name: item
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                }

    entry_module = ".".join(
        Path(entry).with_suffix("").parts
    )
    tree = ast.parse((root / entry).read_text(encoding="utf-8-sig"))
    instances = {}

    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        if ast.unparse(node.test) != "__name__ == '__main__'":
            continue

        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Name):
                continue

            name = call.func.id
            target = imports.get(
                (entry_module, name),
                (entry_module, name)
            )

            if target not in classes:
                imported_module, imported_class = target
                parts = entry_module.split(".")

                for depth in range(len(parts) - 1, 0, -1):
                    candidate = (
                        ".".join(parts[:depth] + [imported_module]),
                        imported_class
                    )

                    if candidate in classes:
                        target = candidate
                        break

            if target in classes:
                for variable in statement.targets:
                    if isinstance(variable, ast.Name):
                        instances[variable.id] = target

    print("CLASSI:", len(classes))
    print("ISTANZE:", instances)

    def expand(module, class_name, method_name, visited=None):
        visited = set() if visited is None else visited
        key = (module, class_name, method_name)

        if key in visited:
            print("    RICORSIONE:", method_name)
            return

        method = classes.get((module, class_name), {}).get(method_name)
        if method is None:
            print("    METODO NON RISOLTO:", method_name)
            return

        visited = visited | {key}
        print("  METODO:", f"{module}.{class_name}.{method_name}")

        for call in ast.walk(method):
            if not isinstance(call, ast.Call):
                continue

            func = call.func

            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "self"
            ):
                print("    SELF:", ast.unparse(call))
                expand(module, class_name, func.attr, visited)
            else:
                print("    ALTRA CHIAMATA:", ast.unparse(call))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue

        variable = node.func.value.id
        if variable not in instances:
            continue

        module, class_name = instances[variable]
        print("CHIAMATA:", ast.unparse(node))
        expand(module, class_name, node.func.attr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python class_call_graph_analyzer.py ROOT ENTRY")

    analyze(sys.argv[1], sys.argv[2])
