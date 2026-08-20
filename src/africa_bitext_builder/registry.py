"""registry.py — Language metadata discovery and licensing registry.

This module provides the :class:`LanguageRegistry` class along with the
:class:`Language` and :class:`BibleVersion` dataclasses for querying, inspecting,
and resolving African and reference language corpora alongside their verified
copyright and Public Domain license statuses.
"""

from __future__ import annotations

import os
import pickle
import re
from dataclasses import dataclass, field


@dataclass
class BibleVersion:
    """A single Bible translation and its licensing details.

    Attributes:
        id (int): Unique numeric translation identifier.
        abbrev (str): Standardized edition abbreviation (e.g., ``'LSG'``, ``'KJV'``, ``'SUV'``).
        name (str): Full title of the Bible translation edition.
        is_public_domain (bool): Whether this translation is Public Domain (PD) or Creative Commons (CC) licensed.
        country (str | None): ISO country code(s) where this version is primarily circulated.
        has_text (bool): Whether verse text is available for this translation.
    """

    id: int
    abbrev: str
    name: str
    is_public_domain: bool
    country: str | None = None
    has_text: bool = True
    _file_rel_path: str = field(repr=False, default="")

    def __repr__(self) -> str:
        pd_str = "PublicDomain" if self.is_public_domain else "Copyrighted"
        return f"<BibleVersion id={self.id} abbrev='{self.abbrev}' name='{self.name}' status={pd_str}>"


@dataclass
class Language:
    """A language and its available Bible translation versions.

    Attributes:
        code (str): Standard ISO-639 language code (e.g., ``'swh'``, ``'twi'``, ``'fr'``).
        name (str): Canonical language name (e.g., ``'Swahili'``).
        is_african (bool): Whether the language is classified as African.
        text_column (str): Default column name holding text in the source CSV files.
        bible_versions (list[BibleVersion]): All available translations for this language.
    """

    code: str
    name: str
    is_african: bool
    text_column: str = "text"
    bible_versions: list[BibleVersion] = field(default_factory=list)
    _files: list[str] = field(repr=False, default_factory=list)

    @property
    def public_domain_versions(self) -> list[BibleVersion]:
        """Versions that are Public Domain or Creative Commons licensed."""
        return [v for v in self.bible_versions if v.is_public_domain]

    @property
    def non_public_domain_versions(self) -> list[BibleVersion]:
        """Versions that are copyrighted."""
        return [v for v in self.bible_versions if not v.is_public_domain]

    @property
    def countries(self) -> list[str]:
        """Sorted list of unique country codes associated with this language."""
        c_set: set[str] = set()
        for v in self.bible_versions:
            if v.country:
                for c in v.country.split(";"):
                    if c.strip():
                        c_set.add(c.strip())
        return sorted(c_set)

    def __repr__(self) -> str:
        geo = "African" if self.is_african else "Non-African"
        pd_count = len(self.public_domain_versions)
        total = len(self.bible_versions)
        return f"<Language code='{self.code}' name='{self.name}' region='{geo}' versions={total} (PD: {pd_count})>"


