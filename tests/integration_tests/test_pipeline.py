import shutil
import tempfile
import os
import time
from pathlib import Path
from glob import glob
import unittest
from tempfile import mkdtemp
import pytest

from qa4sm_api.client_api import Connection, ValidationConfiguration
from qa4sm_autoreports.series import AutoReportSeries

"""
Integration test for the full report generation pipeline.

This test triggers validation runs for multiple epochs, downloads results,
and generates reports from them.
"""

QA4SM = Connection("test.qa4sm.eu")

@pytest.fixture(scope="module")
def qa4sm_connection():
    """Create QA4SM connection for all tests in this module."""
    return QA4SM


@pytest.fixture(scope="module")
def test_series_root(tmp_path_factory) -> Path:
    """Create temporary directory for test series output."""
    return Path(tmp_path_factory.mktemp("test_series"))


@pytest.fixture(scope="module")
def config_templ():
    """Path to report config templates."""
    return Path(__file__).parent / "test_series" / "report_config_templates"


@pytest.fixture(scope="module")
def series(qa4sm_connection, test_series_root):
    """Create AutoReportSeries instance."""
    return AutoReportSeries(series_root=test_series_root,
                            connection=qa4sm_connection)


@pytest.fixture(scope="module", params=[
    {'interval_from': '2020-03-01', 'interval_to': '2020-05-31'},
    {'interval_from': '2020-04-01', 'interval_to': '2020-06-30'}
])
def report_configs(request):
    """Parameterize report configurations."""
    return request.param


