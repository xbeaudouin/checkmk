#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# tails. You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

import os
import sys
import socket
import subprocess
import time
import pprint
from typing import Union, Tuple, Optional, Set, Dict, List  # pylint: disable=unused-import

import six

import cmk.utils.tty as tty
import cmk.utils.paths
import cmk.utils.debug
from cmk.utils.exceptions import MKGeneralException

import cmk.base.utils
import cmk.base.console as console
import cmk.base.config as config
import cmk.base.ip_lookup as ip_lookup
from cmk.base.utils import HostName, HostAddress  # pylint: disable=unused-import

Gateways = List[Tuple[Optional[Tuple[Optional[HostName], HostAddress, Optional[HostName]]], str,
                      int, str]]


def do_scan_parents(hosts):
    # type: (List[HostName]) -> None
    config_cache = config.get_config_cache()

    if not hosts:
        hosts = list(sorted(config_cache.all_active_realhosts()))

    parent_hosts = []
    parent_ips = {}  # type: Dict[HostName, HostAddress]
    parent_rules = []
    gateway_hosts = set()  # type: Set[HostName]

    if config.max_num_processes < 1:
        config.max_num_processes = 1

    outfilename = cmk.utils.paths.check_mk_config_dir + "/parents.mk"

    if not traceroute_available():
        raise MKGeneralException('The program "traceroute" was not found.\n'
                                 'The parent scan needs this program.\n'
                                 'Please install it and try again.')

    if os.path.exists(outfilename):
        first_line = open(outfilename, "r").readline()
        if not first_line.startswith('# Automatically created by --scan-parents at'):
            raise MKGeneralException("conf.d/parents.mk seems to be created manually.\n\n"
                                     "The --scan-parents function would overwrite this file.\n"
                                     "Please rename it to keep the configuration or delete "
                                     "the file and try again.")

    console.output("Scanning for parents (%d processes)..." % config.max_num_processes)
    while hosts:
        chunk = []  # type: List[HostName]
        while len(chunk) < config.max_num_processes and len(hosts) > 0:
            host = hosts.pop()

            host_config = config_cache.get_host_config(host)

            # skip hosts that already have a parent
            if host_config.parents:
                console.verbose("(manual parent) ")
                continue
            chunk.append(host)

        gws = scan_parents_of(config_cache, chunk)

        for host, (gw, _unused_state, _unused_ping_fails, _unused_message) in zip(chunk, gws):
            if gw:
                gateway, gateway_ip, dns_name = gw
                if not gateway:  # create artificial host
                    if dns_name:
                        gateway = dns_name
                    else:
                        gateway = "gw-%s" % (gateway_ip.replace(".", "-"))
                    if gateway not in gateway_hosts:
                        gateway_hosts.add(gateway)
                        parent_hosts.append("%s|parent|ping" % gateway)
                        parent_ips[gateway] = gateway_ip
                        if config.monitoring_host:
                            parent_rules.append(
                                (config.monitoring_host, [gateway]))  # make Nagios a parent of gw
                parent_rules.append((gateway, [host]))
            elif host != config.monitoring_host and config.monitoring_host:
                # make monitoring host the parent of all hosts without real parent
                parent_rules.append((config.monitoring_host, [host]))

    with open(outfilename, "w") as out:
        out.write("# Automatically created by --scan-parents at %s\n\n" % time.asctime())
        out.write("# Do not edit this file. If you want to convert an\n")
        out.write("# artificial gateway host into a permanent one, then\n")
        out.write("# move its definition into another *.mk file\n")

        out.write("# Parents which are not listed in your all_hosts:\n")
        out.write("all_hosts += %s\n\n" % pprint.pformat(parent_hosts))

        out.write("# IP addresses of parents not listed in all_hosts:\n")
        out.write("ipaddresses.update(%s)\n\n" % pprint.pformat(parent_ips))

        out.write("# Parent definitions\n")
        out.write("parents += %s\n\n" % pprint.pformat(parent_rules))
    console.output("\nWrote %s\n" % outfilename)


