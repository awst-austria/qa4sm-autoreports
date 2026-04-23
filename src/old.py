def collect_config_content(self):
    return self.config.data


def collect_nc_content(self):
    ds = xr.open_dataset(self.local_dir / f"{self.remote_id}.nc")
    nc_attrs = ds.attrs
    return nc_attrs


def collect_csv_content(self, stats: list = None):
    lut = {
        "Pearson's r": "PEARSONR",
        "# observations": "NOBS",
        "Bias (difference of means)": "BIAS",
        "Unbiased root-mean-square deviation": "UBRMSD",
        "Spearman's ρ": "SPEARMANR",
        "Root-mean-square deviation": "RMSD",
        "Mean square error": "MSE",
        "Mean square error correlation": "MSECORR",
        "Mean square error bias": "MSEBIAS",
        "Mean square error variance": "MSEVAR",
        "Residual sum of squares": "RSS",
        "Validation errors": "ERRORS"
    }

    if stats is None:
        stats = ['Median', 'Mean', "IQ range"]

    df = pd.read_csv(self.local_dir / 'stats.csv', index_col=0)
    params = {}
    for stat_name in stats:
        for metric_name, table_name in lut.items():
            subdf = df.loc[:, stat_name]
            new_index = [i.split('  ')[0].strip()
                         for i in subdf.index.values]
            subdf.index = new_index
            prefix = f"{stat_name.upper().replace(' ', '')}"
            params[f"{prefix}_{table_name}"] = float(subdf[metric_name])

    return params


class ContentCollection:
    def __init__(self, local_dir, run_id=0):
        self.local_dir = Path(local_dir)
        self.run_id = run_id
        self.data = {}

    def collect_data_summary_table(self):
        """Collect relevant stats from the downloaded summary table """
        metrics_stats_table = {
            "Pearson's r": "pearsonr",
            "# observations": "nobs",
            "Bias (difference of means)": "bias",
            "Unbiased root-mean-square deviation": "ubrmsd",
            "Spearman's ρ": "spearmanr",
            "Root-mean-square deviation": "rmsd",
            "Mean square error": "mse",
            "Mean square correlation": "msecorr",
            "Mean square bias": "msebias",
            "Mean square variance": "msevar",
            "Residual sum of squares": "rss",
            "Validation errors": "errors"
        }

        df = pd.read_csv(self.local_dir / 'stats.csv', index_col=0)
        params = {}
        for metric in ['Median', 'Mean', "IQ range"]:
            for stat_name, table_name in metrics_stats_table.items():
                subdf = df.loc[:, metric]
                new_index = [i.split('  ')[0].strip() for i in subdf.index.values]
                subdf.index = new_index
                prefix = f"{metric.upper().replace(' ', '')}"
                params[f"{prefix}_{table_name}"] = float(subdf[stat_name])

        self.data['summary'] = params

        return params

    def collect_data_validation_config(self, candidate_id=15):
        """Collect data from validation configs """
        if not self.is_complete():
            raise ValueError("Run is not complete yet")

        params = dict(
        DATE_RUN = str(datetime.now().date()),
        RUN_URL = self.connection.session.api_url.replace(
            '/api/', f"/ui/validation-result/{self.remote_id}"),
        PERIOD_START = str(pd.to_datetime(self.config["interval_from"]).date()),
        PERIOD_END = str(pd.to_datetime(self.config["interval_to"]).date()),
        PERIOD_NDAYS = (pd.to_datetime(self.config["interval_to"]) -
                        pd.to_datetime(self.config["interval_from"])).days,
        TEMPWINDOWSIZE = self.config["temporal_matching"],
        ANOMABS = self.config["anomalies_method"],
        SCALINGMETHOD = self.config["scaling_method"],
        )

        if params["SCALINGMETHOD"] == "none":
            params["SCALINGMETHOD"] = "no scaling"
        if params["ANOMABS"] == "none":
            params["ANOMABS"] = "absolute"
        else:
            params["ANOMABS"] = "anomalies"

        params["SCALINGREF"] = "None"

        i = 0
        for dataset_config in self.config.data["dataset_configs"]:
            ds_id = dataset_config['dataset_id']
            if ds_id == candidate_id:
                prefix = f"CAN"
            else:
                i+=1
                prefix = f"OTHER{i}"
            prettyname = self.connection.dataset_info(ds_id)['pretty_name']
            params[f'{prefix}NAME'] = prettyname
            prettyvers = self.connection.version_info(dataset_config['version_id'])['pretty_name']
            params[f'{prefix}VERS'] = prettyvers
            prettyvar = self.connection.variable_info(dataset_config['variable_id'])['pretty_name']
            params[f'{prefix}VAR'] = prettyvar

            filters = []
            for filter_id in dataset_config['basic_filters']:
                d = self.connection.filter_info(filter_id)["description"]
                filters.append(d)
            for pfilter in dataset_config['parametrised_filters']:
                # todo: should probably include the value
                d = self.connection.filter_info(pfilter['id'])["description"]
                filters.append(d)
            params[f'{prefix}FILTERS'] = filters

            if dataset_config['is_spatial_reference']:
                params["SPATIALREF"] = f"{prettyname} ({prettyvers})"
            if dataset_config['is_temporal_reference']:
                params["TEMPORALREF"] = f"{prettyname} ({prettyvers})"
            if dataset_config['is_scaling_reference']:
                params["SCALINGREF"] = f"{prettyname} ({prettyvers})"

        return params

    def collect_from_netcdf(self):
        """
        Download the results from the completed run.
        """
        os.makedirs(str(self.local_dir / "report"), exist_ok=True)

        self.collect_report_graphics(run_id)

        plot_extent_map(
            self.config.data["min_lat"],
            self.config.data["min_lon"],
            self.config.data["max_lat"],
            self.config.data["max_lon"],
            self.local_dir / "report" / f"validation_extent_run_{run_id}.png"
        )

        params1 = self.collect_report_stats_from_results()
        params2 = self.collect_report_stats_from_table()
        params3 = self.collect_report_stats_from_config(15)

        params = {**params1, **params2, **params3}
        params["VALIDATIONRUNID"] = run_id
        with open(self.local_dir / "report" / ymlname, 'w') as f:
            yaml.dump(params, f, default_flow_style=False)

        self.connection.download_results(self.remote_id, self.local_dir)

    def collect_report_stats_from_results(self):
        ds = xr.open_dataset(self.local_dir / f"{self.remote_id}.nc")
        status_var = None
        for v in ds.data_vars:
            if v.startswith('status_'):
                status_var = v
                break
        status = ds[status_var].isel(tsw=0).values
        params = dict(
            GPITOTAL = len(status),
            NGPISUCCESS = len(status[status == 0]),
        )
        params["ERRORRATE"] = (1 - (params['NGPISUCCESS'] / params['GPITOTAL'])) * 100

        return params

    def collect_report_graphics(self, run_id):
        fname = glob.glob(str(self.local_dir / "graphics" / "*_status.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"map_status_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_R.png"))[1]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"map_pearsonr_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_urmsd.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"map_urmsd_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_BIAS.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"map_bias_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_n_obs.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"map_nobs_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_boxplot_R.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"box_pearsonr_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_boxplot_urmsd.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"box_urmsd_run_{run_id}.png")
        fname = glob.glob(str(self.local_dir / "graphics" / "*_boxplot_BIAS.png"))[0]
        shutil.copy(self.local_dir / fname, self.local_dir / "report" / f"box_bias_run_{run_id}.png")
