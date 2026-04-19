"""PrilohaStorage — ukládá PDF soubory na disk ve strukturované formě.

Soubory se ukládají do uploads/doklady/{rok}/{typ}/{cislo}_{sanitized_name}.
Relativní cesty v DB jsou relativní k uploads/.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


UPLOADS_ROOT = Path("uploads/doklady")


def _sanitize_filename(name: str) -> str:
    """Nahradí znaky nepovolené ve filesystémech za _.

    Nebezpečné na Windows/macOS/Linux: : / \\ * ? " < > |
    Zachovává diakritiku a mezery.
    """
    return re.sub(r'[:/\\*?"<>|]', "_", name)


class PrilohaStorage:
    """Ukládá PDF soubory na disk ve strukturované formě."""

    def __init__(self, root: Path = UPLOADS_ROOT) -> None:
        self._root = root

    def save(
        self,
        source_path: Path,
        doklad_typ: str,
        doklad_cislo: str,
        original_name: str,
        rok: int,
    ) -> tuple[str, int]:
        """Uloží soubor a vrátí (relativní cesta k uploads/, velikost v bytech)."""
        target_dir = self._root / str(rok) / doklad_typ
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _sanitize_filename(f"{doklad_cislo}_{original_name}")
        target_path = target_dir / safe_name

        if target_path.exists():
            counter = 1
            stem = target_path.stem
            suffix = target_path.suffix
            while target_path.exists():
                target_path = target_dir / f"{stem}_({counter}){suffix}"
                counter += 1

        shutil.copy2(source_path, target_path)
        relative = target_path.relative_to(self._root.parent)
        size = target_path.stat().st_size
        return str(relative), size

    def full_path(self, relativni_cesta: str) -> Path:
        """Vrátí absolutní cestu k souboru na disku."""
        return self._root.parent / relativni_cesta

    def delete(self, relativni_cesta: str) -> None:
        """Smaže soubor z disku (pokud existuje)."""
        path = self.full_path(relativni_cesta)
        if path.exists():
            path.unlink()
