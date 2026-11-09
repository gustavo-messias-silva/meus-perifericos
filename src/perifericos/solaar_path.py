"""Localiza a instalação do Solaar para reutilizar o protocolo HID++."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_solaar() -> Path | None:
    """Coloca logitech_receiver no path e devolve o diretório encontrado."""
    try:
        import logitech_receiver

        return Path(logitech_receiver.__file__).resolve().parent.parent
    except ImportError:
        pass

    candidates: list[Path] = []
    home = Path.home()
    candidates.extend(sorted(home.glob(".local/share/pipx/venvs/solaar/lib/python*/site-packages")))
    candidates.append(Path("/usr/lib/python3/dist-packages"))
    candidates.extend(sorted(Path("/usr/lib").glob("python3.*/dist-packages")))

    for root in candidates:
        if (root / "logitech_receiver").is_dir() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
            try:
                import logitech_receiver  # noqa: F401
            except ImportError:
                continue
            return root
    return None
