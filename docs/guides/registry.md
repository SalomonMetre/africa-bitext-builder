# Language & License Discovery

The `LanguageRegistry` class indexes dataset files and their licensing records, giving you metadata lookups without downloading the underlying dataset files.

## Resolving a Language by ISO Code

Use `resolve()` for direct lookups using standard ISO-639 language codes:

```python
from africa_bitext_builder.registry import LanguageRegistry

reg = LanguageRegistry()
swh = reg.resolve("swh")
print(swh)
# <Language code='swh' name='Swahili' region='African' versions=13 (PD: 0)>
```

## Inspecting Licensing Status

Each `Language` object provides direct access to its Bible translations and their verified copyright status:

```python
# All available versions
all_ids = [v.id for v in swh.bible_versions]

# Public Domain / Creative Commons versions
pd_ids = [v.id for v in swh.public_domain_versions]

# Copyrighted versions
non_pd_ids = [v.id for v in swh.non_public_domain_versions]

print(
    f"Total: {len(all_ids)} | "
    f"Public Domain: {len(pd_ids)} | "
    f"Non-PD: {len(non_pd_ids)}"
)
```

## Searching Metadata

The `search()` method allows querying the registry across different criteria.

### By Country Code

```python
# Find all indexed languages spoken in Ghana (GH)
ghana_langs = reg.search(country="GH")
for lang in ghana_langs:
    print(f"{lang.code}: {lang.name}")
```

### By Abbreviation

```python
# Search by edition abbreviation
# (e.g. French Louis Segond "LSG")
matches = reg.search(abbr="LSG")
for lang, version in matches:
    print(
        f"{lang.name} -> {version.name} "
        f"(ID: {version.id}, PD: {version.is_public_domain})"
    )
```

### By Version ID

```python
# Locate metadata by numerical translation ID
result = reg.search(version_id=93)
if result:
    lang, version = result
    print(f"ID 93 belongs to {lang.name}: {version.name}")
```

### By Language Name

```python
# Substring search across all language names
results = reg.search(lang_name="oromo")
for lang in results:
    print(f"{lang.code}: {lang.name}")
```

## Listing Languages

Retrieve all indexed languages, or filter to languages with at least one Public Domain version:

```python
# List all indexed languages
all_languages = reg.list()

# Filter exclusively for languages with at least one Public Domain version
pd_languages = reg.list(public_domain_only=True)
```
