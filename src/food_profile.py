import json
import os


PROFILE_PATH = "data/food_profiles.json"


class FoodProfileDatabase:
    """
    Food-specific profile and reference database.

    The database is intentionally flexible:
    different foods may have different amounts of
    reference sensor information.
    """

    def __init__(self, path=PROFILE_PATH):

        self.path = path

        if not os.path.exists(self.path):
            raise FileNotFoundError(
                f"Food profile file not found: {self.path}"
            )

        with open(
            self.path,
            "r",
            encoding="utf-8"
        ) as file:

            self.profiles = json.load(file)

    # ========================================================
    # AVAILABLE FOODS
    # ========================================================

    def get_available_foods(self):

        return sorted(
            self.profiles.keys()
        )

    # ========================================================
    # GET PROFILE
    # ========================================================

    def get_profile(self, food_type):

        key = str(
            food_type
        ).strip().lower()

        if key not in self.profiles:

            raise ValueError(
                f"Food profile not found: {food_type}"
            )

        return self.profiles[key]

    # ========================================================
    # DISPLAY NAME
    # ========================================================

    def get_display_name(self, food_type):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "display_name",
            str(food_type).title()
        )

    # ========================================================
    # CATEGORY
    # ========================================================

    def get_category(self, food_type):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "category",
            "unknown"
        )

    # ========================================================
    # VERSION
    # ========================================================

    def get_version(self, food_type):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "profile_version",
            "unknown"
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def is_validated(self, food_type):

        profile = self.get_profile(
            food_type
        )

        return bool(
            profile.get(
                "validated",
                False
            )
        )

    # ========================================================
    # TEMPERATURE
    # ========================================================

    def get_temperature_limits(
        self,
        food_type
    ):

        profile = self.get_profile(
            food_type
        )

        temperature = profile.get(
            "temperature",
            {}
        )

        return {
            "min_preferred": temperature.get(
                "preferred_min_c"
            ),
            "max_preferred": temperature.get(
                "preferred_max_c"
            ),
            "critical": temperature.get(
                "critical_max_c"
            )
        }

    # ========================================================
    # HUMIDITY
    # ========================================================

    def get_humidity_limits(
        self,
        food_type
    ):

        profile = self.get_profile(
            food_type
        )

        humidity = profile.get(
            "humidity",
            {}
        )

        return {
            "min_preferred": humidity.get(
                "preferred_min_percent"
            ),
            "max_preferred": humidity.get(
                "preferred_max_percent"
            )
        }

    # ========================================================
    # GAS
    # ========================================================

    def get_gas_profile(
        self,
        food_type
    ):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "gas",
            {}
        )

    # ========================================================
    # WEIGHT
    # ========================================================

    def get_weight_profile(
        self,
        food_type
    ):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "weight",
            {}
        )

    # ========================================================
    # REFERENCE INFORMATION
    # ========================================================

    def get_reference(
        self,
        food_type
    ):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "reference",
            {}
        )

    # ========================================================
    # REFERENCE COVERAGE
    # ========================================================

    def get_reference_coverage(
        self,
        food_type
    ):

        reference = self.get_reference(
            food_type
        )

        coverage = reference.get(
            "coverage",
            {}
        )

        return {
            "temperature": bool(
                coverage.get(
                    "temperature",
                    False
                )
            ),
            "humidity": bool(
                coverage.get(
                    "humidity",
                    False
                )
            ),
            "gas": bool(
                coverage.get(
                    "gas",
                    False
                )
            ),
            "weight": bool(
                coverage.get(
                    "weight",
                    False
                )
            ),
            "storage_time": bool(
                coverage.get(
                    "storage_time",
                    False
                )
            ),
            "rsl": bool(
                coverage.get(
                    "rsl",
                    False
                )
            )
        }

    # ========================================================
    # REFERENCE CONFIDENCE
    # ========================================================

    def get_reference_confidence(
        self,
        food_type
    ):

        reference = self.get_reference(
            food_type
        )

        return float(
            reference.get(
                "reference_confidence",
                0.0
            )
        )

    # ========================================================
    # REFERENCE SOURCES
    # ========================================================

    def get_reference_sources(
        self,
        food_type
    ):

        reference = self.get_reference(
            food_type
        )

        return reference.get(
            "source_files",
            []
        )

    # ========================================================
    # ADAPTIVE LEARNING SETTINGS
    # ========================================================

    def get_adaptive_learning_settings(
        self,
        food_type
    ):

        profile = self.get_profile(
            food_type
        )

        return profile.get(
            "adaptive_learning",
            {
                "individual_baseline": True,
                "temporal_learning": True,
                "reference_assisted": True
            }
        )


