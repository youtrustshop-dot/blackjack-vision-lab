"""Run selected code-library definitions from a verified external notebook.

Executed only by HhoppeAdapter in an isolated Python subprocess. No notebook
experiments, test calls, plots, network calculators, or Monte Carlo cells run.
This is a compatibility loader for trusted pinned source, not a security sandbox.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import types
import urllib.request


def deny_network(*args, **kwargs):
    raise RuntimeError("Network access is disabled in the reference worker")


def load_core(checkout: Path, effort: int):
    source_path = checkout / "blackjack.py"
    source = source_path.read_text(encoding="utf-8")
    marker = "\nEXPECTED_BASIC_STRATEGY_ACTION_6DECKS_H17 ="
    if marker not in source:
        raise RuntimeError("Pinned code-library boundary is missing")
    tree = ast.parse(source.split(marker, 1)[0], filename=str(source_path))
    retained = []
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        if names & {"EFFORT", "USE_CUDA"}:
            node.value = ast.Constant(value=effort if "EFFORT" in names else False)
        if names & {"_", "_ORIGINAL_GLOBALS"}:
            continue
        retained.append(node)
    module = types.ModuleType("bjlab_external_hhoppe")
    module.__file__ = str(source_path)
    sys.modules[module.__name__] = module  # dataclass annotations resolve here.
    sys.path.insert(0, str(checkout))  # local tracked random32.py only.
    code = compile(ast.fix_missing_locations(ast.Module(body=retained, type_ignores=[])), str(source_path), "exec")
    exec(code, module.__dict__)
    return module, hashlib.sha256(source.encode("utf-8")).hexdigest()


def main():
    request = json.load(sys.stdin)
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    urllib.request.urlopen = deny_network
    # Source imports may print diagnostics. JSON stdout remains a single object.
    with contextlib.redirect_stdout(io.StringIO()):
        module, source_hash = load_core(Path(request["checkout"]), request["effort"])
        rules = module.Rules(**request["rules"])
        strategy = module.Strategy(attention=module.Attention.HAND_AND_INITIAL_CARDS_IN_PRIOR_SPLITS)
        cards = request["player"]
        ordered = (*sorted(cards[:2]), *sorted(cards[2:]))
        state = ordered, request["dealer"], ()
        values = {name: float(module.reward_for_action(state, rules, strategy, module.Action[name.upper()]))
                  for name in request["actions"]}
    json.dump({"actions": values, "source_sha256": source_hash, "effort": request["effort"],
               "network_disabled": True, "loader": "AST-code-library-definitions-only"}, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
