"""
ecoinvent_modification.py exposes methods to create a database, perform transformations on it,
as well as export it back.
"""
SUPPORTED_EI_VERSIONS = ["3.5", "3.6", "3.7", "3.7.1", "3.8"]
LIST_REMIND_REGIONS = [
    "CAZ",
    "CHA",
    "EUR",
    "IND",
    "JPN",
    "LAM",
    "MEA",
    "NEU",
    "OAS",
    "REF",
    "SSA",
    "USA",
    "World",
]

LIST_IMAGE_REGIONS = [
    "BRA",
    "CAN",
    "CEU",
    "CHN",
    "EAF",
    "INDIA",
    "INDO",
    "JAP",
    "KOR",
    "ME",
    "MEX",
    "NAF",
    "OCE",
    "RCAM",
    "RSAF",
    "RSAM",
    "RSAS",
    "RUS",
    "SAF",
    "SEAS",
    "STAN",
    "TUR",
    "UKR",
    "USA",
    "WAF",
    "WEU",
    "World",
]
import copy
import os
import pickle
import sys
from datetime import date
from pathlib import Path
from typing import List, Union

import wurst
from prettytable import PrettyTable

from . import DATA_DIR, INVENTORY_DIR
from .cement import Cement
from .clean_datasets import DatabaseCleaner
from .custom import (
    Custom,
    check_custom_scenario,
    check_inventories,
    detect_ei_activities_to_adjust,
)
from .data_collection import IAMDataCollection
from .electricity import Electricity
from .export import Export, check_for_duplicates, remove_uncertainty
from .fuels import Fuels
from .inventory_imports import AdditionalInventory, DefaultInventory
from .steel import Steel
from .transformation import BaseTransformation
from .transport import Transport
from .utils import add_modified_tags, build_superstructure_db, eidb_label

DIR_CACHED_DB = DATA_DIR / "cache"

FILEPATH_OIL_GAS_INVENTORIES = INVENTORY_DIR / "lci-ESU-oil-and-gas.xlsx"
FILEPATH_CARMA_INVENTORIES = INVENTORY_DIR / "lci-Carma-CCS.xlsx"
FILEPATH_CHP_INVENTORIES = INVENTORY_DIR / "lci-combined-heat-power-plant-CCS.xlsx"
FILEPATH_DAC_INVENTORIES = INVENTORY_DIR / "lci-direct-air-capture.xlsx"
FILEPATH_BIOFUEL_INVENTORIES = INVENTORY_DIR / "lci-biofuels.xlsx"
FILEPATH_BIOGAS_INVENTORIES = INVENTORY_DIR / "lci-biogas.xlsx"

FILEPATH_CARBON_FIBER_INVENTORIES = INVENTORY_DIR / "lci-carbon-fiber.xlsx"
FILEPATH_HYDROGEN_DISTRI_INVENTORIES = INVENTORY_DIR / "lci-hydrogen-distribution.xlsx"

FILEPATH_HYDROGEN_INVENTORIES = INVENTORY_DIR / "lci-hydrogen-electrolysis.xlsx"

FILEPATH_HYDROGEN_BIOGAS_INVENTORIES = (
    INVENTORY_DIR / "lci-hydrogen-smr-atr-biogas.xlsx"
)
FILEPATH_HYDROGEN_NATGAS_INVENTORIES = (
    INVENTORY_DIR / "lci-hydrogen-smr-atr-natgas.xlsx"
)
FILEPATH_HYDROGEN_WOODY_INVENTORIES = (
    INVENTORY_DIR / "lci-hydrogen-wood-gasification.xlsx"
)
FILEPATH_HYDROGEN_COAL_GASIFICATION_INVENTORIES = (
    INVENTORY_DIR / "lci-hydrogen-coal-gasification.xlsx"
)
FILEPATH_SYNFUEL_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-FT-from-electrolysis.xlsx"
)

FILEPATH_SYNFUEL_FROM_FT_FROM_WOOD_GASIFICATION_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-FT-from-wood-gasification.xlsx"
)
FILEPATH_SYNFUEL_FROM_FT_FROM_WOOD_GASIFICATION_WITH_CCS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-FT-from-wood-gasification-with-CCS.xlsx"
)
FILEPATH_SYNFUEL_FROM_FT_FROM_COAL_GASIFICATION_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-FT-from-coal-gasification.xlsx"
)

