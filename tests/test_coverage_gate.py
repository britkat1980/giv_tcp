"""The gate checks each file, including zero coverage and unrounded boundaries."""
from check_coverage import below_target


def test_individual_files_cannot_hide_behind_a_high_average():
    report = {'files': {name: {'summary': {'percent_covered': percent}}
                        for name, percent in [('good.py', 99), ('missing.py', 0),
                                              ('boundary.py', 70), ('rounded.py', 69.999)]}}
    assert below_target(report, 70) == [('missing.py', 0), ('rounded.py', 69.999)]


def test_empty_python_files_count_as_fully_covered():
    assert below_target({'files': {'empty.py': {'summary': {'percent_covered': 100}}}}, 70) == []
