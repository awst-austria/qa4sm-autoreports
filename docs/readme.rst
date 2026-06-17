.. _overview:

Overview
========

``qa4sm-autoreports`` is a Python package for programmatically creating automated
soil moisture validation reports using `QA4SM <https://qa4sm.eu>`_ (Quality
Assurance for Soil Moisture).

It is a client application built on top of the
`qa4sm-api <https://github.com/awst-austria/qa4sm-api>`_ package and automates
the full workflow: triggering remote validation runs, downloading results, and
compiling a PDF report from LaTeX templates.


Installation
------------

PDF compilation requires ``pdflatex`` from `texlive <https://tug.org/texlive/>`_::

    sudo apt install texlive-full

Install the Python package::

    pip install qa4sm-autoreports

Authentication is done via ``~/.qa4smapirc`` (see
`qa4sm-api authentication <https://github.com/awst-austria/qa4sm-api#authentication>`_)
or by passing the token directly in code.


Main components
---------------

:class:`~qa4sm_autoreports.run.ValidationRun`
    Manages a single QA4SM validation run: triggers it online, tracks its status,
    and downloads results to a local directory.

:class:`~qa4sm_autoreports.report.AutoReportCreator`
    Combines multiple validation runs into a report.  Handles triggering all runs,
    collecting variables from the results, and compiling the final PDF.

:class:`~qa4sm_autoreports.series.AutoReportSeries`
    A time-ordered collection of reports with the same configuration.  Provides
    metric tracking across reporting epochs and methods to add or delete reports.

See :ref:`components` for a full description and :ref:`quickstart` for code examples.


Development
-----------

Install from source with test dependencies::

    pip install -e .[testing]

Run the unit tests::

    pytest

Run integration tests (triggers real validation runs on the test instance)::

    pytest -m "integration"
