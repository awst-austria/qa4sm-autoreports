import os
from qa4sm_autoreports.run import ValidationRun, ValidationConfiguration
from qa4sm_api.client_api import Connection
from qa4sm_autoreports.report import AutoReportCreator

if __name__ == '__main__':
    # Override parameters, change each run
    override_kwargs = dict(
        interval_from = "2024-07-01",
        interval_to = "2024-09-30"
    )
    series_root = "/data-read/USERS/wpreimes/qa4sm_smos_report"

    name1 = "01-SmosL2-vs-C3sComb-abs"
    name2 = "02-SmosL2-vs-Era5Land-abs"
    config1 = ValidationConfiguration.from_file(f"./configs/smos_l2_v700/{name1}.json")
    config2 = ValidationConfiguration.from_file(f"./configs/smos_l2_v700/{name2}.json")

    QA4SM_IP_OR_URL = "test.qa4sm.eu"
    QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
    qa4sm = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)

    run1 = ValidationRun(ValidationConfiguration.from_file(config1),
        os.path.join(series_root, "20220701_20220930", "01-SmosL2-vs-C3sComb-abs"),
        connection=qa4sm)

    run2 = ValidationRun(ValidationConfiguration.from_file(config2),
        os.path.join(series_root, "20220701_20220930", "02-SmosL2-vs-Era5Land-abs"),
        connection=qa4sm)


    report = AutoReportCreator([run1, run2],
                               series_root=series_root,
                               name="20220701_20220930")

    override_kwargs["min_lat"] = -90.0
    override_kwargs["min_lon"] = -180.0
    override_kwargs["max_lat"] = 90.0
    override_kwargs["max_lon"] = 180.0

    report.override_params(**override_kwargs)
    report[0].override_params(**override_kwargs)
    report[1].override_params(**override_kwargs)

    assert report.verify_dataset_availability()

    report.start_all_runs()
