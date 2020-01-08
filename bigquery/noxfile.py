# Copyright 2016 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import os
import shutil

import nox


LOCAL_DEPS = (os.path.join("..", "api_core[grpc]"), os.path.join("..", "core"))

BLACK_PATHS = ("docs", "google", "samples", "tests", "noxfile.py", "setup.py")


def default(session):
    """Default unit test session.

    This is intended to be run **without** an interpreter set, so
    that the current ``python`` (on the ``PATH``) or the version of
    Python corresponding to the ``nox`` binary the ``PATH`` can
    run the tests.
    """
    # Install all test dependencies, then install local packages in-place.
    session.install("mock", "pytest", "pytest-cov")
    for local_dep in LOCAL_DEPS:
        session.install("-e", local_dep)

    session.install("-e", os.path.join("..", "test_utils"))

    coverage_fail_under = "--cov-fail-under=97"

    # fastparquet is not included in .[all] because, in general, it's redundant
    # with pyarrow. We still want to run some unit tests with fastparquet
    # serialization, though.
    dev_install = ".[all,fastparquet]"

    # There is no pyarrow or fastparquet wheel for Python 3.8.
    if session.python == "3.8":
        # Since many tests are skipped due to missing dependencies, test
        # coverage is much lower in Python 3.8. Remove once we can test with
        # pyarrow.
        coverage_fail_under = "--cov-fail-under=92"
        dev_install = ".[pandas,tqdm]"

    session.install("-e", dev_install)

    # IPython does not support Python 2 after version 5.x
    if session.python == "2.7":
        session.install("ipython==5.5")
    else:
        session.install("ipython")

    # Run py.test against the unit tests.
    session.run(
        "py.test",
        "--quiet",
        "--cov=google.cloud.bigquery",
        "--cov=tests.unit",
        "--cov-append",
        "--cov-config=.coveragerc",
        "--cov-report=",
        coverage_fail_under,
        os.path.join("tests", "unit"),
        *session.posargs
    )


@nox.session(python=["2.7", "3.5", "3.6", "3.7", "3.8"])
def unit(session):
    """Run the unit test suite."""
    default(session)


@nox.session(python=["2.7", "3.7"])
def system(session):
    """Run the system test suite."""

    # Sanity check: Only run system tests if the environment variable is set.
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""):
        session.skip("Credentials must be set via environment variable.")

    # Use pre-release gRPC for system tests.
    session.install("--pre", "grpcio")

    # Install all test dependencies, then install local packages in place.
    session.install("mock", "pytest", "psutil")
    for local_dep in LOCAL_DEPS:
        session.install("-e", local_dep)
    session.install("-e", os.path.join("..", "storage"))
    session.install("-e", os.path.join("..", "test_utils"))
    session.install("-e", ".[all]")

    # IPython does not support Python 2 after version 5.x
    if session.python == "2.7":
        session.install("ipython==5.5")
    else:
        session.install("ipython")

    # Run py.test against the system tests.
    session.run(
        "py.test", "--quiet", os.path.join("tests", "system.py"), *session.posargs
    )


@nox.session(python=["2.7", "3.7"])
def snippets(session):
    """Run the snippets test suite."""

    # Sanity check: Only run snippets tests if the environment variable is set.
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""):
        session.skip("Credentials must be set via environment variable.")

    # Install all test dependencies, then install local packages in place.
    session.install("mock", "pytest")
    for local_dep in LOCAL_DEPS:
        session.install("-e", local_dep)
    session.install("-e", os.path.join("..", "storage"))
    session.install("-e", os.path.join("..", "test_utils"))
    session.install("-e", ".[all]")

    # Run py.test against the snippets tests.
    session.run("py.test", os.path.join("docs", "snippets.py"), *session.posargs)
    session.run("py.test", "samples", *session.posargs)


@nox.session(python="3.7")
def cover(session):
    """Run the final coverage report.

    This outputs the coverage report aggregating coverage from the unit
    test runs (not system test runs), and then erases coverage data.
    """
    session.install("coverage", "pytest-cov")
    session.run("coverage", "report", "--show-missing", "--fail-under=100")
    session.run("coverage", "erase")


@nox.session(python="3.7")
def lint(session):
    """Run linters.

    Returns a failure if the linters find linting errors or sufficiently
    serious code quality issues.
    """

    session.install("black", "flake8")
    for local_dep in LOCAL_DEPS:
        session.install("-e", local_dep)
    session.install("-e", ".")
    session.run("flake8", os.path.join("google", "cloud", "bigquery"))
    session.run("flake8", "tests")
    session.run("flake8", os.path.join("docs", "samples"))
    session.run("flake8", os.path.join("docs", "snippets.py"))
    session.run("black", "--check", *BLACK_PATHS)


@nox.session(python="3.7")
def lint_setup_py(session):
    """Verify that setup.py is valid (including RST check)."""

    session.install("docutils", "Pygments")
    session.run("python", "setup.py", "check", "--restructuredtext", "--strict")


@nox.session(python="3.6")
def blacken(session):
    """Run black.
    Format code to uniform standard.

    This currently uses Python 3.6 due to the automated Kokoro run of synthtool.
    That run uses an image that doesn't have 3.6 installed. Before updating this
    check the state of the `gcp_ubuntu_config` we use for that Kokoro run.
    """
    session.install("black")
    session.run("black", *BLACK_PATHS)


@nox.session(python="3.7")
def docs(session):
    """Build the docs."""

    session.install("ipython", "recommonmark", "sphinx", "sphinx_rtd_theme")
    for local_dep in LOCAL_DEPS:
        session.install("-e", local_dep)
    session.install("-e", os.path.join("..", "storage"))
    session.install("-e", ".[all]")

    shutil.rmtree(os.path.join("docs", "_build"), ignore_errors=True)
    session.run(
        "sphinx-build",
        "-W",  # warnings as errors
        "-T",  # show full traceback on exception
        "-N",  # no colors
        "-b",
        "html",
        "-d",
        os.path.join("docs", "_build", "doctrees", ""),
        os.path.join("docs", ""),
        os.path.join("docs", "_build", "html", ""),
    )
