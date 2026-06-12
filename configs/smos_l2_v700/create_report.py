import os.path
import shutil

from datetime import date
from dateutil.relativedelta import relativedelta
import calendar
from pathlib import Path
import time

from qa4sm_autoreports.series import AutoReportSeries
from qa4sm_autoreports import Connection


def period_for_report(ref_date: str, period_months: int = 3) -> tuple[str, str]:
    """
    Take the reference date and compute the interval for the validation
    report, ie. the start_date is the beginning of the month 3 (default)
    months before the reference date. And the end is the end of the month
    before the reference date. e.g. 2025-02-07 -> (2024-11-01), (2025-01-31)

    Parameters
    ----------
    ref_date : str
        Reference date (ISO format: YYYY-MM-DD) from which the period is
        subtracted.
    period_months : int, optional
        Number of months to go back from the reference date to determine
        the start of the interval. Defaults to 3.

    Returns
    -------
    interval_from : str
        Start date of the chosen period interval (first day of the month
        ``period_months`` before ``ref_date``), in ISO format YYYY-MM-DD.
    interval_to : str
        End date of the chosen period interval (last day of the month
        preceding ``ref_date``), in ISO format YYYY-MM-DD.

    Examples
    --------
    >>> period_for_report("2025-02-07")
    ('2024-11-01', '2025-01-31')
    >>> period_for_report("2025-03-15")
    ('2024-12-01', '2025-02-28')
    >>> period_for_report("2024-03-15")  # leap year
    ('2023-12-01', '2024-02-29')
    >>> period_for_report("2025-02-07", period_months=6)
    ('2024-08-01', '2025-01-31')
    """
    ref = date.fromisoformat(ref_date)

    # Start: first day of the month `period_months` before ref_date
    start = ref.replace(day=1) - relativedelta(months=period_months)

    # End: last day of the month before ref_date
    end_month = ref.replace(day=1) - relativedelta(months=1)
    end = end_month.replace(day=calendar.monthrange(end_month.year, end_month.month)[1])

    return start.isoformat(), end.isoformat()

def is_staging_required(series: AutoReportSeries,
                        report_name: str) -> bool:
    # Check if report was not already staged before
    dir_exists = (series.series_root / report_name).exists()
    report_in_series = report_name in series.reports.keys()

    return (not dir_exists) and (not report_in_series)

def sense_status_processed(series: AutoReportSeries,
                           report_name: str) -> int:
    """
    Verify if the report status is "processed"
    """
    # Check the processing status of report in series
    # series[report_name]._STATUS_LUT
    return series[report_name].status == 2


# Airflow input
report_date = date.fromisoformat('2025-05-01')

# DAG vars
report_collection = Path("/data-read/USERS/wpreimes/qa4sm_autoreports/pdf_reports/SMOS_L2_v700")
series_root = Path("/data-read/USERS/wpreimes/qa4sm_autoreports/results/SMOS_L2_v700")
config_path = "/home/wpreimes/shares/home/code/qa4sm-autoreports/configs/smos_l2_v700/report_config_templates"
latex_templ_path = "/home/wpreimes/shares/home/code/qa4sm-autoreports/configs/smos_l2_v700/report_latex_templates/src"
connection = Connection("test.qa4sm.eu")

report_date = report_date.replace(day=1)

os.makedirs(report_collection, exist_ok=True)
os.makedirs(series_root, exist_ok=True)

# Derive the 3-month period for the report based on the ref date from airflow
interval_from, interval_to = period_for_report(str(report_date), period_months=3)

# Name for the report for this ref month
report_name = f"{interval_from}_to_{interval_to}"

# Collect existing reports, potentially staged current report
series = AutoReportSeries(series_root=series_root, connection=connection)


if is_staging_required(series, report_name):  # stage a new report
    report = series.new_report(
        report_name, config_path,
        # make report for the required period
        override_params=dict(
            interval_from=interval_from,
            interval_to=interval_to
        ),
        instance="test.qa4sm.eu",
    )
else:  # report exists, but it might not be finished yet
    report = series[report_name]  # use previously staged report


if report.status == 0 :  # staged -> trigger
    print("Triggering runs...")
    report.start_all_runs()
    time.sleep(2)
    print(f"Report triggered, status: {report.status}")
    print(f"Meaning: {report._STATUS_LUT[report.status]}")
    print("Waiting for runs to finish, this may take a few hours...")


#### Sensor
if sense_status_processed(series, report_name):

    series[report_name].collect_content()

    series.track_metric(metric='urmsd_between_0-SMOS_L2_and_1-C3S_combined',
                        unit='m³m⁻³', ref_epoch=report_name, n_epochs=12,
                        path_out=series[report_name].report_root)

    series.track_metric(metric='urmsd_between_0-SMOS_L2_and_1-ERA5_LAND',
                        unit='m³m⁻³', ref_epoch=report_name, n_epochs=12,
                        path_out=series[report_name].report_root)

    series.track_metric(metric='R_between_0-SMOS_L2_and_1-C3S_combined',
                        pretty_name='R', unit='-', ref_epoch=report_name,
                        n_epochs=12,
                        p_mask_var='p_R_between_0-SMOS_L2_and_1-C3S_combined',
                        path_out=series[report_name].report_root)

    series.track_metric(metric='R_between_0-SMOS_L2_and_1-ERA5_LAND',
                        pretty_name='R', unit='-', ref_epoch=report_name,
                        n_epochs=12,
                        p_mask_var='p_R_between_0-SMOS_L2_and_1-ERA5_LAND',
                        path_out=series[report_name].report_root)

    series[report_name].compile(template_path=latex_templ_path,
                                tex_ignore=None)

    shutil.copy(series[report_name].report_root / 'pdf_report' / 'main.pdf',
                report_collection / f"{report_name}.pdf")




