from __future__ import annotations
import os, re, shutil, subprocess
from pathlib import Path
from typing import Tuple, List, Optional

import numpy as np
try:
    import cv2
    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False

from osgeo import gdal
gdal.UseExceptions()

EXT_TIF_RE = re.compile(r".*_basic_l1a_panchromatic_dn\.tif$", re.IGNORECASE)
SIDECAR_SUFFIXES = [
    ".RPB", ".rpb",
    "_RPC.TXT", "_rpc.txt",
    ".json", ".JSON",
    "_metadata.json", "_METADATA.JSON",
    ".imd", ".IMD",
    ".xml", ".XML",
]

def log(msg: str) -> None:
    print(msg, flush=True)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def copy_sidecars(src_tif: Path, dst_dir: Path) -> List[str]:
    base = src_tif.name[:-4]
    copied: List[str] = []
    for suf in SIDECAR_SUFFIXES:
        cand = src_tif.with_name(base + suf)
        if cand.exists():
            dst = dst_dir / cand.name
            if not dst.exists():
                shutil.copy2(cand, dst)
            copied.append(dst.name)
    return copied

def read_rpc_from_source(src_tif: Path) -> dict:
    ds = gdal.Open(str(src_tif), gdal.GA_ReadOnly)
    if ds is None:
        return {}
    rpc = ds.GetMetadata("RPC") or {}
    ds = None
    return rpc

def embed_rpc_into_tif(dst_tif: Path, rpc: dict) -> bool:
    if not rpc:
        return False
    ds = gdal.Open(str(dst_tif), gdal.GA_Update)
    if ds is None:
        return False
    ds.SetMetadata(rpc, "RPC")
    ds = None
    return True

def verify_embedded_rpc(dst_tif: Path) -> bool:
    ds = gdal.Open(str(dst_tif), gdal.GA_ReadOnly)
    if ds is None:
        return False
    ok = bool(ds.GetMetadata("RPC"))
    ds = None
    return ok

def build_pyramids(tif_path: Path) -> None:
    cmd = ["gdaladdo", "-r", "average", str(tif_path), "2", "4", "8", "16", "32"]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        log(f"[WARN] gdaladdo failed for {tif_path.name}: {e}")

def rpc_quicklook(src_tif: Path, dst_dir: Path, dem: Path, t_srs: str, res: float) -> Optional[Path]:
    out = dst_dir / (src_tif.stem + "_quicklook.tif")
    cmd = [
        "gdalwarp", "-rpc",
        "-t_srs", t_srs,
        "-tr", str(res), str(res),
        "-r", "bilinear",
        "-multi", "-wm", "2048",
        "-overwrite",
        "-co", "TILED=YES",
        "-co", "COMPRESS=DEFLATE",
        "-co", "PREDICTOR=2",
        "-co", "ZLEVEL=6",
        "-co", "BIGTIFF=IF_SAFER",
        "-wo", f"RPC_DEM={dem}",
        str(src_tif), str(out)
    ]
    try:
        subprocess.run(cmd, check=True)
        return out
    except subprocess.CalledProcessError as e:
        log(f"[WARN] gdalwarp quicklook failed for {src_tif.name}: {e}")
        return None

def robust_percentiles(arr_u16: np.ndarray, pmin: float, pmax: float) -> Tuple[float, float]:
    nz = arr_u16[(arr_u16 > 0) & (arr_u16 < 65535)]
    if nz.size == 0:
        return 1.0, 99.0
    lo, hi = np.percentile(nz, [pmin, pmax])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(nz.min()), float(nz.max())
    return lo, hi

def _read_arr(ds: gdal.Dataset) -> np.ndarray:
    return ds.GetRasterBand(1).ReadAsArray()

def _write_uint16_like(src_ds: gdal.Dataset, out_path: Path, arr16: np.ndarray) -> None:
    driver = gdal.GetDriverByName("GTiff")
    ysize, xsize = src_ds.RasterYSize, src_ds.RasterXSize
    out = driver.Create(
        str(out_path), xsize, ysize, 1, gdal.GDT_UInt16,
        options=["TILED=YES", "COMPRESS=LZW", "PREDICTOR=2",
                 "BLOCKXSIZE=1024", "BLOCKYSIZE=1024", "BIGTIFF=IF_SAFER"]
    )
    b = out.GetRasterBand(1)
    b.WriteArray(arr16)
    b.SetNoDataValue(0)
    out.SetMetadata(src_ds.GetMetadata())
    b.FlushCache(); out.FlushCache()
    out = None