class LanguageRegistry:
    """Discovers and queries language metadata and license statuses.

    Provides lookups by ISO-639 code, translation ID, abbreviation, country,
    or a substring search on language name.
    """

    __all__ = ["list", "list_languages", "resolve", "search"]

    _LANG_FILE_RE = re.compile(r"^(?P<name>.+)_(?P<code>[a-z]{2,8})_v(?P<vid>\d+)\.csv$")
    _NON_LANG_FILES = {
        "english_cache.csv",
        "progress.json",
        "progress.json.tmp",
        "testament_status.json",
    }

    def __init__(
        self,
        data_root: str = "african_bible_parallel_text_datasets",
        hf_repo_id: str = "AfriSpeech/africa-corpus",
        pkl_path: str | None = None,
    ) -> None:
        """Initializes the LanguageRegistry instance.

        Args:
            data_root: Local filesystem path where cached dataset files reside.
            hf_repo_id: Remote Hugging Face repository identifier used when files are not cached locally.
            pkl_path: Optional explicit path to the licensing metadata file.
        """
        self.data_root = data_root
        self.hf_repo_id = hf_repo_id

        if pkl_path is None:
            pkg_dir = os.path.dirname(os.path.abspath(__file__))
            self.pkl_path = os.path.join(pkg_dir, "data", ".lang_data.pkl")
        else:
            self.pkl_path = pkl_path

        self._license_db: dict[int, dict[str, object]] = self._load_license_db()
        self._file_cache: list[str] | None = None
        self._registry_cache: dict[str, Language] | None = None

    def _load_license_db(self) -> dict[int, dict[str, object]]:
        """Loads licensing metadata, keyed by translation ID."""
        if not os.path.exists(self.pkl_path):
            return {}

        with open(self.pkl_path, "rb") as f:
            data = pickle.load(f)

        if isinstance(data, dict):
            if "by_id" in data:
                return {int(k): v for k, v in data["by_id"].items()}
            elif "df" in data:
                df = data["df"]
                return {int(row["id"]): row for row in df.to_dict(orient="records")}
            return {int(k): v for k, v in data.items() if str(k).isdigit()}
        else:
            return {int(row["id"]): row for row in data.to_dict(orient="records")}

    def _get_dataset_files(self) -> list[str]:
        """Lists available dataset CSV files, checking local storage before the remote repository."""
        if self._file_cache is not None:
            return self._file_cache

        local_files: list[str] = []
        if os.path.isdir(self.data_root):
            for root, _, files in os.walk(self.data_root):
                for name in files:
                    full = os.path.join(root, name)
                    if name.endswith(".csv") and os.path.getsize(full) >= 64:
                        rel = os.path.relpath(full, self.data_root)
                        local_files.append(rel.replace(os.sep, "/"))

        if local_files:
            self._file_cache = local_files
        else:
            try:
                from huggingface_hub import HfApi

                files = HfApi().list_repo_files(self.hf_repo_id, repo_type="dataset")
                self._file_cache = [f for f in files if f.endswith(".csv")]
            except ImportError:
                raise RuntimeError(
                    "No local data found and huggingface_hub is not installed.\n"
                    "Install it via: pip install huggingface_hub"
                )

        return self._file_cache

    def _build_registry(self) -> dict[str, Language]:
        """Builds the full language registry from the available dataset files."""
        files = self._get_dataset_files()
        langs: dict[str, Language] = {}

        # 1. African datasets (top-level CSVs)
        african_rels = [
            r for r in files if "/" not in r and r.split("/")[-1] not in self._NON_LANG_FILES
        ]
        for rel in sorted(african_rels):
            self._register_file(langs, rel, is_african=True, default_col="local")

        # 2. Non-African / Reference datasets (inside reference_caches/)
        non_african_rels = [r for r in files if r.startswith("reference_caches/")]
        for rel in sorted(non_african_rels):
            self._register_file(langs, rel, is_african=False, default_col="text")

        # 3. Handle default English cache
        if "english_cache.csv" in files:
            meta = self._license_db.get(206, {})
            is_pd = bool(meta.get("is_public_domain", False))
            country_val = meta.get("country")
            eng_version = BibleVersion(
                id=206,
                abbrev=str(meta.get("abbrev", meta.get("abbr", "engWEBUS"))),
                name=str(meta.get("name", meta.get("version_title", "World English Bible"))),
                is_public_domain=is_pd,
                country=str(country_val) if country_val else None,
                has_text=bool(meta.get("has_text", True)),
                _file_rel_path="english_cache.csv",
            )
            if "en" not in langs:
                langs["en"] = Language(
                    code="en",
                    name="English",
                    is_african=False,
                    text_column="eng",
                    bible_versions=[eng_version],
                    _files=["english_cache.csv"],
                )
            else:
                langs["en"]._files.insert(0, "english_cache.csv")
                langs["en"].text_column = "eng"
                if not any(v.id == 206 for v in langs["en"].bible_versions):
                    langs["en"].bible_versions.insert(0, eng_version)

        return langs

    def _register_file(
        self, langs: dict[str, Language], rel_path: str, is_african: bool, default_col: str
    ) -> None:
        """Parses a dataset filename and adds its language and version info to the registry."""
        fname = rel_path.split("/")[-1]
        m = self._LANG_FILE_RE.match(fname)
        if not m:
            return

        code = m.group("code")
        name = m.group("name").replace("_", " ")
        vid = int(m.group("vid"))

        meta = self._license_db.get(vid, {})
        is_pd = bool(meta.get("is_public_domain", False))
        country_val = meta.get("country")

        if code not in langs:
            langs[code] = Language(
                code=code,
                name=name,
                is_african=is_african,
                text_column=default_col,
                bible_versions=[],
                _files=[],
            )
        if name not in langs[code].name:
            langs[code].name += f" / {name}"

        langs[code]._files.append(rel_path)

        version_obj = BibleVersion(
            id=vid,
            abbrev=str(meta.get("abbrev", meta.get("abbr", ""))),
            name=str(meta.get("name", meta.get("version_title", name))),
            is_public_domain=is_pd,
            country=str(country_val) if country_val else None,
            has_text=bool(meta.get("has_text", True)),
            _file_rel_path=rel_path,
        )
        langs[code].bible_versions.append(version_obj)

    def _get_registry(self) -> dict[str, Language]:
        """Returns the language registry, building it on first use."""
        if self._registry_cache is None:
            self._registry_cache = self._build_registry()
        return self._registry_cache

    def list(self, public_domain_only: bool = False) -> list[Language]:
        """Returns all registered languages, optionally filtered by Public Domain availability.

        Args:
            public_domain_only: If ``True``, restricts the list to languages containing
                at least one verified Public Domain translation.

        Returns:
            list[Language]: Sorted list of registered :class:`Language` instances.
        """
        all_langs = sorted(self._get_registry().values(), key=lambda l: l.code)
        if public_domain_only:
            return [l for l in all_langs if len(l.public_domain_versions) > 0]
        return all_langs

    def list_languages(self, public_domain_only: bool = False) -> list[Language]:
        """Alias for :meth:`list`."""
        return self.list(public_domain_only=public_domain_only)

    def resolve(self, iso_code: str) -> Language | None:
        """Looks up a language by its ISO-639 code.

        Args:
            iso_code: Standard language identifier (e.g., ``'swh'``, ``'twi'``, ``'fr'``).

        Returns:
            Language | None: The matching :class:`Language` object if found, otherwise ``None``.
        """
        if not iso_code:
            return None
        return self._get_registry().get(iso_code.strip().lower())

    def search(
        self,
        lang_code: str | None = None,
        lang_name: str | None = None,
        country: str | None = None,
        abbr: str | None = None,
        version_id: int | str | None = None,
    ) -> Language | list[Language] | tuple[Language, BibleVersion] | list[tuple[Language, BibleVersion]] | None:
        """Multi-criteria search across languages and versions.

        Args:
            lang_code: Exact ISO-639 code to resolve (returns :class:`Language` or ``None``).
            lang_name: Case-insensitive substring matching language names (returns ``list[Language]``).
            country: ISO country code (e.g., ``'GH'``, ``'NG'``) to filter languages (returns ``list[Language]``).
            abbr: Case-insensitive edition abbreviation (e.g., ``'LSG'``) to find specific translations
                (returns ``list[tuple[Language, BibleVersion]]``).
            version_id: Numerical translation ID to locate (returns ``tuple[Language, BibleVersion]`` or ``None``).

        Returns:
            Language | list[Language] | tuple[Language, BibleVersion] | list[tuple[Language, BibleVersion]] | None:
            Matching language(s) or version tuple(s) depending on the query parameter provided.
        """
        # 1. Exact ISO Code
        if lang_code is not None:
            return self.resolve(lang_code)

        # 2. Version ID Lookup
        if version_id is not None:
            target_id = int(version_id)
            for lang in self._get_registry().values():
                for v in lang.bible_versions:
                    if v.id == target_id:
                        return (lang, v)
            return None

        # 3. Abbreviation Lookup
        if abbr is not None:
            target_abbr = abbr.strip().lower()
            matches: list[tuple[Language, BibleVersion]] = []
            for lang in self._get_registry().values():
                for v in lang.bible_versions:
                    if v.abbrev.lower() == target_abbr:
                        matches.append((lang, v))
            return matches

        # 4. Country Code Search
        if country is not None:
            target_c = country.strip().upper()
            return [lang for lang in self._get_registry().values() if target_c in lang.countries]

        # 5. Language Name Substring Search
        if lang_name is not None:
            target_name = lang_name.strip().lower()
            return [
                lang for lang in self._get_registry().values() if target_name in lang.name.lower()
            ]

        return []
