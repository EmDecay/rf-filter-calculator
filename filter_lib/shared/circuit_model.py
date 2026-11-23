"""Immutable named-circuit types shared by builders, solvers, and exporters."""

from __future__ import annotations

from dataclasses import dataclass

from .numeric import is_finite_real, require_positive_finite

Branch = (
    tuple[int, int, str, float]
    | tuple[int, int, str, float, float]
    | tuple[int, int, str, float, float, float]
)


@dataclass(frozen=True)
class CircuitElement:
    """One finite passive component in a named circuit.

    ``tolerance`` is the part's own fractional tolerance (0.05 for ±5%), which the
    build simulation's tolerance cases use; ``None`` for an element that is not a
    chosen part. A ``fixed`` element (an assumed parasitic, such as the stray
    capacitance across a parallel pair, or a trimmer, which tuning sets) keeps its value in
    every tolerance case. ``series_inductance_h`` is a capacitor's series inductance (a
    trimmer's), simulated in its own branch and written to SPICE as an inductor in series.
    The first letter of ``name`` is the element's kind, so a SPICE reader sees it as
    the element it is.
    """

    name: str
    node1: int
    node2: int
    kind: str
    value: float
    series_resistance_ohm: float = 0.0
    logical_name: str | None = None
    quality_factor: float | None = None
    loss_reference_frequency_hz: float | None = None
    tolerance: float | None = None
    fixed: bool = False
    series_inductance_h: float = 0.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or any(character.isspace() for character in self.name)
        ):
            raise ValueError("element name must be non-empty and contain no whitespace")
        if not isinstance(self.kind, str) or self.kind not in {"C", "L", "R"}:
            raise ValueError("element kind must be 'C', 'L', or 'R'")
        if self.name[0].upper() != self.kind:
            raise ValueError("element name must start with the letter of its kind")
        if self.tolerance is not None and (
            not is_finite_real(self.tolerance) or not 0 <= self.tolerance < 1
        ):
            raise ValueError("element tolerance must be a fraction from 0 to under 1")
        if not isinstance(self.fixed, bool):
            raise ValueError("element fixed flag must be a boolean")
        if any(
            not isinstance(node, int) or isinstance(node, bool) or node < 0
            for node in (self.node1, self.node2)
        ):
            raise ValueError("element nodes must be non-negative integers")
        require_positive_finite(self.value, "element value")
        if not is_finite_real(self.series_resistance_ohm) or self.series_resistance_ohm < 0:
            raise ValueError("element series resistance must be finite and non-negative")
        if self.kind == "R" and self.series_resistance_ohm:
            raise ValueError("resistors cannot carry an additional series resistance")
        if not is_finite_real(self.series_inductance_h) or self.series_inductance_h < 0:
            raise ValueError("element series inductance must be finite and non-negative")
        if self.kind != "C" and self.series_inductance_h:
            raise ValueError("only capacitors can carry a series inductance")
        if self.quality_factor is not None and (
            not is_finite_real(self.quality_factor) or self.quality_factor <= 0
        ):
            raise ValueError("element quality factor must be positive and finite")
        if self.loss_reference_frequency_hz is not None and (
            not is_finite_real(self.loss_reference_frequency_hz)
            or self.loss_reference_frequency_hz <= 0
        ):
            raise ValueError("loss reference frequency must be positive and finite")

    def as_branch(self) -> Branch:
        """Convert to the solver's compatible four-, five- or six-field branch."""
        if self.series_inductance_h:
            return (
                self.node1,
                self.node2,
                self.kind,
                self.value,
                self.series_resistance_ohm,
                self.series_inductance_h,
            )
        if self.series_resistance_ohm:
            return (
                self.node1,
                self.node2,
                self.kind,
                self.value,
                self.series_resistance_ohm,
            )
        return (self.node1, self.node2, self.kind, self.value)


@dataclass(frozen=True)
class NamedCircuit:
    """A deterministic named passive network with explicit evaluation ports."""

    category: str
    n_nodes: int
    elements: tuple[CircuitElement, ...]
    in_node: int
    out_node: int

    def __post_init__(self) -> None:
        if not isinstance(self.category, str) or self.category not in {
            "lowpass",
            "highpass",
            "bandpass",
        }:
            raise ValueError(f"Unknown category {self.category!r}")
        if not isinstance(self.n_nodes, int) or isinstance(self.n_nodes, bool) or self.n_nodes < 1:
            raise ValueError("n_nodes must be >= 1")
        if any(
            not isinstance(node, int) or isinstance(node, bool)
            for node in (self.in_node, self.out_node)
        ):
            raise ValueError("circuit ports must be integers")
        if not (1 <= self.in_node <= self.n_nodes and 1 <= self.out_node <= self.n_nodes):
            raise ValueError("circuit ports must be within 1..n_nodes")
        names = [element.name for element in self.elements]
        if len(names) != len(set(names)):
            raise ValueError("element names must be unique")
        if any(
            element.node1 > self.n_nodes or element.node2 > self.n_nodes
            for element in self.elements
        ):
            raise ValueError("element node exceeds n_nodes")

    def branches(self) -> list[Branch]:
        """Return solver branches in stable physical-element order."""
        return [element.as_branch() for element in self.elements]

    def as_legacy_netlist(self) -> tuple[int, list[Branch], int, int]:
        """Return the tuple historically consumed by ``solve_s21``."""
        return self.n_nodes, self.branches(), self.in_node, self.out_node
