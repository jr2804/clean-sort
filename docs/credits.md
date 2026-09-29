---
title: Credits
hide:
- toc
---

## Acknowledgements

pyreorder builds on ideas from several Python sorting tools. The in-class
method sorter (`pyreorder.undersort`) is an adapted reimplementation of
**[undersort](https://github.com/kivicode/undersort)** by Kivikood (MIT) —
class-method ordering by visibility and method type, including the `# nosort`
opt-out directive.

The dependency-aware function ordering was inspired by
**[ssort](https://github.com/bwhmather/ssort)**,
**[sdsort](https://github.com/eirikurt/sdsort)** (the step-down rule), and
**[ABSort](https://github.com/MapleCCC/ABSort)**. Import-block integration
follows the configuration model of **[isort](https://pycqa.github.io/isort/)**
and **[ruff](https://docs.astral.sh/ruff/)**.

All reused concepts retain their original licences and copyright; vendored
code carries an attribution header in its module docstring.

## Dependencies

```python exec="yes"
--8<-- "scripts/gen_credits.py"
```
