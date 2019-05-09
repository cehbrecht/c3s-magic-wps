import logging
import os

from pywps import FORMATS, ComplexInput, ComplexOutput, Format, LiteralInput, LiteralOutput, Process
from pywps.app.Common import Metadata
from pywps.response.status import WPS_STATUS

from .utils import default_outputs, model_experiment_ensemble, outputs_from_plot_names

from .. import runner, util

LOGGER = logging.getLogger("PYWPS")


class WeatherRegimes(Process):
    def __init__(self):
        inputs = [
            *model_experiment_ensemble(start_end_year=(1850, 2005), start_end_defaults=(1980, 1989)),
            LiteralInput('ref_model',
                         'Reference Model',
                         abstract='Choose a reference model like ERA-Interim.',
                         data_type='string',
                         allowed_values=['ERA-Interim'],
                         default='ERA-Interim',
                         min_occurs=1,
                         max_occurs=1),
            # Removed on request of Jost
            # LiteralInput('season', 'Season',
            #              abstract='Choose a season like DJF.',
            #              data_type='string',
            #              allowed_values=['DJF'],
            #              default='DJF'),
            # LiteralInput('nclusters', 'nclusters',
            #              abstract='Choose a number of clusters.',
            #              data_type='string',
            #              allowed_values=['4'],
            #              default='4'),
        ]
        self.plotlist = [("Regime{}".format(i), [Format('image/png')]) for i in range(1, 5)]
        outputs = [
            *outputs_from_plot_names(self.plotlist),
            ComplexOutput('data',
                          'Regime Data',
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

        super(WeatherRegimes, self).__init__(
            self._handler,
            identifier="weather_regimes",
            title="Weather regimes",
            version=runner.VERSION,
            abstract="Diagnostic providing North-Atlantic Weather Regimes",
            metadata=[
                Metadata('ESMValTool', 'http://www.esmvaltool.org/'),
                Metadata('Documentation',
                         'https://esmvaltool.readthedocs.io/en/version2_development/recipes/recipe_miles.html',
                         role=util.WPS_ROLE_DOC),
                Metadata('Media', util.diagdata_url() + '/pydemo/pydemo_thumbnail.png', role=util.WPS_ROLE_MEDIA),
            ],
            inputs=inputs,
            outputs=outputs,
            status_supported=True,
            store_supported=True)

    def _handler(self, request, response):
        response.update_status("starting ...", 0)
        workdir = self.workdir

        # build esgf search constraints
        constraints = dict(
            model=request.inputs['model'][0].data,
            experiment=request.inputs['experiment'][0].data,
            ensemble=request.inputs['ensemble'][0].data,
        )

        # Only DJF and 4 clusters is supported currently
        options = dict(
            season='DJF',  # request.inputs['season'][0].data,
            nclusters=4  # int(request.inputs['nclusters'][0].data)
        )

        # generate recipe
        response.update_status("generate recipe ...", 10)
        start_year = request.inputs['start_year'][0].data
        end_year = request.inputs['end_year'][0].data
        recipe_file, config_file = runner.generate_recipe(
            workdir=workdir,
            diag='miles_regimes',
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
                                      "{}-{}".format(start_year, end_year), options['season'], 'Regimes')
                self.get_outputs(result, subdir, response)
            except Exception as e:
                response.update_status("exception occured: " + str(e), 85)
        else:
            LOGGER.exception('esmvaltool failed!')
            response.update_status("exception occured: " + result['exception'], 85)

        response.update_status("creating archive of diagnostic result ...", 90)

        response.outputs['archive'].output_format = Format('application/zip')
        response.outputs['archive'].file = runner.compress_output(os.path.join(workdir, 'output'),
                                                                  'weather_regimes_result.zip')

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
                                                               'miles_diagnostics', 'miles_regimes', subdir),
                                                           name_filter="{}_*".format(plot),
                                                           output_format="png")

        response.outputs['data'].output_format = FORMATS.NETCDF
        response.outputs['data'].file = runner.get_output(result['work_dir'],
                                                          path_filter=os.path.join('miles_diagnostics',
                                                                                   'miles_regimes', subdir),
                                                          name_filter="RegimesPattern*",
                                                          output_format="nc")
