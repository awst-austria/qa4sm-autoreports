.. _components:

Components
==========

This page describes the main classes and modules in ``qa4sm_autoreports``.


ValidationRun  (``run.py``)
----------------------------

Represents a single QA4SM validation run — a pairing of a dataset against
one or more reference datasets over a defined geographic extent and time period.

**Construction**

.. code-block:: python

    from qa4sm_autoreports.run import ValidationRun

    # From a local JSON config template (run not yet triggered)
    run = ValidationRun.from_template(local_dir, connection=qa4sm)

    # From an existing online run (fetches config from the server)
    run = ValidationRun.from_remote(local_root, connection=qa4sm,
                                    remote_id="<uuid>")

    # From local results that were previously downloaded
    run = ValidationRun.from_results(local_dir, connection=qa4sm)

**Key methods**

* ``run.start()`` — trigger the run on QA4SM; saves response to disk.
* ``run.status`` — ``(status_str, progress_int)`` from the remote service.
* ``run.verify_period()`` — check that all datasets cover the configured period.
* ``run.download_data()`` — download netCDF results and plots to ``local_root``.
* ``run.override_params(**kwargs)`` — change config fields before starting.
* ``run.plot_extent()`` — save a map image of the validation bounding box.
* ``run.delete(local, remote)`` — remove local folder and/or online run.


AutoReportCreator  (``report.py``)
-----------------------------------

Combines multiple :class:`ValidationRun` objects into a single report.
Handles triggering, status tracking, result collection, and PDF compilation.

**Construction**

.. code-block:: python

    from qa4sm_autoreports.report import AutoReportCreator

    # From JSON config templates (creates directory structure)
    report = AutoReportCreator.from_scratch(
        report_root, templates_path, connection=qa4sm)

    # From previously created local run directories
    report = AutoReportCreator.from_results(report_root, connection=qa4sm)

**Key methods**

* ``report.start_all_runs(override)`` — trigger all runs (optional param overrides).
* ``report.validations_complete()`` — ``True`` when all remote runs are done.
* ``report.download_all_results()`` — download netCDF and graphics for every run.
* ``report.collect_content()`` — gather variables from all sources into YAML files.
* ``report.compile(template_path)`` — populate LaTeX templates with collected data
  and call ``pdflatex`` to produce a PDF.
* ``report.validation_run_table()`` — ``DataFrame`` listing all runs with URLs and dates.
* ``report.verify_dataset_availability()`` — check period coverage for all datasets.
* ``report.override_params(**kwargs)`` — forward param overrides to every run.
* ``report.delete(remote)`` — delete all runs and the local directory.
* ``report[0]`` / ``report["run1"]`` — access individual :class:`ValidationRun` by
  index or name.

**Status codes**: 0 Staged → 1 Started → 2 Processed → 3 Collected → 4 Compiled.

Content collection
^^^^^^^^^^^^^^^^^^

``collect_content()`` assembles data from four sources, writing per-run
``ContentVars.yml`` files and a common ``ReportVars.yml``:

* **ConfigData** — dataset names, versions, filters, scaling references,
  validation period.
* **NetcdfMetaData** — global attributes from the result netCDF (QA4SM version,
  processing notes, …).
* **NetcdfData** — point counts and per-dataset ``status`` pass/fail rates.
* **SummaryStatsData** — median/mean/std metrics from ``summary_stats.csv``.
* **RemoteData** — run timing and final status from the QA4SM API.

A common-extent map (``common_extent.png``) is also saved to ``report_root``.

LaTeX template rendering
^^^^^^^^^^^^^^^^^^^^^^^^

``compile()`` reads ``*.tex`` template files and replaces ``$<expr>$``
placeholders with Python expressions evaluated against the collected YAML
bindings.  Example placeholder::

    $<Run1ContentVars['ConfigVars']['interval_from']>$

Variables are accessed by YAML section name (``ReportVars``,
``Run1ContentVars``, ``Run2ContentVars``, …).  NumPy is available as ``np``
and utility functions as ``utils`` inside the expression context.


AutoReportSeries  (``series.py``)
-----------------------------------

A collection of :class:`AutoReportCreator` reports that share the same
datasets and configuration but cover different time periods (called *epochs*).

.. code-block:: python

    from qa4sm_autoreports.series import AutoReportSeries

    series = AutoReportSeries("/results/my_series", connection=qa4sm)

**Key methods**

* ``series.new_report(name, config_template_path, override_params)`` — create
  and register a new report in the series.
* ``series.delete_report(name, remote)`` — remove a report from the series.
* ``series.reports_complete()`` — ``True`` if every report is at least *collected*.
* ``series.track_metric(metric, ...)`` — compute per-epoch boxplot statistics for
  one metric and save a tracking plot and YAML to disk.
* ``series[0]`` / ``series["epoch_name"]`` — access a report by index or name.


GeographicExtent  (``extent.py``)
-----------------------------------

An immutable bounding box (``min_lat``, ``min_lon``, ``max_lat``, ``max_lon``).

.. code-block:: python

    from qa4sm_autoreports.extent import GeographicExtent

    a = GeographicExtent(min_lat=-10, min_lon=10, max_lat=20, max_lon=50)
    b = GeographicExtent.from_corners(-10, 10, 20, 50)  # same result

    a & b   # intersection  (returns None if no overlap)
    a | b   # union (bounding box)
    a.overlaps(b)
    a.contains(b)
    a.equals(b, tolerance=0.01)  # fuzzy comparison
    GeographicExtent.multi_intersection(a, b, c)  # common region of N extents

    fig = a.plot_map()           # cartopy map focused on the extent
    fig = a.plot_map(global_map=True)  # world map with extent highlighted


Data containers  (``data.py``)
--------------------------------

``Data`` and its subclasses are thin wrappers around a ``dict`` that can be
serialised to / loaded from YAML.

.. code-block:: python

    from qa4sm_autoreports.data import Data

    d = Data()
    d.add({"my_key": 42}, section="MySection")
    d.dump("/path/to/file.yml", overwrite=True)

    d2 = Data.from_yml("/path/to/file.yml")

Subclasses — ``ConfigData``, ``NetcdfMetaData``, ``NetcdfData``,
``SummaryStatsData``, ``RemoteData`` — each expose a ``collect()`` method that
reads from the appropriate source and returns ``self`` so they can be chained
with ``RunData.append()``.


Utilities  (``utils.py``)
--------------------------

* ``escape_latex(value)`` — escape LaTeX special characters (``&``, ``%``,
  ``$``, ``_``, …) so that plain strings can be safely embedded in ``.tex``
  files.
* ``ValidationReportError`` — base exception for report-level failures.
