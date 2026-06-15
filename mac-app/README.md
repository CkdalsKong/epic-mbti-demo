# Interactive EPIC

Interactive EPIC is a macOS demo app that visualizes EPIC indexing for a Wikipedia document:

1. Set a PrefWiki persona.
2. Search and extract a Wikipedia page.
3. Chunk the document.
4. Compare indiscriminate Existing RAG indexing with EPIC indexing.
5. Inspect kept chunks, generated instructions, and related preferences.

## Runtime Pieces

- **macOS app**: SwiftUI app in `InteractiveEPIC.xcodeproj`
- **Local EPIC runtime**: `InteractiveEPIC/epic_runtime_server.py`
- **Embedding model**: `facebook/contriever`
- **Vector index**: `FAISS IndexFlatIP`
- **LLM server**: OpenAI-compatible vLLM endpoint at `http://127.0.0.1:8123`
- **LLM model**: `meta-llama/Llama-3.1-8B-Instruct`

The app talks to the local EPIC runtime at `http://127.0.0.1:8765`. The local runtime talks to vLLM at `http://127.0.0.1:8123`.

## 1. Create the Conda Environment

From the repository root:

```zsh
cd /path/to/InteractiveEPIC
conda create -n epic python=3.11
conda activate epic
pip install -r requirements.txt
```

The Python runtime uses `facebook/contriever` with `local_files_only=True`, so the model must already exist in your Hugging Face cache. If needed, download it once while the `epic` environment is active:

```zsh
python -c "from transformers import AutoModel, AutoTokenizer; AutoTokenizer.from_pretrained('facebook/contriever'); AutoModel.from_pretrained('facebook/contriever')"
```

## 2. Start or Connect vLLM

Start vLLM so it is reachable from this Mac at port `8123`.

If vLLM is running on a remote server, create an SSH tunnel:

```zsh
ssh ubi -L 8123:localhost:8123
```

In another terminal, verify the forwarded vLLM endpoint:

```zsh
curl -i http://127.0.0.1:8123/health
curl -sS http://127.0.0.1:8123/v1/models | python -m json.tool
```

The model list should include:

```txt
meta-llama/Llama-3.1-8B-Instruct
```

## 3. Start the Local EPIC Runtime

Run:

```zsh
./start_epic_runtime.sh
```

This script:

1. Activates the `epic` conda environment.
2. Checks vLLM at `http://127.0.0.1:8123/health`.
3. Loads `facebook/contriever`.
4. Starts the EPIC runtime server at `http://127.0.0.1:8765`.

Keep this terminal open while using the app.

To stop the runtime:

```zsh
./stop_epic_runtime.sh
```

## 4. Run the Mac App

### Option A: Xcode

Open the project:

```zsh
open InteractiveEPIC.xcodeproj
```

Select the `InteractiveEPIC` scheme, then press Run.

### Option B: Command Line

Build and open the app:

```zsh
xcodebuild \
  -project InteractiveEPIC.xcodeproj \
  -scheme InteractiveEPIC \
  -destination platform=macOS \
  -derivedDataPath /private/tmp/InteractiveEPICDerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build

open /private/tmp/InteractiveEPICDerivedData/Build/Products/Debug/InteractiveEPIC.app
```

## Expected Order

Use this order for demos:

1. Create and install the `epic` conda environment.
2. Start vLLM or open the SSH tunnel to vLLM.
3. Confirm `http://127.0.0.1:8123/health` returns HTTP 200.
4. Run `./start_epic_runtime.sh`.
5. Launch the macOS app.
6. Choose a persona, search Wikipedia, chunk the document, then start indexing.
