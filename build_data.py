"""
build_data.py  --  Preprocess drought-model inputs/results into compact web files.

Reads:
  * merged_all_table_1month_full.csv   (gridded inputs: indices + static variables)
  * results_SSMI1_lagSSMI_pfi / results_SRI1_lagSRI_pfi  (model outputs, PFI, scalers)

Writes everything the static website needs into ./data/:
  grid.json            grid geometry, mask, index date list
  idx_<name>.f32       (ndates x 22 x 23) float32 map cube per drought index
  static.json          {variable: 22x23 map} for each static variable
  model_<key>.json     metrics, scatter sample, time series, PFI ranking, PFI feature list
  model_<key>_obs.f32  (ntest x 22 x 23) observed physical maps
  model_<key>_pred.f32 (ntest x 22 x 23) predicted physical maps
  model_<key>_pfimaps.f32  (nfeat x 22 x 23) spatial PFI (delta-RMSE) maps

Run with anaconda python:
  "C:/Users/mgarc120/AppData/Local/anaconda3/python.exe" build_data.py
"""
import os, json, pickle, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------------
ROOT     = os.path.dirname(os.path.abspath(__file__))
DATA_OUT = os.path.join(ROOT, "data")
os.makedirs(DATA_OUT, exist_ok=True)

CSV = r"C:\Users\mgarc120\ASU Dropbox\DroughtPropagation\Analysis\WindowTests\merged_all_table_1month_full.csv"
RES = r"C:\Users\mgarc120\ASU Dropbox\DroughtPropagation\Analysis\ConvLSTM_test\Results"

# Which timestamped run to publish for each model (latest of each).
MODELS = {
    "ssmi": {
        "title": "SSMI (1-month soil-moisture drought index)",
        "dir":   os.path.join(RES, "results_SSMI1_lagSSMI_pfi"),
        "stamp": "20260825_1213",
        "scaler_key": "SSMI",     # key inside all_scalers.pkl for the target
        "index_col":  "ssmi",     # matching column in the input CSV (for orientation check)
    },
    "sri": {
        "title": "SRI (1-month streamflow drought index)",
        "dir":   os.path.join(RES, "results_SRI1_lagSRI_pfi"),
        "stamp": "20260825_1254",
        "scaler_key": "SRI",
        "index_col":  "sri",
    },
}

INDEX_COLS = ["spi", "spei", "ssmi", "sri"]
# Static predictors kept in the analysis. The following were dropped upstream to
# reduce inter-feature correlation and are intentionally excluded here:
#   Mean_Annual_Pet, Mean_Annual_Precipitation, Temperature_Maxima,
#   Temperature_Minima, Storm_Arrival_Rate, soil_organic_carbon,
#   Vapour_Pressure_Deficit, water1500
STATIC_COLS = [
    "Aspect", "Average_Storm_Depth", "Baseflow", "Coefficient_Variation_P",
    "Cultivated_Area", "Elevation", "Forest_Cover", "Ratio_P_Pet", "Rcms",
    "Relativeairhumidity_Min", "Seasonality_P", "Seasonality_Pet",
    "Shrubland_Area", "Slope", "Urban_Area", "bulk_density", "clay", "sand",
    "silt", "water33",
]

def jclean(x):
    """JSON-safe: turn NaN/inf into None."""
    if isinstance(x, float):
        return x if np.isfinite(x) else None
    return x

def write_f32(path, arr):
    np.asarray(arr, dtype="<f4").tofile(path)

# ----------------------------------------------------------------------------
print("Loading CSV (indices + static) ...")
usecols = ["longitude", "latitude", "date"] + INDEX_COLS + STATIC_COLS
df = pd.read_csv(CSV, usecols=usecols)
df["date"] = pd.to_datetime(df["date"])

lons = np.sort(df["longitude"].unique())          # 23, ascending west->east
lats = np.sort(df["latitude"].unique())           # 22, ascending south->north
nlon, nlat = len(lons), len(lats)
lon_ix = {v: i for i, v in enumerate(lons)}
lat_ix = {v: i for i, v in enumerate(lats)}
dates = np.sort(df["date"].unique())
date_str = [pd.Timestamp(d).strftime("%Y-%m") for d in dates]
ndates = len(dates)
print(f"  grid = {nlat} lat x {nlon} lon, {ndates} months "
      f"({date_str[0]} .. {date_str[-1]})")

# row = latitude index (0 = southern-most), col = longitude index (0 = west)
ri = df["latitude"].map(lat_ix).to_numpy()
ci = df["longitude"].map(lon_ix).to_numpy()
di = df["date"].map({pd.Timestamp(d): i for i, d in enumerate(dates)}).to_numpy()

