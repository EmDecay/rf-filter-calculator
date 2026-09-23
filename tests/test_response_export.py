"""Unified --plot-data response export: JSON schema, CSV layout, and validation."""

import json

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.bandpass.display import PLOT_POINTS
from filter_lib.bandpass.transfer import netlist_frequency_sweep
from filter_lib.shared.response_export import (
    export_response_csv,
    export_response_json,
    response_meta,
)

_LP_META = {
    "category": "lowpass",
    "response_type": "butterworth",
    "order": 3,
    "cutoff_hz": 10e6,
}
_BP_META = {
    "category": "bandpass",
    "response_type": "butterworth",
    "order": 3,
    "f0_hz": 14e6,
    "bw_hz": 1e6,
}


class TestResponseMeta:
    def test_lowpass_result_maps_to_cutoff_schema(self):
        result = {
            "filter_type": "butterworth",
            "freq_hz": 10e6,
            "order": 3,
            "ripple": None,
            "topology": "pi",
            "impedance": 50.0,
        }

        assert response_meta("lowpass", result) == {
            "category": "lowpass",
            "response_type": "butterworth",
            "order": 3,
            "cutoff_hz": 10e6,
            "ripple_db": None,
            "topology": "pi",
        }

    def test_highpass_chebyshev_result_carries_ripple(self):
        result = {
            "filter_type": "chebyshev",
            "freq_hz": 10e6,
            "order": 5,
            "ripple": 0.5,
            "topology": "t",
        }

        meta = response_meta("highpass", result)

        assert meta["category"] == "highpass"
        assert meta["ripple_db"] == 0.5
        assert meta["topology"] == "t"

    def test_bandpass_result_maps_to_center_and_bandwidth_schema(self):
        result = {
            "filter_type": "chebyshev",
            "coupling": "top",
            "f0": 14e6,
            "bw": 1e6,
            "n_resonators": 5,
            "ripple_db": 0.1,
            "z0": 50.0,
        }

        assert response_meta("bandpass", result) == {
            "category": "bandpass",
            "response_type": "chebyshev",
            "order": 5,
            "f0_hz": 14e6,
            "bw_hz": 1e6,
            "ripple_db": 0.1,
            "coupling": "top",
        }

    @pytest.mark.parametrize("category", ["not-a-category", "", None, [], {}])
    def test_rejects_unknown_category(self, category):
        with pytest.raises(ValueError, match="category must be 'lowpass', 'highpass', or"):
            response_meta(category, {})

    @pytest.mark.parametrize("result", [None, [], "result"])
    def test_requires_mapping_result(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            response_meta("lowpass", result)

    @pytest.mark.parametrize(
        ("category", "result", "message"),
        [
            ("lowpass", {}, "meta.response_type must be"),
            ("highpass", {"filter_type": "butterworth", "order": 3}, "meta.cutoff_hz must be"),
            (
                "bandpass",
                {"filter_type": "butterworth", "n_resonators": 3, "f0": 14e6},
                "meta.bw_hz must be",
            ),
            (
                "lowpass",
                {"filter_type": "butterworth", "order": 10**400, "freq_hz": 10e6},
                "meta.order must be a positive finite integer",
            ),
        ],
    )
    def test_rejects_result_missing_required_fields(self, category, result, message):
        with pytest.raises(ValueError, match=message):
            response_meta(category, result)


class TestResponseJson:
    def test_lowpass_document_has_filter_block_and_data(self):
        result = {
            "filter_type": "butterworth",
            "freq_hz": 10e6,
            "order": 3,
            "ripple": None,
            "topology": "pi",
        }

        data = json.loads(
            export_response_json([1e6, 10e6], [-0.1, -3.0], response_meta("lowpass", result))
        )

        assert data == {
            "filter": {
                "category": "lowpass",
                "response_type": "butterworth",
                "order": 3,
                "cutoff_hz": 10e6,
                "topology": "pi",
            },
            "data": [
                {"frequency_hz": 1e6, "magnitude_db": -0.1},
                {"frequency_hz": 10e6, "magnitude_db": -3.0},
            ],
        }

    def test_bandpass_document_has_filter_block_and_data(self):
        meta = {**_BP_META, "response_type": "chebyshev", "ripple_db": 0.5, "coupling": "top"}

        data = json.loads(export_response_json([13e6, 14e6], [-3.0, 0.0], meta))

        assert data == {
            "filter": {
                "category": "bandpass",
                "response_type": "chebyshev",
                "order": 3,
                "f0_hz": 14e6,
                "bw_hz": 1e6,
                "ripple_db": 0.5,
                "coupling": "top",
            },
            "data": [
                {"frequency_hz": 13e6, "magnitude_db": -3.0},
                {"frequency_hz": 14e6, "magnitude_db": 0.0},
            ],
        }

    def test_filter_block_uses_documented_key_order_and_omits_none(self):
        meta = {
            "topology": "t",
            "ripple_db": 0.5,
            "cutoff_hz": 10e6,
            "order": 5,
            "response_type": "chebyshev",
            "category": "highpass",
            "f0_hz": None,
        }

        data = json.loads(export_response_json([], [], meta))

        assert list(data["filter"]) == [
            "category",
            "response_type",
            "order",
            "cutoff_hz",
            "ripple_db",
            "topology",
        ]
        assert data["data"] == []

    def test_magnitude_is_rounded_to_hundredths_and_frequency_is_exact(self):
        data = json.loads(export_response_json([1234567.891, 1e10], [-3.14159, -150.456], _BP_META))

        assert data["data"] == [
            {"frequency_hz": 1234567.891, "magnitude_db": -3.14},
            {"frequency_hz": 1e10, "magnitude_db": -150.46},
        ]

    @pytest.mark.parametrize(
        ("meta", "message"),
        [
            ([], "meta must be a mapping"),
            ({**_LP_META, "category": "bandstop"}, "meta.category must be"),
            ({**_LP_META, "category": []}, "meta.category must be"),
            ({**_LP_META, "response_type": "elliptic"}, "meta.response_type must be"),
            ({**_LP_META, "response_type": []}, "meta.response_type must be"),
            ({**_LP_META, "order": 0}, "meta.order must be a positive finite integer"),
            ({**_LP_META, "order": 3.0}, "meta.order must be a positive finite integer"),
            ({**_LP_META, "order": True}, "meta.order must be a positive finite integer"),
            ({**_LP_META, "cutoff_hz": None}, "meta.cutoff_hz must be positive and finite"),
            ({**_LP_META, "f0_hz": 1e6}, "cannot contain f0_hz, bw_hz, or coupling"),
            ({**_LP_META, "coupling": "top"}, "cannot contain f0_hz, bw_hz, or coupling"),
            ({**_LP_META, "topology": "ladder"}, "meta.topology must be 'pi' or 't'"),
            ({**_BP_META, "f0_hz": 0.0}, "meta.f0_hz must be positive and finite"),
            ({**_BP_META, "cutoff_hz": 1e6}, "cannot contain cutoff_hz or topology"),
            ({**_BP_META, "topology": "pi"}, "cannot contain cutoff_hz or topology"),
            ({**_BP_META, "coupling": "shunt"}, "meta.coupling must be 'top'"),
            ({**_LP_META, "response_type": "chebyshev"}, "meta.ripple_db must be positive"),
            (
                {**_LP_META, "response_type": "chebyshev", "ripple_db": 3.1},
                "meta.ripple_db must be at most 3.0 dB",
            ),
            ({**_LP_META, "ripple_db": 0.5}, "valid only for a Chebyshev response"),
        ],
    )
    def test_rejects_schema_invalid_metadata(self, meta, message):
        with pytest.raises(ValueError, match=message):
            export_response_json([], [], meta)

    @pytest.mark.parametrize(
        "meta",
        [
            {**_LP_META, "order": 1},
            {**_LP_META, "response_type": "chebyshev", "ripple_db": 3.0},
            {**_BP_META, "response_type": "chebyshev", "ripple_db": 5e-324},
        ],
        ids=["first-order", "ripple-ceiling-inclusive", "smallest-positive-ripple"],
    )
    def test_accepts_schema_boundary_metadata(self, meta):
        data = json.loads(export_response_json([1e6], [-3.0], meta))

        assert data["filter"]["order"] == meta["order"]
        assert data["filter"].get("ripple_db") == meta.get("ripple_db")

    def test_rejects_ripple_just_above_the_ceiling(self):
        meta = {**_LP_META, "response_type": "chebyshev", "ripple_db": 3.001}

        with pytest.raises(ValueError, match="meta.ripple_db must be at most 3.0 dB"):
            export_response_json([1e6], [-3.0], meta)

    @pytest.mark.parametrize(
        ("meta", "message"),
        [
            ({**_LP_META, "note": object()}, r"\$\.filter\.note contains non-JSON value"),
            ({**_LP_META, 7: "seven"}, r"\$\.filter has non-string JSON object key 7"),
            ({**_LP_META, "cutoff_hz": b"1e7"}, r"\$\.filter\.cutoff_hz contains non-JSON"),
        ],
    )
    def test_rejects_non_json_metadata_with_value_error(self, meta, message):
        with pytest.raises(ValueError, match=message):
            export_response_json([1e6], [-3.0], meta)

    def test_negative_zero_magnitude_serializes_unsigned(self):
        text = export_response_json([1e6, 2e6], [-0.001, -0.0], _LP_META)

        assert "-0.0" not in text
        assert [point["magnitude_db"] for point in json.loads(text)["data"]] == [0.0, 0.0]

    def test_rejects_non_finite_metadata_with_json_path(self):
        with pytest.raises(ValueError, match=r"\$\.filter\.cutoff_hz must be finite"):
            export_response_json([1e6], [-3.0], {**_LP_META, "cutoff_hz": float("inf")})


class TestResponseCsv:
    def test_frequencies_round_trip_and_magnitudes_use_hundredth_db(self):
        csv_text = export_response_csv([1234567.891, 2e6, 0.5], [-3.14159, -0.005, -120])

        assert csv_text.split("\n") == [
            "frequency_hz,magnitude_db",
            "1234567.891,-3.14",
            "2000000.0,-0.01",
            "0.5,-120.00",
        ]

    def test_narrow_bandpass_grid_keeps_every_frequency_distinct_and_equal_to_json(self):
        result = calculate_bandpass_filter(1e9, 100e3, 50, 3, "butterworth", "top")
        sweep = netlist_frequency_sweep(result, points=PLOT_POINTS)
        freqs = [frequency for frequency, _db in sweep]
        response_db = [db for _frequency, db in sweep]

        rows = export_response_csv(freqs, response_db).split("\n")[1:]
        csv_freqs = [float(row.split(",")[0]) for row in rows]
        json_freqs = [
            point["frequency_hz"]
            for point in json.loads(
                export_response_json(freqs, response_db, response_meta("bandpass", result))
            )["data"]
        ]

        assert len(csv_freqs) == PLOT_POINTS
        assert csv_freqs == json_freqs == freqs
        assert all(low < high for low, high in zip(csv_freqs, csv_freqs[1:]))

    def test_negative_zero_magnitude_prints_unsigned(self):
        assert export_response_csv([1e6, 2e6], [-0.001, -0.0]).split("\n")[1:] == [
            "1000000.0,0.00",
            "2000000.0,0.00",
        ]

    def test_empty_response_is_header_only(self):
        assert export_response_csv([], []) == "frequency_hz,magnitude_db"


class TestResponseArrayValidation:
    @pytest.mark.parametrize("exporter", ["json", "csv"])
    @pytest.mark.parametrize(
        ("freqs", "response_db", "message"),
        [
            ([1e6, 10e6], [-0.1], r"same length \(got 2 and 1\)"),
            ("abc", "def", "must be numeric sequences"),
            ([True], [False], r"\$\.data\[0\]\.frequency_hz must be positive and finite"),
            (["1MHz"], [0.0], r"\$\.data\[0\]\.frequency_hz must be positive and finite"),
            ([0.0], [0.0], r"\$\.data\[0\]\.frequency_hz must be positive and finite"),
            ([1e6, -1.0], [0.0, 0.0], r"\$\.data\[1\]\.frequency_hz must be positive"),
            ([float("inf")], [-3.0], r"\$\.data\[0\]\.frequency_hz must be positive and finite"),
            ([1e6], [True], r"\$\.data\[0\]\.magnitude_db must be a finite real"),
            ([1e6], ["-3"], r"\$\.data\[0\]\.magnitude_db must be a finite real"),
            ([1e6], [float("nan")], r"\$\.data\[0\]\.magnitude_db must be a finite real"),
        ],
    )
    def test_rejects_invalid_response_arrays(self, exporter, freqs, response_db, message):
        with pytest.raises(ValueError, match=message):
            if exporter == "json":
                export_response_json(freqs, response_db, _LP_META)
            else:
                export_response_csv(freqs, response_db)
