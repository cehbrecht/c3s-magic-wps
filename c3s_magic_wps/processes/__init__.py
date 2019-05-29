from .wps_sleep import Sleep
from .wps_preproc_example import PreprocessExample
from .wps_consecdrydays import ConsecDryDays
from .wps_cvdp import CVDP
from .wps_ensclus import EnsClus
from .wps_shapeselect import ShapeSelect
from .wps_blocking import Blocking
from .wps_zmnam import ZMNAM
from .wps_teleconnections import Teleconnections
from .wps_weather_regimes import WeatherRegimes
from .wps_modes_variability import ModesVariability
from .wps_combined_indices import CombinedIndices
from .wps_multimodel_products import MultimodelProducts
from .wps_heatwaves_coldwaves import HeatwavesColdwaves
from .wps_diurnal_temperature_index import DiurnalTemperatureIndex
from .wps_capacity_factor import CapacityFactor
from .wps_extreme_index import ExtremeIndex
from .wps_drought_indicator import DroughtIndicator
from .wps_quantilebias import QuantileBias
from .wps_toymodel import Toymodel
from .wps_rainfarm import RainFARM
from .wps_perfmetrics import Perfmetrics
from .wps_smpi import SMPI

processes = sorted(
    [
        CVDP(),
        EnsClus(),
        Sleep(),
        Blocking(),
        PreprocessExample(),
        ZMNAM(),
        Teleconnections(),
        WeatherRegimes(),
        ModesVariability(),
        CombinedIndices(),
        MultimodelProducts(),
        HeatwavesColdwaves(),
        DiurnalTemperatureIndex(),
        CapacityFactor(),
        ExtremeIndex(),
        DroughtIndicator(),
        ConsecDryDays(),
        ShapeSelect(),
        QuantileBias(),
        RainFARM(),
        Toymodel(),
        Perfmetrics(),
        SMPI(),
    ],
    key=lambda process: process.title,
)