# mask of populated cells (constant across time)
mask = np.zeros((nlat, nlon), dtype=bool)
mask[ri, ci] = True
print(f"  populated cells = {int(mask.sum())} of {nlat*nlon}")

# ---- index map cubes -------------------------------------------------------
print("Writing index cubes ...")
for col in INDEX_COLS:
    cube = np.full((ndates, nlat, nlon), np.nan, dtype="<f4")
    cube[di, ri, ci] = df[col].to_numpy(dtype="float32")
    write_f32(os.path.join(DATA_OUT, f"idx_{col}.f32"), cube)
    vals = df[col].to_numpy()
    print(f"    {col}: range {np.nanmin(vals):.2f} .. {np.nanmax(vals):.2f}")

# ---- static variable maps --------------------------------------------------
print("Writing static.json ...")
static_maps = {}
static_meta = {}
# static values are constant in time; take the first occurrence per cell
first = df.drop_duplicates(subset=["latitude", "longitude"])
fr = first["latitude"].map(lat_ix).to_numpy()
fc = first["longitude"].map(lon_ix).to_numpy()
for col in STATIC_COLS:
    g = np.full((nlat, nlon), np.nan)
    g[fr, fc] = first[col].to_numpy(dtype="float64")
    static_maps[col] = [[jclean(v) for v in row] for row in g]
    static_meta[col] = {"min": jclean(float(np.nanmin(g))),
                         "max": jclean(float(np.nanmax(g)))}
with open(os.path.join(DATA_OUT, "static.json"), "w") as f:
    json.dump({"variables": STATIC_COLS, "meta": static_meta, "maps": static_maps}, f)

# ---- grid.json -------------------------------------------------------------
with open(os.path.join(DATA_OUT, "grid.json"), "w") as f:
    json.dump({
        "lons": [float(x) for x in lons],
        "lats": [float(x) for x in lats],
        "nlat": nlat, "nlon": nlon,
        "mask": mask.astype(int).tolist(),
        "index_dates": date_str,
        "index_cols": INDEX_COLS,
    }, f)

# small per-index value ranges for consistent color scaling
idx_ranges = {c: {"min": jclean(float(np.nanmin(df[c]))),
                  "max": jclean(float(np.nanmax(df[c])))} for c in INDEX_COLS}

# ----------------------------------------------------------------------------
# Model outputs
# ----------------------------------------------------------------------------
def inv_minmax(scaler, x):
    """Undo sklearn MinMaxScaler: X = (X_scaled - min_) / scale_."""
    return (x - scaler.min_[0]) / scaler.scale_[0]

def orient_to_grid(model_map_2d, ref_grid):
    """model arrays are (lat,lon) but row order (N->S vs S->N) is unknown.
    Return the flip (identity or vertical) that best matches ref_grid."""
    a = model_map_2d
    b = np.flipud(model_map_2d)
    m = np.isfinite(ref_grid)
    if m.sum() < 5:
        return "identity"
    def corr(x):
        mm = m & np.isfinite(x)
        return np.corrcoef(x[mm], ref_grid[mm])[0, 1]
    return "identity" if corr(a) >= corr(b) else "flipud"