FILEPATH_SYNFUEL_FROM_BIOMASS_CCS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-FT-from-biomass-CCS.xlsx"
)
FILEPATH_SYNGAS_INVENTORIES = INVENTORY_DIR / "lci-syngas.xlsx"
FILEPATH_SYNGAS_FROM_COAL_INVENTORIES = INVENTORY_DIR / "lci-syngas-from-coal.xlsx"
FILEPATH_GEOTHERMAL_HEAT_INVENTORIES = INVENTORY_DIR / "lci-geothermal.xlsx"
FILEPATH_METHANOL_FUELS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-methanol-from-electrolysis.xlsx"
)
FILEPATH_METHANOL_CEMENT_FUELS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-methanol-from-cement-plant.xlsx"
)
FILEPATH_METHANOL_FROM_COAL_FUELS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-methanol-from-coal.xlsx"
)
FILEPATH_METHANOL_FROM_BIOMASS_FUELS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-methanol-from-biomass.xlsx"
)
FILEPATH_METHANOL_FROM_BIOGAS_FUELS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-methanol-from-biogas.xlsx"
)
FILEPATH_METHANOL_FROM_NATGAS_FUELS_INVENTORIES = (
    INVENTORY_DIR / "lci-synfuels-from-methanol-from-natural-gas.xlsx"
)
FILEPATH_BATTERIES = INVENTORY_DIR / "lci-batteries.xlsx"
FILEPATH_PHOTOVOLTAICS = INVENTORY_DIR / "lci-PV.xlsx"
FILEPATH_BIGCC = INVENTORY_DIR / "lci-BIGCC.xlsx"


SUPPORTED_MODELS = ["remind", "image"]
SUPPORTED_PATHWAYS = [
    "SSP2-Base",
    "SSP2-NDC",
    "SSP2-NPi",
    "SSP2-PkBudg900",
    "SSP2-PkBudg1100",
    "SSP2-PkBudg1300",
    "SSP2-PkBudg900_Elec",
    "SSP2-PkBudg1100_Elec",
    "SSP2-PkBudg1300_Elec",
    "SSP2-RCP26",
    "SSP2-RCP19",
    "static",
]


LIST_TRANSF_FUNC = [
    "update_electricity",
    "update_cement",
    "update_steel",
    "update_two_wheelers",
    "update_cars",
    "update_trucks",
    "update_buses",
    "update_fuels",
    "update_custom_scenario",
]

# clear the cache folder
def clear_cache():
    [f.unlink() for f in Path(DATA_DIR / "cache").glob("*") if f.is_file()]
    print("Cache folder cleared!")


# Disable printing
def blockPrint():
    sys.stdout = open(os.devnull, "w")


# Restore printing
def enablePrint():
    sys.stdout = sys.__stdout__


def check_ei_filepath(filepath: str) -> Path:
    """Check for the existence of the file path."""

    if not Path(filepath).is_dir():
        raise FileNotFoundError(
            f"The directory for ecospold files {filepath} could not be found."
        )
    return Path(filepath)


def check_model_name(name: str) -> str:
    """Check for the validity of the IAM model name."""
    if name.lower() not in SUPPORTED_MODELS:
        raise ValueError(
            f"Only {SUPPORTED_MODELS} are currently supported, not {name}."
        )
    return name.lower()


def check_pathway_name(name: str, filepath: Path, model: str) -> str:
    """Check the pathway name"""

    if name not in SUPPORTED_PATHWAYS:
        # If the pathway name is not a default one,
        # check that the filepath + pathway name
        # leads to an actual file

        if model.lower() not in name:
            name_check = "_".join((model.lower(), name))
        else:
            name_check = name

        if (filepath / name_check).with_suffix(".mif").is_file():
            return name
        if (filepath / name_check).with_suffix(".xlsx").is_file():
            return name
        if (filepath / name_check).with_suffix(".csv").is_file():
            return name
        raise ValueError(
            f"Only {SUPPORTED_PATHWAYS} are currently supported, not {name}."
        )
    else:
        if model.lower() not in name:
            name_check = "_".join((model.lower(), name))
        else:
            name_check = name

        if (filepath / name_check).with_suffix(".mif").is_file():
            return name
        if (filepath / name_check).with_suffix(".xlsx").is_file():
            return name
        if (filepath / name_check).with_suffix(".csv").is_file():
            return name

        raise ValueError(
            f"Cannot find the IAM scenario file at this location: {filepath / name_check}."
        )


