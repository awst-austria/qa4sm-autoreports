import os
from tempfile import TemporaryDirectory
from pathlib import Path

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.run import ValidationRun
from qa4sm_autoreports.report import AutoReportCreator


def test_compile_report_from_template():
    """
    Collect results from 2 remote validation runs and compiles a PDF report
    based on the SMOS L2 template.
    """
    QA4SM_IP_OR_URL = "test.qa4sm.eu"
    QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
    report_name = "20220701_20220930"

    qa4sm = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)
    with TemporaryDirectory() as series_root:
        series_root = Path(series_root)
        name1 = "01-SmosL2-vs-C3sComb-abs"
        id1 = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
        path1 = series_root / "01-SmosL2-vs-C3sComb-abs"

        name2 = "02-SmosL2-vs-Era5Land-abs"
        id2 = "e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e"
        path2 = series_root / "02-SmosL2-vs-Era5Land-abs"

        run1 = ValidationRun.from_remote(path1, connection=qa4sm,
                    remote_id="6eb61199-59b8-4ecc-8e3c-7b1139df4a05")

        run2 = ValidationRun.from_remote(path2, connection=qa4sm,
                    remote_id="e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e")

        s, p = run1.status()
        t = run1.timing()

        report = AutoReportCreator(
            runs=[run1, run2],
            series_root=series_root,
        )

        assert report.validations_complete()

        # Download, config, results, compile contents, make plots
        # report.collect_content()
        report.compile(
            from_scratch=True,
            template_path= os.path.join(os.path.dirname(__file__), "template"),
        )


if __name__ == '__main__':
    test_compile_report_from_template()