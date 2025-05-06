#!/bin/zsh
set -e

# Activate virtual environment
source venv-build-3.12/bin/activate

# Destination
BUNDLE_PYTHON="dist/Agentic.app/Contents/Resources/lib/python3.12"
SITE_PACKAGES="$BUNDLE_PYTHON/site-packages"

mkdir -p "$SITE_PACKAGES"

MODULES=(
    PyQt5
    agentic
    agentic.dashboard
    agentic.swarm
    agentic.tools
    colorful
    dotenv
    html
    huggingface_hub
    icalendar
    litellm
    numpy
    pandas
    pydantic
    pyarrow
    pytz
    ray
    smart_open
    socketserver
    sqlalchemy
    sympy
    torch
    torchgen
    tornado
    tqdm
    transformers
    typer
    validators
    websockets
    click
    requests
    urllib3
    idna
    uvicorn
    rich
    markdown_it
    mdurl
    pygments
    fastapi
    starlette
    pydantic_core
    annotated_types
    anyio
    sniffio
    httpx
    aiohttp
    multidict
    attr
    yarl
    propcache
    aiohappyeyeballs
    aiosignal
    frozenlist
    openai
    distro
    jiter
    httpcore
    h11
    regex
    tokenizers
    packaging
    jinja2
    markupsafe
    yaml
    cryptography
    sqlmodel
    dateutil
    
    googlenewsdecoder
    selectolax
    google_news_feed
    requests_toolbelt
    lxml
    dateparser
    tzlocal
    dateparser_data
    langsmith
    PIL
    psycopg2
    RayFacadeAgent
    weaviate
    git
)







# Special-cased problematic modules requiring clean reinstallation or wheel builds:
SPECIAL_MODULES=(pandas ray tiktoken typing_extensions)

# Regular copy for most modules:
for MOD in "${MODULES[@]}"; do
    echo "Copying $MOD..."
    MOD_DIR=$(uv run --active python -c "import $MOD, os; print(os.path.dirname($MOD.__file__))" || true)
    if [ -n "$MOD_DIR" ]; then
        cp -R "$MOD_DIR" "$SITE_PACKAGES/"
        DISTINFO=$(find venv-build-3.12/lib/python3.12/site-packages -maxdepth 1 -name "$MOD-"*.dist-info | head -n 1)
        [ -n "$DISTINFO" ] && cp -R "$DISTINFO" "$SITE_PACKAGES/"
    else
        echo "Module $MOD not found in environment, skipping..."
    fi
done

# Manually copy stdlib modules that are just .py files and not in site-packages
STD_PY_MODULES=(socketserver html)

for MOD in "${STD_PY_MODULES[@]}"; do
  echo "Copying stdlib module $MOD..."
  MOD_PATH=$(uv run --active python -c "import $MOD, os; print($MOD.__file__)")
  cp "$MOD_PATH" "$SITE_PACKAGES/" || echo "Failed to copy $MOD"
done






# Handle problematic modules explicitly
echo "Handling problematic modules explicitly..."




# === Special case: dateparser_data (bundled with dateparser, no dist-info) ===
DPDATA_DIR="venv-build-3.12/lib/python3.12/site-packages/dateparser_data"
if [ -d "$DPDATA_DIR" ]; then
    echo "Copying dateparser_data..."
    cp -R "$DPDATA_DIR" dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages/
else
    echo "Warning: dateparser_data not found in venv."
fi






uv pip install Pillow
PIL_PATH=$(uv run --active python -c "import PIL; print(PIL.__file__)")
PIL_DIR=$(dirname "$PIL_PATH")

if [ -d "$PIL_DIR" ]; then
  cp -R "$PIL_DIR" dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages/
else
  echo "❌ PIL directory not found at: $PIL_DIR"
fi

PIL_DISTINFO=$(find venv-build-3.12/lib/python3.12/site-packages -maxdepth 1 -type d -iname "pillow-*.dist-info" | head -n 1)
if [ -n "$PIL_DISTINFO" ] && [ -d "$PIL_DISTINFO" ]; then
  cp -R "$PIL_DISTINFO" dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages/
else
  echo "❌ Pillow dist-info not found."
fi




uv pip install html2text
HTML2TEXT_DIR=$(uv run --active python -c "import html2text, os; print(os.path.dirname(html2text.__file__))")
cp -R "$HTML2TEXT_DIR" dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages/

HTML2TEXT_DISTINFO=$(find venv-build-3.12/lib/python3.12/site-packages -maxdepth 1 -name "html2text-*.dist-info" | head -n 1)
cp -R "$HTML2TEXT_DISTINFO" dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages/