def check_year(year: [int, float]) -> int:
    """Check for the validity of the year passed."""
    try:
        year = int(year)
    except ValueError as err:
        raise Exception(f"{year} is not a valid year.") from err

    try:
        assert 2005 <= year <= 2100
    except AssertionError as err:
        raise Exception(f"{year} must be comprised between 2005 and 2100.") from err

    return year


def check_filepath(path: str) -> Path:
    if not Path(path).is_dir():
        raise FileNotFoundError(f"The IAM output directory {path} could not be found.")
    return Path(path)


def check_exclude(list_exc: List[str]) -> List[str]:

    if not isinstance(list_exc, list):
        raise TypeError("`exclude` should be a sequence of strings.")

    if not set(list_exc).issubset(LIST_TRANSF_FUNC):
        raise ValueError(
            "One or several of the transformation that you wish to exclude is not recognized."
        )
    return list_exc


def check_additional_inventories(inventories_list: List[dict]) -> List[dict]:
    """
    Check that any additional inventories that need to be imported are properly listed.
    :param inventories_list: list of dictionaries
    :return: list of dictionaries
    """

    if not isinstance(inventories_list, list):
        raise TypeError(
            "Inventories to import need to be in a sequence of dictionaries like so:"
            "["
            "{'inventories': 'a file path', 'ecoinvent version: '3.6'},"
            " {'inventories': 'a file path', 'ecoinvent version: '3.6'}"
            "]"
        )

    for inventory in inventories_list:
        if not isinstance(inventory, dict):
            raise TypeError(
                "Inventories to import need to be in a sequence of dictionaries like so:"
                "["
                "{'inventories': 'a file path', 'ecoinvent version: '3.6'},"
                " {'inventories': 'a file path', 'ecoinvent version: '3.6'}"
                "]"
            )
        if "region_duplicate" in inventory:
            if not isinstance(inventory["region_duplicate"], bool):
                raise TypeError(
                    "`region_duplicate`must be a boolean (`True`` `False`.)"
                )

        if not all(
            i for i in inventory.keys() if i in ["inventories", "ecoinvent version"]
        ):
            raise TypeError(
                "Both `inventories` and `ecoinvent version` must be present in the list of inventories to import."
            )

        if not Path(inventory["inventories"]).is_file():
            raise FileNotFoundError(
                f"Cannot find the inventory file: {inventory['inventories']}."
            )
        inventory["inventories"] = Path(inventory["inventories"])

        if inventory["ecoinvent version"] not in ["3.7", "3.7.1", "3.8"]:
            raise ValueError(
                "A lot of trouble will be avoided if the additional "
                f"inventories to import are ecoinvent 3.7 or 3.8-compliant, not {inventory['ecoinvent version']}."
            )

    return inventories_list


def check_db_version(version: [str, float]) -> str:
    """
    Check that the ecoinvent database version is supported
    :param version:
    :return:
    """
    version = str(version)
    if version not in SUPPORTED_EI_VERSIONS:
        raise ValueError(
            f"Only {SUPPORTED_EI_VERSIONS} are currently supported, not {version}."
        )
    return version


def check_scenarios(scenario: dict, key: bytes) -> dict:

    if not all(name in scenario for name in ["model", "pathway", "year"]):
        raise ValueError(
            f"Missing parameters in {scenario}. Needs to include at least `model`,"
            f"`pathway` and `year`."
        )

    if "filepath" in scenario:
        filepath = scenario["filepath"]
        scenario["filepath"] = check_filepath(filepath)
    else:
        if key is not None:
            scenario["filepath"] = DATA_DIR / "iam_output_files"
        else:
            raise PermissionError(
                "You will need to provide a decryption key "
                "if you want to use the IAM scenario files included "
                "in premise. If you do not have a key, "
                "please contact the developers."
            )

    scenario["model"] = check_model_name(scenario["model"])
    scenario["pathway"] = check_pathway_name(
        scenario["pathway"], scenario["filepath"], scenario["model"]
    )
    scenario["year"] = check_year(scenario["year"])

    if "exclude" in scenario:
        scenario["exclude"] = check_exclude(scenario["exclude"])

    return scenario


def check_system_model(system_model: str) -> str:

    if not isinstance(system_model, str):
        raise TypeError(
            "The argument `system_model` must be a string"
            "('attributional', 'consequential')."
        )

    if system_model not in ("attributional", "consequential"):
        raise ValueError(
            "The argument `system_model` must be one of the two values:"
            "'attributional', 'consequential'."
        )

    return system_model


