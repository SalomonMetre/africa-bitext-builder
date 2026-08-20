# Africa Bitext Builder

A Python library for discovering, inspecting, and compiling sentence-aligned parallel and monolingual text corpora across 690+ African languages.
📚 [Read the Full Documentation](https://africa-bitext-builder.readthedocs.io/)
---

## Quickstart

### 1. Discover Languages & Check Public Domain Status

Use `LanguageRegistry` to inspect supported languages, available translations, and their legal licensing status:

```python
from africa_bitext_builder.registry import LanguageRegistry

reg = LanguageRegistry()

# Check if a language is supported by its ISO-639 code
swh = reg.resolve("swh")
print(swh)
# <Language code='swh' name='Swahili' region='African' versions=13 (PD: 0)>

# Inspect Public Domain vs. Copyrighted translations
print("Public Domain versions:", [v.id for v in swh.public_domain_versions])
print("All available versions:", [v.id for v in swh.bible_versions])

```

---

### 2. Build a Parallel Corpus

#### Case A: Public Domain Only (Default)

If the requested languages have verified Public Domain versions (e.g., Twi ↔ English), pass the language codes without version IDs:

```python
from africa_bitext_builder.builder import CorpusBuilder

builder = CorpusBuilder(
    source_lang="twi",
    target_lang="en",
    limit=5000,
)

# Saves automatically to 'corpora/twi_en_parallel.csv'
out_file = builder.download("corpora/")
print(f"Saved: {out_file}")

```

#### Case B: Supplying Non-Public Domain Version IDs (User's Own Risk)

If a language has no Public Domain versions (like Swahili) or you want a specific translation, pass the version IDs explicitly discovered from the registry:

```python
from africa_bitext_builder.builder import CorpusBuilder

# Explicitly selecting Swahili (ID: 1627) and French Louis Segond 1910 (ID: 93 - PD)
builder = CorpusBuilder(
    source_lang="swh",
    target_lang="fr",
    source_version_ids=[1627],  # Explicit opt-in
    target_version_ids=[93],    # French Louis Segond (PD)
    limit=1000,
    sample=True,
    seed=42,
)

# Provide a specific .csv file path or a directory path
out_file = builder.download("data/corpora/swahili_french.csv")
print(f"Saved: {out_file}")

```

---

### 3. Build a Monolingual Corpus

Extract deduplicated sentences for a single language:

```python
from africa_bitext_builder.builder import CorpusBuilder

builder = CorpusBuilder(
    source_lang="amh",
    source_version_ids=[206],  # Explicit version opt-in
    mode="monolingual",
    limit=5000,
)
out_file = builder.download("corpora/amharic.csv")

```

---

## Data Source & Acknowledgements

* **Primary Source:** Bible verse texts are retrieved from [YouVersion](https://www.bible.com).
* **Attributions:** Derived from the pioneering corpus collection work by **Mic-Seth Owusu** ([AfriSpeech/africa-corpus-builder](https://github.com/AfriSpeech/africa-corpus-builder)) and inspired by the [Ghana NLP Community](https://ghananlp.org).
* **License:** Code in this repository is licensed under the [MIT License](https://www.google.com/search?q=LICENSE).

---

## ⚠️ Licensing & Safety Notice

**By default, this library builds corpora restricted exclusively to verified Public Domain (PD) / Creative Commons translations.**

* If a language has no Public Domain translations indexed, `CorpusBuilder` will refuse to run by default to prevent unintentional copyright infringement.
* You may explicitly specify Bible version IDs (`source_version_ids` or `target_version_ids`) using the metadata retrieved via `LanguageRegistry`.
* **Important Notice on Copyrighted Versions:** Supplying version IDs that are **not in the public domain** is done entirely **at your own risk**. You are solely responsible for ensuring you have obtained all necessary permissions or licenses from the relevant copyright holders. We assume no legal responsibility or liability for your extraction, use, or redistribution of copyrighted translations.
