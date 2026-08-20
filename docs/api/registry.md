# LanguageRegistry API Reference

::: africa_bitext_builder.registry.LanguageRegistry
    options:
      members:
        - list_languages
        - resolve
        - search

::: africa_bitext_builder.registry.Language
    options:
      members:
        - code
        - name
        - is_african
        - text_column
        - bible_versions
        - public_domain_versions
        - non_public_domain_versions
        - countries

::: africa_bitext_builder.registry.BibleVersion
    options:
      members:
        - id
        - abbrev
        - name
        - is_public_domain
        - country
        - has_text
