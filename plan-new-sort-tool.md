# @GitHub

Ok, let's discuss my own sorting tool and make a plan that I will later handover to a coding agent!
Name: clean-sort
CLI name: csort

Use project template with all features enables from: [jr2804/copier-uv-plus: Copier template for modern Python projects with mise, uv, and AI tooling - Codeberg.org](https://codeberg.org/jr2804/copier-uv-plus)

Concept:

- Should be based on the tools we already listed.
- must run as uv-tool (uv tool instal ..., uvx ... -> already guaranteed via template!)
- comprehensive documentation with a lot of examples for each sorting type
- should have a TOML config that can be either part of pyproject toml (as in e.g., undersort) or stand-alone (in project root or in <project>/.config/csort.toml)
- [module.sections] sorting as you suggested
- in general, for in-section sorting, there might be multiple ways to sort it. From alphabetical to "clean code" methods from absort, ssort and/or
- for in-class sorting, nothing needs to be re-invent; undersort is *exactly* what I want (including its configuration). We may simply take over (improved) code from there and give acknowledgements?
- on isort functionality, I'm unsure; which option would you recommend?
  - leave out, refer to ruff / isort
  - Use [PyCQA/isort: A Python utility / library to sort imports.](https://github.com/pycqa/isort) as dependency (and move all settings from here: [isort/docs/configuration/custom_sections_and_ordering.md at main · PyCQA/isort](https://github.com/PyCQA/isort/blob/main/docs/configuration/custom_sections_and_ordering.md) into the TOML config)
  - use ruff-bindings, as in e.g., [reflex-dev/ruff-format](https://github.com/reflex-dev/ruff-format) (requires compiler on target machine or setting up build system on Github/Codeberg repo -> complicated)
  - use ruff-pseudo-bindings from official ruff package (installs  another ruff.exe as dependency and communicates via subprocess)
- having ruff available would allow skipping ruff installation completely, we could then have a subcommand like: "csort ruff <...arguments for ruff ...> ", which simply would be a "proxy" for an integrated ruff?

Anything left?

Please draft a  comprehensive implementation plan in Markdown that I can hand over to a coding agent

Here’s a draft implementation plan for **clean-sort** / **csort** that you can hand over to a coding agent.

***

## 1. Goals and scope

**Primary goal:**
Provide an AST‑based, non‑AI “structural sorter” for Python that:

- Reorders **top‑level statements** by configurable *section types* (imports, constants, enums, classes, functions, main block, etc.).
- Provides configurable **in‑section sorting strategies** (alphabetical, dependency/abstraction-based via ssort/ABSort/sdsort, or “keep order”).
- Reuses **undersort** semantics for in‑class method ordering, including its configuration model.[^1]
- Integrates cleanly into **uv tool** workflows (`uv tool install …`, `uvx …`) via the `copier-uv-plus` template (mise + uv + AI tooling).[^2][^3]

**Non‑goals (for v1):**

- No formatting (whitespace, line wrapping) beyond what is necessary to keep code syntactically correct.
- No semantic refactoring (renames, dead code removal, etc.) like pyrefact does.[^4]

***

## 2. Project scaffolding and packaging

**Template:**

- Use the Codeberg `jr2804/copier-uv-plus` template as base; it’s conceptually similar to existing **copier‑uv** templates: uv‑based project, preconfigured tools (ruff, pytest, docs), GitHub workflows, etc.[^5][^3]

**Project metadata:**

- Project name: `clean-sort`
- Python import package: `clean_sort` (or `csort`).
- CLI executable: `csort` (via `pyproject.toml` `[project.scripts]` entry).

**uv tool integration:**

- Ensure `pyproject.toml` is set up for `uv tool install` consumption (as in uv‑based templates).[^6][^3]
- Target commands:
  - `uv tool install git+https://codeberg.org/<you>/clean-sort`
  - `csort ...` via `uvx csort` or directly after tool install.

***

## 3. High‑level architecture

**Layers:**

1. **CLI layer** (`clean_sort.cli`):
    - Argument parsing (`typer` or `click`, depending on template).
    - Commands: `csort run`, `csort check`, `csort diff`, `csort ruff`, `csort version`, etc.
2. **Config layer** (`clean_sort.config`):
    - Discover and parse TOML config (pyproject and standalone files).
    - Produce a unified `Config` object (typed dataclass) describing module sections and per‑section strategies.
3. **AST / CST layer** (`clean_sort.ast`):
    - Parse source into a concrete syntax tree while preserving comments and formatting as much as possible.
    - Strong recommendation: base on `libcst` or similar CST, to support safe reordering without losing comments.[^7]
4. **Classification \& layout layer** (`clean_sort.layout`):
    - Classify top‑level statements into semantic **section types**.
    - Build intermediate representation: `ModuleLayout` = list of sections with contained nodes.
5. **Sorting engines layer** (`clean_sort.engines`):
    - Pluggable sorting strategies:
        - `alpha` (simple alphabetical).
        - `stepdown` (sdsort‑style step‑down rule).[^8][^9]
        - `abstraction` (ABSort‑/ssort‑inspired dependency/abstraction ordering).[^10][^11]
        - `undersort` (class method ordering).[^1]
        - `keep` (preserve original order).
    - Engines operate on IR rather than raw CST.
6. **Import integration layer** (`clean_sort.imports`):
    - Optional integration with isort or Ruff for import‑only sorting.[^12][^13][^14]
7. **Renderer layer** (`clean_sort.render`):
    - Reassemble sorted CST back into source code.

***

## 4. Configuration model

### 4.1 Config discovery

Mimic **isort**’s multi‑file config resolution:[^15]

1. Look for **project‑local standalone config** (in this priority order):
    - `<project_root>/csort.toml`
    - `<project_root>/.config/csort.toml`
2. Look for **pyproject config**:
    - `[tool.csort]` table in `pyproject.toml`.[^16][^17]
3. Optionally allow explicit `--config PATH` override, as isort’s `--settings-path` does.[^15]

Algorithm:

- Starting from the target file’s directory, walk up to the project root; first matching config wins, but allow **hierarchical overrides** if desired (similar to isort’s `--resolve-all-configs`).[^15]

### 4.2 Config schema (TOML)

Top‑level:

```toml
[tool.csort]
# global defaults
enabled = true
check = false  # exit non-zero if changes would be made
diff = false   # show unified diff instead of writing files
```

Module sections (ordering):

```toml
[tool.csort.module]
sections = [
  "imports",
  "typing_imports",
  "module_constants",
  "enums",
  "dataclasses",
  "classes",
  "functions",
  "main_block",
]
```

Per‑section settings:

```toml
[tool.csort.section.imports]
engine = "ruff"    # "ruff", "isort", "none"
respect_external_config = true  # use [tool.isort] / [tool.ruff] if present [web:52][web:67]

[tool.csort.section.module_constants]
strategy = "alpha" # "alpha", "keep"

[tool.csort.section.classes]
strategy = "abstraction"  # "abstraction", "alpha", "keep"
sub_strategy = "undersort"  # "undersort" for in-class methods [web:13]

[tool.csort.section.functions]
strategy = "stepdown"  # Clean Code step-down rule [web:27][web:29]

[tool.csort.section.main_block]
strategy = "keep"
```

Class‑level configuration (delegated to undersort semantics):

```toml
[tool.csort.class_methods]
enabled = true
order = [
  "dunder_lifecycle",   # __init__, __new__, etc. [web:9]
  "public_instance",
  "public_class",
  "public_static",
  "protected",
  "private_unused",
  "other_dunder",
]
```

The coding agent should design this schema so that **undersort’s existing configuration** can be mapped as closely as possible, potentially allowing `csort` to read `[tool.undersort]` for backwards compatibility and translate it into `[tool.csort.class_methods]`.[^1]

***

## 5. Section classification rules

Implement a classifier that maps each top‑level CST node into one of the configured section names:

- `imports`: `import ...`, `from ... import ...`.
- `typing_imports`: `if TYPE_CHECKING: ...` blocks + type‑only imports.
- `module_constants`: assignments to ALL_CAPS names, simple literal assignments, config dicts, etc.
- `enums`: subclasses of `enum.Enum` / `StrEnum`.
- `dataclasses`: classes decorated with `@dataclass`.
- `classes`: all other top-level `class` definitions.
- `functions`: top-level `def` definitions (excluding `main` if identified).
- `main_block`: `if __name__ == "__main__":` block.

Important: classification should be **configurable**:

```toml
[tool.csort.classification]
constants_pattern = "^[A-Z_][A-Z0-9_]*$"
main_detection = "if_name_main"  # alternative strategies possible
```

***

## 6. Sorting strategies per scope

### 6.1 Module section ordering

Algorithm:

1. For each file:
    - Parse CST.
    - Classify each top-level node into a section type.
    - Group nodes by section type.
2. Reassemble:
    - Iterate `module.sections` in configured order.
    - For each section:
        - Apply section-specific **in‑section strategy**.
        - Append resulting nodes to output sequence.

Ensure we preserve comments attached to sections (e.g., module header comments) by treating leading comments as belonging to the first logical node they precede.

### 6.2 In‑section strategies

Design a pluggable engine interface:

```python
class SectionSorter(Protocol):
    def sort(self, nodes: list[CSTNode], context: SortContext) -> list[CSTNode]:
        ...
```

Engines:

- `alpha`: sort nodes lexicographically by primary symbol name (`class Foo`, `def bar`).
- `keep`: return nodes unchanged.
- `stepdown`: implement sdsort‑like step‑down ordering by analyzing call relationships among functions/methods and ordering high‑level callers before callees.[^9][^18][^8]
- `abstraction`: ABSort/ssort‑style dependency graph and abstraction ordering:
  - Build dependency graph among defs (classes/functions) based on symbol usage.
  - Use topological sort + SCC condensation to determine abstraction levels.[^11][^10]
  - Provide options analogous to ABSort (DFS/BFS traversal, aggressive AST similarity grouping, etc.).[^11]

Configuration example:

```toml
[tool.csort.section.functions]
strategy = "abstraction"
graph_traversal = "dfs"        # like ABSort's --dfs / --bfs [web:14]
aggressive = true              # AST-similarity grouping [web:14]
```

### 6.3 In‑class sorting (undersort integration)

Approach:

- Treat undersort as the **reference implementation** for method ordering:
  - License: MIT, so code reuse with attribution is allowed.[^1]
- Options:

1. **Vendor undersort’s core logic** into `clean_sort.engines.undersort`, preserving copyright and adding clear acknowledgements in `CREDITS.md` and module docstring.
2. Or, depend on undersort as a library and call its API, if stable.

Behavior:

- For each class body, separate:
  - Docstring, special attributes, inner classes, attributes, lifecycle dunders, public methods, unused private methods, other dunders—mirroring ssort’s default groups where appropriate.[^10]
- Order methods by configured visibility/type sequence (public/protected/private, instance/class/static) and any subclass rules the undersort config allows.[^19][^1]
- Respect user configuration from `[tool.csort.class_methods]` and, optionally, `[tool.undersort]` if present.[^1]

***

## 7. Import sorting design and recommendation

You listed four options; here’s a recommended plan.

### 7.1 Engines and options

Support three `imports.engine` modes:

1. `none`: csort does not change imports; user relies on Ruff/isort externally.
2. `isort`: csort delegates to **isort** either as:
    - A library call (`isort.api.sort_file`) with config auto‑detected via isort’s normal rules.[^20][^15]
    - Or a subprocess `isort` invocation.
3. `ruff`: csort delegates to **Ruff**’s `I` rule:
    - Subprocess: `ruff check <paths> --select I --fix`.[^14][^21]

### 7.2 Recommendation

Given:

- You already use **Ruff** for imports (`--select I --fix`).[^22][^23]
- isort’s configuration model is rich but independent and already documented.[^13][^12]
- ruff‑format shows that using Ruff’s Rust bindings from Python requires more build system complexity.[^24]

**Recommended approach for v1:**

- Implement **pluggable, subprocess‑based delegation**:
  - Default `imports.engine = "ruff"` (for users who already have Ruff).
  - Fallback to `isort` if Ruff is unavailable and `imports.engine = "isort"` is configured.
- Do **not** ship Rust bindings via ruff‑format in v1; keep the project pure Python + external CLI.[^24]

Config example:

```toml
[tool.csort.section.imports]
engine = "ruff"
ruff_args = ["--select", "I", "--fix"]
isort_args = ["--profile", "black"]
```

The coding agent should implement robust subprocess handling and pass through extra args from config.

***

## 8. Ruff proxy subcommand (`csort ruff`)

To allow users to skip installing Ruff separately:

- Add optional dependency group:

```toml
[project.optional-dependencies]
ruff = ["ruff"]
```

- In CLI:

```bash
csort ruff <args...>
```

Behavior:
    - If `ruff` is importable in the csort environment, spawn `ruff` as a subprocess with the given args.
    - If `ruff` is not installed:
        - Emit a clear error suggesting either:
            - `uv tool install ruff` separately, or
            - Installing `clean-sort[ruff]` so Ruff is bundled.

This design keeps `csort` as a **thin proxy** rather than reimplementing Ruff bindings, similar to your “ruff‑pseudo‑bindings” idea.[^21][^24]

***

## 9. CLI design

Main commands:

- `csort run [PATH ...]`
  - Apply sorting in‑place based on config.
- `csort check [PATH ...]`
  - Exit non‑zero if any file is not in sorted form; used in CI/pre‑commit.
- `csort diff [PATH ...]`
  - Print unified diffs for changes.
- `csort ruff [ARGS ...]`
  - Proxy to Ruff as described above.
- `csort config show`
  - Show effective config for a given file (merged from pyproject and local TOML).
- `csort config init`
  - Generate a template `csort.toml` into project root.

Options:

- `--section-only imports,classes` to limit which sections to sort.
- `--strategy-overrides` for quick experiments (e.g., `functions=alpha` overriding config).

***

## 10. Testing strategy

Tests should target safety and determinism:

- **Golden file tests**:
  - For each sorting mode (alpha, abstraction, stepdown, undersort), provide example inputs and expected outputs.
- **Round‑trip safety**:
  - Parse → sort → render → reparse; assert semantic equivalence via AST comparison for supported transformations.
- **Config resolution tests**:
  - Direct pyproject config, standalone TOML, nested directory configs (like isort’s multi‑config behavior).[^15]
- **Integration tests**:
  - With `imports.engine = "isort"` and `="ruff"`, ensure subprocess invocation respects project’s existing config.[^12][^16]

Optionally add property‑based tests for classification (e.g., random code snippets where only section grouping changes).

***

## 11. Documentation plan

Use the template’s docs stack (likely something like Zensical), mirroring **copier‑uv**: README, reference docs, usage examples, CI docs.[^3][^5]

Documentation structure:

- **Overview**: Why structural sorting, how it complements Ruff/Black.
- **Quickstart**:
  - `uvx copier ...` to generate project (already handled by template).[^3]
  - `uv tool install git+...` for installing `csort`.
- **Configuration**:
  - Detailed TOML schema with examples per section and strategy.
  - Examples of `module.sections` layouts (“constants above classes”, “classes above functions”, etc.).
- **Sorting modes**:
  - Example files sorted with:
    - `functions.strategy = "stepdown"` (top‑down narrative).[^9]
    - `classes.strategy = "abstraction"` (ABSort‑style).[^11]
    - `class_methods.sub_strategy = "undersort"` (visibility/type ordering).[^1]
- **Integration guides**:
  - Pre‑commit hook configuration.
  - CI recipes (GitHub Actions, GitLab) similar to those for Black/isort/Ruff.[^17]

***

## 12. Licensing and acknowledgements

- Use a permissive license (MIT or Apache‑2), consistent with template defaults.[^3]
- Add `CREDITS.md` acknowledging:
  - undersort (MIT).[^1]
  - ABSort, ssort, sdsort, isort, Ruff, and any other libraries reused.
- For vendored code (e.g., portions of undersort), retain original copyright headers.

***

## 13. Future extensions (for roadmap)

- IDE/agent integration:
  - Expose a pure‑Python API (e.g., `clean_sort.sort_code(text: str, config: Config) -> str`) for coding agents and IDE extensions.
- Multi‑file dependency sorting:
  - Optionally compute abstraction/dependency across multiple modules at once (advanced).
- Language‑server protocol (LSP) hook:
  - Provide “organize structure” command analogous to “organize imports”.

This plan should give the coding agent a clear roadmap: scaffold with `copier-uv-plus`, implement config and AST layers, plug in section classification and sorting engines inspired by ABSort/ssort/sdsort and undersort, and provide pragmatic import- and Ruff‑integration via subprocess rather than compiled bindings.[^8][^12][^10][^24][^11][^1]

***

[^1]: <https://github.com/kivicode/undersort>

[^2]: <https://mise.jdx.dev/mise-cookbook/python.html>

[^3]: <https://pawamoy.github.io/copier-uv/generate/>

[^4]: <https://github.com/OlleLindgren/pyrefact>

[^5]: <https://pawamoy.github.io/copier-uv/>

[^6]: <https://github.com/kj-9/uv-tool-min-copier>

[^7]: <https://gist.github.com/gtors/27f878d2d42721d0f69e0ec98810ef80>

[^8]: <https://github.com/eirikurt/sdsort>

[^9]: <https://dzone.com/articles/the-stepdown-rule>

[^10]: <https://github.com/bwhmather/ssort>

[^11]: <https://github.com/MapleCCC/ABSort>

[^12]: <https://pycqa.github.io/isort/docs/configuration/custom_sections_and_ordering.html>

[^13]: <https://github.com/PyCQA/isort/wiki/isort-Settings>

[^14]: <https://github.com/PyCQA/isort>

[^15]: <https://pycqa.github.io/isort/docs/configuration/config_files.html>

[^16]: <https://stackoverflow.com/questions/62069596/configuring-isort-and-autoflake-with-project-toml>

[^17]: <https://docs.gitlab.com/development/python_guide/create_project/>

[^18]: <https://stackoverflow.com/questions/76611154/how-to-automatically-sort-functions-in-classes-by-their-usage>

[^19]: <https://www.reddit.com/r/Python/comments/1oeauls/undersort_a_util_for_sorting_class_methods/>

[^20]: <https://pycqa.github.io/isort/reference/isort/index.html>

[^21]: <https://github.com/reflex-dev/templates/blob/main/ruff.toml>

[^22]: <https://realpython.com/python-pyproject-toml/>

[^23]: <https://github.com/WeblateOrg/customize-example/blob/main/pyproject.toml>

[^24]: <https://github.com/reflex-dev/ruff-format>
