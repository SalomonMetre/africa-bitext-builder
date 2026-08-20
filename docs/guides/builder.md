# Compiling Corpora

The `CorpusBuilder` class handles alignment, deduplication, sampling, and file export.

---

## Parallel Corpus Generation

### Default Mode (Public Domain Only)

When no version IDs are passed, `CorpusBuilder` uses only verified Public Domain translations. If a language lacks Public Domain translations, initialization raises a `ValueError`.

```python
from africa_bitext_builder.builder import CorpusBuilder

builder = CorpusBuilder(
    source_lang="twi",
    target_lang="en",
    limit=5000,
)

# Downloads required files, aligns on verse_key, and writes CSV
out_path = builder.download("corpora/")
print("Exported to:", out_path)

```

---

### Explicit Version Opt-In (Non-Public Domain)

To extract translations that are not in the public domain, pass the target version IDs explicitly.

/// warning | Licensing Disclaimer
Supplying version IDs that are not in the public domain is done at your own risk. Ensure you have obtained proper licensing permissions before redistributing copyrighted text.
///

```python
builder = CorpusBuilder(
    source_lang="swh",
    target_lang="fr",
    source_version_ids=[1627],  # Explicit Swahili version ID
    target_version_ids=[93],    # French Louis Segond 1910 (PD)
    limit=1000,
    sample=True,                # Randomly sample verses
    seed=42,
)

# Export directly to a specified filename
out_path = builder.download("data/swahili_french_sample.csv")

```

---

## Monolingual Extraction

Set `mode="monolingual"` to extract deduplicated sentences for a single language:

```python
builder = CorpusBuilder(
    source_lang="amh",
    source_version_ids=[206],
    mode="monolingual",
    limit=10000,
)

out_path = builder.download("corpora/")

```

---

## Export Path Rules

The `download(out)` method handles both directory destinations and explicit filenames:

| Argument | Resulting Output Path |
| --- | --- |
| `download("corpora/")` | `corpora/{source}_{target}_parallel.csv` |
| `download("corpora/")` *(mono)* | `corpora/{source}_monolingual.csv` |
| `download("custom.csv")` | `custom.csv` |
