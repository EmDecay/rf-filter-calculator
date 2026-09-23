"""Accepted ranges for component Q and evaluation-port resistances.

The helpers are the single owner of both ranges; BuildConfig, bandpass Q combination,
evaluation ports, and the wizard's build form all delegate to them.
"""

import math

import pytest

from filter_lib.shared.physical_input_limits import (
    MAX_COMPONENT_Q,
    MIN_COMPONENT_Q,
    PORT_RESISTANCE_RATIO_LIMIT,
    require_component_q,
    require_port_resistance,
)

Q_MESSAGE = r"^inductor_q must be finite and in \[0\.01, 1e\+09\]$"


def test_ranges_are_the_documented_values():
    assert (MIN_COMPONENT_Q, MAX_COMPONENT_Q, PORT_RESISTANCE_RATIO_LIMIT) == (0.01, 1e9, 1e6)


class TestComponentQ:
    @pytest.mark.parametrize("value", [0.01, 1e9, 1, 150.0])
    def test_values_inside_the_inclusive_range_are_returned(self, value):
        assert require_component_q(value, "inductor_q") == value

    @pytest.mark.parametrize(
        "value",
        [
            math.nextafter(0.01, 0.0),
            math.nextafter(1e9, math.inf),
            0.0,
            -100.0,
            math.nan,
            math.inf,
            True,
            "100",
            None,
            10**400,
        ],
        ids=[
            "below",
            "above",
            "zero",
            "negative",
            "nan",
            "inf",
            "bool",
            "text",
            "none",
            "huge-int",
        ],
    )
    def test_everything_else_is_a_value_error_naming_the_input(self, value):
        with pytest.raises(ValueError, match=Q_MESSAGE):
            require_component_q(value, "inductor_q")


class TestPortResistance:
    @pytest.mark.parametrize("ratio", [1e-6, 1e-3, 1.0, 1e3, 1e6])
    @pytest.mark.parametrize("design", [50.0, 3.3, 1e-200, 1e200])
    def test_ratios_inside_the_inclusive_range_are_returned(self, ratio, design):
        value = design * ratio

        assert require_port_resistance(value, design, "Load resistance") == value

    @pytest.mark.parametrize("ratio", [1e-6 * (1 - 1e-9), 1e6 * (1 + 1e-9), 1e-12, 1e12])
    def test_ratios_beyond_the_rounding_slack_are_rejected(self, ratio):
        with pytest.raises(ValueError, match="^Source resistance .* is outside the supported"):
            require_port_resistance(50.0 * ratio, 50.0, "Source resistance")

    def test_a_ratio_that_overflows_binary64_is_rejected(self):
        """1e300 against 1e-300 overflows the quotient to infinity, still outside the range."""
        with pytest.raises(ValueError, match="^Load resistance 1e\\+300 ohm is outside"):
            require_port_resistance(1e300, 1e-300, "Load resistance")

    @pytest.mark.parametrize(
        ("value", "design", "bounds"),
        [
            (1e9, 50.0, "5e-05 to 5e+07 ohm"),
            # Binary64 would print these bounds as "inf" and "0".
            (1.0, 1e303, "1e+297 to 1e+309 ohm"),
            (1e-300, 1e-320, "1e-326 to 1e-314 ohm"),
        ],
    )
    def test_message_states_both_bounds_at_any_design_scale(self, value, design, bounds):
        with pytest.raises(ValueError) as raised:
            require_port_resistance(value, design, "Load resistance")

        assert f"outside the supported range {bounds} (1e-06 to 1e+06 times the " in str(
            raised.value
        )
        assert "inf" not in str(raised.value)