@pytest.mark.integration
class TestFullReport(unittest.TestCase):

    STORAGE_PATH = Path(tempfile.gettempdir()) / "integration_test_report"

    @classmethod
    def setUpClass(cls):
        cls.qa4sm_connection = QA4SM
        cls.test_series_root = Path(mkdtemp()) / "test_full_report"
        cls.test_series_root.mkdir(parents=True, exist_ok=True)
        cls.config_templ = Path(__file__).parent.parent / "testdata" / "report_config_templates"

        # Some templates are different here to include tracking
        cls.latex_templ = Path(mkdtemp()) / "latex_templates"
        os.makedirs(cls.latex_templ, exist_ok=True)
        # from other tests
        for fname in ["references.bib", "run.tex", "something.tex"]:
            shutil.copy(Path(__file__).parent.parent / "latex_templates" / fname,
                        cls.latex_templ / fname)
        # this test only
        shutil.copy(Path(__file__).parent / "main.tex",
                    cls.latex_templ / "main.tex")
        shutil.copy(Path(__file__).parent / "tracking.tex",
                    cls.latex_templ / "tracking.tex")

        cls.series = AutoReportSeries(series_root=cls.test_series_root,
                                      connection=cls.qa4sm_connection)
        cls.report_configs = [
            {'interval_from': '2020-03-01', 'interval_to': '2020-05-31'},
            {'interval_from': '2020-04-01', 'interval_to': '2020-06-30'}
        ]

    @classmethod
    def tearDownClass(cls):
        cls._run_cleanup()

    @classmethod
    def _run_cleanup(cls):
        # Delete the test reports from the server
        for name in list(cls.series.reports.keys()):
            try:
                cls.series.delete_report(name, remote=True)
            except KeyError:
                pass

    def test_full_report(self):
        report_path = None
        for report_configs in self.report_configs:
            interval_from = report_configs['interval_from']
            interval_to = report_configs['interval_to']
            report_name = f"epoch_{interval_from}_to_{interval_to}"

            override_params = {
                'interval_from': interval_from,
                'interval_to': interval_to
            }

            if not os.path.exists(self.series.series_root / report_name):
                print("Report not staged yet: ", report_name)
                report = self.series.new_report(
                    report_name, self.config_templ,
                    override_params=override_params,
                    instance=QA4SM.session.instance,
                )
            else:
                report = self.series[report_name]

            for run in list(report.runs.values()):
                assert run.config['interval_from'] == interval_from
                assert run.config['interval_to'] == interval_to

            assert report_name in self.series.reports.keys(), "Report not found"

            status_str = report._STATUS_LUT[report.status].lower()
            if status_str == 'staged':
                print("Staged. Triggering...")
                report.start_all_runs()

                t = 0
                while self.series[report_name]._STATUS_LUT[self.series[report_name].status].lower() != 'processed':
                    print(f"{report_name} ... still processing...")
                    time.sleep(2)
                    t += 1
                print(f"{report_name} Done after {t} seconds.")

            assert self.series[report_name]._STATUS_LUT[self.series[report_name].status].lower() in ['processed', 'collected']

            run_id = report[0].remote_id

            if self.series[report_name]._STATUS_LUT[self.series[report_name].status].lower() != "collected":
                self.series[report_name].collect_content()

            assert self.series[report_name]._STATUS_LUT[self.series[report_name].status].lower() == 'collected'

            report_path = self.series.series_root / report_name
            run_path = report_path / "run1"

            assert report_path.is_dir()
            assert run_path.is_dir()
            assert (report_path / "val_run_list.csv").is_file()
            assert (report_path / "common_extent.png").is_file()
            assert (report_path / "ReportVars.yml").is_file()

            assert len(glob(str(run_path / "qa4sm_graphics" / "*"))) > 0
            assert len(glob(str(run_path / "latex" / "*"))) > 0

            assert (run_path / f"{run_id}.nc").is_file()
            assert (run_path / f"response-{run_id}.csv").is_file()
            assert (run_path / "extent.png").is_file()
            assert (run_path / "summary_stats.csv").is_file()
            assert (run_path / f"config-{QA4SM.session.instance}.json").is_file()
            assert (run_path / "ContentVars.yml").is_file()

            config = ValidationConfiguration.from_file(
                run_path / f"config-{QA4SM.session.instance}.json"
            )

            assert config.data['interval_from'] == override_params['interval_from']
            assert config.data['interval_to'] == override_params['interval_to']

            assert report[0].config == config

            self.series.track_metric(metric='urmsd_between_0-ISMN_and_1-C3S_combined',
                                     unit='m³m⁻³', ref_epoch=-1, n_epochs=10,
                                     path_out=report_path)
            assert (report_path / "tracking_ubRMSD.png").is_file()

            self.series.track_metric(metric='R_between_0-ISMN_and_1-C3S_combined',
                                     pretty_name='R', unit='-', ref_epoch=-1, n_epochs=10,
                                     p_mask_var='p_R_between_0-ISMN_and_1-C3S_combined',
                                     path_out=report_path)
            assert (report_path / "tracking_R.png").is_file()

            self.series[report_name].compile(template_path=self.latex_templ,
                                             tex_ignore=None)
            assert (run_path / "run.tex").is_file()

            assert os.path.exists(report_path / 'pdf_report' / 'main.pdf')
            assert os.path.exists(report_path / 'pdf_report' / 'main.log')
            assert os.path.exists(report_path / 'pdf_report' / 'main.tex')
            assert os.path.exists(report_path / 'pdf_report' / 'main.bbl')
            assert os.path.exists(report_path / 'pdf_report' / 'something.tex')
            assert os.path.exists(report_path / 'pdf_report' / 'tracking.tex')
            assert os.path.exists(report_path / 'pdf_report' / 'references.bib')

        ##  copy report to storage
        if os.path.exists(self.STORAGE_PATH):
            shutil.rmtree(self.STORAGE_PATH)
        shutil.copytree(report_path, self.STORAGE_PATH)
        print(f"Report stored in {self.STORAGE_PATH}")

        # test deleting / clean up
        assert len(self.series) == 2
        self.series.delete_report("epoch_2020-03-01_to_2020-05-31")
        assert len(self.series) == 1
        self.series.delete_report("epoch_2020-04-01_to_2020-06-30")
        assert len(self.series) == 0

