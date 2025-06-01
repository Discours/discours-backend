#!/usr/bin/env python3
"""
Простая проверка основных модулей на ошибки mypy
"""

import subprocess
import sys


def check_mypy():
    """Запускает mypy и возвращает количество ошибок"""
    try:
        result = subprocess.run(["mypy", ".", "--explicit-package-bases"], capture_output=True, text=True, check=False)

        lines = result.stdout.split("\n")
        error_lines = [line for line in lines if "error:" in line]

        print("MyPy проверка завершена")
        print(f"Найдено ошибок: {len(error_lines)}")

        if error_lines:
            print("\nОсновные ошибки:")
            for i, error in enumerate(error_lines[:10]):  # Показываем первые 10
                print(f"{i + 1}. {error}")

            if len(error_lines) > 10:
                print(f"... и ещё {len(error_lines) - 10} ошибок")

        return len(error_lines)

    except Exception as e:
        print(f"Ошибка при запуске mypy: {e}")
        return -1


if __name__ == "__main__":
    errors = check_mypy()

    if errors == 0:
        print("✅ Все проверки mypy пройдены!")
        sys.exit(0)
    elif errors > 0:
        print(f"⚠️  Найдено {errors} ошибок типизации")
        sys.exit(1)
    else:
        print("❌ Ошибка при выполнении проверки")
        sys.exit(2)
