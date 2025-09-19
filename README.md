# SkySatPrep

**Authors:** Aram Fathian; Dan Shugar
**Affiliation:** Department of Earth, Energy, and Environment; Water, Sediment, Hazards, and Earth-surface Dynamics (waterSHED) Lab; University of Calgary

**License:** MIT


Radiometric preprocessing for **SkySat Basic L1A panchromatic stereo imagery**. The tool performs robust
**radiometric correction** (percentile stretch + optional CLAHE + conservative shadow/highlight tone curve),
**preserves and embeds RPC metadata**, and can generate **RPC‑based quicklook orthos** (via GDAL) to aid QA.


**Input data**: single‑band 16‑bit GeoTIFF frames matching the SkySat L1A PAN naming convention
(`*_basic_l1a_panchromatic_dn.tif`) with sidecar metadata (e.g., `.RPB`, `_RPC.TXT`, `.json`, `.imd`, `.xml`).
The tool is optimized for **stereo** pairs but also works on individual L1A PAN frames.

**Output data**: radiometrically corrected **16‑bit GeoTIFF** with embedded RPC and optional internal pyramids.
Quicklook orthos (optional) are generated using `gdalwarp -rpc` and a user‑supplied DEM.

- Robust percentile stretch (`--pmin/--pmax`)
- Optional CLAHE (local contrast) if OpenCV is available
- Conservative tone curve to **lift shadows** while **protecting highlights**
- Copies SkySat sidecar files and **embeds RPC** in the output TIFF
- Optional `gdaladdo` pyramids
- Optional `gdalwarp -rpc` quicklooks with `RPC_DEM=...`

## Install

You need GDAL (>=3.4) available to Python **and** the `gdalwarp/gdaladdo` CLI on PATH.

```bash
# create env (recommended)
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# install from source
pip install -U pip
pip install -e .[dev]     # or: pip install -e .

# If you want CLAHE:
pip install opencv-python
```

## Usage

```bash
skysatprep   --pair1_src /path/to/Pair1/SkySatScene   --pair2_src /path/to/Pair2/SkySatScene   --pair1_out /path/to/Pair1/radprep   --pair2_out /path/to/Pair2/radprep   --pmin 1 --pmax 99   --clahe 3.0 --tiles 8   --shadow_boost 0.20 --highlight_comp 0.10   --pyramids   --quicklook --rm_quicklook   --dem /path/to/ellipsoidal_dem.tif   --t_srs EPSG:32608 --ql_res 1.5
```

**Notes**
- Input files must match `*_basic_l1a_panchromatic_dn.tif`.
- Sidecars found next to each input (e.g., `.RPB`, `_RPC.TXT`, `.json`, `.imd`, `.xml`) are copied to the output directory and RPC is embedded into the processed TIFF.
- Quicklooks use `gdalwarp -rpc` with `-wo RPC_DEM=<DEM>` for approximate ortho + resampling; they are *not* a substitute for rigorous photogrammetry.

## Metashape tips

- Import the processed 16-bit panchro TIFFs; Metashape will see the embedded RPC.
- Use your usual SfM settings for SkySat stereo (align, build DSM/mesh) and any sensor-specific tweaks.

## Reproducibility

- Default stretch is `--pmin 1 --pmax 99`. Pin these and the tone-curve parameters in your paper’s methods to ensure consistent output.
- Consider committing a small config and logging the full CLI (see your shell history).

## License

MIT (see `LICENSE`).

## Data handling & limits

- Expects **single‑band panchromatic** L1A frames (PAN). Multispectral products are not processed by this tool.
- File discovery defaults to the SkySat PAN L1A naming pattern. Adjust `EXT_TIF_RE` in `core.py` if your filenames differ.
- Quicklook orthos are for QA/visualization; they are **not** a substitute for rigorous photogrammetric processing.
- For best quicklooks, use an **ellipsoidal‑height DEM** (or a DEM consistent with the scene’s RPC model).


## How to cite
```
Fathian, A., Shugar, D. (2025). SkySatPrep (v0.1.0) [Software]. Zenodo. https://doi.org/xxxxxxxxx 
```
