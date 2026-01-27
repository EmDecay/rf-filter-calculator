"""Tests for Pi/T topology support in lowpass and highpass calculations."""
import json
import math
import pytest
from filter_lib.lowpass import calculations as lp
from filter_lib.highpass import calculations as hp
from filter_lib.shared.filter_result import FilterResult
from filter_lib.shared.display_common import format_json_result


class TestLowpassTTopology:
    """Test LPF with T topology (new)."""

    def test_t_topology_component_counts_odd(self):
        """LPF T with n=5: 3 inductors (odd pos) + 2 capacitors (even pos)."""
        caps, inds, order = lp.calculate_butterworth(10e6, 50, 5, topology='t')
        assert len(inds) == 3
        assert len(caps) == 2
        assert order == 5

    def test_t_topology_component_counts_even(self):
        """LPF T with n=4: 2 inductors + 2 capacitors."""
        caps, inds, order = lp.calculate_butterworth(10e6, 50, 4, topology='t')
        assert len(inds) == 2
        assert len(caps) == 2

    def test_t_topology_all_values_positive(self):
        """All component values should be positive."""
        caps, inds, _ = lp.calculate_butterworth(10e6, 50, 5, topology='t')
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_t_topology_chebyshev(self):
        """Chebyshev T topology works."""
        caps, inds, order = lp.calculate_chebyshev(10e6, 50, 0.5, 3, topology='t')
        assert len(inds) == 2  # odd positions
        assert len(caps) == 1  # even positions
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_t_topology_bessel(self):
        """Bessel T topology works."""
        caps, inds, order = lp.calculate_bessel(10e6, 50, 3, topology='t')
        assert len(inds) == 2
        assert len(caps) == 1

    def test_t_topology_all_orders(self):
        """T topology works for all orders 2-9."""
        for n in range(2, 10):
            caps, inds, order = lp.calculate_butterworth(10e6, 50, n, topology='t')
            assert len(caps) + len(inds) == n
            expected_inds = (n + 1) // 2
            expected_caps = n // 2
            assert len(inds) == expected_inds
            assert len(caps) == expected_caps


class TestHighpassPiTopology:
    """Test HPF with Pi topology (new)."""

    def test_pi_topology_component_counts_odd(self):
        """HPF Pi with n=5: 3 inductors (odd pos, shunt) + 2 capacitors (even pos, series)."""
        inds, caps, order = hp.calculate_butterworth(10e6, 50, 5, topology='pi')
        assert len(inds) == 3
        assert len(caps) == 2
        assert order == 5

    def test_pi_topology_component_counts_even(self):
        """HPF Pi with n=4."""
        inds, caps, order = hp.calculate_butterworth(10e6, 50, 4, topology='pi')
        assert len(caps) == 2
        assert len(inds) == 2

    def test_pi_topology_all_values_positive(self):
        """All component values should be positive."""
        inds, caps, _ = hp.calculate_butterworth(10e6, 50, 5, topology='pi')
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_pi_topology_chebyshev(self):
        """Chebyshev Pi topology works."""
        inds, caps, order = hp.calculate_chebyshev(10e6, 50, 0.5, 3, topology='pi')
        assert len(inds) == 2  # odd positions (shunt L)
        assert len(caps) == 1  # even positions (series C)

    def test_pi_topology_bessel(self):
        """Bessel Pi topology works."""
        inds, caps, order = hp.calculate_bessel(10e6, 50, 3, topology='pi')
        assert len(inds) == 2  # odd positions (shunt L)
        assert len(caps) == 1  # even positions (series C)

    def test_pi_topology_all_orders(self):
        """Pi topology works for all orders 2-9."""
        for n in range(2, 10):
            inds, caps, order = hp.calculate_butterworth(10e6, 50, n, topology='pi')
            assert len(inds) + len(caps) == n
            expected_inds = (n + 1) // 2  # odd positions (shunt L)
            expected_caps = n // 2  # even positions (series C)
            assert len(inds) == expected_inds
            assert len(caps) == expected_caps

    def test_invalid_topology_raises(self):
        """Invalid topology string raises ValueError."""
        with pytest.raises(ValueError, match="Topology must be"):
            hp.calculate_butterworth(10e6, 50, 3, topology='x')


