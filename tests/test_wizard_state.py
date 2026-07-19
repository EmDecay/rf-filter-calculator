"""Tests for wizard state management."""

from copy import deepcopy

from filter_lib.shared.build_simulation import BuildConfig
from filter_lib.wizard.state import FilterState


class TestFilterState:
    """Tests for FilterState dataclass."""

    def test_default_values(self):
        """Test FilterState has correct default values."""
        state = FilterState()
        assert state.category == ""
        assert state.filter_type == "butterworth"
        assert state.topology == "pi"
        assert state.frequency_hz == 0.0
        assert state.bandwidth_hz == 0.0
        assert state.impedance == 50.0
        assert state.order == 3
        assert state.ripple_db == 0.5
        assert state.eseries == "E24"
        assert state.output_format == "table"
        assert state.show_plot is True
        assert state.export_format is None
        assert state.raw_units is False
        assert state.quiet is False
        assert state.build_analysis_enabled is False
        assert state.build_capacitor_tolerance_pct == 5.0
        assert state.build_inductor_tolerance_pct == 10.0
        assert state.build_inductor_q is None
        assert state.build_capacitor_q is None
        assert state.build_resonator_q is None
        assert state.build_source_resistance_ohm is None
        assert state.build_load_resistance_ohm is None
        assert state.build_sample_count == 0
        assert state.build_seed == 0
        assert state.build_grid_points == 601
        assert state.build_use_toroid_candidates is True
        assert state.build_analysis is None
        assert state.resonator_impedance is None
        assert state.resonator_inductance is None
        assert state.calculation_status == "idle"
        assert state.calculation_error is None
        assert state.calculation_revision == 0
        assert state.result == {}
        assert state.output_text == ""

    def test_state_mutation(self):
        """Test FilterState can be mutated."""
        state = FilterState()
        state.category = "lowpass"
        state.filter_type = "chebyshev"
        state.frequency_hz = 10e6
        state.impedance = 75.0
        state.order = 5
        state.ripple_db = 1.0

        assert state.category == "lowpass"
        assert state.filter_type == "chebyshev"
        assert state.frequency_hz == 10e6
        assert state.impedance == 75.0
        assert state.order == 5
        assert state.ripple_db == 1.0

    def test_begin_calculation_clears_stale_result_synchronously(self):
        state = FilterState(
            result={"old": True},
            output_text="old output",
            calculation_status="success",
            calculation_error="old error",
            build_analysis={"old": True},
        )

        revision = state.begin_calculation()

        assert revision == 1
        assert state.calculation_status == "pending"
        assert state.calculation_error is None
        assert state.result == {}
        assert state.output_text == ""
        assert state.build_analysis is None
        assert not state.is_exportable

    def test_invalidate_calculation_makes_old_revision_stale(self):
        state = FilterState(
            result={"old": True},
            output_text="old output",
            calculation_status="success",
        )
        previous_revision = state.calculation_revision

        state.invalidate_calculation()

        assert state.calculation_revision == previous_revision + 1
        assert state.calculation_status == "idle"
        assert state.result == {}
        assert state.output_text == ""

    def test_calculation_copy_is_independent(self):
        state = FilterState(category="lowpass", result={"nested": {"value": 1}})
        snapshot = state.calculation_copy()

        snapshot.result["nested"]["value"] = 2
        snapshot.category = "highpass"

        assert state.category == "lowpass"
        assert state.result == {"nested": {"value": 1}}
        assert deepcopy(snapshot.result) != state.result

    def test_publish_outcome_rejects_stale_revision(self):
        state = FilterState()
        old_revision = state.begin_calculation()
        current_revision = state.begin_calculation()

        assert not state.publish_success(old_revision, "old", {"old": True})
        assert state.publish_success(current_revision, "current", {"current": True})
        assert state.calculation_status == "success"
        assert state.output_text == "current"
        assert state.result == {"current": True}
        assert state.is_exportable

    def test_publish_failure_clears_previous_success(self):
        state = FilterState(
            result={"old": True},
            output_text="old output",
            calculation_status="success",
            build_analysis={"old": True},
        )
        revision = state.begin_calculation()

        assert state.publish_error(revision, "solver failed")
        assert state.calculation_status == "error"
        assert state.calculation_error == "solver failed"
        assert state.result == {}
        assert state.output_text == ""
        assert state.build_analysis is None
        assert not state.is_exportable

    def test_empty_success_is_published_as_error_and_returns_false(self):
        state = FilterState()
        revision = state.begin_calculation()

        published = state.publish_success(revision, "", {})

        assert not published
        assert state.calculation_status == "error"
        assert state.calculation_error == "Calculation returned no usable result"
        assert not state.is_exportable

    def test_new_success_can_replace_a_previous_failure(self):
        state = FilterState()
        failed_revision = state.begin_calculation()
        state.publish_error(failed_revision, "first attempt failed")

        success_revision = state.begin_calculation()
        published = state.publish_success(success_revision, "new result", {"ok": True})

        assert published
        assert state.calculation_status == "success"
        assert state.calculation_error is None
        assert state.is_exportable

    def test_build_config_uses_wizard_advanced_values(self):
        state = FilterState(
            eseries="E96",
            build_capacitor_tolerance_pct=2.0,
            build_inductor_tolerance_pct=7.5,
            build_inductor_q=120.0,
            build_capacitor_q=500.0,
            build_source_resistance_ohm=25.0,
            build_load_resistance_ohm=100.0,
            build_sample_count=7,
            build_seed=42,
            build_grid_points=301,
            build_use_toroid_candidates=False,
        )

        config = state.make_build_config()

        assert isinstance(config, BuildConfig)
        assert config.eseries == "E96"
        assert config.capacitor_tolerance_pct == 2.0
        assert config.inductor_tolerance_pct == 7.5
        assert config.inductor_q == 120.0
        assert config.capacitor_q == 500.0
        assert config.source_resistance_ohm == 25.0
        assert config.load_resistance_ohm == 100.0
        assert config.sample_count == 7
        assert config.seed == 42
        assert config.grid_points == 301
        assert config.use_toroid_candidates is False

    def test_build_analysis_is_required_for_exportable_build_success(self):
        state = FilterState(build_analysis_enabled=True)
        revision = state.begin_calculation()

        assert state.publish_success(revision, "result", {"ok": True})
        assert not state.is_exportable

    def test_build_analysis_publishes_and_clears_with_result_lifecycle(self):
        state = FilterState(build_analysis_enabled=True)
        revision = state.begin_calculation()
        analysis = {"same_worker_analysis": True}

        assert state.publish_success(revision, "result", {"ok": True}, analysis)
        assert state.build_analysis == analysis
        assert state.is_exportable

        state.invalidate_calculation()
        assert state.build_analysis is None
        assert not state.is_exportable