# pandas: Clean reinstall from source (wheel)
uv pip uninstall pandas
uv pip install --no-binary=:all: pandas
cp -R "$(uv run --active python -c 'import pandas, os; print(os.path.dirname(pandas.__file__))')" "$SITE_PACKAGES/"







# ray: Direct wheel install
uv pip uninstall ray
uv pip install ray
cp -R "$(uv run --active python -c 'import ray, os; print(os.path.dirname(ray.__file__))')" "$SITE_PACKAGES/"








# typing_extensions: Explicit copy
# typing_extensions is special-cased due to Py2app mishandling.
# It must exist in BOTH single-file and directory forms.

SITE_PACKAGES="dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages"

uv pip install typing_extensions typing_inspection click requests

# Copy typing_extensions explicitly (special handling)
TYPING_EXTENSIONS_PY=$(uv run --active python -c 'import typing_extensions; print(typing_extensions.__file__)')
cp -f "$TYPING_EXTENSIONS_PY" "$SITE_PACKAGES/"

TYPING_EXTENSIONS_DIR=$(uv run --active python -c 'import typing_extensions, os; print(os.path.dirname(typing_extensions.__file__))')
cp -R "$TYPING_EXTENSIONS_DIR" "$SITE_PACKAGES/"

# typing_inspection (standard handling)
TYPING_INSPECTION_DIR=$(uv run --active python -c 'import typing_inspection, os; print(os.path.dirname(typing_inspection.__file__))')
cp -R "$TYPING_INSPECTION_DIR" "$SITE_PACKAGES/"

# click (standard handling)
CLICK_DIR=$(uv run --active python -c 'import click, os; print(os.path.dirname(click.__file__))')
cp -R "$CLICK_DIR" "$SITE_PACKAGES/"

# requests (standard handling)
REQUESTS_DIR=$(uv run --active python -c 'import requests, os; print(os.path.dirname(requests.__file__))')
cp -R "$REQUESTS_DIR" "$SITE_PACKAGES/"








# tiktoken (from your third_party_builds directory)

# Build and manually install tiktoken for Python 3.12 compatibility
if [ ! -d "third_party_builds/tiktoken" ]; then
    mkdir -p third_party_builds
    git clone https://github.com/openai/tiktoken.git third_party_builds/tiktoken
fi

pushd third_party_builds/tiktoken
uv pip install maturin
maturin build --release --interpreter python3.12
uv pip install --force-reinstall target/wheels/tiktoken-*.whl
popd

# Copy compiled tiktoken into app bundle
cp -R "third_party_builds/tiktoken/tiktoken" \
      "$SITE_PACKAGES/"
cp -R "third_party_builds/tiktoken/tiktoken_ext" \
      "$SITE_PACKAGES/"
cp -R "$(uv run --active python -c 'import site; print(site.getsitepackages()[0])')"/tiktoken-*.dist-info \
      "$SITE_PACKAGES/"




# Copy internal 'agentic.db' module
cp -R src/agentic/db "$SITE_PACKAGES/agentic/"
cp -R src/agentic/utils "$SITE_PACKAGES/agentic/"
cp -R src/agentic/custom_models "$SITE_PACKAGES/agentic/"



# Handle special case: _cffi_backend required by cryptography
CFFI_SO=$(find "$VENV_SITE_PACKAGES" -name "_cffi_backend*.so" | head -n 1)
if [ -n "$CFFI_SO" ]; then
  cp "$CFFI_SO" "$SITE_PACKAGES/"
  echo "✓ Copied _cffi_backend from $CFFI_SO"
else
  echo "✗ Could not find _cffi_backend in $VENV_SITE_PACKAGES"
fi




# Handle special case: six (single-file module)
uv pip install six

SIX_DIR=$(uv run --active python -c "import six, os; print(os.path.dirname(six.__file__))")
cp "$SIX_DIR/six.py" "$SITE_PACKAGES/"

SIX_DISTINFO=$(find "$VENV_SITE_PACKAGES" -maxdepth 1 -name "six-*.dist-info" | head -n 1)
if [ -n "$SIX_DISTINFO" ]; then
  cp -R "$SIX_DISTINFO" "$SITE_PACKAGES/"
  echo "✓ Copied six module and dist-info"
else
  echo "✗ Could not find six dist-info directory"
fi

# Copy static_dashboard_server.py into the bundle (for dashboard serving in production)
cp static_dashboard_server.py dist/Agentic.app/Contents/Resources/lib/python3.12/