class TestTopologyFormulas:
    """Verify formulas for new topologies against manual calculations."""

    def test_lpf_t_2component_formula(self):
        """Verify LPF T 2-component Butterworth formula.

        n=2, T topology: L1 at pos 1, C1 at pos 2
        g1 = 2*sin(pi/4) = sqrt(2)
        g2 = 2*sin(3pi/4) = sqrt(2)
        L1 = g1*Z0/omega, C1 = g2/(Z0*omega)
        """
        cutoff = 1e6
        z0 = 50
        omega = 2 * math.pi * cutoff

        caps, inds, _ = lp.calculate_butterworth(cutoff, z0, 2, topology='t')

        g1 = 2 * math.sin(math.pi / 4)
        g2 = 2 * math.sin(3 * math.pi / 4)

        expected_l1 = g1 * z0 / omega
        expected_c1 = g2 / (z0 * omega)

        assert abs(inds[0] - expected_l1) < 1e-15
        assert abs(caps[0] - expected_c1) < 1e-15

    def test_hpf_pi_2component_formula(self):
        """Verify HPF Pi 2-component Butterworth formula.

        n=2, Pi topology: L1 at pos 1 (shunt, odd), C1 at pos 2 (series, even)
        g1 = sqrt(2), g2 = sqrt(2)
        L1 = Z0/(omega*g1)
        C1 = 1/(g2*omega*Z0)
        """
        cutoff = 1e6
        z0 = 50
        omega = 2 * math.pi * cutoff

        inds, caps, _ = hp.calculate_butterworth(cutoff, z0, 2, topology='pi')

        g1 = 2 * math.sin(math.pi / 4)
        g2 = 2 * math.sin(3 * math.pi / 4)

        expected_l1 = z0 / (omega * g1)
        expected_c1 = 1.0 / (g2 * omega * z0)

        assert abs(inds[0] - expected_l1) < 1e-15
        assert abs(caps[0] - expected_c1) < 1e-15


class TestFilterResultTopology:
    """Test FilterResult topology field."""

    def test_topology_in_to_dict(self):
        """FilterResult.to_dict() includes topology."""
        r = FilterResult('butterworth', 10e6, 50, 3, [1e-10], [1e-6],
                         topology='pi')
        d = r.to_dict()
        assert d['topology'] == 'pi'

    def test_topology_none_omitted(self):
        """FilterResult.to_dict() omits topology when None."""
        r = FilterResult('butterworth', 10e6, 50, 3, [1e-10], [1e-6])
        d = r.to_dict()
        assert 'topology' not in d


class TestTopologyJsonOutput:
    """Test topology in JSON output."""

    def test_json_includes_topology(self):
        """JSON output includes topology field."""
        result = {
            'filter_type': 'butterworth',
            'freq_hz': 10e6,
            'impedance': 50,
            'order': 3,
            'capacitors': [1e-10, 1e-10],
            'inductors': [1e-6],
            'ripple': None,
            'topology': 'pi',
        }
        output = format_json_result(result, primary_component='capacitors')
        data = json.loads(output)
        assert data.get('topology') == 'pi'

    def test_json_no_topology_when_absent(self):
        """JSON output omits topology when not in result."""
        result = {
            'filter_type': 'butterworth',
            'freq_hz': 10e6,
            'impedance': 50,
            'order': 3,
            'capacitors': [1e-10],
            'inductors': [1e-6],
            'ripple': None,
        }
        output = format_json_result(result, primary_component='capacitors')
        data = json.loads(output)
        assert 'topology' not in data
