import re
from difflib import ndiff


def get_diff(original: str, modified: str) -> list[str]:
    """
    Get the difference between two strings using difflib.

    Parameters:
    - original: The original string.
    - modified: The modified string.

    Returns:
    A list of differences.
    """
    diff = list(ndiff(original.split(), modified.split()))
    return [d for d in diff if d.startswith(("+", "-"))]


def apply_diff(original: str, diff: list[str]) -> str:
    """
    Apply the difference to the original string.

    Parameters:
    - original: The original string.
    - diff: The difference obtained from get_diff function.

    Returns:
    The modified string.
    """
    pattern = re.compile(r"^(\+|-) ")

    # Используем list comprehension вместо цикла с append
    result = []
    for line in diff:
        match = pattern.match(line)
        if match:
            op = match.group(1)
            if op == "+":
                result.append(line[2:])  # content
            # Игнорируем удаленные строки (op == "-")
        else:
            result.append(line)

    return " ".join(result)