def traceroute_available():
    # type: () -> Optional[str]
    for path in os.environ['PATH'].split(os.pathsep):
        f = path + '/traceroute'
        if os.path.exists(f) and os.access(f, os.X_OK):
            return f
    return None


def scan_parents_of(config_cache, hosts, silent=False, settings=None):
    # type: (config.ConfigCache, List[HostName], bool, Optional[Dict[str, int]]) -> Gateways
    if settings is None:
        settings = {}

    if config.monitoring_host:
        nagios_ip = ip_lookup.lookup_ipv4_address(config.monitoring_host)
    else:
        nagios_ip = None

    os.putenv("LANG", "")
    os.putenv("LC_ALL", "")

    # Start processes in parallel
    procs = []  # type: List[Tuple[HostName, Optional[HostAddress], Union[str, subprocess.Popen]]]
    for host in hosts:
        console.verbose("%s " % host)
        try:
            ip = ip_lookup.lookup_ipv4_address(host)
            if ip is None:
                raise RuntimeError()
            command = [
                "traceroute", "-w",
                "%d" % settings.get("timeout", 8), "-q",
                "%d" % settings.get("probes", 2), "-m",
                "%d" % settings.get("max_ttl", 10), "-n", ip
            ]
            console.vverbose("Running '%s'\n" % subprocess.list2cmdline(command))

            procs.append((host, ip,
                          subprocess.Popen(command,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT,
                                           close_fds=True)))
        except Exception as e:
            if cmk.utils.debug.enabled():
                raise
            procs.append((host, None, "ERROR: %s" % e))

    # Output marks with status of each single scan
    def dot(color, dot='o'):
        # type: (str, str) -> None
        if not silent:
            console.output(tty.bold + color + dot + tty.normal)

    # Now all run and we begin to read the answers. For each host
    # we add a triple to gateways: the gateway, a scan state  and a diagnostic output
    gateways = []  # type: Gateways
    for host, ip, proc_or_error in procs:
        if isinstance(proc_or_error, six.string_types):
            lines = [proc_or_error]
            exitstatus = 1
        else:
            exitstatus = proc_or_error.wait()
            if proc_or_error.stdout is None:
                raise RuntimeError()
            lines = [l.strip() for l in proc_or_error.stdout.readlines()]

        if exitstatus:
            dot(tty.red, '*')
            gateways.append(
                (None, "failed", 0, "Traceroute failed with exit code %d" % (exitstatus & 255)))
            continue

        if len(lines) == 1 and lines[0].startswith("ERROR:"):
            message = lines[0][6:].strip()
            console.verbose("%s: %s\n", host, message, stream=sys.stderr)
            dot(tty.red, "D")
            gateways.append((None, "dnserror", 0, message))
            continue

        if len(lines) == 0:
            if cmk.utils.debug.enabled():
                raise MKGeneralException(
                    "Cannot execute %s. Is traceroute installed? Are you root?" % command)
            dot(tty.red, '!')
            continue

        if len(lines) < 2:
            if not silent:
                console.error("%s: %s\n" % (host, ' '.join(lines)))
            gateways.append((None, "garbled", 0,
                             "The output of traceroute seem truncated:\n%s" % ("".join(lines))))
            dot(tty.blue)
            continue

        # Parse output of traceroute:
        # traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 40 byte packets
        #  1  * * *
        #  2  10.0.0.254  0.417 ms  0.459 ms  0.670 ms
        #  3  172.16.0.254  0.967 ms  1.031 ms  1.544 ms
        #  4  217.0.116.201  23.118 ms  25.153 ms  26.959 ms
        #  5  217.0.76.134  32.103 ms  32.491 ms  32.337 ms
        #  6  217.239.41.106  32.856 ms  35.279 ms  36.170 ms
        #  7  74.125.50.149  45.068 ms  44.991 ms *
        #  8  * 66.249.94.86  41.052 ms 66.249.94.88  40.795 ms
        #  9  209.85.248.59  43.739 ms  41.106 ms 216.239.46.240  43.208 ms
        # 10  216.239.48.53  45.608 ms  47.121 ms 64.233.174.29  43.126 ms
        # 11  209.85.255.245  49.265 ms  40.470 ms  39.870 ms
        # 12  8.8.8.8  28.339 ms  28.566 ms  28.791 ms
        routes = []  # type: List[Optional[str]]
        for line in lines[1:]:
            parts = line.split()
            route = parts[1]
            if route.count('.') == 3:
                routes.append(route)
            elif route == '*':
                routes.append(None)  # No answer from this router
            else:
                if not silent:
                    console.error("%s: invalid output line from traceroute: '%s'\n" % (host, line))

        if len(routes) == 0:
            error = "incomplete output from traceroute. No routes found."
            console.error("%s: %s\n" % (host, error))
            gateways.append((None, "garbled", 0, error))
            dot(tty.red)
            continue

        # Only one entry -> host is directly reachable and gets nagios as parent -
        # if nagios is not the parent itself. Problem here: How can we determine
        # if the host in question is the monitoring host? The user must configure
        # this in monitoring_host.
        if len(routes) == 1:
            if ip == nagios_ip:
                gateways.append((None, "root", 0, ""))  # We are the root-monitoring host
                dot(tty.white, 'N')
            elif config.monitoring_host:
                gateways.append(((config.monitoring_host, nagios_ip, None), "direct", 0, ""))
                dot(tty.cyan, 'L')
            else:
                gateways.append((None, "direct", 0, ""))
            continue

        # Try far most route which is not identical with host itself
        ping_probes = settings.get("ping_probes", 5)
        skipped_gateways = 0
        this_route = None  # type: Optional[HostAddress]
        for r in routes[::-1]:
            if not r or (r == ip):
                continue
            # Do (optional) PING check in order to determine if that
            # gateway can be monitored via the standard host check
            if ping_probes:
                if not gateway_reachable_via_ping(r, ping_probes):
                    console.verbose("(not using %s, not reachable)\n", r, stream=sys.stderr)
                    skipped_gateways += 1
                    continue
            this_route = r
            break
        if not this_route:
            error = "No usable routing information"
            if not silent:
                console.error("%s: %s\n" % (host, error))
            gateways.append((None, "notfound", 0, error))
            dot(tty.blue)
            continue

        # TTLs already have been filtered out)
        gateway_ip = this_route
        gateway = _ip_to_hostname(config_cache, this_route)
        if gateway:
            console.verbose("%s(%s) ", gateway, gateway_ip)
        else:
            console.verbose("%s ", gateway_ip)

        # Try to find DNS name of host via reverse DNS lookup
        dns_name = _ip_to_dnsname(gateway_ip)
        gateways.append(((gateway, gateway_ip, dns_name), "gateway", skipped_gateways, ""))
        dot(tty.green, 'G')
    return gateways


def gateway_reachable_via_ping(ip, probes):
    # type: (HostAddress, int) -> bool
    return subprocess.call(
        ["ping", "-q", "-i", "0.2", "-l", "3", "-c",
         "%d" % probes, "-W", "5", ip],
        stdout=open(os.devnull, "w"),
        stderr=subprocess.STDOUT,
        close_fds=True) == 0


# find hostname belonging to an ip address. We must not use
# reverse DNS but the Check_MK mechanisms, since we do not
# want to find the DNS name but the name of a matching host
# from all_hosts
def _ip_to_hostname(config_cache, ip):
    # type: (config.ConfigCache, Optional[HostAddress]) -> Optional[HostName]
    if not cmk.base.config_cache.exists("ip_to_hostname"):
        cache = cmk.base.config_cache.get_dict("ip_to_hostname")

        for host in config_cache.all_active_realhosts():
            try:
                cache[ip_lookup.lookup_ipv4_address(host)] = host
            except Exception:
                pass
    else:
        cache = cmk.base.config_cache.get_dict("ip_to_hostname")

    return cache.get(ip)


def _ip_to_dnsname(ip):
    # type: (HostAddress) -> Optional[HostName]
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None
