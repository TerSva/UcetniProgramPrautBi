"""Testy pro PrilohaStorage — disk-based ukládání příloh."""

from pathlib import Path

import pytest

from infrastructure.storage.priloha_storage import PrilohaStorage, _sanitize_filename


class TestSanitizeFilename:
    """Testy sanitizace názvů souborů."""

    def test_colon_replaced(self):
        assert _sanitize_filename("RCH0002:25.pdf") == "RCH0002_25.pdf"

    def test_no_change_needed(self):
        assert _sanitize_filename("faktura.pdf") == "faktura.pdf"

    def test_multiple_dangerous_chars(self):
        assert _sanitize_filename('a/b\\c:d*e?f.pdf') == "a_b_c_d_e_f.pdf"

    def test_diacritics_preserved(self):
        assert _sanitize_filename("česká_faktura.pdf") == "česká_faktura.pdf"

    def test_spaces_preserved(self):
        assert _sanitize_filename("moje faktura.pdf") == "moje faktura.pdf"

    def test_pipe_replaced(self):
        assert _sanitize_filename("a|b.pdf") == "a_b.pdf"

    def test_angle_brackets_replaced(self):
        assert _sanitize_filename("a<b>c.pdf") == "a_b_c.pdf"


class TestPrilohaStorage:
    """Testy ukládání a manipulace se soubory."""

    @pytest.fixture
    def storage(self, tmp_path):
        root = tmp_path / "doklady"
        return PrilohaStorage(root=root)

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        pdf = tmp_path / "source.pdf"
        pdf.write_bytes(b"%PDF-1.4 test content")
        return pdf

    def test_save_creates_correct_path(self, storage, sample_pdf):
        rel_path, size = storage.save(
            sample_pdf,
            doklad_typ="FP",
            doklad_cislo="FP-2025-0001",
            original_name="meta.pdf",
            rok=2025,
        )
        assert rel_path == "doklady/2025/FP/FP-2025-0001_meta.pdf"
        assert size == len(b"%PDF-1.4 test content")
        assert (storage._root / "2025" / "FP" / "FP-2025-0001_meta.pdf").exists()

    def test_save_sanitizes_filename(self, storage, sample_pdf):
        rel_path, _ = storage.save(
            sample_pdf,
            doklad_typ="FP",
            doklad_cislo="FP-2025-0001",
            original_name="RCH0002:25.pdf",
            rok=2025,
        )
        assert rel_path == "doklady/2025/FP/FP-2025-0001_RCH0002_25.pdf"

    def test_save_collision_adds_suffix(self, storage, sample_pdf):
        # First save
        storage.save(
            sample_pdf,
            doklad_typ="FP",
            doklad_cislo="FP-2025-0001",
            original_name="meta.pdf",
            rok=2025,
        )
        # Second save with same name
        rel_path, _ = storage.save(
            sample_pdf,
            doklad_typ="FP",
            doklad_cislo="FP-2025-0001",
            original_name="meta.pdf",
            rok=2025,
        )
        assert rel_path == "doklady/2025/FP/FP-2025-0001_meta_(1).pdf"

    def test_full_path(self, storage):
        full = storage.full_path("doklady/2025/FP/test.pdf")
        assert full == storage._root.parent / "doklady" / "2025" / "FP" / "test.pdf"

    def test_delete_existing(self, storage, sample_pdf):
        rel_path, _ = storage.save(
            sample_pdf,
            doklad_typ="FP",
            doklad_cislo="FP-2025-0001",
            original_name="meta.pdf",
            rok=2025,
        )
        full = storage.full_path(rel_path)
        assert full.exists()
        storage.delete(rel_path)
        assert not full.exists()

    def test_delete_nonexistent_no_error(self, storage):
        storage.delete("doklady/2025/FP/nonexistent.pdf")
