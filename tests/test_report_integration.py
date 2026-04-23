import os
import shutil
import time
from pathlib import Path
from glob import glob

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.series import AutoReportSeries
from qa4sm_api.client_api import ValidationConfiguration

"""
This integration test takes a validation configuration, and triggers the
validation runs for multiple epochs and downloads the results. 

It then generates a report from
"""
QA4SM_IP_OR_URL = "test.qa4sm.eu"
QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"

TEST_ROOT_PATH = Path(os.path.dirname(os.path.abspath(__file__)))

config_templ = TEST_ROOT_PATH / "test_series" / "report_config_templates"
out_path = TEST_ROOT_PATH / "testdata" / "test_series"
shutil.rmtree(out_path, ignore_errors=True)
os.makedirs(out_path, exist_ok=False)

# Create a new Validation Report Series Object that contains the individual reports
series = AutoReportSeries(series_root=out_path)

reports = {
    'epoch1': {'interval_from': '2020-03-01', 'interval_to': '2020-05-31'},
    'epoch2': {'interval_from': '2020-04-01', 'interval_to': '2020-06-30'},
}

for report_name, override_params in reports.items():
    # Add a new report to the series, for the chosen interval
    report = series.new_report(report_name, config_templ,
                      override_params=override_params,
                      instance=QA4SM_IP_OR_URL)

    # start validation run for this report online
    report.start_all_runs()

    #wait until the validation run is done
    t = 0
    while series[report_name].status.lower() != 'processed':
        print(series[report_name].status.lower())
        time.sleep(2)
        t += 1
        print(t)

    print(report_name, f"Done after {t} seconds.")

    assert series[report_name].status.lower() == 'processed'

    run_id = series[0][0].remote_id

    # collect the results of the validation run into the local folder
    series[report_name].collect_content()
    assert series[report_name].status.lower() == 'collected'

    assert os.path.isdir(out_path / report_name)
    assert os.path.isdir(out_path / report_name / "run1 - ismn_c3s")
    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / "val_run_list.csv"))
    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / "common_extent.png"))
    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / "ReportVars.yml"))

    assert len(glob(str(out_path / report_name / "run1 - ismn_c3s" / "qa4sm_graphics" / "*"))) > 0
    assert len(glob(str(out_path / report_name / "run1 - ismn_c3s" / "latex" / "*"))) > 0

    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / f"{run_id}.nc"))
    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / "extent.png"))
    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / "summary_stats.png"))
    assert os.path.isfile(str(out_path / report_name / "run1 - ismn_c3s" / f"config-{QA4SM_IP_OR_URL}.json"))

    config = ValidationConfiguration.from_file(out_path / report_name / "run1 - ismn_c3s" / "ContentVars.yml")
    assert config.data["remote_id"] == run_id



# Make the across-series plots
#series.metric_tracking()


