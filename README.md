# Arizona Drought Model Explorer

A static website to explore the inputs and results of two ConvLSTM models that
predict 1-month **SSMI** (soil-moisture drought index) and **SRI** (streamflow
drought index) over Arizona.

## Run it

Double-click **`start_website.bat`** (or run it from a terminal). It serves this
folder on `http://localhost:8000` and opens your browser.

Manual equivalent:

```
cd drought_explorer
python -m http.server 8000
# then open http://localhost:8000/index.html
```

A tiny web server is required because browsers block `fetch()` of local files
when opening `index.html` directly (`file://`). Any static host works too
(GitHub Pages, ASU web space, S3, etc.) — just upload the whole `drought_explorer`
folder.

## What's in each tab

| Tab | Shows |
|-----|-------|
| **Drought indices** | Maps of SPI / SPEI / SSMI / SRI with a monthly date slider (1979–2025) and play button. |
| **Static variables** | Maps of the 28 static physiographic/climatological predictors; pick one from the dropdown. |
| **Modeled vs observed** | Test-period skill for each model: R²/RMSE/MAE/bias, predicted-vs-observed scatter, domain-mean time series, and Observed / Predicted / Error maps with a month slider. |
| **Feature importance** | Permutation feature importance (Δ RMSE) ranked and colored by group (dynamic / temporal lag / static), with group filter and "top 20". |
| **PFI maps** | Spatial permutation importance (local Δ RMSE) per feature; pick the feature to see where it matters most. |

Model outputs are inverse-transformed from the models' scaled target back to
physical index units. The published run is the latest of each model
(SSMI `20260825_1213`, SRI `20260825_1254`).

## Regenerating the data

All web data lives in `data/` and is produced by **`build_data.py`** from:

* `WindowTests/merged_all_table_1month_full.csv` — gridded inputs
* `Results/results_SSMI1_lagSSMI_pfi/` and `Results/results_SRI1_lagSRI_pfi/` — model outputs

To rebuild (e.g. after a new model run — edit the `MODELS` stamps at the top of
the script):

```
"C:/Users/mgarc120/AppData/Local/anaconda3/python.exe" build_data.py
```

### Files written to `data/`
* `grid.json` — grid geometry, domain mask, index date list
* `idx_{spi,spei,ssmi,sri}.f32` — `(564 × 22 × 23)` float32 map cubes
* `static.json` — 28 static-variable maps
* `model_{ssmi,sri}.json` — metrics, scatter sample, time series, PFI ranking, feature list
* `model_{ssmi,sri}_{obs,pred}.f32` — test observed/predicted map cubes
* `model_{ssmi,sri}_pfimaps.f32` — spatial PFI map cubes
* `manifest.json` — top-level summary

## Layout

```
drought_explorer/
  index.html          page + tab markup
  css/style.css       styling
  js/app.js           all interactivity (Plotly heatmaps, charts, sliders)
  vendor/plotly.min.js  charting library (bundled for offline use)
  data/               generated web data (see above)
  build_data.py       preprocessing pipeline
  start_website.bat   local launcher
```
