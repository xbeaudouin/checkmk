#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""
This special agent is deprecated. Please use netapp_ontap_info.
"""


from cmk.agent_based.v2 import Attributes, InventoryPlugin, InventoryResult, StringTable


def inventory_netapp_api_info(section: StringTable) -> InventoryResult:
    info_dict = {x[0]: x[1] for x in section if x[0] != "node"}

    sw_os: dict[str, str] = {}
    hw_chassis: dict[str, str] = {}
    hw_system: dict[str, str] = {}
    hw_cpu: dict[str, str] = {}

    for what, name, where_to in [
        ("backplane-serial-number", "serial", hw_chassis),
        ("system-model", "model", hw_system),
        ("system-machine-type", "product", hw_system),
        ("system-serial-number", "serial", hw_system),
        ("system-id", "id", hw_system),
        ("vendor-id", "vendor", sw_os),
        ("number-of-processors", "cores", hw_cpu),
        ("cpu-processor-type", "model", hw_cpu),
    ]:
        if what in info_dict:
            where_to[name] = info_dict[what]

    yield Attributes(path=["hardware", "chassis"], inventory_attributes=hw_chassis)
    yield Attributes(path=["hardware", "cpu"], inventory_attributes=hw_cpu)
    yield Attributes(path=["hardware", "system"], inventory_attributes=hw_system)
    yield Attributes(path=["software", "os"], inventory_attributes=sw_os)


inventory_plugin_netapp_api_info = InventoryPlugin(
    name="netapp_api_info",
    inventory_function=inventory_netapp_api_info,
)
