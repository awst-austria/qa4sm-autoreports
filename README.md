# qa4sm-autoreports

[![CI](https://img.shields.io/badge/CI-Github%20Actions-success?logo=github-actions)](https://github.com/awst-austria/qa4sm-autoreports/actions)
[![PyPI](https://img.shields.io/pypi/v/qa4sm-autoreports)](https://pypi.org/project/qa4sm-autoreports/)
[![Coverage Status](https://coveralls.io/repos/github/awst-austria/qa4sm-autoreports/badge.svg?branch=main)](https://coveralls.io/github/awst-austria/qa4sm-autoreports?branch=main)
[![Documentation](https://img.shields.io/badge/Docs-GitHub%20Pages-blue?logo=sphinx)](https://awst-austria.github.io/qa4sm-autoreports)

<img src="https://qa4sm.eu/static/images/logo/qa4sm_logo_long.webp" width="25%" alt="QA4SM Logo">

This packages contains the python code to programmatically create validation
reports using QA4SM (automated validation reports).

This is a client application written in python that uses the
QA4SM public API (access via the python API wrapper package)

## Installation

In order to compile latex to pdf reports, you need to install texlive from
https://tug.org/texlive/. This should enable the command line program `pdflatex`
which is called from some python functions in this package.

```bash
sudo apt install texlive-full
```

Afterwards, you can install the package. This will also install the
[qa4sm-api](https://github.com/awst-austria/qa4sm-api)
package (which is the most important dependency.)

```bash
pip install qa4sm-autoreports
```

Then, you ideally set up the `.qa4smapirc` file as described [here](https://github.com/awst-austria/qa4sm-api#authentication)
to enable access to different QA4SM instances via the API.

Alternatively, you can also set the `QA4SM_INSTANCE` and `QA4SM_TOKEN` environment
variables, or pass the token and instance in your application code.

## Development and testing

To install the package from source, with optional dependencies for testing (as
required for developing the code), run

```bash
pip install -e .[testing]
```

Afterwards you can run pytest (integration tests are excluded)

```bash
pytest
```

To run the integration tests, which sets up a new validation report series
and actually trigger validation runs on the test instance (which will take a 
few minutes), run

```bash
pytest -m "integration"
```

## Main components 

### qa4sm_autoreports.run.ValidationRun

A class that sets up a local validation run directory, with a predefined validation
configuration or an existing online validation run. 
Afterwards, it can be used to trigger a validation run online,
check the run status of the run, or synchronize the validation results to the local
folder.

### qa4sm_autoreports.report.AutoReportCreator

A validation report combines **multiple validation runs**. 
It is a setup of multiple validation configurations (i.e., multiple 
runs required for a report to trigger online), download all results and 
collect various variables from different sources (processing date,
status, errors, stats, etc.).

This also contains a method to compile a PDF using the downloaded and collected
results for this report and a set up predefined latex templates. The latex template is filled with the data
from the report, and the pdf is exported.

### qa4sm_autoreports.series.AutoReportSeries

A validation report series combines **multiple validation reports**. It contains
methods to track metrics across the report series and add/delete reports to/from
the series.


