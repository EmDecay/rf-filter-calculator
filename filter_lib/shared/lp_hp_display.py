"""Shared display renderer for lowpass and highpass filters.

Single source of the LP/HP table/JSON/CSV/quiet output used by both the
CLI subcommands and the wizard results screen. Per-filter differences
(topology diagrams, frequency sweep, transfer function) are injected via
LpHpDisplayConfig rather than duplicated per module.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .cli_aliases import DEFAULT_RIPPLE_DB, resolve_filter_type
from .display_common import (
    format_component_table,
    format_csv_result,
    format_header,
    format_json_result,
    format_quiet_result,
)
from .display_helpers import eseries_section_lines, format_eseries_match
from .formatting import format_capacitance
from .inductor_display import has_suggestion, suggestion_section_lines
from .plotting import find_db_thresholds, format_threshold_table, render_plot_pair
from .resolved_parts import ResolvedParts

# Injection points supplied by each filter module's display config:
#   ComponentFormatter: value in F/H -> display string
#   DiagramFormatter: (n_first, n_second, series_label, shunt_label) -> diagram
#   FrequencyPoints: cutoff_hz -> sweep frequencies in Hz
#   FrequencyResponse: (filter_type, freqs, cutoff_hz, order, ripple_db) -> dB list
#   ResponseDbFactory: (filter_type, cutoff_hz, order, ripple_db) -> f(freq_hz) -> dB
ComponentFormatter = Callable[[float], str]
DiagramFormatter = Callable[[int, int, str, str], str]
FrequencyPoints = Callable[[float], list[float]]
FrequencyResponse = Callable[[str, list[float], float, int, float], list[float]]
ResponseDbFactory = Callable[[str, float, int, float], Callable[[float], float]]


@dataclass(frozen=True)
class DiagramConfig:
    """Topology diagram formatter plus component-count bindings."""

    formatter: DiagramFormatter
    count_keys: tuple[str, str]
    series_label: str = "L"
    shunt_label: str = "C"

    def render(self, result: dict) -> str:
        first, second = self.count_keys
        return self.formatter(
            len(result[first]),
            len(result[second]),
            self.series_label,
            self.shunt_label,
        )


@dataclass(frozen=True)
class MatchConfig:
    """E-series recommendation target for text output."""

    component_key: str
    prefix: str
    display_name: str
    formatter: ComponentFormatter


@dataclass(frozen=True)
class LpHpDisplayConfig:
    """Per-filter display differences for the shared LP/HP renderer."""

    category: str
    plot_filter_type: str
    default_topology: str
    primary_for_topology: dict[str, str]
    diagrams: dict[str, DiagramConfig]
    frequency_points: FrequencyPoints
    frequency_response: FrequencyResponse
    response_db_factory: ResponseDbFactory


@dataclass(frozen=True)
class LpHpRenderOptions:
    """Runtime display options for LP/HP text rendering.

    ``parts`` are the parts ``design()`` resolved: the standard-value section shows
    their capacitor choices (when the design has an E-series and ``raw`` is off), and
    the suggestion section their inductor suggestions at their detail.
    """

    config: LpHpDisplayConfig
    parts: ResolvedParts
    raw: bool = False
    show_plot: bool = False
    match: MatchConfig | None = None
    trailing_blank: bool = True


CAPACITOR_MATCH = MatchConfig("capacitors", "C", "Capacitor", format_capacitance)

# Header spelling for every LP/HP surface (CLI, wizard, web share this renderer).
TOPOLOGY_LABELS = {"pi": "Pi", "t": "T"}


def chebyshev_cutoff_note_lines(ripple_db: float | None) -> list[str]:
    """Explain that a Chebyshev cutoff is the ripple-band edge, not the -3 dB point.

    At fc the loss equals the ripple setting; the -3 dB point lies past fc toward the
    stopband (higher for LP, lower for HP). The wording stays surface-neutral because
    the wizard and web print the same lines; each surface offers the response plot,
    whose threshold table lists the -3 dB frequency.
    """
    ripple = f"the {ripple_db:g} dB ripple" if ripple_db is not None else "the ripple"
    return [
        f"Note: The Chebyshev cutoff is the ripple-band edge, where loss equals {ripple}.",
        "      The -3 dB point lies beyond it, toward the stopband (listed with the response plot).",
    ]


def primary_component(result: dict, config: LpHpDisplayConfig) -> str:
    """Return the configured primary component for a result topology."""
    topology = str(result.get("topology", config.default_topology)).lower()
    return config.primary_for_topology[topology]


def format_json_for_config(
    result: dict,
    config: LpHpDisplayConfig,
    parts: ResolvedParts,
    build_analysis=None,
) -> str:
    """Format an LP/HP result as JSON."""
    return format_json_result(
        result,
        parts,
        primary_component=primary_component(result, config),
        build_analysis=build_analysis,
    )


def format_csv_for_config(result: dict, config: LpHpDisplayConfig, parts: ResolvedParts) -> str:
    """Format an LP/HP result as CSV."""
    return format_csv_result(result, parts, primary_component=primary_component(result, config))


def format_quiet_for_config(result: dict, config: LpHpDisplayConfig, raw: bool = False) -> str:
    """Format an LP/HP result as quiet text."""
    return format_quiet_result(result, raw, primary_component=primary_component(result, config))


def render_results_lines(result: dict, options: LpHpRenderOptions) -> list[str]:
    """Render LP/HP table output as lines."""
    config = options.config
    parts = options.parts
    match = options.match or CAPACITOR_MATCH
    topology = str(result.get("topology", config.default_topology)).lower()
    primary = primary_component(result, config)
    lines = [
        format_header(
            result,
            topology=TOPOLOGY_LABELS.get(topology, topology.upper()),
            filter_category=config.category,
        ),
    ]
    if resolve_filter_type(str(result.get("filter_type", ""))) == "chebyshev":
        lines.extend(chebyshev_cutoff_note_lines(result.get("ripple")))
    lines += [
        "\nTopology:",
        config.diagrams[topology].render(result),
        format_component_table(
            result,
            raw=options.raw,
            primary_component=primary,
            mention_suggestions=parts.shows_suggestions
            and has_suggestion([parts.inductor(name) for name in _inductor_names(result)]),
        ),
    ]

    if parts.eseries and not options.raw:
        _extend_match_lines(lines, result, match, parts)

    if parts.shows_suggestions:
        lines.extend(_suggestion_lines(result, parts))

    if options.show_plot:
        lines.extend(_plot_lines(result, config))

    if options.trailing_blank:
        lines.append("")
    return lines


def _inductor_names(result: dict) -> list[str]:
    return [f"L{i + 1}" for i in range(len(result["inductors"]))]


def _extend_match_lines(
    lines: list[str], result: dict, match: MatchConfig, parts: ResolvedParts
) -> None:
    """Append the E-series standard-value section from the resolved choices, in place."""
    lines.extend(eseries_section_lines(parts.eseries, match.display_name, parts.match_policy))
    for i, value in enumerate(result[match.component_key]):
        name = f"{match.prefix}{i + 1}"
        lines.append(f"{name} calculated {match.formatter(value)}")
        lines.extend(format_eseries_match(parts.capacitor(name), match.formatter))


def _suggestion_lines(result: dict, parts: ResolvedParts) -> list[str]:
    """Build the inductor suggestion section (one block per inductor)."""
    targets = [(name, parts.inductor(name)) for name in _inductor_names(result)]
    return suggestion_section_lines(targets, result["freq_hz"], parts.inductor_detail)


def _plot_lines(result: dict, config: LpHpDisplayConfig) -> list[str]:
    """Build the ASCII plot pair + threshold table section."""
    freqs = config.frequency_points(result["freq_hz"])
    # Non-Chebyshev results carry no ripple; the transfer functions still
    # take a ripple argument, so pass DEFAULT_RIPPLE_DB (0.5) — it is
    # ignored for Butterworth/Bessel responses.
    ripple = result.get("ripple") or DEFAULT_RIPPLE_DB
    response = config.frequency_response(
        result["filter_type"], freqs, result["freq_hz"], result["order"], ripple
    )
    response_fn = config.response_db_factory(
        result["filter_type"], result["freq_hz"], result["order"], ripple
    )
    # The grid only brackets each crossing; bisecting the analytic response keeps the
    # printed labels exact where log interpolation across a steep skirt is not.
    thresholds = find_db_thresholds(
        freqs, response, filter_type=config.plot_filter_type, response_fn=response_fn
    )
    return [
        "",
        render_plot_pair(
            freqs,
            response,
            result["freq_hz"],
            filter_type=config.plot_filter_type,
            ripple_db=ripple,
            response_fn=response_fn,
        ),
        format_threshold_table(thresholds, filter_type=config.plot_filter_type),
    ]
