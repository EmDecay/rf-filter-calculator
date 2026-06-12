"""Golden-string snapshots for LP/HP rendered display output."""

from contextlib import redirect_stdout
from io import StringIO

import pytest

from filter_lib.highpass import display as hp_display
from filter_lib.highpass.calculations import calculate_butterworth as hp_butterworth
from filter_lib.highpass.calculations import calculate_chebyshev as hp_chebyshev
from filter_lib.lowpass import display as lp_display
from filter_lib.lowpass.calculations import calculate_butterworth as lp_butterworth
from filter_lib.lowpass.calculations import calculate_chebyshev as lp_chebyshev


def _make_result(category: str, filter_type: str, topology: str) -> dict:
    freq_hz = 10e6 if category == "lowpass" else 1e6
    impedance = 50.0
    order = 3

    if category == "lowpass":
        if filter_type == "butterworth":
            caps, inds, actual_order = lp_butterworth(freq_hz, impedance, order, topology)
            ripple = None
        else:
            caps, inds, actual_order = lp_chebyshev(freq_hz, impedance, 0.5, order, topology)
            ripple = 0.5
        return {
            "filter_type": filter_type,
            "freq_hz": freq_hz,
            "impedance": impedance,
            "capacitors": caps,
            "inductors": inds,
            "order": actual_order,
            "ripple": ripple,
            "topology": topology,
        }

    if filter_type == "butterworth":
        inds, caps, actual_order = hp_butterworth(freq_hz, impedance, order, topology)
        ripple = None
    else:
        inds, caps, actual_order = hp_chebyshev(freq_hz, impedance, 0.5, order, topology)
        ripple = 0.5
    return {
        "filter_type": filter_type,
        "freq_hz": freq_hz,
        "impedance": impedance,
        "capacitors": caps,
        "inductors": inds,
        "order": actual_order,
        "ripple": ripple,
        "topology": topology,
    }


def _table_output(module, result: dict) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        module.display_results(result, eseries="E24", show_match=True, include_toroids=False)
    return buf.getvalue()


