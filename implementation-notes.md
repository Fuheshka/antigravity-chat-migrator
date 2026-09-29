# Implementation Notes: Antigravity Chat Migrator

## 2026-09-29: Промпт 1.1 — Инициализация структуры проекта и кроссплатформенный PathManager

### Принятые архитектурные решения
1. **Нулевые внешние зависимости для тестов (Ponytail YAGNI):**
   - Тесты написаны с использованием стандартного `unittest` и `unittest.mock`, что позволяет запускать весь тестовый набор командой `PYTHONPATH=src python3 -m unittest discover tests` без необходимости предварительной установки `pytest` или активации виртуального окружения. При этом тесты на 100% совместимы с `pytest`.
2. **Кроссплатформенная модель путей (`PathManager`):**
   - Вычисление базовых путей опирается на `Path.home() / ".gemini"`:
     - macOS: `~/.gemini/antigravity/` и `~/.gemini/config/`.
     - Windows: `%USERPROFILE%\.gemini\antigravity\` и `%USERPROFILE%\.gemini\config\`.
   - Поддержаны явные переопределения через конструктор `PathManager(data_dir=..., config_dir=...)` и переменные окружения (`GEMINI_DATA_DIR`, `GEMINI_CONFIG_DIR`), что гарантирует простоту интеграционного тестирования без засорения пользовательских директорий.
   - Метод `normalize_uri` приводит локальные пути macOS и Windows к стандарту `file:///...` Antigravity (включая Windows диски `file:///C:/...` и экранирование обратных слэшей).
3. **Структура репозитория:**
   - Ветка по умолчанию для разработки: `dev`.
   - Пакет расположен в `src/antigravity_migrator/`.
   - Конфигурация в `pyproject.toml` по стандарту PEP 621 / setuptools.

### Результаты тестирования
- `tests/test_paths.py`: 9 тестов, 100% pass (0.008s).
- Проверены: дефолтные пути macOS/Windows, env-переопределения, явные аргументы, нормализация URI в обе стороны (`normalize_uri`, `uri_to_path`), создание каталогов (`ensure_dirs`).
