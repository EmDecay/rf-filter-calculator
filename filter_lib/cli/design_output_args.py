"""Map parsed CLI output flags onto the shared design dispatcher's options."""

from argparse import Namespace

from ..design import RenderOptions


def render_options_from_args(args: Namespace) -> RenderOptions:
    """Return the CLI's render options; ``--quiet`` selects the quiet format."""
    return RenderOptions(
        output_format="quiet" if args.quiet else args.format,
        raw=args.raw,
        eseries=None if args.no_match else args.eseries,
        show_plot=args.plot,
        include_toroids=not args.no_toroids,
        toroid_compact=args.toroid_compact,
        toroid_full=args.toroid_full,
    )


def spice_realization_from_args(args: Namespace) -> str:
    """Return the SPICE realization id; nominal-build is the CLI default."""
    return (getattr(args, "spice_realization", None) or "nominal-build").replace("-", "_")
