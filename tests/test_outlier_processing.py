"""Exercise smoothing with real pandas data and temporary capture files."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import outliers


@pytest.mark.parametrize("index", [0, 5, 10])
def test_median_smoother_replaces_spikes_at_edges_and_middle(index):
    values = np.ones(11)
    values[index] = 100
    np.testing.assert_array_equal(outliers.outlier_smoother(values), np.ones(11))
    assert values[index] == 100  # input belongs to the caller


@pytest.mark.parametrize("level", ["High", "Medium", "Low"])
def test_iqr_marks_extreme_values_without_changing_normal_values(monkeypatch, level):
    monkeypatch.setattr(outliers.GiV_Settings, "data_smoother", level)
    values = [10.] * 98 + [1000., -1000.]
    clean, count = outliers.impute_outliers_IQR(pd.DataFrame(values), "PV_Power", 2)
    assert count == 4
    np.testing.assert_array_equal(clean[:98, 0], values[:98])
    assert np.isnan(clean[-2:]).all()


def test_flattening_ignores_raw_and_find_preserves_nested_paths():
    data = {"Power": {"PV_Power": 10}, "raw": {"register": 999}, "status": "ok"}
    assert outliers.iterate_dict(data) == {"PV_Power": 10, "status": "ok"}
    assert outliers.makeFlatStack([data, data]) == {"PV_Power": [10, 10], "status": ["ok", "ok"]}
    assert list(outliers.find("x", {"items": [{"x": 1}, {"deep": {"x": 2}}]})) == [
        ".items.[0]", ".items.[1].deep"]
    assert list(outliers.find("x", None)) == []


def test_capture_only_records_changed_smoothed_values(monkeypatch, tmp_path):
    monkeypatch.setattr(outliers.GiV_Settings, "cache_location", str(tmp_path))
    raw = {"power": [1, 99], "status": [0, 1], "mismatch": [1]}
    clean = {"power": [1, 2], "status": [0, 2], "mismatch": [1, 2]}
    for _ in range(2):
        outliers.capture_outlier_analysis(raw, clean, ["power", "mismatch"])
    rows = pd.read_csv(tmp_path / 'outlier_capture.csv')
    assert rows['item'].tolist() == ['power', 'power']
    assert rows['raw'].tolist() == [99, 99]
    assert rows['cleaned'].tolist() == [2, 2]


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_removal_interpolates_newest_sample_and_keeps_unsmoothed_data(monkeypatch, tmp_path, depth):
    monkeypatch.setattr(outliers.GiV_Settings, "data_smoother", "High")
    monkeypatch.setattr(outliers.GiV_Settings, "cache_location", str(tmp_path))
    monkeypatch.setattr(outliers, "givLUT", {"power": SimpleNamespace(smooth=True),
                                            "status": SimpleNamespace(smooth=False)})
    def sample(value):
        data = {"power": value, "status": "ready"}
        for key in ['Power', 'Rates', 'nested'][:depth]:
            data = {key: data}
        return data
    latest, history = outliers.outlierRemoval(sample(1000), [sample(10) for _ in range(20)])
    assert outliers.iterate_dict(latest) == {"power": 10., "status": "ready"}
    assert len(history) == 20
    assert pd.read_csv(tmp_path / 'outlier_capture.csv')['raw'].tolist() == [1000]
