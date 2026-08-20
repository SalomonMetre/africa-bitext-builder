"""builder.py — Parallel and monolingual dataset compilation and export.

This module provides the core :class:`CorpusBuilder` engine for compiling,
aligning, and exporting multilingual sentence-aligned parallel bitext and
monolingual corpora from harvested Bible datasets.
"""

from __future__ import annotations

import csv
import os
import random
import sys
from collections.abc import Sequence
from pathlib import Path

from africa_bitext_builder.registry import BibleVersion, Language, LanguageRegistry

# Set CSV field limit dynamically to avoid platform integer overflow errors
max_int = sys.maxsize
while True:
    try:
        csv.field_size_limit(max_int)
        break
    except OverflowError:
        max_int = int(max_int / 10)

_BOOK_ORDER: list[str] = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]
_BOOK_INDEX: dict[str, int] = {b: i for i, b in enumerate(_BOOK_ORDER)}


def _verse_sort_key(verse_key: str) -> tuple[int, int, int]:
    """Generates a canonical sorting key from a standard verse identifier."""
    try:
        parts = verse_key.split(".")
        if len(parts) >= 3:
            book, ch, vs = parts[0], parts[1], parts[2]
            return (_BOOK_INDEX.get(book, 999), int(ch), int(vs))
    except (ValueError, KeyError):
        pass
    return (999, 0, 0)


