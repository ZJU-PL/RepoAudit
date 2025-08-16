# Plugins for RepoAudit

## Reports Judge


- **False Possitive Judge**: Identify critical conditions, Solve constraints
- **Incorrecness Logic Judge**: Identify bugs tha are "more likely" to be true
- **Security Judge**: Identify bugs that are more related to secrity 


## Semantic Indexing

### 🚀 Phase 1: Code Semantic Indexing

Generate a semantic index of the codebase to enable context-aware retrieval.

**General**

```bash
python semantic_summary.py /path/to/repo
```

**Domain-Specific**

```bash
python nullability_summary.py /path/to/repo
```

### 🚀 Phase 2: Querying the CodeBases

TBD: provide interfaces for RepoAudit

## Swarm Auditors

## Tool  Use

- Retrival: grep, diff, ctags, clangd, ...
- Linter: pylint, ....

