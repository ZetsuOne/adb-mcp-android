[English](README.md) | Русский

# adb-mcp-android

MCP-мост между Cursor / Claude Desktop (или любым MCP-клиентом) и Android-смартфоном или эмулятором через **ADB**.

Сервер вызывает установленный у вас бинарник `adb`. **USB-драйверы и Android platform-tools в репозиторий не входят** — ставятся отдельно (драйверы могут лежать в другой папке на диске).

## Возможности

| Инструмент | Назначение |
| --- | --- |
| `adb_version` | Путь к `adb` и строка версии |
| `list_devices` | `adb devices -l` |
| `device_info` | Модель, версия Android, ABI, батарея, размер экрана |
| `shell` | Любая команда `adb shell` |
| `getprop` | Одно свойство или полный список |
| `install_apk` / `uninstall_app` | Установка / удаление пакетов |
| `push_file` / `pull_file` | Копирование файлов хост ↔ устройство |
| `screenshot` | Снимок экрана PNG (путь и/или base64) |
| `logcat` | Дамп логов, фильтр / очистка |
| `input_tap` / `input_swipe` / `input_text` / `input_keyevent` | Ввод |
| `start_activity` / `force_stop` / `list_packages` | Управление приложениями |
| `connect` / `disconnect` | ADB по TCP/IP |
| `reboot` | Обычная перезагрузка / bootloader / recovery / sideload |
| `battery` / `screen_metrics` | Питание и `wm size` / density |
| `port_forward` / `port_forward_remove` | Проброс портов хост → устройство |
| `port_reverse` / `port_reverse_remove` | Проброс устройство → хост |

У большинства инструментов есть необязательный `serial`. Если не указан — берутся `ANDROID_SERIAL` / `ADB_SERIAL`, иначе поведение ADB по умолчанию (одно устройство).

## Что нужно заранее (не входит в проект)

1. **Android platform-tools** — в проекте ожидается `bin/platform-tools/adb` (на Windows — `adb.exe`). Можно также добавить `adb` в `PATH` или задать другой путь через `ADB_PATH`.
2. **USB-драйверы** (Windows) — OEM или Google USB Driver; храните отдельно. Этот репозиторий драйверы не содержит.
3. На телефоне: **Параметры разработчика → Отладка по USB** (подтвердите отпечаток ПК).
4. Python **3.10+**.

Проверка:

```powershell
adb version
adb devices
```

Устройство должно быть в состоянии `device` (не `unauthorized` / `offline`).

## Быстрый старт через `uvx`

Нужен [uv](https://docs.astral.sh/uv/).

```bash
uvx --from git+https://github.com/ZetsuOne/adb-mcp-android adb-mcp-android
```

### Cursor / Claude Desktop

```json
{
  "mcpServers": {
    "adb-android": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ZetsuOne/adb-mcp-android", "adb-mcp-android"]
    }
  }
}
```

`adb` подхватывается из `bin/platform-tools/` автоматически. Опционально:

```json
"env": {
  "ANDROID_SERIAL": "XXXXXXXX"
}
```

## Классическая установка (venv)

### Windows (PowerShell)

```powershell
git clone https://github.com/ZetsuOne/adb-mcp-android.git
cd adb-mcp-android
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Если PowerShell блокирует скрипты активации:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Дымовой тест:

```powershell
python client.py
```

Запуск сервера (stdio; ждёт MCP-клиента):

```powershell
python server.py
# или после `pip install -e .`:
adb-mcp-android
```

Локальный конфиг Cursor:

```json
{
  "mcpServers": {
    "adb-android": {
      "command": "C:\\Projects\\adb-mcp-android\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Projects\\adb-mcp-android\\server.py"]
    }
  }
}
```

### Linux / macOS

```bash
git clone https://github.com/ZetsuOne/adb-mcp-android.git
cd adb-mcp-android
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python client.py
```

## Переменные окружения

| Переменная | Смысл |
| --- | --- |
| `ADB_PATH` / `ADB_EXECUTABLE` | Переопределить путь к `adb` (по умолчанию: `bin/platform-tools/adb[.exe]`, затем `PATH`) |
| `ANDROID_SERIAL` / `ADB_SERIAL` | Серийник по умолчанию, если в tool не передан `serial` |

## Примеры ответов

`list_devices`:

```json
{
  "ok": true,
  "count": 1,
  "devices": [
    {
      "serial": "RFCX123456",
      "state": "device",
      "model": "Pixel_7",
      "device": "panther",
      "product": "panther"
    }
  ]
}
```

## Структура проекта

| Путь | Роль |
| --- | --- |
| `server.py` | MCP-сервер (stdio) и точка входа `adb-mcp-android` |
| `adb_client.py` | Обёртка над subprocess ADB |
| `client.py` | Клиент для дымового теста |
| `pyproject.toml` | Упаковка и console script |
| `requirements.txt` | Зависимости для `pip install -r` |

## Безопасность

- `shell` выполняет произвольные команды на устройстве — только на своих девайсах.
- Драйверы и platform-tools — **внешние** зависимости; не коммитьте проприетарные OEM-драйверы сюда.
- Для экспериментов с install / reboot / force-stop лучше отдельный тестовый телефон.

## Лицензия

MIT — см. [LICENSE](LICENSE).
