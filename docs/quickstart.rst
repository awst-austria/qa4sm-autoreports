.. _quickstart:

Quickstart
==========

Prerequisites
-------------

Install `texlive <https://tug.org/texlive/>`_ for PDF compilation::

    sudo apt install texlive-full

Install the package::

    pip install qa4sm-autoreports

Authenticate by creating ``~/.qa4smapirc`` as described in the
`qa4sm-api docs <https://github.com/awst-austria/qa4sm-api#authentication>`_,
or pass the token directly in code.


Connecting to QA4SM
--------------------

.. code-block:: python

    from qa4sm_autoreports import Connection

    qa4sm = Connection("qa4sm.eu")                      # uses .qa4smapirc
    qa4sm = Connection("qa4sm.eu", token="<your-token>")  # explicit token


.. _run-config-templates:

Run configuration templates
----------------------------

Each validation run in a report is defined by a JSON configuration template.
Place one ``.json`` file per run in the ``templates_path`` directory — the
filename (without the extension) becomes the run's folder name inside the
report directory.

The template follows the QA4SM validation API schema.  A working example
(ISMN vs. C3S, used by the integration tests) is provided in
``tests/testdata/report_config_templates/ismn_c3s.json``:

.. literalinclude:: ../tests/testdata/report_config_templates/ismn_c3s.json
   :language: json

Any top-level field can be overridden at runtime without editing the template,
which is useful when only the time period changes between epochs:

.. code-block:: python

    report.override_params(
        interval_from="2024-01-01",
        interval_to="2024-03-31",
    )


.. _latex-templates:

LaTeX report templates
-----------------------

The ``template_path`` directory passed to ``compile()`` must contain a root
``main.tex`` and any supporting files (``.tex``, ``.bib``, images).  All files
are copied into a ``pdf_report/`` subfolder inside the report root, then
``pdflatex`` is run on ``main.tex`` there.

Placeholders ``\detokenize{$<expr>$}`` are replaced before compilation.
``expr`` is a Python expression evaluated against two variable namespaces:
``ReportVars`` (period, QA4SM version, URL, …) and ``Run1ContentVars``,
``Run2ContentVars``, … (per-run dataset names, metrics, …).

``run.tex`` is a per-run template: it is copied into each run's subdirectory
and included via ``\import{./runN/}{run.tex}``, so relative paths to
QA4SM graphics resolve correctly.

Example ``main.tex``:

.. literalinclude:: ../tests/latex_templates/main.tex
   :language: latex

Example ``run.tex``:

.. literalinclude:: ../tests/latex_templates/run.tex
   :language: latex

For series reports that include metric tracking plots, add a ``tracking.tex``:

.. literalinclude:: ../tests/integration_tests/tracking.tex
   :language: latex


Creating a single report
------------------------

A report combines multiple validation runs (one per config template).
Place JSON config templates in a folder, then:

.. code-block:: python

    from qa4sm_autoreports.report import AutoReportCreator

    # 1. Set up from templates (creates local directory structure)
    report = AutoReportCreator.from_scratch(
        report_root="/results/my_report",
        templates_path="/configs/my_report_templates",
        connection=qa4sm,
    )

    # 2. Optionally override parameters (e.g. the validation period)
    report.override_params(
        interval_from="2024-01-01",
        interval_to="2024-03-31",
    )

    # 3. Start all runs on QA4SM
    report.start_all_runs()

    # 4. Check status
    print(report)  # shows each run with status and progress

    # 5. Once all runs are done, collect results and compile PDF
    if report.validations_complete():
        report.compile(template_path="/configs/my_latex_templates")

.. note::
   ``compile()`` calls ``collect_content()`` internally, which downloads
   results and collects variables into YAML files used to populate the
   LaTeX templates.

Resume an interrupted workflow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If runs are already triggered or results already downloaded, load the
existing local state instead of starting from scratch:

.. code-block:: python

    report = AutoReportCreator.from_results("/results/my_report",
                                            connection=qa4sm)


Managing a report series
------------------------

A *series* is a folder of reports sharing the same configuration but
covering different time periods (epochs).

.. code-block:: python

    from qa4sm_autoreports.series import AutoReportSeries

    series = AutoReportSeries("/results/my_series", connection=qa4sm)

    # Add a new report for the next period
    report = series.new_report(
        "2024-04-01_to_2024-06-30",
        config_template_path="/configs/my_report_templates",
        override_params={"interval_from": "2024-04-01",
                         "interval_to": "2024-06-30"},
    )

    # Check series status
    print(series)

    # Once all validations are done, compile
    if series["2024-04-01_to_2024-06-30"].validations_complete():
        series["2024-04-01_to_2024-06-30"].compile("/configs/my_latex_templates")


Tracking metrics over time
--------------------------

After multiple reports in a series are collected, track a metric across epochs:

.. code-block:: python

    series.track_metric(
        metric="urmsd_between_0-ISMN_and_1-C3S_combined",
        pretty_name="ubRMSD",
        unit="m³m⁻³",
        ref_epoch=-1,   # last epoch
        n_epochs=12,    # look back 12 epochs
        p_mask_var="p_R_between_0-ISMN_and_1-C3S_combined",  # optional p-masking
        path_out="/results/my_series/latest_report/tracking",
    )

This saves a ``.yml`` file with per-epoch statistics and a boxplot ``.png``
that can be embedded in the LaTeX template.


Report status codes
-------------------

``AutoReportCreator.status`` returns an integer:

========  ================  ==============================================
Code      Name              Meaning
========  ================  ==============================================
0         Staged            Local config created; runs not yet triggered.
1         Started           All runs triggered on QA4SM.
2         Processed         All runs completed on QA4SM.
3         Collected         Results downloaded; ``ReportVars.yml`` written.
4         Compiled          PDF exists in ``pdf_report/`` subfolder.
========  ================  ==============================================
