# DemandServe: chronological demand forecasting with a prediction API

A reproducible ML engineering project using the UCI Bike Sharing daily dataset. It connects feature generation, training, model selection, held-out evaluation, a versioned artifact, input validation, and a working HTTP service.

## Run

```bash
python3 -m pip install -r requirements-ml.txt
python3 -m unittest discover -s tests -p 'test_demandserve.py' -v
python3 scripts/verify_demandserve_api.py
python3 -m demandserve.api
```

The final command starts a loopback-only server. In another terminal:

```bash
curl http://127.0.0.1:8000/health
curl -H 'Content-Type: application/json' --data-binary @examples/demandserve-request.json http://127.0.0.1:8000/predict
```

Reproduce training:

```bash
python3 -m demandserve.train --download
```

The downloader reads only `day.csv` from the official ZIP into ignored local data storage. The model artifact and full evaluation are checked in; the API needs no training-data download.

## Evaluation protocol

- 731 daily observations; 717 usable after constructing 14-day histories.
- Chronological 430/143/144 train/validation/test split. No random shuffle.
- Standardization is fitted only on the training subset during tuning.
- Ridge regularization is selected using validation RMSE, then the final model is fitted on train plus validation.
- Test window: August 10–December 31, 2012.
- One-day-ahead rolling evaluation uses only dates/calendar and previous actual counts. Earlier test-day outcomes are available for later one-day-ahead predictions; this is not a fixed-origin 144-day forecast.
- No same-day weather/temperature, casual/registered counts, or target count enters the features.
- Tests alter every test target and verify that the fitted model artifact remains unchanged.

| Held-out method | MAE (rentals/day) | RMSE (rentals/day) |
| --- | ---: | ---: |
| Standardized ridge | 898.523 | 1242.936 |
| Yesterday's count | 891.354 | 1295.075 |
| Same weekday last week | 1218.736 | 1777.879 |

The ridge model improves RMSE by about 4.0% relative to yesterday's count and 30.1% relative to last week's weekday. Its MAE is slightly worse than yesterday's count. These are results from one historical holdout, not a generalization guarantee or business impact measurement. Hyperparameters were not retuned after inspecting test results.

Full [evaluation and daily predictions](../evidence/demandserve-evaluation.json), [local HTTP verification](../evidence/demandserve-api-verification.json), and [model artifact](../models/demandserve.json) are available.

## API contract

`POST /predict` accepts exactly `target_date` and `history`. History contains the preceding 14 consecutive daily observations, each with `date` and nonnegative finite `count`. Duplicate dates, gaps, future observations, unknown top-level fields, invalid numbers, and oversized bodies are rejected. A model ID and training cutoff accompany every prediction. Request payloads are not logged.

This historical demo refuses prediction dates more than 366 days after its training cutoff. It cannot responsibly forecast 2026 demand using this old artifact. Retrain on current data before contemporary use.

The standard-library HTTP server is a local prototype: no public hosting, authentication, TLS termination, production load testing, or autoscaling is claimed. There is no prediction interval or calibrated uncertainty estimate. The linear model cannot represent all disruptions or nonlinear weather effects. Historical rental count is observed demand under system conditions, not unconstrained demand.

## Dataset attribution

Fanaee-T, H. (2013). *Bike Sharing* [Dataset]. UCI Machine Learning Repository. [DOI: 10.24432/C5W894](https://doi.org/10.24432/C5W894). [Dataset and documentation](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset), [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/).

The example request contains an attributed 14-day subset; evaluation outputs and the model are derived from this public dataset. MIT applies to project code, not a replacement license for the dataset. No affiliation with the original dataset authors is implied. Implementation developed with Codex assistance.

## Interview exercise

Explain why random splitting and same-day casual/registered counts would leak information; compare RMSE versus MAE; show a valid HTTP prediction and a rejected request; trace its features; and explain when the stale-model guard requires retraining. Extend a feature or service test yourself before stating your personal contribution.
