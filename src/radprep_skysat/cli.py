import argparse
from pathlib import Path
from .core import process_pair_dirs

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="radprep-skysat",
        description="Radiometric prep for SkySat L1A panchromatic stereo with RPC preservation and optional RPC-quicklooks"
    )
    ap.add_argument("--pair1_src", required=True)
    ap.add_argument("--pair2_src", required=True)
    ap.add_argument("--pair1_out", required=True)
    ap.add_argument("--pair2_out", required=True)
    ap.add_argument("--pmin", type=float, default=1.0)
    ap.add_argument("--pmax", type=float, default=99.0)
    ap.add_argument("--clahe", type=float, default=3.0, help="CLAHE clip limit (<=0 disables)")
    ap.add_argument("--tiles", type=int, default=8, help="CLAHE tiles (NxN)")
    ap.add_argument("--pyramids", action="store_true", help="Build internal overviews")
    ap.add_argument("--quicklook", action="store_true", help="Create RPC-warped quicklooks")
    ap.add_argument("--rm_quicklook", action="store_true", help="Remove quicklook after creation")
    ap.add_argument("--dem", type=str, help="DEM for RPC warping (ellipsoidal heights recommended)")
    ap.add_argument("--t_srs", type=str, help="Target CRS (e.g., EPSG:32608)")
    ap.add_argument("--ql_res", type=float, default=1.0, help="Quicklook resolution (map units)")
    ap.add_argument("--shadow_boost", type=float, default=0.20, help="Lift shadows (0..0.5)")
    ap.add_argument("--highlight_comp", type=float, default=0.10, help="Protect highlights (0..0.4)")
    args = ap.parse_args()

    common = dict(
        pmin=args.pmin, pmax=args.pmax,
        clahe_clip=args.clahe, clahe_tiles=args.tiles,
        do_pyramids=args.pyramids, do_quicklook=args.quicklook,
        rm_quicklook=args.rm_quicklook,
        dem_path=Path(args.dem) if args.dem else None,
        t_srs=args.t_srs, ql_res=args.ql_res,
        shadow_boost=args.shadow_boost, highlight_comp=args.highlight_comp,
    )

    process_pair_dirs(Path(args.pair1_src), Path(args.pair1_out), **common)
    process_pair_dirs(Path(args.pair2_src), Path(args.pair2_out), **common)

if __name__ == "__main__":
    main()