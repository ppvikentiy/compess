# Установка и сборка (деплой)

Документ описывает установку окружения, запуск из исходников и упаковку приложения «Мастер сжатия изображений» в переносимую папку с `.exe`.

---

## Установка для разработки и обычного запуска

### 1. Python

Установите [Python для Windows](https://www.python.org/downloads/) (**3.10 или новее**). В инсталляторе отметьте **Add Python to PATH**.

Проверка в командной строке (`cmd` или PowerShell):

```powershell
python --version
pip --version
```

### 2. Зависимости проекта

Перейдите в каталог репозитория (где лежит `requirements.txt`) и выполните:

```powershell
cd путь\к\compess
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Состав:

| Пакет | Назначение |
|--------|------------|
| `Pillow` | Обработка изображений |
| `tkinterdnd2` | Перетаскивание файла в окно; приложение работает и без пакета, но без drag-and-drop |
| `PyInstaller` | Сборка однофайловой/папочной дистрибуции |

**Tkinter** входит в стандартную установку официального Python для Windows; отдельно ставить обычно не нужно. Если после установки Python команда `python` не находит Tkinter — переустановите Python с галочкой **tcl/tk** (обычно включена по умолчанию) или воспользуйтесь официальной сборкой python.org.

### 3. Запуск приложения

Из корня репозитория:

```powershell
python src\main.py
```

Или дважды щёлкните `run_compress_wizard.bat` (он переходит в папку скрипта и вызывает `python src\main.py`).

---

## Проверочный виртуальный env (необязательно)

Изоляция зависимостей:

```powershell
cd путь\к\compess
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src\main.py
```

Для активации в **cmd** вместо PowerShell:

```cmd
.\.venv\Scripts\activate.bat
```

---

## Выпуск сборки через PyInstaller (деплой без Python у конечного пользователя)

В репозитории есть спецификация `compress_app.spec`: в результате сборки образуется каталог **`dist\CompressWizard\`** с `CompressWizard.exe` и нужными DLL/данными (windowed-сборка, без консольного окна).

### Шаги

1. Убедитесь, что установлены зависимости: `pip install -r requirements.txt`.
2. В корне репозитория выполните:

```powershell
cd путь\к\compess
pyinstaller compress_app.spec
```

Альтернатива (если `pyinstaller` в PATH после установки через pip):

```powershell
python -m PyInstaller compress_app.spec
```

### Результат

- Исполняемый файл: `dist\CompressWizard\CompressWizard.exe`
- **Распространение:** заархивируйте всю папку `dist\CompressWizard\` и передайте пользователю. Запуск — двойным щелчком по `CompressWizard.exe`. Устанавливать Python на целевой машине **не нужно**.
- При первом запуске антивирусы иногда блокируют неподписанные `.exe`; при необходимости добавьте исключение или подпишите сборку код-подписью (отдельная процедура).

### Однофайловый EXE (опционально)

Текущий `compress_app.spec` настроен на режим **onedef + COLLECT** (папка). Чтобы собрать один большой файл, нужно менять блоки `EXE`/`COLLECT` в спецификации PyInstaller и при необходимости проверять стартовые пути ресурсов. Для простой раздачи чаще удобна именно целевая папка `CompressWizard`.

---

## Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| «python не является внутренней или внешней командой» | PATH или переустановка Python с галочкой **Add Python to PATH** |
| Нет интерфейса / ошибка про `_tkinter` | Официальный установщик с python.org, не «minimal» сборка без Tcl/Tk |
| Drag-and-drop не работает | `pip install tkinterdnd2`, перезапуск приложения |
| PyInstaller жалуется на отсутствие модуля | Повторно `pip install -r requirements.txt`, сборку запускать из корня где лежит `compress_app.spec` |

---

## Выкладка исходников на GitHub

В корне репозитория файл [`.gitignore`](.gitignore) исключает виртуальные окружения, каталоги `build/` и `dist/` после PyInstaller и другие служебные артефакты.

После создания пустого репозитория на GitHub (можно без шаблонного README, если документация уже есть локально):

```powershell
cd путь\к\compess
git init
git branch -M main
git remote add origin https://github.com/USER/REPONAME.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

При push и pull request в ветки `main`/`master` срабатывает workflow [CI](.github/workflows/ci.yml): установка зависимостей по `requirements.txt` и проверка компиляции модулей в `src/`.

---

English version: [DEPLOY-EN](DEPLOY-EN.md).