manifest_models = {}
for key, cfg in MODELS.items():
    print(f"Model '{key}' ({cfg['stamp']}) ...")
    mdir, stamp = cfg["dir"], cfg["stamp"]
    scalers = pickle.load(open(os.path.join(mdir, "all_scalers.pkl"), "rb"))
    sc = scalers[cfg["scaler_key"]]

    ypred = np.load(os.path.join(mdir, f"Y_pred_test_{stamp}.npy"))   # (T,1,22,23,1)
    ytrue = np.load(os.path.join(mdir, "Y_true_test.npy"))
    tdates = np.load(os.path.join(mdir, "target_dates_test.npy"))
    mmask = np.load(os.path.join(mdir, "domain_mask.npy"))            # (22,23) bool

    ypred = ypred[:, 0, :, :, 0].astype("float64")
    ytrue = ytrue[:, 0, :, :, 0].astype("float64")
    T = ypred.shape[0]
    # inverse-transform to physical index units
    ypred = inv_minmax(sc, ypred)
    ytrue = inv_minmax(sc, ytrue)

    # apply domain mask (cells outside domain -> NaN)
    fullmask = mmask.astype(bool)

    # orientation: compare first test month's observed to the CSV index map
    t0 = pd.Timestamp(tdates[0])
    ref = np.full((nlat, nlon), np.nan)
    sub = df[df["date"] == t0]
    ref[sub["latitude"].map(lat_ix), sub["longitude"].map(lon_ix)] = \
        sub[cfg["index_col"]].to_numpy()
    flip = orient_to_grid(np.where(fullmask, ytrue[0], np.nan), ref)
    print(f"    orientation = {flip}")

    def fix(a2d):
        a2d = np.where(fullmask, a2d, np.nan)
        return np.flipud(a2d) if flip == "flipud" else a2d

    obs_cube  = np.stack([fix(ytrue[t]) for t in range(T)]).astype("<f4")
    pred_cube = np.stack([fix(ypred[t]) for t in range(T)]).astype("<f4")
    write_f32(os.path.join(DATA_OUT, f"model_{key}_obs.f32"),  obs_cube)
    write_f32(os.path.join(DATA_OUT, f"model_{key}_pred.f32"), pred_cube)

    # metrics over all valid obs/pred pairs
    o = obs_cube.reshape(-1); p = pred_cube.reshape(-1)
    good = np.isfinite(o) & np.isfinite(p)
    o, p = o[good].astype(float), p[good].astype(float)
    err = p - o
    rmse = float(np.sqrt(np.mean(err**2)))
    mae  = float(np.mean(np.abs(err)))
    bias = float(np.mean(err))
    ss_res = float(np.sum(err**2)); ss_tot = float(np.sum((o - o.mean())**2))
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else None
    r  = float(np.corrcoef(o, p)[0, 1])

    # scatter sample (cap for browser)
    rng = np.random.default_rng(0)
    n = o.size
    sel = rng.choice(n, size=min(6000, n), replace=False)
    scatter = {"obs": [round(float(v), 4) for v in o[sel]],
               "pred": [round(float(v), 4) for v in p[sel]]}

    # domain-mean time series obs vs pred
    ts_dates = [pd.Timestamp(d).strftime("%Y-%m") for d in tdates]
    ts_obs  = [jclean(round(float(np.nanmean(obs_cube[t])),  4)) for t in range(T)]
    ts_pred = [jclean(round(float(np.nanmean(pred_cube[t])), 4)) for t in range(T)]

    # ---- PFI ranking table ----
    # Keep only overall-variable importance: 'dynamic' = whole time series of an
    # index, 'static' = static predictors. Drop 'temporal' (per-lag) rows so each
    # dynamic index appears once rather than also as t-0, t-1, ... lags.
    pfi = pd.read_csv(os.path.join(mdir, f"permutation_importance_{stamp}.csv"))
    pfi = pfi[pfi["group"] != "temporal"]
    pfi = pfi.sort_values("delta_rmse_mean", ascending=False)
    pfi_rank = [{"feature": str(rw.feature), "group": str(rw.group),
                 "delta": float(rw.delta_rmse_mean), "std": float(rw.delta_rmse_std)}
                for rw in pfi.itertuples()]

    # ---- PFI spatial maps ----
    spz = np.load(os.path.join(mdir, f"pfi_spatial_{stamp}.npz"), allow_pickle=True)
    feats = [str(x) for x in spz["features"]]
    smaps = spz["maps"].astype("float64")   # (nfeat,22,23)
    smaps = np.stack([fix(smaps[i]) for i in range(smaps.shape[0])]).astype("<f4")
    write_f32(os.path.join(DATA_OUT, f"model_{key}_pfimaps.f32"), smaps)

    vmin = float(np.nanmin([v for v in [pfi_rank[i]["delta"] for i in range(len(pfi_rank))]]))
    model_json = {
        "key": key, "title": cfg["title"], "stamp": stamp,
        "index_col": cfg["index_col"], "orientation": flip,
        "ntest": T, "test_dates": ts_dates,
        "value_range": idx_ranges[cfg["index_col"]],
        "metrics": {"r2": jclean(r2), "r": jclean(r), "rmse": rmse,
                    "mae": mae, "bias": bias, "n": int(n)},
        "scatter": scatter,
        "timeseries": {"dates": ts_dates, "obs": ts_obs, "pred": ts_pred},
        "pfi_rank": pfi_rank,
        "pfi_features": feats,
        "pfi_nfeat": len(feats),
    }
    with open(os.path.join(DATA_OUT, f"model_{key}.json"), "w") as f:
        json.dump(model_json, f)

    manifest_models[key] = {"title": cfg["title"], "stamp": stamp,
                            "ntest": T, "pfi_nfeat": len(feats)}
    print(f"    R2={r2:.3f}  RMSE={rmse:.3f}  bias={bias:+.3f}  n={n}")

# ---- top-level manifest ----------------------------------------------------
with open(os.path.join(DATA_OUT, "manifest.json"), "w") as f:
    json.dump({
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "grid": {"nlat": nlat, "nlon": nlon},
        "index_cols": INDEX_COLS,
        "index_ranges": idx_ranges,
        "index_ndates": ndates,
        "n_static": len(STATIC_COLS),
        "models": manifest_models,
    }, f)

print("Done. Wrote data to", DATA_OUT)
