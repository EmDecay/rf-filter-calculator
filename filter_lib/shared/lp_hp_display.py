"""Shared display renderer for lowpass and highpass filters."""

from collections.abc import Callable
from dataclasses import dataclass

from .display_common import (
    format_component_table,
    format_csv_result,
    format_header,
    format_json_result,
    format_quiet_result,
)
from .display_helpers import format_eseries_match
from .formatting import format_capacitance, format_inductance
from .plotting import find_db_thresholds, format_threshold_table, render_plot_pair
from .toroid_display import format_recommendation_block, format_recommendation_block_compact
from .toroid_selection import recommend_cores

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
    parallel_mode: str


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
    """Runtime display options for LP/HP text rendering."""

    config: LpHpDisplayConfig
    raw: bool = False
    eseries: str | None = "E24"
    show_match: bool = True
    show_plot: bool = False
    include_toroids: bool = True
    toroid_compact: bool = False
    toroid_full: bool = False
    match: MatchConfig | None = None
    trailing_blank: bool = True


CAPACITOR_MATCH = MatchConfig("capacitors", "C", "Capacitor", format_capacitance, "additive")
INDUCTOR_MATCH = MatchConfig("inductors", "L", "Inductor", format_inductance, "harmonic")


def primary_component(result: dict, config: LpHpDisplayConfig) -> str:
    """Return the configured primary component for a result topology."""
    topology = str(result.get("topology", config.default_topology)).lower()
    return config.primary_for_topology[topology]


def format_json_for_config(
    result: dict,
    config: LpHpDisplayConfig,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format an LP/HP result as JSON."""
    return format_json_result(
        result,
        primary_component=primary_component(result, config),
        eseries=eseries,
        toroid_freq_hz=result["freq_hz"],
        include_toroids=include_toroids,
    )


def format_csv_for_config(
    result: dict,
    config: LpHpDisplayConfig,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format an LP/HP result as CSV."""
    return format_csv_result(
        result,
        primary_component=primary_component(result, config),
        eseries=eseries,
        toroid_freq_hz=result["freq_hz"],
        include_toroids=include_toroids,
    )


def format_quiet_for_config(result: dict, config: LpHpDisplayConfig, raw: bool = False) -> str:
    """Format an LP/HP result as quiet text."""
    return format_quiet_result(result, raw, primary_component=primary_component(result, config))


def render_results_lines(result: dict, options: LpHpRenderOptions) -> list[str]:
    """Render LP/HP table output as lines."""
    config = options.config
    match = options.match or CAPACITOR_MATCH
    topology = str(result.get("topology", config.default_topology)).lower()
    primary = primary_component(result, config)
    lines = [
        format_header(result, topology=topology.upper(), filter_category=config.category),
        "\nTopology:",
        config.diagrams[topology].render(result),
        format_component_table(result, raw=options.raw, primary_component=primary),
    ]

    if options.show_match and not options.raw and options.eseries:
        _extend_match_lines(lines, result, match, options.eseries)

    if options.include_toroids:
        lines.extend(_toroid_lines(result, options.toroid_compact, 3 if options.toroid_full else 1))

    if options.show_plot:
        lines.extend(_plot_lines(result, config))

    if options.trailing_blank:
        lines.append("")
    return lines


def display_results_for_config(
    result: dict,
    config: LpHpDisplayConfig,
    raw: bool = False,
    output_format: str = "table",
    quiet: bool = False,
    eseries: str = "E24",
    show_match: bool = True,
    show_plot: bool = False,
    include_toroids: bool = True,
    toroid_compact: bool = False,
    toroid_full: bool = False,
) -> None:
    """Print LP/HP result output."""
    if output_format == "json":
        print(
            format_json_for_config(
                result,
                config,
                eseries=eseries if show_match else None,
                include_toroids=include_toroids,
            )
        )
        return
    if output_format == "csv":
        print(
            format_csv_for_config(
                result,
                config,
                eseries=eseries if show_match else None,
                include_toroids=include_toroids,
            ),
            end="",
        )
        return
    if quiet:
        print(format_quiet_for_config(result, config, raw))
        return

    options = LpHpRenderOptions(
        config=config,
        raw=raw,
        eseries=eseries,
        show_match=show_match,
        show_plot=show_plot,
        include_toroids=include_toroids,
        toroid_compact=toroid_compact,
        toroid_full=toroid_full,
        match=CAPACITOR_MATCH,
    )
    print("\n".join(render_results_lines(result, options)))


def _extend_match_lines(lines: list[str], result: dict, match: MatchConfig, eseries: str) -> None:
    lines.append(f"\n{eseries} Standard {match.display_name} Recommendations")
    lines.append("-" * 45)
    lines.append("(Calculated values with nearest standard matches)")
    lines.append("")
    for i, value in enumerate(result[match.component_key]):
        lines.append(f"{match.prefix}{i + 1} Calculated: {match.formatter(value)}")
        lines.extend(
            format_eseries_match(
                value,
                eseries,
                match.formatter,
                parallel_mode=match.parallel_mode,
            )
        )


def _toroid_lines(result: dict, compact: bool, top_n: int) -> list[str]:
    formatter = format_recommendation_block_compact if compact else format_recommendation_block
    lines = [
        "",
        "Toroid Winding Recommendations (Iron-Powder T-Series)",
        "-" * 55,
    ]
    if not compact:
        lines.append("(Accuracy: A_L tolerance \u00b15% per spec; N rounding shown as %)")
    lines.append("")
    for i, value in enumerate(result["inductors"]):
        recs = recommend_cores(value, result["freq_hz"], top_n=top_n)
        lines.extend(formatter(f"L{i + 1}", value, result["freq_hz"], recs))
        lines.append("")
    return lines


def _plot_lines(result: dict, config: LpHpDisplayConfig) -> list[str]:
    freqs = config.frequency_points(result["freq_hz"])
    ripple = result.get("ripple") or 0.5
    response = config.frequency_response(
        result["filter_type"], freqs, result["freq_hz"], result["order"], ripple
    )
    response_fn = config.response_db_factory(
        result["filter_type"], result["freq_hz"], result["order"], ripple
    )
    thresholds = find_db_thresholds(freqs, response, filter_type=config.plot_filter_type)
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
