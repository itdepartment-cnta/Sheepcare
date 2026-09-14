"""
SpectralParser - Reads NIR spectral Excel files for the milk quality model.

Unlike ExcelParser (celo), the input schema here is fixed by the spectrometer
export format: column "id" + a fixed, known set of wavelength columns. A file
that doesn't match this exact schema is rejected rather than best-effort
parsed, since a silently-misaligned column would feed the model garbage.
"""

import numpy as np
import pandas as pd
from io import BytesIO
from typing import List

# Wavelength columns (nm), in order, as exported by the spectrometer.
EXPECTED_WAVELENGTH_COLUMNS: List[float] = [
    569.1, 573.99, 578.84, 583.66, 588.46, 593.22, 597.95, 602.65, 607.33,
    611.98, 616.59, 621.19, 625.75, 630.29, 634.8, 639.29, 643.75, 648.19,
    652.6, 656.99, 661.35, 665.69, 670.01, 674.3, 678.58, 682.83, 687.05,
    691.26, 695.44, 699.61, 703.75, 707.87, 711.97, 716.05, 720.11, 724.14,
    728.16, 732.16, 736.14, 740.1, 744.03, 747.95, 751.85, 755.73, 759.59,
    763.43, 767.25, 771.06, 774.84, 778.6, 782.35, 786.07, 789.78, 793.47,
    797.14, 800.78, 804.42, 808.03, 811.62, 815.19, 818.74, 822.28, 825.79,
    829.29, 832.77, 836.23, 839.66, 843.08, 846.48, 849.86, 853.22, 856.56,
    859.88, 863.18, 866.47, 869.73, 872.97, 876.19, 879.39, 882.57, 885.74,
    888.88, 892, 895.1, 898.18, 901.24, 904.28, 907.3, 910.29, 913.27,
    916.23, 919.17, 922.08, 924.98, 927.85, 930.7, 933.54, 936.35, 939.14,
    941.91, 944.66, 947.39, 950.1, 952.78, 955.45, 958.1, 960.72, 963.32,
    965.91, 968.47, 971.01, 973.54, 976.04, 978.52, 980.98, 983.42, 985.85,
    988.25, 990.63, 992.99, 995.34, 997.66, 999.97, 1002.26, 1004.52,
    1006.77, 1009.01, 1011.22, 1013.42, 1015.6, 1017.76, 1019.9, 1022.03,
    1024.14, 1026.24, 1028.32, 1030.39, 1032.44, 1034.47, 1036.5, 1038.5,
    1040.5, 1042.48, 1044.45, 1046.41, 1048.36, 1050.29, 1052.22, 1054.14,
    1056.04, 1057.94, 1059.83, 1061.71, 1063.59, 1065.45, 1067.32, 1069.18,
    1071.03, 1072.88, 1074.73, 1076.57, 1078.42, 1080.26, 1082.1, 1083.95,
    1085.8, 1087.65, 1089.5, 1091.36, 1093.22, 1095.09, 1096.97, 1098.86,
    1100.75, 1102.66, 1104.58, 1106.51, 1108.46, 1110.42, 1112.39, 1114.39,
    1116.4, 1118.43, 1120.48, 1122.56, 1124.66, 1126.78, 1128.93, 1131.11,
    1133.32, 1135.56, 1137.83,
]

ID_COLUMN = "id"

# Sub-range of wavelength columns the model was trained on.
FEATURE_RANGE = (643.75, 1048.36)


class SpectralParser:
    """Parses and validates the fixed-schema NIR spectral Excel format."""

    @staticmethod
    def parse_content(content: bytes, filename: str) -> pd.DataFrame:
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext not in ("xlsx", "xls"):
            raise ValueError(f"Unsupported file format: .{ext}. Use .xlsx or .xls")

        df = pd.read_excel(BytesIO(content))
        SpectralParser._validate_schema(df)
        return df.dropna(subset=[ID_COLUMN, *EXPECTED_WAVELENGTH_COLUMNS])

    @staticmethod
    def _validate_schema(df: pd.DataFrame) -> None:
        columns = list(df.columns)
        if not columns or columns[0] != ID_COLUMN:
            raise ValueError(
                f"First column must be named '{ID_COLUMN}', found '{columns[0] if columns else ''}'"
            )

        missing = [c for c in EXPECTED_WAVELENGTH_COLUMNS if c not in columns]
        if missing:
            raise ValueError(
                f"Missing {len(missing)} expected wavelength column(s), e.g. {missing[:5]}. "
                f"This file's column layout does not match the expected spectral format."
            )

    @staticmethod
    def extract_features(df: pd.DataFrame) -> pd.DataFrame:
        """Select the trained feature sub-range and convert to absorbance."""
        low, high = FEATURE_RANGE
        X = df.loc[:, low:high]
        return 2.0 - np.log10(X)