def check_time_horizon(th: int) -> int:
    """
    Check the validity of the time horizon provided (in years).
    :param th: time horizon (in years), to determine marginal mixes for consequential modelling.
    :return: time horizon (in years)
    """

    if th is None:
        print(
            "`time_horizon`, used to identify marginal suppliers, is not specified. "
            "It is therefore set to 20 years."
        )
        th = 20

    try:
        int(th)
    except ValueError as err:
        raise Exception(
            "`time_horizon` must be an integer with a value between 5 and 50 years."
        ) from err

    if th < 5 or th > 50:
        raise ValueError(
            "`time_horizon` must be an integer with a value between 5 and 50 years."
        )

    return int(th)


def warning_about_biogenic_co2() -> None:
    """
    Prints a simple warning about characterizing biogenic CO2 flows.
    :return: Does not return anything.
    """
    t = PrettyTable(["Warning"])
    t.add_row(
        [
            "Because some of the scenarios can yield LCI databases\n"
            "containing net negative emission technologies (NET),\n"
            "it is advised to account for biogenic CO2 flows when calculating\n"
            "Global Warming potential indicators.\n"
            "`premise_gwp` provides characterization factors for such flows.\n"
            "It also provides factors for hydrogen emissions to air.\n\n"
            "Within your bw2 project:\n"
            "from premise_gwp import add_premise_gwp\n"
            "add_premise_gwp()"
        ]
    )
    # align text to the left
    t.align = "l"
    print(t)


class HiddenPrints:
    """
    From https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
    """

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


