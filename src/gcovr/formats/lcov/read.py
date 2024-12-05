# -*- coding:utf-8 -*-

#  ************************** Copyrights and license ***************************
#
# This file is part of gcovr 8.2+main, a parsing and reporting tool for gcov.
# https://gcovr.com/en/main
#
# _____________________________________________________________________________
#
# Copyright (c) 2013-2024 the gcovr authors
# Copyright (c) 2013 Sandia Corporation.
# Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
# the U.S. Government retains certain rights in this software.
#
# This software is distributed under the 3-clause BSD License.
# For more information, see the README.rst file.
#
# ****************************************************************************

import json
import logging
import os
from glob import glob
from typing import Any, Optional

from ...coverage import (
    BranchCoverage,
    ConditionCoverage,
    CoverageContainer,
    DecisionCoverage,
    DecisionCoverageConditional,
    DecisionCoverageSwitch,
    DecisionCoverageUncheckable,
    FileCoverage,
    FunctionCoverage,
    LineCoverage,
    CallCoverage,
)
from ...merging import (
    get_merge_mode_from_options,
    insert_branch_coverage,
    insert_condition_coverage,
    insert_decision_coverage,
    insert_file_coverage,
    insert_function_coverage,
    insert_line_coverage,
    insert_call_coverage,
)
from ...options import Options
from ...utils import is_file_excluded

LOGGER = logging.getLogger("gcovr")


#
#  Get coverage from already existing LCOV files
#
def read_report(options: Options) -> CoverageContainer:
    """merge a coverage from multiple reports in the format
    partially compatible with gcov JSON output"""

    covdata = CoverageContainer()
    if len(options.lcov_add_tracefile) == 0:
        return covdata

    datafiles = set()

    for trace_files_regex in options.lcov_add_tracefile:
        trace_files = glob(trace_files_regex, recursive=True)
        if not trace_files:
            raise RuntimeError(
                "Bad --lcov-add-tracefile option.\n"
                "\tThe specified file does not exist."
            )

        for trace_file in trace_files:
            datafiles.add(os.path.normpath(trace_file))

    merge_options = get_merge_mode_from_options(options)

    for data_source_filename in datafiles:
        LOGGER.debug(f"Processing LCOV file: {data_source_filename}")

        function_to_line_number = dict()

        with open(data_source_filename, encoding="utf-8") as lcov_file:
            for line in lcov_file:
                line = line.strip()
                if line.startswith("SF:"):
                    file_path = line.split(":")[-1]
                    file_path = os.path.join(
                        os.path.abspath(options.root), os.path.normpath(file_path)
                    )
                    filecov = FileCoverage(file_path, data_source_filename)
                elif line.startswith("FN:"):
                    line_number, function_name = line.removeprefix("FN:").split(",")
                    line_number = int(line_number)
                    function_to_line_number[function_name] = line_number
                    fc = FunctionCoverage(
                            function_name,
                            function_name,
                            count=0,
                            blocks=0,
                            lineno=line_number)
                    insert_function_coverage(filecov, fc, merge_options)
                elif line.startswith("FNDA:"):
                    count, function_name = line.removeprefix("FNDA:").split(",")
                    count = int(count)
                    fc = FunctionCoverage(
                            function_name,
                            function_name,
                            count=count,
                            blocks=0,
                            lineno=function_to_line_number[function_name])
                    insert_function_coverage(filecov, fc, merge_options)
                elif line.startswith("DA:"):
                    # Skip the optional checksum
                    line_number, count = line.removeprefix("DA:").split(",")[0:2]
                    line_number = int(line_number)
                    count = int(count)
                    lc = LineCoverage(
                        line_number,
                        count
                    )
                    insert_line_coverage(filecov, lc)
                elif line.startswith("BRDA:"):
                    line_number, block, branch, taken = line.removeprefix("BRDA:").split(",")
                    line_number = int(line_number)
                    if block.startswith("e"):
                        exception = True
                        block = int(block.removeprefix("e"))
                    else:
                        exception = False
                        block = int(block)

                    if taken == "-":
                        taken = 0
                    else:
                        taken = int(taken)

                    # Workaround for coverage.py generating BRDA:0
                    # https://github.com/nedbat/coveragepy/issues/1846
                    if line_number == 0:
                        continue

                    lc = LineCoverage(
                        line_number,
                        0,
                    )

                    bc = BranchCoverage(
                        blockno=block,
                        throw=exception,
                        count = taken,
                    )

                    insert_branch_coverage(lc, block, bc)
                    insert_line_coverage(filecov, lc)

                elif line.startswith("end_of_record"):
                    if is_file_excluded(file_path, options.filter, options.exclude):
                        continue
                    insert_file_coverage(covdata, filecov, merge_options)
                    filecov = None
                    file_path = None

    return covdata
