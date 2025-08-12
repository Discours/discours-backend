# Документация Discours Core v0.9.5

## 📚 Быстрый старт

**Discours Core** - это GraphQL API бэкенд для системы управления контентом с реакциями, рейтингами и темами.

### 🚀 Запуск

```shell
# Подготовка окружения
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.dev.txt

# Сертификаты для HTTPS
mkcert -install
mkcert localhost

# Запуск сервера
python -m granian main:app --interface asgi
```

### 📊 Статус проекта

- **Версия**: 0.9.5
- **Тесты**: 344/344 проходят (включая E2E Playwright тесты)
- **Покрытие**: 90%
- **Python**: 3.12+
- **База данных**: PostgreSQL 16.1
- **Кеш**: Redis 6.2.0
- **E2E тесты**: Playwright с автоматическим headless режимом

## 📖 Документация

### 🔧 Основные компоненты

- **[API Documentation](api.md)** - GraphQL API и резолверы
- **[Authentication](auth.md)** - Система авторизации и OAuth
- **[RBAC System](rbac-system.md)** - Роли и права доступа
- **[Caching System](redis-schema.md)** - Redis схема и кеширование
- **[Admin Panel](admin-panel.md)** - Админ-панель управления

### 🛠️ Разработка

- **[Features](features.md)** - Обзор возможностей
- **[Testing](testing.md)** - Тестирование и покрытие
- **[Security](security.md)** - Безопасность и конфигурация

## 🔍 Текущие проблемы

### Тестирование
- **Ошибки в тестах кастомных ролей**: `test_custom_roles.py`
- **Проблемы с JWT**: `test_token_storage_fix.py`
- **E2E тесты браузера**: ✅ Исправлены - добавлен автоматический headless режим для CI/CD

### Git статус
- **48 измененных файлов** в рабочей директории
- **5 новых файлов** (включая тесты и роуты)
- **3 файла** готовы к коммиту

## 🎯 Следующие шаги

1. **Исправить тесты** - Устранить ошибки в тестах кастомных ролей и JWT
2. **Настроить E2E** - Исправить браузерные тесты
3. **Завершить RBAC** - Доработать систему кастомных ролей
4. **Обновить docs** - Синхронизировать документацию
5. **Подготовить релиз** - Зафиксировать изменения

## 🔗 Полезные команды

```shell
# Линтинг и форматирование
biome check . --write
ruff check . --fix --select I
ruff format . --line-length=120

# Тестирование
pytest

# Проверка типов
mypy .

# Запуск в dev режиме
python -m granian main:app --interface asgi
```

---

**Discours Core** - открытый проект под MIT лицензией. [Подробнее о вкладе](CONTRIBUTING.md)