def apply_shadow_highlight_tone(arr01: np.ndarray, shadow_boost: float, highlight_comp: float) -> np.ndarray:
    if shadow_boost <= 0 and highlight_comp <= 0:
        return arr01
    y = arr01.astype(np.float32)
    if shadow_boost > 0:
        y = y + float(shadow_boost) * (1.0 - y) * (1.0 - y)
    if highlight_comp > 0:
        y = y - float(highlight_comp) * (y * y)
    return np.clip(y, 0.0, 1.0)

def process_one(
    src_tif: Path,
    out_dir: Path,
    pmin: float = 1.0,
    pmax: float = 99.0,
    clahe_clip: float = 3.0,
    clahe_tiles: int = 8,
    do_pyramids: bool = False,
    do_quicklook: bool = False,
    rm_quicklook: bool = False,
    dem_path: Optional[Path] = None,
    t_srs: Optional[str] = None,
    ql_res: Optional[float] = 1.0,
    shadow_boost: float = 0.20,
    highlight_comp: float = 0.10,
) -> Tuple[Path, List[str], Optional[Path]]:
    ensure_dir(out_dir)
    copied = copy_sidecars(src_tif, out_dir)
    dst_tif = out_dir / src_tif.name
    log(f"[RADPREP] {src_tif.name}")

    sds = gdal.Open(str(src_tif), gdal.GA_ReadOnly)
    if sds is None:
        raise RuntimeError(f"Cannot open {src_tif}")
    if sds.RasterCount != 1:
        raise RuntimeError(f"{src_tif.name}: expected 1 band, found {sds.RasterCount}")

    arr = _read_arr(sds)
    if arr.dtype != np.uint16:
        arr = arr.astype(np.uint16)

    lo, hi = robust_percentiles(arr, pmin, pmax)
    arrf = arr.astype(np.float32)
    arrf = np.clip((arrf - lo) / max(1e-6, (hi - lo)), 0, 1)

    if _HAS_CV2 and clahe_clip and clahe_clip > 0:
        arr8 = (arrf * 255.0 + 0.5).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=float(clahe_clip),
                                tileGridSize=(int(clahe_tiles), int(clahe_tiles)))
        arr8 = clahe.apply(arr8)
        arrf = arr8.astype(np.float32) / 255.0

    arrf = apply_shadow_highlight_tone(arrf, shadow_boost=shadow_boost, highlight_comp=highlight_comp)
    arr16 = (arrf * 65535.0 + 0.5).astype(np.uint16)
    _write_uint16_like(sds, dst_tif, arr16)

    rpc = sds.GetMetadata("RPC") or read_rpc_from_source(src_tif)
    sds = None
    if not embed_rpc_into_tif(dst_tif, rpc):
        log(f"[WARN] No RPC embedded for {dst_tif.name} (source had none or write failed)")
    elif not verify_embedded_rpc(dst_tif):
        log(f"[WARN] Could not verify RPC in {dst_tif.name}")

    if do_pyramids:
        build_pyramids(dst_tif)

    ql_path: Optional[Path] = None
    if do_quicklook and dem_path and t_srs and ql_res:
        ql_path = rpc_quicklook(dst_tif, out_dir, dem_path, t_srs, float(ql_res))
        if rm_quicklook and ql_path and ql_path.exists():
            try:
                os.remove(ql_path)
                log(f"  → removed quicklook: {ql_path.name}")
            except Exception as e:
                log(f"[WARN] failed to remove quicklook {ql_path.name}: {e}")

    return dst_tif, copied, ql_path

def find_tifs(src_dir: Path) -> List[Path]:
    return sorted([p for p in src_dir.iterdir() if p.is_file() and EXT_TIF_RE.match(p.name)])

def process_pair_dirs(pair_src: Path, pair_out: Path, **kwargs) -> None:
    ensure_dir(pair_out)
    tifs = find_tifs(pair_src)
    if not tifs:
        log(f"[WARN] No SkySat L1A TIFFs found in {pair_src}")
        return
    for tif in tifs:
        try:
            dst, copied, ql = process_one(tif, pair_out, **kwargs)
            log(f"  → wrote {dst.name}")
            if copied: log(f"  → sidecars: {', '.join(copied)}")
            if ql and not kwargs.get("rm_quicklook", False):
                log(f"  → quicklook: {ql.name}")
        except Exception as e:
            log(f"[ERROR] {tif.name}: {e}")