# TreeTracer

TreeTracer is tool to visualize phylogenetic tree space.

## Recommended installation and usage (Linux/macOS)

### 1. Install the `uv` package manager

```
wget -qO- https://astral.sh/uv/install.sh | sh
```

Or using Homebrew:

```
brew install uv
```

### 2. Clone the repo

```
git clone https://github.com/hongsamL/treetracer.git
cd treetracer
```
### 3. Sync dependencies and activate a virtual environment with `uv`

```
uv sync
source .venv/bin/activate
```
### 4. Install TreeTracer
```
uv pip install -e .
```

### 5. Run treetracer

```
uv run treetracer
```

### NOTE

To run each time using `uv` it's NOT necessary to load the python virtual environment using `source .venv/bin/activate`. 

`uv run treetracer` will automatically take care of this.
