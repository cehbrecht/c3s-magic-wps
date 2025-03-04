import logging
import os

from pywps import FORMATS, ComplexInput, ComplexOutput, Format, LiteralInput, LiteralOutput, Process
from pywps.app.Common import Metadata
from pywps.response.status import WPS_STATUS

from .. import runner, util
from .utils import default_outputs, model_experiment_ensemble, outputs_from_plot_names, year_ranges

LOGGER = logging.getLogger("PYWPS")


class Blocking(Process):
    def __init__(self):
        self.variables = ['zg']
        self.frequency = 'day'
        inputs = [
            *model_experiment_ensemble(model='ACCESS1-0',
                                       experiment='historical',
                                       ensemble='r1i1p1',
                                       max_occurs=1,
                                       required_variables=self.variables,
                                       required_frequency=self.frequency),
            *year_ranges((1980, 1989)),
            LiteralInput('ref_dataset',
                         'Reference Dataset',
                         abstract='Choose a reference dataset like ERA-Interim.',
                         data_type='string',
                         allowed_values=['ERA-Interim'],
                         default='ERA-Interim',
                         min_occurs=1,
                         max_occurs=1),
            LiteralInput('season',
                         'Season',
                         abstract='Choose a season like DJF.',
                         data_type='string',
                         allowed_values=['DJF', 'MAM', 'JJA', 'SON', 'ALL'],
                         default='DJF'),
        ]
        self.plotlist = [
            ('TM90', [Format('image/png')]),
            ('NumberEvents', [Format('image/png')]),
            ('DurationEvents', [Format('image/png')]),
            ('LongBlockEvents', [Format('image/png')]),
            ('BlockEvents', [Format('image/png')]),
            ('ACN', [Format('image/png')]),
            ('CN', [Format('image/png')]),
            ('BI', [Format('image/png')]),
            ('MGI', [Format('image/png')]),
            ('Z500', [Format('image/png')]),
            ('ExtraBlock', [Format('image/png')]),
            ('InstBlock', [Format('image/png')]),
        ]
        outputs = [
            *outputs_from_plot_names(self.plotlist),
            ComplexOutput('data_full',
                          'Full Blocking Data',
                          abstract='Generated output data of ESMValTool processing.',
                          as_reference=True,
                          supported_formats=[FORMATS.NETCDF]),
            ComplexOutput('data_clim',
                          'Clim Blocking Data',
                          abstract='Generated output data of ESMValTool processing.',
                          as_reference=True,
                          supported_formats=[FORMATS.NETCDF]),
            ComplexOutput('archive',
                          'Archive',
                          abstract='The complete output of the ESMValTool processing as an zip archive.',
                          as_reference=True,
                          supported_formats=[Format('application/zip')]),
            *default_outputs(),
        ]

        super(Blocking, self).__init__(
            self._handler,
            identifier="blocking",
            title="Blocking metrics and indices",
            version=runner.VERSION,
            abstract="Calculate Blocking metrics that shows the mid-latitude 1D and 2D blocking indices.",
            metadata=[
                Metadata('ESMValTool', 'http://www.esmvaltool.org/'),
                Metadata(
                    'Documentation',
                    'https://esmvaltool.readthedocs.io/en/version2_development/recipes/recipe_miles.html',
                    role=util.WPS_ROLE_DOC,
                ),
                Metadata('Estimated Calculation Time', '2 minutes'),
            ],
            inputs=inputs,
            outputs=outputs,
            status_supported=True,
            store_supported=True)

    def _handler(self, request, response):
        response.update_status("starting ...", 0)

        # build esgf search constraints
        constraints = dict(
            model=request.inputs['model'][0].data,
            experiment=request.inputs['experiment'][0].data,
            ensemble=request.inputs['ensemble'][0].data,
        )

        options = dict(season=request.inputs['season'][0].data)

        # generate recipe
        response.update_status("generate recipe ...", 10)
        start_year = request.inputs['start_year'][0].data
        end_year = request.inputs['end_year'][0].data
        recipe_file, config_file = runner.generate_recipe(
            workdir=self.workdir,
            diag='miles_blocking',
            constraints=constraints,
            options=options,
            start_year=start_year,
            end_year=end_year,
            output_format='png',
        )

        # recipe output
        response.outputs['recipe'].output_format = FORMATS.TEXT
        response.outputs['recipe'].file = recipe_file

        # run diag
        response.update_status("running diagnostic ...", 20)
        result = runner.run(recipe_file, config_file)

        response.outputs['success'].data = result['success']

        # log output
        response.outputs['log'].output_format = FORMATS.TEXT
        response.outputs['log'].file = result['logfile']

        # debug log output
        response.outputs['debug_log'].output_format = FORMATS.TEXT
        response.outputs['debug_log'].file = result['debug_logfile']

        if result['success']:
            try:
                subdir = os.path.join(constraints['model'], constraints['experiment'], constraints['ensemble'],
                                      "{}-{}".format(start_year, end_year), options['season'], 'Block')

                self.get_outputs(result, subdir, response)
            except Exception as e:
                response.update_status("exception occured: " + str(e), 85)
        else:
            LOGGER.exception('esmvaltool failed!')
            response.update_status("exception occured: " + result['exception'], 85)

        response.update_status("creating archive of diagnostic result ...", 90)

        response.outputs['archive'].output_format = Format('application/zip')
        response.outputs['archive'].file = runner.compress_output(
            os.path.join(self.workdir, 'output'),
            os.path.join(self.workdir, 'blocking_result.zip'))

        response.update_status("done.", 100)
        return response

    def get_outputs(self, result, subdir, response):
        # result plot
        response.update_status("collecting output ...", 80)
        for plot, _ in self.plotlist:
            key = '{}_plot'.format(plot.lower())
            response.outputs[key].output_format = Format('application/png')
            response.outputs[key].file = runner.get_output(result['plot_dir'],
                                                           path_filter=os.path.join(
                                                               'miles_diagnostics', 'miles_block', subdir),
                                                           name_filter="{}*".format(plot),
                                                           output_format="png")

        response.outputs['data_full'].output_format = FORMATS.NETCDF
        response.outputs['data_full'].file = runner.get_output(result['work_dir'],
                                                               path_filter=os.path.join(
                                                                   'miles_diagnostics', 'miles_block', subdir),
                                                               name_filter="BlockFull*",
                                                               output_format="nc")

        response.outputs['data_clim'].output_format = FORMATS.NETCDF
        response.outputs['data_clim'].file = runner.get_output(result['work_dir'],
                                                               path_filter=os.path.join(
                                                                   'miles_diagnostics', 'miles_block', subdir),
                                                               name_filter="BlockClim*",
                                                               output_format="nc")