GOLDENS = {
    "lowpass_butterworth_pi": {
        "category": "lowpass",
        "filter_type": "butterworth",
        "topology": "pi",
        "table": "\n"
        "Butterworth PI Low Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    10 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┬───┤ L1 ├───┬─── OUT\n"
        "        │            │       \n"
        "       ===          ===      \n"
        "       C1           C2       \n"
        "        │            │       \n"
        "       GND          GND      \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Capacitors       │       Inductors        │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ C1: 318.31 pF          │ L1: 1.59 µH            │\n"
        "│ C2: 318.31 pF          │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 318.31 pF\n"
        "  Nearest Std:  330.00 pF (+3.7%)\n"
        "  Parallel Std: 47.00 pF || 270.00 pF (-0.4%)\n"
        "C2 Calculated: 318.31 pF\n"
        "  Nearest Std:  330.00 pF (+3.7%)\n"
        "  Parallel Std: 47.00 pF || 270.00 pF (-0.4%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "butterworth",\n'
        '  "cutoff_frequency_hz": 10000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 3.1830988618379065e-10,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 3.3e-10,\n'
        '            "error_pct": 3.6725575684631835\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 4.7e-11\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 2.7000000000000005e-10\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 3.1700000000000004e-10,\n'
        '            "error_pct": -0.41151288120353385\n'
        "          }\n"
        "        }\n"
        "      },\n"
        "      {\n"
        '        "name": "C2",\n'
        '        "value_farads": 3.1830988618379065e-10,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 3.3e-10,\n'
        '            "error_pct": 3.6725575684631835\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 4.7e-11\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 2.7000000000000005e-10\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 3.1700000000000004e-10,\n'
        '            "error_pct": -0.41151288120353385\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ],\n"
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 1.5915494309189533e-06\n'
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "pi"\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "C1,318.31,pF,330.00,pF,3.7,47.00 pF || 270.00 pF,-0.4,E24\n"
        "C2,318.31,pF,330.00,pF,3.7,47.00 pF || 270.00 pF,-0.4,E24\n"
        "L1,1.59,µH,,,,,,",
    },
    "lowpass_butterworth_t": {
        "category": "lowpass",
        "filter_type": "butterworth",
        "topology": "t",
        "table": "\n"
        "Butterworth T Low Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    10 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┤L1├───┬───┤L2├─── OUT\n"
        "               │              \n"
        "              ===             \n"
        "              C1              \n"
        "               │              \n"
        "              GND             \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Inductors        │       Capacitors       │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ L1: 795.77 nH          │ C1: 636.62 pF          │\n"
        "│ L2: 795.77 nH          │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 636.62 pF\n"
        "  Nearest Std:  620.00 pF (-2.6%)\n"
        "  Parallel Std: 75.00 pF || 560.00 pF (-0.3%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "butterworth",\n'
        '  "cutoff_frequency_hz": 10000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 7.957747154594766e-07\n'
        "      },\n"
        "      {\n"
        '        "name": "L2",\n'
        '        "value_henries": 7.957747154594766e-07\n'
        "      }\n"
        "    ],\n"
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 6.366197723675814e-10,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 6.2e-10,\n'
        '            "error_pct": -2.610627738716414\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 7.5e-11\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 5.6e-10\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 6.35e-10,\n'
        '            "error_pct": -0.25443324852407717\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "t"\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "L1,795.77,nH,,,,,,\n"
        "L2,795.77,nH,,,,,,\n"
        "C1,636.62,pF,620.00,pF,-2.6,75.00 pF || 560.00 pF,-0.3,E24",
    },
    "lowpass_chebyshev_pi": {
        "category": "lowpass",
        "filter_type": "chebyshev",
        "topology": "pi",
        "table": "\n"
        "Chebyshev PI Low Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    10 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Ripple:              0.5 dB\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┬───┤ L1 ├───┬─── OUT\n"
        "        │            │       \n"
        "       ===          ===      \n"
        "       C1           C2       \n"
        "        │            │       \n"
        "       GND          GND      \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Capacitors       │       Inductors        │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ C1: 508.11 pF          │ L1: 872.72 nH          │\n"
        "│ C2: 508.11 pF          │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 508.11 pF\n"
        "  Nearest Std:  510.00 pF (+0.4%)\n"
        "C2 Calculated: 508.11 pF\n"
        "  Nearest Std:  510.00 pF (+0.4%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "chebyshev",\n'
        '  "cutoff_frequency_hz": 10000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 5.081117254341799e-10,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 5.1e-10,\n'
        '            "error_pct": 0.37162585929434255\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 1.2e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 3.9e-10\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 5.1e-10,\n'
        '            "error_pct": 0.37162585929434255\n'
        "          }\n"
        "        }\n"
        "      },\n"
        "      {\n"
        '        "name": "C2",\n'
        '        "value_farads": 5.081117254341798e-10,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 5.1e-10,\n'
        '            "error_pct": 0.371625859294363\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 1.2e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 3.9e-10\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 5.1e-10,\n'
        '            "error_pct": 0.371625859294363\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ],\n"
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 8.727195466182308e-07\n'
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "pi",\n'
        '  "ripple_db": 0.5\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "C1,508.11,pF,510.00,pF,0.4,120.00 pF || 390.00 pF,0.4,E24\n"
        "C2,508.11,pF,510.00,pF,0.4,120.00 pF || 390.00 pF,0.4,E24\n"
        "L1,872.72,nH,,,,,,",
    },
    "lowpass_chebyshev_t": {
        "category": "lowpass",
        "filter_type": "chebyshev",
        "topology": "t",
        "table": "\n"
        "Chebyshev T Low Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    10 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Ripple:              0.5 dB\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┤L1├───┬───┤L2├─── OUT\n"
        "               │              \n"
        "              ===             \n"
        "              C1              \n"
        "               │              \n"
        "              GND             \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Inductors        │       Capacitors       │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ L1: 1.27 µH            │ C1: 349.09 pF          │\n"
        "│ L2: 1.27 µH            │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 349.09 pF\n"
        "  Nearest Std:  360.00 pF (+3.1%)\n"
        "  Parallel Std: 110.00 pF || 240.00 pF (+0.3%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "chebyshev",\n'
        '  "cutoff_frequency_hz": 10000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 1.2702793135854499e-06\n'
        "      },\n"
        "      {\n"
        '        "name": "L2",\n'
        '        "value_henries": 1.2702793135854497e-06\n'
        "      }\n"
        "    ],\n"
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 3.490878186472923e-10,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 3.6e-10,\n'
        '            "error_pct": 3.125912956513969\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 1.1000000000000001e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 2.4e-10\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 3.5000000000000003e-10,\n'
        '            "error_pct": 0.2613042632774796\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "t",\n'
        '  "ripple_db": 0.5\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "L1,1.27,µH,,,,,,\n"
        "L2,1.27,µH,,,,,,\n"
        "C1,349.09,pF,360.00,pF,3.1,110.00 pF || 240.00 pF,0.3,E24",
    },
    "highpass_butterworth_pi": {
        "category": "highpass",
        "filter_type": "butterworth",
        "topology": "pi",
        "table": "\n"
        "Butterworth PI High Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    1 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┬───┤ C1 ├───┬─── OUT\n"
        "        │            │       \n"
        "       ===          ===      \n"
        "       L1           L2       \n"
        "        │            │       \n"
        "       GND          GND      \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Inductors        │       Capacitors       │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ L1: 7.96 µH            │ C1: 1.59 nF            │\n"
        "│ L2: 7.96 µH            │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 1.59 nF\n"
        "  Nearest Std:  1.60 nF (+0.5%)\n"
        "  Parallel Std: 390.00 pF || 1.20 nF (-0.1%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "butterworth",\n'
        '  "cutoff_frequency_hz": 1000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 7.957747154594769e-06\n'
        "      },\n"
        "      {\n"
        '        "name": "L2",\n'
        '        "value_henries": 7.957747154594769e-06\n'
        "      }\n"
        "    ],\n"
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 1.5915494309189535e-09,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 1.6000000000000003e-09,\n'
        '            "error_pct": 0.5309649148733911\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 3.9e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 1.2e-09\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 1.59e-09,\n'
        '            "error_pct": -0.09735361584457833\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "pi"\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "L1,7.96,µH,,,,,,\n"
        "L2,7.96,µH,,,,,,\n"
        "C1,1.59,nF,1.60,nF,0.5,390.00 pF || 1.20 nF,-0.1,E24",
    },
    "highpass_butterworth_t": {
        "category": "highpass",
        "filter_type": "butterworth",
        "topology": "t",
        "table": "\n"
        "Butterworth T High Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    1 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┤C1├───┬───┤C2├─── OUT\n"
        "               │              \n"
        "              ===             \n"
        "              L1              \n"
        "               │              \n"
        "              GND             \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Capacitors       │       Inductors        │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ C1: 3.18 nF            │ L1: 3.98 µH            │\n"
        "│ C2: 3.18 nF            │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 3.18 nF\n"
        "  Nearest Std:  3.30 nF (+3.7%)\n"
        "  Parallel Std: 470.00 pF || 2.70 nF (-0.4%)\n"
        "C2 Calculated: 3.18 nF\n"
        "  Nearest Std:  3.30 nF (+3.7%)\n"
        "  Parallel Std: 470.00 pF || 2.70 nF (-0.4%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "butterworth",\n'
        '  "cutoff_frequency_hz": 1000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 3.183098861837908e-09,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 3.3e-09,\n'
        '            "error_pct": 3.6725575684631457\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 4.7e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 2.7e-09\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 3.1700000000000004e-09,\n'
        '            "error_pct": -0.4115128812035759\n'
        "          }\n"
        "        }\n"
        "      },\n"
        "      {\n"
        '        "name": "C2",\n'
        '        "value_farads": 3.183098861837908e-09,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 3.3e-09,\n'
        '            "error_pct": 3.6725575684631457\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 4.7e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 2.7e-09\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 3.1700000000000004e-09,\n'
        '            "error_pct": -0.4115128812035759\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ],\n"
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 3.9788735772973834e-06\n'
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "t"\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "C1,3.18,nF,3.30,nF,3.7,470.00 pF || 2.70 nF,-0.4,E24\n"
        "C2,3.18,nF,3.30,nF,3.7,470.00 pF || 2.70 nF,-0.4,E24\n"
        "L1,3.98,µH,,,,,,",
    },
    "highpass_chebyshev_pi": {
        "category": "highpass",
        "filter_type": "chebyshev",
        "topology": "pi",
        "table": "\n"
        "Chebyshev PI High Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    1 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Ripple:              0.5 dB\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┬───┤ C1 ├───┬─── OUT\n"
        "        │            │       \n"
        "       ===          ===      \n"
        "       L1           L2       \n"
        "        │            │       \n"
        "       GND          GND      \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Inductors        │       Capacitors       │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ L1: 4.99 µH            │ C1: 2.90 nF            │\n"
        "│ L2: 4.99 µH            │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 2.90 nF\n"
        "  Nearest Std:  3.00 nF (+3.4%)\n"
        "  Parallel Std: 1.10 nF || 1.80 nF (-0.1%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "chebyshev",\n'
        '  "cutoff_frequency_hz": 1000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 4.985182321651755e-06\n'
        "      },\n"
        "      {\n"
        '        "name": "L2",\n'
        '        "value_henries": 4.985182321651756e-06\n'
        "      }\n"
        "    ],\n"
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 2.902455434708526e-09,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 3.0000000000000004e-09,\n'
        '            "error_pct": 3.3607601386400003\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 1.1000000000000001e-09\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 1.8000000000000002e-09\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 2.9000000000000003e-09,\n'
        '            "error_pct": -0.08459853264800143\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "pi",\n'
        '  "ripple_db": 0.5\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "L1,4.99,µH,,,,,,\n"
        "L2,4.99,µH,,,,,,\n"
        "C1,2.90,nF,3.00,nF,3.4,1.10 nF || 1.80 nF,-0.1,E24",
    },
    "highpass_chebyshev_t": {
        "category": "highpass",
        "filter_type": "chebyshev",
        "topology": "t",
        "table": "\n"
        "Chebyshev T High Pass Filter\n"
        "==================================================\n"
        "Cutoff Frequency:    1 MHz\n"
        "Impedance Z0:        50 Ohm\n"
        "Ripple:              0.5 dB\n"
        "Order:               3\n"
        "==================================================\n"
        "\n"
        "Topology:\n"
        "  IN ───┤C1├───┬───┤C2├─── OUT\n"
        "               │              \n"
        "              ===             \n"
        "              L1              \n"
        "               │              \n"
        "              GND             \n"
        "\n"
        "                 Component Values                 \n"
        "┌────────────────────────┬────────────────────────┐\n"
        "│       Capacitors       │       Inductors        │\n"
        "├────────────────────────┼────────────────────────┤\n"
        "│ C1: 1.99 nF            │ L1: 7.26 µH            │\n"
        "│ C2: 1.99 nF            │                        │\n"
        "└────────────────────────┴────────────────────────┘\n"
        "Inductors: wind to value\n"
        "\n"
        "E24 Standard Capacitor Recommendations\n"
        "---------------------------------------------\n"
        "(Calculated values with nearest standard matches)\n"
        "\n"
        "C1 Calculated: 1.99 nF\n"
        "  Nearest Std:  2.00 nF (+0.3%)\n"
        "  Parallel Std: 390.00 pF || 1.60 nF (-0.2%)\n"
        "C2 Calculated: 1.99 nF\n"
        "  Nearest Std:  2.00 nF (+0.3%)\n"
        "  Parallel Std: 390.00 pF || 1.60 nF (-0.2%)\n"
        "\n",
        "json": "{\n"
        '  "filter_type": "chebyshev",\n'
        '  "cutoff_frequency_hz": 1000000.0,\n'
        '  "impedance_ohms": 50.0,\n'
        '  "order": 3,\n'
        '  "components": {\n'
        '    "capacitors": [\n'
        "      {\n"
        '        "name": "C1",\n'
        '        "value_farads": 1.994072928660702e-09,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 2e-09,\n'
        '            "error_pct": 0.2972344318058163\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 3.9e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 1.6000000000000003e-09\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 1.9900000000000004e-09,\n'
        '            "error_pct": -0.20425174035320065\n'
        "          }\n"
        "        }\n"
        "      },\n"
        "      {\n"
        '        "name": "C2",\n'
        '        "value_farads": 1.9940729286607027e-09,\n'
        '        "standard_match": {\n'
        '          "series": "E24",\n'
        '          "nearest": {\n'
        '            "value_farads": 2e-09,\n'
        '            "error_pct": 0.2972344318057747\n'
        "          },\n"
        '          "parallel": {\n'
        '            "components": [\n'
        "              {\n"
        '                "value_farads": 3.9e-10\n'
        "              },\n"
        "              {\n"
        '                "value_farads": 1.6000000000000003e-09\n'
        "              }\n"
        "            ],\n"
        '            "value_farads": 1.9900000000000004e-09,\n'
        '            "error_pct": -0.20425174035324203\n'
        "          }\n"
        "        }\n"
        "      }\n"
        "    ],\n"
        '    "inductors": [\n'
        "      {\n"
        '        "name": "L1",\n'
        '        "value_henries": 7.256138586771314e-06\n'
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "topology": "t",\n'
        '  "ripple_db": 0.5\n'
        "}",
        "csv": "Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries\n"
        "C1,1.99,nF,2.00,nF,0.3,390.00 pF || 1.60 nF,-0.2,E24\n"
        "C2,1.99,nF,2.00,nF,0.3,390.00 pF || 1.60 nF,-0.2,E24\n"
        "L1,7.26,µH,,,,,,",
    },
}


@pytest.mark.parametrize("case", GOLDENS.values(), ids=GOLDENS.keys())
def test_lp_hp_table_output_matches_golden(case: dict) -> None:
    module = lp_display if case["category"] == "lowpass" else hp_display
    result = _make_result(case["category"], case["filter_type"], case["topology"])

    assert _table_output(module, result) == case["table"]


@pytest.mark.parametrize("case", GOLDENS.values(), ids=GOLDENS.keys())
def test_lp_hp_json_output_matches_golden(case: dict) -> None:
    module = lp_display if case["category"] == "lowpass" else hp_display
    result = _make_result(case["category"], case["filter_type"], case["topology"])

    assert module.format_json(result, eseries="E24", include_toroids=False) == case["json"]


@pytest.mark.parametrize("case", GOLDENS.values(), ids=GOLDENS.keys())
def test_lp_hp_csv_output_matches_golden(case: dict) -> None:
    module = lp_display if case["category"] == "lowpass" else hp_display
    result = _make_result(case["category"], case["filter_type"], case["topology"])

    assert module.format_csv(result, eseries="E24", include_toroids=False) == case["csv"]
