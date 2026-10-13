# 9. Dependencies and licenses

RLR's own code is MIT-licensed. This page records what else ships with or is
pulled in by it, so that downstream users (and the Open QA Initiative's
disclosure requirement for copyleft dependencies) have one place to look.
Regenerate the package table from `uv.lock` when dependencies change.

## Summary

- **No GPL, LGPL or AGPL anywhere** in the dependency tree, in any extra.
- Three packages are **MPL-2.0** (file-level weak copyleft): `certifi`,
  `pathspec`, `tqdm`. RLR uses them unmodified, which carries no obligation
  beyond leaving their license notices intact; MPL does not extend to RLR's
  code.
- The optional `mt` extra pulls **NVIDIA CUDA runtime wheels** under NVIDIA's
  proprietary license, via `torch` on Linux x86-64. They are redistributable
  binaries, not open source. Installations without the `mt` extra do not
  receive them.
- One runtime dependency has **no license metadata on PyPI**: `biblelib`
  (Clear-Bible). Its repository states MIT for the code.
- The datasets RLR reads are **not** part of the Python distribution and keep
  their own terms (next section).

## Runtime dependencies (default install)

| Package | License | Why |
|---|---|---|
| pydantic, pydantic-core, annotated-types, typing-inspection | MIT | domain types |
| typer, click, rich, shellingham, markdown-it-py, mdurl, pygments | MIT / BSD / ISC / BSD-2 | CLI |
| pyyaml | MIT | figures-of-speech YAML |
| httpx, httpcore, h11, anyio, idna, sniffio | BSD-3-Clause / MIT | downloads |
| certifi | **MPL-2.0** | CA bundle for httpx and requests |
| bible-figures-of-speech | MIT (code) + CC BY-SA 4.0 (data) | stage 5 notes, data bundled |
| biblelib, pooch, requests, urllib3, charset-normalizer, platformdirs, packaging | MIT (per repository; no PyPI metadata) / BSD / Apache-2.0 / MIT / MIT / MIT / Apache-2.0 OR BSD-2 | verse references for the notes; `biblelib` downloads optional word-mapping data on first use of features RLR does not call |

## `demo` extra

| Package | License |
|---|---|
| fastapi, starlette | MIT / BSD-3-Clause |
| uvicorn | BSD-3-Clause |

## `mt` extra (MADLAD-400 locally)

| Package | License |
|---|---|
| transformers, tokenizers, safetensors, huggingface-hub, hf-xet | Apache-2.0 |
| sentencepiece | Apache-2.0 |
| torch | BSD-3-Clause (plus bundled third-party notices) |
| tqdm | **MPL-2.0 AND MIT** |
| numpy, sympy, mpmath, networkx, filelock, fsspec, jinja2, markupsafe, regex, triton, setuptools | BSD / MIT / Apache-2.0 / CNRI-Python (regex) |
| nvidia-* (cublas, cuda-cupti, cuda-nvrtc, cuda-runtime, cudnn, cufft, cufile, curand, cusolver, cusparse, cusparselt, nccl, nvjitlink, nvshmem, nvtx), cuda-toolkit, cuda-bindings, cuda-pathfinder | **NVIDIA proprietary** (CUDA EULA) / Apache-2.0 (bindings, pathfinder) |

The model itself, `google/madlad400-3b-mt`, is Apache-2.0 and is downloaded
from Hugging Face at first use, not shipped.

## `dev` extra (not needed to run RLR)

ruff, mypy, mypy-extensions, pytest, pytest-cov, coverage, pre-commit,
virtualenv, distlib, cfgv, identify, nodeenv, iniconfig, pluggy,
types-pyyaml, httpx2 (and httpcore2, truststore): all MIT, BSD, PSF or
Apache-2.0, except `pathspec` (**MPL-2.0**, via mypy and pre-commit).

## Data shipped inside the package

| File | What | License |
|---|---|---|
| `src/rlr/data/renderings/swh.json.gz`, `ind.json.gz`, `por.json.gz` | The figures-of-speech notes for Mark, Luke and John rendered into Swahili, Indonesian and Portuguese by MADLAD-400 (`rlr pretranslate --bundle`), keyed by a hash of the English | **CC BY-SA 4.0**: derivative works of unfoldingWord's notes, so they carry the same license (recorded in each file) |

## Data read at run time

| Source | License | Redistributed by RLR? |
|---|---|---|
| Glottolog CLDF export (`glottolog/glottolog-cldf`) | CC BY 4.0 | No; downloaded into the user's cache. A few rows are reproduced as test fixtures, credited in NOTICE. |
| eBible Corpus (`BibleNLP/ebible`) metadata and texts | Per text, from `licences.tsv`: public domain, CC BY, CC BY-SA, CC BY-NC, CC BY-ND, CC BY-NC-ND, or unknown | No; each edition is downloaded on request and its license is shown with every verse. No-derivatives texts are displayed but never machine-translated. |
| unfoldingWord Translation Notes and translationAcademy, as `bible-figures-of-speech` | CC BY-SA 4.0 | Yes, inside the dependency, with its own LICENSE and attribution. Two notes appear in the test fixtures, credited in NOTICE. |
| MADLAD-400 weights (`mt` extra) | Apache-2.0 | No; fetched from Hugging Face. |

## How to regenerate

```bash
uv lock
uv tree --all-extras --all-groups
```

and check each package on PyPI (`https://pypi.org/pypi/<name>/json`, fields
`license_expression`, `license`, and the `License ::` classifiers). The
summary above was produced that way on 2026-10-13 against 92 locked packages.