# ============================================================
# TEST
# ============================================================

def main():

    print("=" * 50)
    print("FOOD PROFILE DATABASE TEST")
    print("=" * 50)

    database = FoodProfileDatabase()

    print(
        "\nAvailable Food Profiles"
    )

    print("-" * 30)

    foods = database.get_available_foods()

    for index, food in enumerate(
        foods,
        start=1
    ):

        print(
            f"{index}. "
            f"{database.get_display_name(food)} "
            f"({database.get_category(food)})"
        )

    # --------------------------------------------------------
    # Test Tomato because its reference data now exists.
    # --------------------------------------------------------

    selected_food = "tomato"

    print(
        "\nFood Profile"
    )

    print("-" * 40)

    print(
        f"Name       : "
        f"{database.get_display_name(selected_food)}"
    )

    print(
        f"Category   : "
        f"{database.get_category(selected_food)}"
    )

    print(
        f"Version    : "
        f"{database.get_version(selected_food)}"
    )

    print(
        f"Validated  : "
        f"{database.is_validated(selected_food)}"
    )

    print(
        "\nTemperature limits:"
    )

    print(
        database.get_temperature_limits(
            selected_food
        )
    )

    print(
        "\nHumidity limits:"
    )

    print(
        database.get_humidity_limits(
            selected_food
        )
    )

    print(
        "\nReference coverage:"
    )

    coverage = database.get_reference_coverage(
        selected_food
    )

    for key, value in coverage.items():

        print(
            f"{key:18}: {value}"
        )

    print(
        "\nReference confidence:"
    )

    print(
        database.get_reference_confidence(
            selected_food
        )
    )

    print(
        "\nReference sources:"
    )

    sources = database.get_reference_sources(
        selected_food
    )

    for source in sources:

        print(
            f"  ✓ {source}"
        )

    print(
        "\nAdaptive learning:"
    )

    print(
        database.get_adaptive_learning_settings(
            selected_food
        )
    )

    print(
        "\nFood profile loaded successfully."
    )


# ============================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# ============================================================

def _get_database():
    return FoodProfileDatabase()


def list_available_foods():
    database = _get_database()
    return database.get_available_foods()


def get_food_profile(food_type):
    database = _get_database()
    return database.get_profile(food_type)


def load_food_profile(food_type):
    database = _get_database()
    return database.get_profile(food_type)


def get_temperature_limits(food_type):
    database = _get_database()
    return database.get_temperature_limits(food_type)


def get_humidity_limits(food_type):
    database = _get_database()
    return database.get_humidity_limits(food_type)


def get_reference_coverage(food_type):
    database = _get_database()
    return database.get_reference_coverage(food_type)


def get_reference_confidence(food_type):
    database = _get_database()
    return database.get_reference_confidence(food_type)


def get_food_profiles():
    database = _get_database()
    return database.profiles


def get_food_category(food_type):
    database = _get_database()
    return database.get_category(food_type)


def get_food_profile_version(food_type):
    database = _get_database()
    return database.get_version(food_type)


def is_food_profile_validated(food_type):
    database = _get_database()
    return database.is_validated(food_type)


def get_gas_profile(food_type):
    database = _get_database()
    return database.get_gas_profile(food_type)


def get_weight_profile(food_type):
    database = _get_database()
    return database.get_weight_profile(food_type)


def get_reference_data(food_type):
    database = _get_database()
    return database.get_reference(food_type)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
