#!/usr/bin/env bash
# Instala o Periféricos no menu do usuário (~/.local), usando o Python do sistema
# para o GTK e o Solaar já instalado para falar com o mouse e o headset.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${HOME}/.local"
VENV="${PREFIX}/share/perifericos/venv"
DESKTOP_DIR="${PREFIX}/share/applications"
ICON_DIR="${PREFIX}/share/icons/hicolor/scalable/apps"

if ! python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw"; then
  echo "Faltam as bibliotecas gráficas. Instale com:" >&2
  echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1" >&2
  exit 1
fi

python3 -m venv --system-site-packages "${VENV}"
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install "${ROOT}"

install -d "${DESKTOP_DIR}" "${ICON_DIR}" "${PREFIX}/bin"
install -m 644 "${ROOT}/share/perifericos.desktop" "${DESKTOP_DIR}/perifericos.desktop"
install -m 644 "${ROOT}/share/perifericos.svg" "${ICON_DIR}/perifericos.svg"
ln -sfn "${VENV}/bin/perifericos" "${PREFIX}/bin/perifericos"

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "${DESKTOP_DIR}" || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
  gtk-update-icon-cache -f -t "${PREFIX}/share/icons/hicolor" || true
fi

echo "Instalado. Abra Periféricos no menu ou rode: perifericos"
echo "No menu do app, ative «Iniciar com o sistema» para restaurar a configuração ao entrar."
