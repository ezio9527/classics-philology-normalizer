# Changelog

All notable changes to `classics-philology-normalizer` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-01

### Added
- **Core Invariants Definition**:
  - Zero Semantic/Textual Mutation principle: 100% preservation of classical Chinese characters, forbidding vernacular paraphrasing or unauthorized character replacement.
  - Text Diff Invariance Gate: character similarity $\ge 99.8\%$ before and after cleaning.
- **Operational 4-Step Pipeline**:
  - Step 1: Typology Classification across Paradigm A (汇编全书型), Paradigm B (主干经注型), and Paradigm C (纲目矩阵型).
  - Step 2: Heading AST & Echo Suppression (Single global H1, TOC alignment, echo heading elimination, runaway heading fix, macro container recovery).
  - Step 3: Micro-Structural Styling (independent scripture paragraphs, blockquote double-column original notes, H4 commentary headings, standardized 4-pillar bazi tables, rhymed poetry blockquotes).
  - Step 4: Large File Chunking Strategy for books over 30,000 words.
- **Automation Scripts (`resources/scripts/`)**:
  - `diff_verifier.py`: Markdown token and crawler noise stripping with SequenceMatcher similarity measurement and diff reporting.
  - `chunk_splitter.py`: Heading-based AST splitter with manifest generation for large classical works.
  - `chunk_merger.py`: Topological chunk assembler with integrated end-to-end textual invariance validation.
  - `normalizer_tools.py`: Paradigm detector, crawler noise cleaner, echo suppressor, runaway heading corrector, and four-pillar bazi chart formatter.
- **Standardized Templates (`resources/templates/`)**:
  - `paradigm_A_template.md`: Compilation encyclopedia paradigm structure.
  - `paradigm_B_template.md`: Scripture with commentary paradigm structure.
  - `paradigm_C_template.md`: Matrix outline paradigm structure.
  - `bazi_table_template.md`: Standard four-pillar natal chart table layout.
  - `chunk_manifest_template.json`: Chunking manifest metadata schema.
- **Automated Test Suite (`tests/`)**:
  - Unit tests covering `diff_verifier`, `chunk_lifecycle`, and `normalizer_tools` (12 tests, 100% passing).
