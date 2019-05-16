import logging
import os

from pywps import FORMATS, ComplexInput, ComplexOutput, Format, LiteralInput, LiteralOutput, Process
from pywps.inout.literaltypes import make_allowedvalues
from pywps.app.Common import Metadata
from pywps.response.status import WPS_STATUS

from .. import runner, util
from .utils import default_outputs, model_experiment_ensemble, outputs_from_plot_names, outputs_from_data_names

LOGGER = logging.getLogger("PYWPS")


class PreprocessExample(Process):
    def __init__(self):
        inputs = [
            *model_experiment_ensemble(model_name='model1',
                                       ensemble_name='ensemble1',
                                       start_end_year=(1850, 2005),
                                       start_end_defaults=(2000, 2005)),
            *model_experiment_ensemble(model_name='model2',
                                       ensemble_name='ensemble2',
                                       start_end_year=(1850, 2005),
                                       start_end_defaults=(2000, 2005)),
            *model_experiment_ensemble(model_name='model3',
                                       ensemble_name='ensemble3',
                                       start_end_year=(1850, 2005),
                                       start_end_defaults=(2000, 2005)),
            LiteralInput(
                'extract_levels',
                'Extraction levels',
                abstract='Choose an extraction level for the preprocessor.',
                data_type='float',
                # allowed_values=make_allowedvalues([0.0, 110000.0]),
                default=85000.0),
        ]
        self.plotlist = [
            ('multi_model_mean_ta', [Format('image/png')]),
            ('multi_model_median_ta', [Format('image/png')]),
            ('model1_mean_ta', [Format('image/png')]),
            ('model2_mean_ta', [Format('image/png')]),
            ('model3_mean_ta', [Format('image/png')]),
            ('reference_model_mean_ta', [Format('image/png')]),
            ('model1_mean_pr', [Format('image/png')]),
            ('model2_mean_pr', [Format('image/png')]),
            ('model3_mean_pr', [Format('image/png')]),
            ('reference_model_mean_pr', [Format('image/png')]),
        ]

        self.datalist = [
            ('multi_model_mean_ta', [FORMATS.NETCDF]),
            ('multi_model_median_ta', [FORMATS.NETCDF]),
            ('model1_mean_ta', [FORMATS.NETCDF]),
            ('model2_mean_ta', [FORMATS.NETCDF]),
            ('model3_mean_ta', [FORMATS.NETCDF]),
            ('reference_model_mean_ta', [FORMATS.NETCDF]),
            ('model1_mean_pr', [FORMATS.NETCDF]),
            ('model2_mean_pr', [FORMATS.NETCDF]),
            ('model3_mean_pr', [FORMATS.NETCDF]),
            ('reference_model_mean_pr', [FORMATS.NETCDF]),
        ]
        outputs = [
            *outputs_from_plot_names(self.plotlist),
            *outputs_from_data_names(self.datalist),
            ComplexOutput('archive',
                          'Archive',
                          abstract='The complete output of the ESMValTool processing as an zip archive.',
                          as_reference=True,
                          supported_formats=[Format('application/zip')]),
            *default_outputs(),
        ]

        super(PreprocessExample, self).__init__(
            self._handler,
            identifier="preproc",
            title="Preprocessing Demo",
            version=runner.VERSION,
            abstract="""The ESMValTool climate data pre-processor can be used to
                        perform all types of climate data pre-processing needed before indices
                        or diagnostics can be calculated. It is a base component for many other
                        diagnostics and metrics shown on this portal. It can be applied to
                        tailor the climate model data to the need of the user for its own
                        calculations.""",
            metadata=[
                Metadata('ESMValTool', 'http://www.esmvaltool.org/'),
                Metadata('Documentation', '', role=util.WPS_ROLE_DOC),
                Metadata('Media', util.diagdata_url() + '/pydemo/pydemo_thumbnail.png', role=util.WPS_ROLE_MEDIA)
            ],
            inputs=inputs,
            outputs=outputs,
            status_supported=True,
            store_supported=True,
        )

    def _handler(self, request, response):
        response.update_status("starting ...", 0)
        workdir = self.workdir

        # build esgf search constraints
        constraints = dict(
            model1=request.inputs['model1'][0].data,
            ensemble1=request.inputs['ensemble1'][0].data,
            model2=request.inputs['model2'][0].data,
            ensemble2=request.inputs['ensemble2'][0].data,
            model3=request.inputs['model3'][0].data,
            ensemble3=request.inputs['ensemble3'][0].data,
            experiment=request.inputs['experiment'][0].data,
        )

        options = dict(extract_levels=request.inputs['extract_levels'][0].data)

        # generate recipe
        response.update_status("generate recipe ...", 10)
        recipe_file, config_file = runner.generate_recipe(workdir=workdir,
                                                          diag='python',
                                                          constraints=constraints,
                                                          start_year=request.inputs['start_year'][0].data,
                                                          end_year=request.inputs['end_year'][0].data,
                                                          output_format='png',
                                                          options=options)

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
                self.get_outputs(result, constraints, response)
            except Exception as e:
                response.update_status("exception occured: " + str(e), 85)
                LOGGER.exception('Getting output failed: ' + str(e))
        else:
            LOGGER.exception('esmvaltool failed!')
            response.update_status("exception occured: " + result['exception'], 85)

        response.update_status("creating archive of diagnostic result ...", 90)

        response.outputs['archive'].output_format = Format('application/zip')
        response.outputs['archive'].file = runner.compress_output(os.path.join(workdir, 'output'),
                                                                  'preproc_result.zip')

        response.update_status("done.", 100)
        return response

    def get_outputs(self, result, constraints, response):
        response.update_status("collecting output ...", 80)

        for var in ['mean', 'median']:
            plotkey = 'multi_model_{}_ta_plot'.format(var)
            datakey = 'multi_model_{}_ta_data'.format(var)

            LOGGER.info('Setting response for: {}'.format(plotkey))
            response.outputs[plotkey].output_format = Format('application/png')
            response.outputs[plotkey].file = runner.get_output(result['plot_dir'],
                                                               path_filter=os.path.join('diagnostic1', 'script1'),
                                                               name_filter="MultiModel{}*".format(var.capitalize()),
                                                               output_format="png")

            LOGGER.info('Setting response for: {}'.format(datakey))
            response.outputs[datakey].output_format = FORMATS.NETCDF
            response.outputs[datakey].file = runner.get_output(result['work_dir'],
                                                               path_filter=os.path.join('diagnostic1', 'script1'),
                                                               name_filter="MultiModel{}*".format(var.capitalize()),
                                                               output_format="nc")

        for var in ['ta', 'pr']:
            for i in range(1, 4):
                model = 'model{}'.format(i)
                plotkey = '{}_mean_{}_plot'.format(model, var)
                datakey = '{}_mean_{}_data'.format(model, var)

                LOGGER.info('Setting response for: {}'.format(plotkey))
                LOGGER.info('Setting response for: {}'.format(datakey))
                response.outputs[plotkey].output_format = Format('application/png')
                response.outputs[plotkey].file = runner.get_output(result['plot_dir'],
                                                                   path_filter=os.path.join('diagnostic1', 'script1'),
                                                                   name_filter="*{}*{}*".format(
                                                                       constraints[model], var),
                                                                   output_format="png")

                response.outputs[datakey].output_format = FORMATS.NETCDF
                response.outputs[datakey].file = runner.get_output(result['work_dir'],
                                                                   path_filter=os.path.join('diagnostic1', 'script1'),
                                                                   name_filter="*{}*{}*".format(
                                                                       constraints[model], var),
                                                                   output_format="nc")

            plotkey = 'reference_model_mean_{}_plot'.format(var)
            datakey = 'reference_model_mean_{}_data'.format(var)

            LOGGER.info('Setting response for: {}'.format(plotkey))
            LOGGER.info('Setting response for: {}'.format(datakey))
            response.outputs[plotkey].output_format = Format('application/png')
            response.outputs[plotkey].file = runner.get_output(result['plot_dir'],
                                                               path_filter=os.path.join('diagnostic1', 'script1'),
                                                               name_filter="OBS*{}*".format(var),
                                                               output_format="png")

            response.outputs[datakey].output_format = FORMATS.NETCDF
            response.outputs[datakey].file = runner.get_output(result['work_dir'],
                                                               path_filter=os.path.join('diagnostic1', 'script1'),
                                                               name_filter="OBS*{}*".format(var),
                                                               output_format="nc")
