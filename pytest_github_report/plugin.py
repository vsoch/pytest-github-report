import os
from collections import defaultdict
from typing import Dict, Mapping, Sequence, Tuple

from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from pytablewriter import TableWriterFactory


# Get default emojis
# https://gist.github.com/rxaviers/7360908
emojis = {
    "passed": os.environ.get("pytest_passed_emoji", ":green_circle:"),
    "failed": os.environ.get("pytest_failed_emoji", ":red_circle:"),
    "error": os.environ.get("pytest_error_emoji", ":red_circle:"),
    "skipped": os.environ.get("pytest_skipped_emoji", ":leftwards_arrow_with_hook:"),
    "xfailed": os.environ.get("pytest_xfailed_emoji", ":red_circle:"),
    "xpassed": os.environ.get("pytest_xpassed_emoji", ":green_circle:"),
}

# Get verbosity
try:
    verbosity = int(os.environ.get("pytest_verbosity", 0))
except:
    verbosity = 0


detail = """<details>

<summary>%s</summary>

```python
%s
```

</details>
"""


def pytest_addoption(parser):
    group = parser.getgroup(
        "github report", "output tables for GitHub Workflow reports"
    )
    group.addoption(
        "--github-report",
        action="store_true",
        default=None,
        help="Generate a GitHub Workflow markdown report.",
    )

    # Add pytest.ini values
    parser.addini(
        "pytest-github-report",
        default=False,
        help="Generate a GitHub workflow markdown report (via pytest.ini)",
    )


def wants_github_report(config: Config) -> bool:
    """
    Determine if the user requested to make the GitHub report.
    """
    if config.option.help:
        return False

    # First look at command line and environment
    make_report = config.option.github_report or os.environ.get("pytest_github_report")

    # Then pytest.ini
    if make_report is None:
        make_report = config.getini("pytest-github-report")

    # Allows it to be None, False, etc.
    if not make_report:
        return False
    return True


def extract_pytest_stats(
    reporter: TerminalReporter, outcomes: Sequence[str]
) -> Mapping[Tuple, Mapping[str, int]]:
    """
    Extract stats from outcomes
    """
    results_per_testfunc: Dict[Tuple, Dict[str, int]] = {}

    for stat_key, values in reporter.stats.items():
        if stat_key not in outcomes:
            continue

        for value in values:
            try:
                filesystempath, lineno, domaininfo = value.location
            except AttributeError:
                continue

            testfunc = value.head_line.split("[")[0]

            if verbosity == 0:
                key: Tuple = (filesystempath,)
            elif verbosity >= 1:
                key = (filesystempath, testfunc)

            if key not in results_per_testfunc:
                results_per_testfunc[key] = {
                    "count": defaultdict(int),
                    "duration": 0,
                    "out": "",
                }
            results_per_testfunc[key]["count"][stat_key] += 1
            results_per_testfunc[key]["duration"] += value.duration
            if value.longrepr:
                results_per_testfunc[key]["out"] += str(value.longrepr)
    return results_per_testfunc


def pytest_unconfigure(config):
    """
    Called before test process is exited.
    """
    if not wants_github_report(config):
        return

    reporter = config.pluginmanager.get_plugin("terminalreporter")
    stats = retrieve_stats(reporter)
    report = make_github_report(config, reporter, stats)
    reporter._tw.write(report["table"])

    # Also echo to GitHub Step summary
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    report_title = os.environ.get("pytest_report_title", "⭐️ Test Report ⭐️")
    if step_summary:
        with open(step_summary, "a") as fd:
            fd.write(f"### {report_title}\n")
            fd.write(report["table"] + "\n")
            fd.write(report["details"])


def retrieve_stats(reporter: TerminalReporter) -> Dict[str, int]:
    """
    Get a lookup of final stats for what passed, skipped, etc.
    """
    stats = {}
    for name in ["failed", "passed", "skipped", "error", "xfailed", "xpassed"]:
        stats[name] = len(reporter.getreports(name))
    return stats


def prepare_details(results):
    """
    Prepare a details tab for each result
    """
    details = ""
    for key, result in results.items():
        if result["out"]:
            # By file or test
            if len(key) == 1:
                details += detail % (key[0], result["out"])
            else:
                details += detail % (key[0] + ":" + key[1], result["out"])
    return details


def make_github_report(
    config: Config, reporter: TerminalReporter, total_stats: Mapping[str, int]
) -> str:
    """
    main function for generating report!
    """
    outcomes = ["passed", "failed", "error", "skipped", "xfailed", "xpassed"]
    outcomes = [key for key in outcomes if total_stats.get(key, 0) > 0]
    results_per_testfunc = extract_pytest_stats(reporter=reporter, outcomes=outcomes)
    writer = TableWriterFactory.create_from_format_name("md")
    details = prepare_details(results_per_testfunc)

    use_zeros = os.environ.get("pytest_use_zeros")
    use_blanks = os.environ.get("pytest_use_blanks")

    if use_blanks is not None:
        matrix = [
            list(key)
            + [
                results["count"].get(key) if results["count"].get(key) != 0 else ""
                for key in outcomes
            ]
            + [sum(results["count"].values())]
            for key, results in results_per_testfunc.items()
        ]

    elif use_zeros is not None:
        matrix = [
            list(key)
            + [results["count"].get(key, 0) for key in outcomes]
            + [sum(results["count"].values())]
            for key, results in results_per_testfunc.items()
        ]
    else:
        matrix = [
            list(key)
            + [
                emojis.get(outcomes[i])
                if (
                    results["count"].get(key) is not None
                    and results["count"].get(key) != 0
                )
                else results["count"].get(key)
                for i, key in enumerate(outcomes)
            ]
            + [sum(results["count"].values())]
            for key, results in results_per_testfunc.items()
        ]

    writer.headers = ["path", "function"] + outcomes + ["subtotal"]
    if verbosity == 0:
        writer.headers = ["path"] + outcomes + ["subtotal"]
        matrix.append(
            ["TOTAL"]
            + [total_stats.get(key, 0) for key in outcomes]
            + [sum(total_stats.values())]
        )
    else:
        matrix.append(
            ["TOTAL", ""]
            + [total_stats.get(key, 0) for key in outcomes]
            + [sum(total_stats.values())]
        )

    # Could customize these if desired
    writer.margin = 1
    writer.value_matrix = matrix
    report_color = "auto"

    # Add report colors
    writer.style_filter_kwargs = {
        "report_color": report_color,
        "color_map": {
            "SUCCESS": "light_green",
            "ERROR": "light_red",
            "SKIP": "light_yellow",
            "GRAYOUT": "light_black",
        },
        "num_rows": len(writer.value_matrix),
    }
    return {"table": writer.dumps(), "details": details}
