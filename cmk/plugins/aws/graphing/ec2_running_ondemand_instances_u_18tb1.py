#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from cmk.graphing.v1 import graphs, metrics, Title

UNIT_NUMBER = metrics.Unit(metrics.DecimalNotation(""), metrics.StrictPrecision(2))

metric_aws_ec2_running_ondemand_instances_u_18tb1_metal = metrics.Metric(
    name="aws_ec2_running_ondemand_instances_u-18tb1.metal",
    title=Title("Total running on-demand u-18tb1.metal instances"),
    unit=UNIT_NUMBER,
    color=metrics.Color.DARK_BLUE,
)

graph_aws_ec2_running_ondemand_instances_u_18tb1 = graphs.Graph(
    name="aws_ec2_running_ondemand_instances_u_18tb1",
    title=Title("Total running on-demand instances of type u-18tb1"),
    compound_lines=[
        "aws_ec2_running_ondemand_instances_u-18tb1.metal",
    ],
    optional=[],
)
