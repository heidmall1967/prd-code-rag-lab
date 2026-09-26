import re
import ast

def check_default_client_claim(claim, path, excerpt, proposed_label):
    if proposed_label != "supports" or not path.startswith("tests/"):
        return proposed_label, None

    if "default" not in claim.lower() or not re.search(
        r"\bclients?\b", claim, re.I
    ):
        return proposed_label, None

    constructs_client = re.search(
        r"\b(?:httpx\.)?(?:Async)?Client\s*\(", excerpt
    )
    if not constructs_client:
        return (
            "related",
            "This test does not construct a client, so it cannot directly "
            "establish the client's built-in default.",
        )

    return proposed_label, None


def has_client_call_without_timeout(excerpt):
      tree = ast.parse(excerpt)

      for node in ast.walk(tree):
          if not isinstance(node, ast.Call):
              continue

          function = node.func
          is_httpx_client = (
              isinstance(function, ast.Attribute)
              and isinstance(function.value, ast.Name)
              and function.value.id == "httpx"
              and function.attr in {"Client", "AsyncClient"}
          )
          supplies_timeout = any(
              keyword.arg == "timeout" for keyword in node.keywords
          )

          if is_httpx_client and not supplies_timeout:
              return True

      return False
