import os

from qa4sm_autoreports.run import ValidationRun
from qa4sm_api.client_api import Connection
from qa4sm_autoreports.report import AutoReportCreator

QA4SM_IP_OR_URL = "test.qa4sm.eu"
QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
qa4sm = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)

series_root = "/data-read/USERS/wpreimes/qa4sm_smos_report"
report_name = "20220701_20220930"

name1 = "01-SmosL2-vs-C3sComb-abs"
id1 = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"

name2 = "02-SmosL2-vs-Era5Land-abs"
id2 = "e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e"


run1 = ValidationRun.from_remote(
    os.path.join(series_root, report_name, name1),
    connection=qa4sm, remote_id=id1)

run2 = ValidationRun.from_remote(
    os.path.join(series_root, report_name, name2),
    connection=qa4sm, remote_id=id2)

s, p = run1.status()
t = run1.timing()

report = AutoReportCreator(
    runs=[run1, run2],
    series_root=series_root,
)

assert report.validations_complete()

# Download, config, results, compile contents, make plots
#report.collect_content()
report.compile(from_scratch=False,
               template_path="/src/qa4sm_autoreports/pipelines/configs/smos_l2_v700/latex_template",
               )


