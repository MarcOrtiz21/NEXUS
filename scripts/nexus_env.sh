#!/usr/bin/env bash
# Helpers compartidos para lanzadores NEXUS en macOS/Linux.

: "${NEXUS_ROOT:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

nexus_find_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        echo "python"
        return 0
    fi
    return 1
}

nexus_activate_venv() {
    local python_cmd="$1"
    local venv_python="$NEXUS_ROOT/.venv/bin/python"

    if [[ -x "$venv_python" ]]; then
        echo "$venv_python"
        return 0
    fi

    echo "Creando entorno virtual en .venv ..." >&2
    "$python_cmd" -m venv "$NEXUS_ROOT/.venv"
    echo "$venv_python"
}

nexus_check_imports() {
    local python_cmd="$1"
    local imports="$2"
    "$python_cmd" -c "import ${imports}"
}

nexus_install_dependencies() {
    local python_cmd="$1"
    "$python_cmd" -m pip install -r "$NEXUS_ROOT/requirements.txt" >&2
}

nexus_ensure_dependencies() {
    local python_cmd="$1"
    local imports="$2"

    if nexus_check_imports "$python_cmd" "$imports" >/dev/null 2>&1; then
        return 0
    fi

    echo "Faltan dependencias. Instalando desde requirements.txt ..." >&2
    nexus_install_dependencies "$python_cmd"
}

nexus_prepare_python() {
    local imports="${1:-yfinance, pandas, numpy, requests, rich, feedparser}"

    cd "$NEXUS_ROOT" || exit 1

    local base_python
    if ! base_python="$(nexus_find_python)"; then
        echo "[ERROR] Python no esta disponible en el PATH."
        echo "Instala Python 3 (por ejemplo: brew install python) y vuelve a intentarlo."
        return 1
    fi

    local python_cmd
    python_cmd="$(nexus_activate_venv "$base_python")"
    nexus_ensure_dependencies "$python_cmd" "$imports"
    echo "$python_cmd"
}
