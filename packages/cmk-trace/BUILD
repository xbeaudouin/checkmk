load("@aspect_rules_py//py:defs.bzl", "py_library")
load("@omd_packages//omd/packages/rules:package_wheel.bzl", "package_wheel")
load("@rules_python//python:packaging.bzl", "py_wheel")

py_library(
    name = "cmk-trace",
    srcs = [
        "cmk/trace/__init__.py",
        "cmk/trace/_config.py",
        "cmk/trace/export.py",
        "cmk/trace/logs.py",
        "cmk/trace/py.typed",
    ],
    imports = ["."],
    visibility = ["//cmk:__pkg__"],
)

py_wheel(
    name = "wheel",
    distribution = "cmk-trace",
    strip_path_prefixes = ["packages/cmk-trace"],
    # TODO: Duplicated from pyproject.toml
    version = "1.0.0",
    deps = [
        ":cmk-trace",
    ],
)

package_wheel(
    name = "pkg_tar",
    visibility = ["//visibility:public"],
    whl = "wheel",
)
