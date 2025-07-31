import sys
from pathlib import Path

# Получаем путь к корневой директории проекта
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path))
