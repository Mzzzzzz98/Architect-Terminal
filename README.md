# ArchitectTerminal (refactor-in-progress)

This workspace is being refactored from a single-file app into a proper Python package.

## Run (dev)

```powershell
cd F:\Architect_Project
python -m architect_terminal
```

Legacy entrypoint still exists:

```powershell
python .\01_Engineering_Base\tracker.py
```

## Quick checks

```powershell
python -m py_compile .\architect_terminal\__main__.py
python -m pytest
```

