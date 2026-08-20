# Africa Bitext Builder

**Africa Bitext Builder** is a Python library for discovering, inspecting, and compiling sentence-aligned parallel and monolingual text corpora across 690+ African languages.

The library pairs African languages with English, French, Arabic, Portuguese, and Chinese, or directly aligns two African languages (e.g., Twi ↔ Yoruba, Hausa ↔ Amharic).

---

## Core Principles

1. **Explicit Licensing Enforcement:** Defaults strictly to verified Public Domain (PD) and Creative Commons (CC) translations.
2. **On-Demand Dataset Streaming:** Data is downloaded only when requested from Hugging Face (`AfriSpeech/africa-corpus`) and cached locally.
3. **Canonical Alignment:** Verses are matched deterministically using canonical scripture identifiers (`GEN.1.1` to `REV.22.21`).
4. **Fast Discovery:** Look up translation metadata, country distributions, and licensing across hundreds of dialects in constant time.

---

## Installation

Install the latest published version directly from PyPI:

=== "pip"

```bash
pip install africa-bitext-builder
```

=== "uv"

```bash
uv add africa-bitext-builder
```

---

## Next Steps

- **[Language & License Discovery](guides/registry.md):** Learn how to query ISO codes, verify Public Domain availability, and search by country or abbreviation.
- **[Compiling Corpora](guides/builder.md):** Configure parallel extraction, apply random sampling, and export CSV files.
- **[API Reference](api/registry.md):** Detailed docstring references for `LanguageRegistry` and `CorpusBuilder`.