class CorpusBuilder:
    """Compiles and exports parallel and monolingual text datasets.

    `CorpusBuilder` performs immediate pre-flight validation of input language
    codes and translation version IDs during initialization. By default, it
    restricts data selection strictly to verified Public Domain (PD) and Creative
    Commons (CC) versions unless specific version IDs are explicitly passed.

    Attributes:
        mode (str): Operating mode, either ``'parallel'`` or ``'monolingual'``.
        limit (int): Maximum number of records to return (0 means no limit).
        sample (bool): Whether to sample rows randomly instead of sequential ordering.
        seed (int): Random seed for reproducible sampling.
        data_root (str): Local filesystem directory where dataset CSV files reside.
        hf_repo_id (str): Hugging Face dataset repository identifier for on-demand caching.
        registry (LanguageRegistry): Active language registry instance.
        src_lang (Language): Resolved source :class:`Language` metadata object.
        src_versions (list[BibleVersion]): List of active source :class:`BibleVersion` instances.
        tgt_lang (Language | None): Resolved target :class:`Language` metadata object (None in mono mode).
        tgt_versions (list[BibleVersion]): List of active target :class:`BibleVersion` instances.

    Raises:
        ValueError: If a language code is unknown, if no public domain versions are
            available by default, if version IDs do not exist, or if parallel source
            and target languages are identical.

    Example:
        >>> from africa_bitext_builder.builder import CorpusBuilder
        >>> # Public domain parallel alignment (Twi to English)
        >>> builder = CorpusBuilder(source_lang="twi", target_lang="en", limit=1000)
        >>> csv_path = builder.download("corpora/")
        >>>
        >>> # Opt into specific version IDs (Swahili ID 1627 to French ID 93)
        >>> custom_builder = CorpusBuilder(
        ...     source_lang="swh",
        ...     target_lang="fr",
        ...     source_version_ids=[1627],
        ...     target_version_ids=[93],
        ... )
        >>> custom_builder.download("swahili_french.csv")
    """

    __all__ = ["download"]

    def __init__(
        self,
        source_lang: str = "swh",
        target_lang: str | None = "en",
        source_version_ids: Sequence[int] | set[int] | int | None = None,
        target_version_ids: Sequence[int] | set[int] | int | None = None,
        mode: str = "parallel",
        limit: int = 0,
        sample: bool = False,
        registry: LanguageRegistry | None = None,
        data_root: str = "african_bible_parallel_text_datasets",
        hf_repo_id: str = "AfriSpeech/africa-corpus",
        seed: int = 42,
    ) -> None:
        """Initializes the CorpusBuilder and validates language parameters immediately.

        Args:
            source_lang: ISO-639 language code for the source language (e.g., ``'swh'``, ``'twi'``).
            target_lang: ISO-639 language code for the target language (e.g., ``'en'``, ``'fr'``).
                Ignored when ``mode='monolingual'``.
            source_version_ids: Specific Bible translation version ID(s) to use for the source
                language. When ``None``, defaults exclusively to Public Domain versions.
            target_version_ids: Specific Bible translation version ID(s) to use for the target
                language. When ``None``, defaults exclusively to Public Domain versions.
            mode: Extraction mode. Allowed values are ``'parallel'`` (or ``'bitext'``) and
                ``'monolingual'`` (or ``'mono'``). Defaults to ``'parallel'``.
            limit: Maximum number of rows to extract. When ``0``, all matching rows are returned.
            sample: When ``True`` and ``limit > 0``, extracts a uniform random sample of size
                `limit` instead of taking the first `limit` rows in canonical order.
            registry: Optional pre-configured :class:`LanguageRegistry` instance. If omitted,
                a new registry is instantiated using `data_root` and `hf_repo_id`.
            data_root: Local filesystem path where cached dataset files are stored.
            hf_repo_id: Hugging Face dataset repository for automatic remote downloading.
            seed: Random seed used when `sample=True` for deterministic reproducibility.
        """
        self.mode = mode.lower().strip()
        self.limit = max(0, limit)
        self.sample = sample
        self.seed = seed

        self.data_root = data_root
        self.hf_repo_id = hf_repo_id
        self.registry = registry or LanguageRegistry(
            data_root=self.data_root, hf_repo_id=self.hf_repo_id
        )

        self.source_lang_code = source_lang.strip().lower()
        self.target_lang_code = (
            None if self.mode.startswith("mono") else (target_lang.strip().lower() if target_lang else "en")
        )

        source_v_ids = self._normalize_version_ids(source_version_ids)
        target_v_ids = self._normalize_version_ids(target_version_ids)

        # Immediate pre-flight validation
        self.src_lang, self.src_versions = self._resolve_and_filter_versions(
            self.source_lang_code, source_v_ids, role="source"
        )

        if not self.mode.startswith("mono"):
            if not self.target_lang_code:
                raise ValueError("Target language must be specified in parallel mode.")
            if self.source_lang_code == self.target_lang_code:
                raise ValueError(
                    f"Source and target languages cannot be identical ('{self.source_lang_code}'). "
                    f"Use mode='monolingual' for single-language datasets."
                )
            self.tgt_lang, self.tgt_versions = self._resolve_and_filter_versions(
                self.target_lang_code, target_v_ids, role="target"
            )
        else:
            self.tgt_lang, self.tgt_versions = None, []

    @staticmethod
    def _normalize_version_ids(v_ids: Sequence[int] | set[int] | int | None) -> set[int] | None:
        if v_ids is None:
            return None
        if isinstance(v_ids, int):
            return {v_ids}
        return {int(i) for i in v_ids}

    def _resolve_and_filter_versions(
        self, lang_code: str, allowed_ids: set[int] | None, role: str
    ) -> tuple[Language, list[BibleVersion]]:
        lang = self.registry.resolve(lang_code)
        if not lang:
            raise ValueError(f"Unknown {role} language code '{lang_code}'.")

        if not lang.bible_versions:
            raise ValueError(f"Language '{lang.name}' ({lang.code}) has no Bible versions indexed.")

        if allowed_ids is not None and len(allowed_ids) == 0:
            raise ValueError(f"Empty version ID list provided for {role} language '{lang.code}'.")

        if allowed_ids is not None:
            selected = [v for v in lang.bible_versions if v.id in allowed_ids]
            if not selected:
                available_ids = [v.id for v in lang.bible_versions]
                raise ValueError(
                    f"Requested version ID(s) {sorted(allowed_ids)} not found for '{lang.code}'. "
                    f"Available version IDs: {available_ids}"
                )
            return lang, selected

        selected = lang.public_domain_versions
        if not selected:
            available_ids = [v.id for v in lang.bible_versions]
            raise ValueError(
                f"No public domain versions available by default for {role} language '{lang.name}' ({lang.code}).\n"
                f"Available version IDs: {available_ids}\n"
                f"To use them, pass `{role}_version_ids={available_ids}` explicitly."
            )

        return lang, selected

    def _resolve_file_path(self, rel_path: str) -> str:
        if not rel_path:
            raise FileNotFoundError("Empty relative path encountered for version file.")

        local = os.path.join(self.data_root, rel_path)
        if os.path.exists(local):
            return local

        try:
            from huggingface_hub import hf_hub_download

            return hf_hub_download(self.hf_repo_id, rel_path, repo_type="dataset")
        except ImportError:
            raise RuntimeError(
                f"File '{rel_path}' is not present locally and huggingface_hub is not installed.\n"
                "Install it with: pip install huggingface_hub"
            )

    def _load_verses_from_versions(self, lang: Language, versions: list[BibleVersion]) -> dict[str, set[str]]:
        verses: dict[str, set[str]] = {}

        for version in versions:
            rel_path = version._file_rel_path
            if not rel_path:
                continue

            path = self._resolve_file_path(rel_path)
            if not os.path.exists(path):
                continue

            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames or []

                col = lang.text_column if lang.text_column in fields else None
                if col is None:
                    col = "local" if lang.is_african else "text"
                    if col not in fields:
                        candidates = [c for c in fields if c not in ("verse_key", "id", "book", "chapter", "verse")]
                        col = candidates[0] if candidates else None

                if not col:
                    continue

                for row in reader:
                    key = (row.get("verse_key") or "").strip()
                    text = (row.get(col) or "").strip()
                    if key and text:
                        verses.setdefault(key, set()).add(text)

        return verses

    def _apply_limits(self, rows: list) -> list:
        if self.limit <= 0 or self.limit >= len(rows):
            return rows
        if self.sample:
            indices = sorted(random.Random(self.seed).sample(range(len(rows)), self.limit))
            return [rows[i] for i in indices]
        return rows[: self.limit]

    def _build_parallel(self) -> tuple[list[tuple[str, str, str]], Language, Language]:
        if not self.tgt_lang:
            raise ValueError("Target language is not configured for parallel build.")

        va = self._load_verses_from_versions(self.src_lang, self.src_versions)
        vb = self._load_verses_from_versions(self.tgt_lang, self.tgt_versions)

        shared = set(va) & set(vb)
        if not shared:
            src_ids = [v.id for v in self.src_versions]
            tgt_ids = [v.id for v in self.tgt_versions]
            raise ValueError(
                f"No overlapping verses found between {self.src_lang.name} (IDs: {src_ids}) "
                f"and {self.tgt_lang.name} (IDs: {tgt_ids})."
            )

        rows: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()

        for key in sorted(shared, key=_verse_sort_key):
            for ta in va[key]:
                for tb in vb[key]:
                    pair = (ta, tb)
                    if pair not in seen:
                        seen.add(pair)
                        rows.append((key, ta, tb))

        return self._apply_limits(rows), self.src_lang, self.tgt_lang

    def _build_monolingual(self) -> tuple[list[str], Language]:
        verses = self._load_verses_from_versions(self.src_lang, self.src_versions)
        if not verses:
            src_ids = [v.id for v in self.src_versions]
            raise ValueError(f"No valid verses could be read for {self.src_lang.name} (IDs: {src_ids}).")

        seen: set[str] = set()
        sentences: list[str] = []

        for key in sorted(verses, key=_verse_sort_key):
            for text in sorted(verses[key]):
                if text not in seen:
                    seen.add(text)
                    sentences.append(text)

        return self._apply_limits(sentences), self.src_lang

    def download(self, out: str | Path = "corpora") -> str:
        """Compiles the corpus and saves the result to a CSV file.

        Args:
            out: Destination file path ending in ``.csv`` or a directory path.
                If a directory is supplied, the file is automatically named using
                standard ISO codes (e.g., ``'swh_en_parallel.csv'`` or ``'swh_monolingual.csv'``).

        Returns:
            str: Path to the generated output CSV file.
        """
        out_path = Path(out)

        if self.mode.startswith("mono"):
            sentences, lang = self._build_monolingual()
            if out_path.suffix.lower() == ".csv":
                final_file = out_path
            else:
                final_file = out_path / f"{lang.code}_monolingual.csv"

            final_file.parent.mkdir(parents=True, exist_ok=True)
            with open(final_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([lang.code])
                for s in sentences:
                    writer.writerow([s])
            return str(final_file)
        else:
            rows, src_lang, tgt_lang = self._build_parallel()
            if out_path.suffix.lower() == ".csv":
                final_file = out_path
            else:
                final_file = out_path / f"{src_lang.code}_{tgt_lang.code}_parallel.csv"

            final_file.parent.mkdir(parents=True, exist_ok=True)
            with open(final_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["verse_key", src_lang.code, tgt_lang.code])
                writer.writerows(rows)
            return str(final_file)