class NewDatabase:
    """
    Class that represents a new wurst inventory database, modified according to IAM data.

    :ivar source_type: the source of the ecoinvent database. Can be `brigthway` or `ecospold`.
    :vartype source_type: str
    :ivar source_db: name of the ecoinvent source database
    :vartype source_db: str
    :ivar source_version: version of the ecoinvent source database.
        Currently works with ecoinvent cut-off 3.5, 3.6, 3.7, 3.7.1 and 3.8.
    :vartype source_version: str
    :ivar system_model: Can be `attributional` (default) or `consequential`.
    :vartype system_model: str

    """

    def __init__(
        self,
        scenarios: List[dict],
        source_version: str = "3.8",
        source_type: str = "brightway",
        key: bytes = None,
        source_db: str = None,
        source_file_path: str = None,
        additional_inventories: List[dict] = None,
        system_model: str = "attributional",
        time_horizon: int = None,
        use_cached_inventories: bool = True,
        use_cached_database: bool = True,
        custom_scenario: dict = None,
    ) -> None:

        self.source = source_db
        self.version = check_db_version(source_version)
        self.source_type = source_type
        self.system_model = check_system_model(system_model)
        self.time_horizon = (
            check_time_horizon(time_horizon)
            if system_model == "consequential"
            else None
        )

        if self.source_type == "ecospold":
            self.source_file_path = check_ei_filepath(source_file_path)
        else:
            self.source_file_path = None

        self.scenarios = [check_scenarios(scenario, key) for scenario in scenarios]

        # warning about biogenic CO2
        warning_about_biogenic_co2()

        if additional_inventories:
            self.additional_inventories = check_additional_inventories(
                additional_inventories
            )
        else:
            self.additional_inventories = None

        if custom_scenario:
            self.custom_scenario = check_custom_scenario(
                custom_scenario, self.scenarios
            )
        else:
            self.custom_scenario = None

        print("\n//////////////////// EXTRACTING SOURCE DATABASE ////////////////////")
        if use_cached_database:
            self.database = self.__find_cached_db(source_db)
            print("Done!")
        else:
            self.database = self.__clean_database()

        print("\n////////////////// IMPORTING DEFAULT INVENTORIES ///////////////////")
        if use_cached_inventories:
            data = self.__find_cached_inventories(source_db)
            if data is not None:
                self.database.extend(data)

        else:
            self.__import_inventories()

        if self.additional_inventories:
            data = self.__import_additional_inventories(self.additional_inventories)
            self.database.extend(data)

        print("Done!")

        print("\n/////////////////////// EXTRACTING IAM DATA ////////////////////////")

        for scenario in self.scenarios:
            data = IAMDataCollection(
                model=scenario["model"],
                pathway=scenario["pathway"],
                year=scenario["year"],
                filepath_iam_files=scenario["filepath"],
                key=key,
                system_model=self.system_model,
                time_horizon=self.time_horizon,
            )
            scenario["iam data"] = data

            if self.custom_scenario:
                scenario["custom data"] = data.get_custom_data(self.custom_scenario)

            scenario["database"] = copy.deepcopy(self.database)

        print("Done!")

    def __find_cached_db(self, db_name: str) -> List[dict]:
        """
        If `use_cached_db` = True, then we look for a cached database.
        If cannot be found, we create a cache for next time.
        :param db_name: database name
        :return: database
        """
        # check that directory exists, otherwise create it
        Path(DIR_CACHED_DB).mkdir(parents=True, exist_ok=True)
        # build file path
        if db_name is None:
            db_name = "unnamed"

        file_name = Path(DIR_CACHED_DB / f"cached_{db_name.strip().lower()}.pickle")

        # check that file path leads to an existing file
        if file_name.exists():
            # return the cached database
            return pickle.load(open(file_name, "rb"))
        else:
            # extract the database, pickle it for next time and return it
            print("Cannot find cached database. Will create one now for next time...")
            db = self.__clean_database()
            pickle.dump(db, open(file_name, "wb"))
            return db

    def __find_cached_inventories(self, db_name: str) -> Union[None, List[dict]]:
        """
        If `use_cached_inventories` = True, then we look for a cached inventories.
        If cannot be found, we create a cache for next time.
        :param db_name: database name
        :return: database
        """
        # check that directory exists, otherwise create it
        Path(DIR_CACHED_DB).mkdir(parents=True, exist_ok=True)
        # build file path
        if db_name is None:
            db_name = "unnamed"

        file_name = Path(
            DIR_CACHED_DB / f"cached_{db_name.strip().lower()}_inventories.pickle"
        )

        # check that file path leads to an existing file
        if file_name.exists():
            # return the cached database
            return pickle.load(open(file_name, "rb"))

        # else, extract the database, pickle it for next time and return it
        print("Cannot find cached inventories. Will create them now for next time...")
        data = self.__import_inventories()
        pickle.dump(data, open(file_name, "wb"))
        return None

    def __clean_database(self) -> List[dict]:
        """
        Extracts the ecoinvent database, loads it into a dictionary and does a little bit of housekeeping
        (adds missing locations, reference products, etc.).
        :return:
        """
        return DatabaseCleaner(
            self.source, self.source_type, self.source_file_path
        ).prepare_datasets()

    def __import_inventories(self) -> List[dict]:
        """
        This method will trigger the import of a number of pickled inventories
        and merge them into the database dictionary.
        """

        print("Importing default inventories...\n")

        with HiddenPrints():
            # Manual import
            # file path and original ecoinvent version
            data = []
            filepaths = [
                (FILEPATH_OIL_GAS_INVENTORIES, "3.7"),
                (FILEPATH_CARMA_INVENTORIES, "3.5"),
                (FILEPATH_CHP_INVENTORIES, "3.5"),
                (FILEPATH_DAC_INVENTORIES, "3.7"),
                (FILEPATH_BIOGAS_INVENTORIES, "3.6"),
                (FILEPATH_CARBON_FIBER_INVENTORIES, "3.7"),
                (FILEPATH_BATTERIES, "3.8"),
                (FILEPATH_PHOTOVOLTAICS, "3.7"),
                (FILEPATH_HYDROGEN_DISTRI_INVENTORIES, "3.7"),
                (FILEPATH_HYDROGEN_INVENTORIES, "3.7"),
                (FILEPATH_HYDROGEN_BIOGAS_INVENTORIES, "3.7"),
                (FILEPATH_HYDROGEN_COAL_GASIFICATION_INVENTORIES, "3.7"),
                (FILEPATH_HYDROGEN_NATGAS_INVENTORIES, "3.7"),
                (FILEPATH_HYDROGEN_WOODY_INVENTORIES, "3.7"),
                (FILEPATH_SYNGAS_INVENTORIES, "3.6"),
                (FILEPATH_SYNGAS_FROM_COAL_INVENTORIES, "3.7"),
                (FILEPATH_BIOFUEL_INVENTORIES, "3.7"),
                (FILEPATH_SYNFUEL_INVENTORIES, "3.7"),
                (
                    FILEPATH_SYNFUEL_FROM_FT_FROM_WOOD_GASIFICATION_INVENTORIES,
                    "3.7",
                ),
                (
                    FILEPATH_SYNFUEL_FROM_FT_FROM_WOOD_GASIFICATION_WITH_CCS_INVENTORIES,
                    "3.7",
                ),
                (
                    FILEPATH_SYNFUEL_FROM_FT_FROM_COAL_GASIFICATION_INVENTORIES,
                    "3.7",
                ),
                (FILEPATH_GEOTHERMAL_HEAT_INVENTORIES, "3.6"),
                (FILEPATH_METHANOL_FUELS_INVENTORIES, "3.7"),
                (FILEPATH_METHANOL_CEMENT_FUELS_INVENTORIES, "3.7"),
                (FILEPATH_METHANOL_FROM_COAL_FUELS_INVENTORIES, "3.7"),
                (FILEPATH_BIGCC, "3.8"),
            ]
            for filepath in filepaths:
                inventory = DefaultInventory(
                    database=self.database,
                    version_in=filepath[1],
                    version_out=self.version,
                    path=filepath[0],
                )
                datasets = inventory.merge_inventory()
                data.extend(datasets)
                self.database.extend(datasets)

        print("Done!\n")
        return data

    def __import_additional_inventories(self, list_inventories) -> List[dict]:

        print("\n//////////////// IMPORTING USER-DEFINED INVENTORIES ////////////////")

        data = []

        for file in list_inventories:

            if file["inventories"] != "":
                additional = AdditionalInventory(
                    database=self.database,
                    version_in=file["ecoinvent version"]
                    if "ecoinvent version" in file
                    else "3.8",
                    version_out=self.version,
                    path=file["inventories"],
                )
                additional.prepare_inventory()

                # if the inventories are to be duplicated
                # to be made specific to each IAM region
                # we flag them
                if "region_duplicate" in file:
                    if file["region_duplicate"]:
                        for ds in additional.import_db:
                            ds["duplicate"] = True

                data.extend(additional.merge_inventory())

        return data

    def update_electricity(self) -> None:

        print("\n/////////////////////////// ELECTRICITY ////////////////////////////")

        for scenario in self.scenarios:
            if (
                "exclude" not in scenario
                or "update_electricity" not in scenario["exclude"]
            ):
                electricity = Electricity(
                    database=scenario["database"],
                    iam_data=scenario["iam data"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    year=scenario["year"],
                )

                electricity.update_ng_production_ds()
                electricity.update_efficiency_of_solar_pv()
                electricity.create_biomass_markets()
                electricity.create_region_specific_power_plants()
                electricity.update_electricity_markets()
                electricity.update_electricity_efficiency()
                scenario["database"] = electricity.database

    def update_fuels(self) -> None:
        print("\n////////////////////////////// FUELS ///////////////////////////////")

        for scenario in self.scenarios:

            if "exclude" not in scenario or "update_fuels" not in scenario["exclude"]:

                fuels = Fuels(
                    database=scenario["database"],
                    iam_data=scenario["iam data"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    year=scenario["year"],
                    version=self.version,
                )
                fuels.generate_fuel_markets()
                scenario["database"] = fuels.database

    def update_cement(self) -> None:
        print("\n///////////////////////////// CEMENT //////////////////////////////")

        for scenario in self.scenarios:
            if "exclude" not in scenario or "update_cement" not in scenario["exclude"]:

                cement = Cement(
                    database=scenario["database"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    iam_data=scenario["iam data"],
                    year=scenario["year"],
                    version=self.version,
                )

                cement.add_datasets_to_database()
                scenario["database"] = cement.database

    def update_steel(self) -> None:
        print("\n////////////////////////////// STEEL //////////////////////////////")

        for scenario in self.scenarios:

            if "exclude" not in scenario or "update_steel" not in scenario["exclude"]:

                steel = Steel(
                    database=scenario["database"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    iam_data=scenario["iam data"],
                    year=scenario["year"],
                    version=self.version,
                )
                steel.generate_activities()
                scenario["database"] = steel.database

    def update_cars(self) -> None:
        print("\n///////////////////////// PASSENGER CARS ///////////////////////////")

        for scenario in self.scenarios:
            if "exclude" not in scenario or "update_cars" not in scenario["exclude"]:
                trspt = Transport(
                    database=scenario["database"],
                    year=scenario["year"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    iam_data=scenario["iam data"],
                    version=self.version,
                    vehicle_type="car",
                    relink=False,
                    has_fleet=True,
                )
                trspt.create_vehicle_markets()
                scenario["database"] = trspt.database

    def update_two_wheelers(self) -> None:
        print("\n////////////////////////// TWO-WHEELERS ////////////////////////////")

        for scenario in self.scenarios:
            if (
                "exclude" not in scenario
                or "update_two_wheelers" not in scenario["exclude"]
            ):

                trspt = Transport(
                    database=scenario["database"],
                    year=scenario["year"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    iam_data=scenario["iam data"],
                    version=self.version,
                    vehicle_type="two wheeler",
                    relink=False,
                    has_fleet=False,
                )
                trspt.create_vehicle_markets()
                scenario["database"] = trspt.database

    def update_trucks(self) -> None:

        print("\n////////////////// MEDIUM AND HEAVY DUTY TRUCKS ////////////////////")

        for scenario in self.scenarios:
            if "exclude" not in scenario or "update_trucks" not in scenario["exclude"]:

                trspt = Transport(
                    database=scenario["database"],
                    year=scenario["year"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    iam_data=scenario["iam data"],
                    version=self.version,
                    vehicle_type="truck",
                    relink=False,
                    has_fleet=True,
                )

                trspt.create_vehicle_markets()
                scenario["database"] = trspt.database

    def update_custom_scenario(self):

        if self.custom_scenario:
            for i, scenario in enumerate(self.scenarios):
                if (
                    "exclude" not in scenario
                    or "update_custom_scenario" not in scenario["exclude"]
                ):

                    data = self.__import_additional_inventories(self.custom_scenario)

                    if data:
                        data = check_inventories(
                            self.custom_scenario,
                            data,
                            scenario["model"],
                            scenario["pathway"],
                            scenario["custom data"],
                        )
                        scenario["database"].extend(data)

                    scenario["database"] = detect_ei_activities_to_adjust(
                        self.custom_scenario,
                        scenario["database"],
                        scenario["model"],
                        scenario["pathway"],
                        scenario["custom data"],
                    )

                    custom = Custom(
                        database=scenario["database"],
                        model=scenario["model"],
                        pathway=scenario["pathway"],
                        iam_data=scenario["iam data"],
                        year=scenario["year"],
                        version=self.version,
                        custom_scenario=self.custom_scenario,
                        custom_data=scenario["custom data"],
                    )
                    custom.regionalize_imported_inventories()
                    scenario["database"] = custom.database
                    custom.create_custom_markets()
                    scenario["database"] = custom.database

    def update_buses(self) -> None:

        print("\n////////////////////////////// BUSES ///////////////////////////////")

        for scenario in self.scenarios:
            if "exclude" not in scenario or "update_buses" not in scenario["exclude"]:

                trspt = Transport(
                    database=scenario["database"],
                    year=scenario["year"],
                    model=scenario["model"],
                    pathway=scenario["pathway"],
                    iam_data=scenario["iam data"],
                    version=self.version,
                    vehicle_type="bus",
                    relink=False,
                    has_fleet=True,
                )

                trspt.create_vehicle_markets()
                scenario["database"] = trspt.database

    def update_all(self) -> None:
        """
        Shortcut method to execute all transformation functions.
        """

        self.update_two_wheelers()
        self.update_cars()
        self.update_trucks()
        self.update_buses()
        self.update_electricity()
        self.update_cement()
        self.update_steel()
        self.update_fuels()
        self.update_custom_scenario()

    def prepare_db_for_export(self, scenario):

        base = BaseTransformation(
            database=scenario["database"],
            iam_data=scenario["iam data"],
            model=scenario["model"],
            pathway=scenario["pathway"],
            year=scenario["year"],
        )

        # check if additional inventories
        # need to be duplicated for each
        # IAM region

        list_add_ds = []
        for ds in base.database:
            if "duplicate" in ds:
                list_add_ds.extend(
                    base.fetch_proxies(
                        ds["name"], ds["reference product"], relink=True
                    ).values()
                )

        if len(list_add_ds) > 0:
            base.database.extend(list_add_ds)

        # we ensure the absence of duplicate datasets
        base.database = check_for_duplicates(base.database)
        base.database = remove_uncertainty(base.database)

        base.relink_datasets(
            excludes_datasets=["cobalt industry", "market group for electricity"],
            alt_names=[
                "market group for electricity, high voltage",
                "market group for electricity, medium voltage",
                "market group for electricity, low voltage",
                "carbon dioxide, captured from atmosphere, with heat pump heat, and grid electricity",
                "methane, from electrochemical methanation, with carbon from atmospheric CO2 capture, using heat pump heat",
                "Methane, synthetic, gaseous, 5 bar, from electrochemical methanation (H2 from electrolysis, CO2 from DAC using heat pump heat), at fuelling station, using heat pump heat",
            ],
        )

        return base.database

    def write_superstructure_db_to_brightway(
        self, name: str = f"super_db_{date.today()}", filepath: str = None
    ) -> None:
        """
        Register a super-structure database, according to https://github.com/dgdekoning/brightway-superstructure
        :return: filepath of the "scenarios difference file"
        """

        for scen, scenario in enumerate(self.scenarios):

            print(f"Prepare database {scen + 1}.")
            scenario["database"] = self.prepare_db_for_export(scenario)

        self.database = build_superstructure_db(
            self.database, self.scenarios, db_name=name, fp=filepath
        )

        print("Done!")

        self.database = check_for_duplicates(self.database)

        wurst.write_brightway2_database(
            self.database,
            name,
        )

    def write_db_to_brightway(self, name: [str, List[str]] = None):
        """
        Register the new database into an open brightway2 project.
        :param name: to give a (list) of custom name(s) to the database.
        Should either be a string if there's only one database to export.
        Or a list of strings if there are several databases.
        :type name: str
        """

        if name:
            if isinstance(name, str):
                name = [name]
            elif isinstance(name, list):
                if not all(isinstance(item, str) for item in name):
                    raise TypeError(
                        "`name` should be a string or a sequence of strings."
                    )
            else:
                raise TypeError("`name` should be a string or a sequence of strings.")
        else:
            name = [
                eidb_label(scenario["model"], scenario["pathway"], scenario["year"])
                for scenario in self.scenarios
            ]

        if len(name) != len(self.scenarios):
            raise ValueError(
                "The number of databases does not match the number of `name` given."
            )

        print("Write new database(s) to Brightway2.")
        for scen, scenario in enumerate(self.scenarios):

            print(f"Prepare database {scen + 1}.")
            scenario["database"] = self.prepare_db_for_export(scenario)

            wurst.write_brightway2_database(
                scenario["database"],
                name[scen],
            )

    def write_db_to_matrices(self, filepath: str = None):
        """

        Exports the new database as a sparse matrix representation in csv files.

        :param filepath: path provided by the user to store the exported matrices.
        If it is a string, the path is used as main directory from which
        "iam model" / "pathway" / "year" subdirectories will be created.
        If it is a sequence of strings, each string becomes the directory
        under which the set of matrices is saved. If `filepath` is not provided,
        "iam model" / "pathway" / "year" subdirectories are created under
        "premise" / "data" / "export".
        :type filepath: str or list

        """

        if filepath is not None:
            if isinstance(filepath, str):
                filepath = [
                    (Path(filepath) / s["model"] / s["pathway"] / str(s["year"]))
                    for s in self.scenarios
                ]
            elif isinstance(filepath, list):
                filepath = [Path(f) for f in filepath]
            else:
                raise TypeError(
                    f"Expected a string or a sequence of strings for `filepath`, not {type(filepath)}."
                )
        else:
            filepath = [
                (DATA_DIR / "export" / s["model"] / s["pathway"] / str(s["year"]))
                for s in self.scenarios
            ]

        print("Write new database(s) to matrix.")
        for scen, scenario in enumerate(self.scenarios):

            print(f"Prepare database {scen + 1}.")
            scenario["database"] = self.prepare_db_for_export(scenario)

            Export(
                scenario["database"],
                scenario["model"],
                scenario["pathway"],
                scenario["year"],
                filepath[scen],
            ).export_db_to_matrices()

    def write_db_to_simapro(self, filepath: str = None):
        """
        Exports database as a CSV file to be imported in Simapro 9.x

        :param filepath: path provided by the user to store the exported import file
        :type filepath: str

        """

        filepath = filepath or Path(DATA_DIR / "export" / "simapro")

        if not os.path.exists(filepath):
            os.makedirs(filepath)

        print("Write Simapro import file(s).")
        for scen, scenario in enumerate(self.scenarios):

            print(f"Prepare database {scen + 1}.")
            scenario["database"] = self.prepare_db_for_export(scenario)

            Export(
                scenario["database"],
                scenario["model"],
                scenario["pathway"],
                scenario["year"],
                filepath,
            ).export_db_to_simapro()
