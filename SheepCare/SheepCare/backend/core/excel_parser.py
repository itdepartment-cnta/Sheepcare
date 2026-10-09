"""
Excel/CSV Parser - Reads animal data files in wide format.
Hoja "datos": Col A = ID_ANIMAL, Col B+ = fechas con valores.

Supports both .xlsx (openpyxl) and .csv files.
"""

import os
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from io import StringIO, BytesIO


class ExcelParser:
    """
    Parses Excel (.xlsx) and CSV files containing animal resistance data.

    Expected format (wide):
        Col A: ID_ANIMAL (animal identifier)
        Col B+: Date columns with resistance values
    """

    @staticmethod
    def _numerar_lecturas(animals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Numera las lecturas y decide, para todo el fichero, si llevan fecha.

        Cada lectura sale con `order` (1 la primera del animal, 2 la segunda): es lo
        único que garantiza el fichero. La fecha solo se conserva si TODAS las
        cabeceras eran fechas reales; si una sola no lo es, van todas sin fecha
        (`None`). Antes se guardaba la etiqueta de la columna («date_1», «dia 2»)
        como si fuera una fecha. Mezclar lecturas con y sin fecha en una misma
        subida parte el historial en dos, y por eso la decisión es del fichero
        entero (igual que en el backend público).
        """

        def es_fecha_iso(valor) -> bool:
            try:
                datetime.strptime(str(valor), "%Y-%m-%d")
                return True
            except (ValueError, TypeError):
                return False

        con_fecha = all(
            es_fecha_iso(r.get("date")) for a in animals for r in a["readings"]
        )
        for animal in animals:
            for i, lectura in enumerate(animal["readings"]):
                lectura["order"] = i + 1
                if not con_fecha:
                    lectura["date"] = None
        return animals

    @staticmethod
    def parse(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse a file and return structured animal data.

        Returns:
            List of dicts: [{
                'animal_id': str,
                'readings': [{'date': str (YYYY-MM-DD), 'value': float}, ...]
            }, ...]
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return ExcelParser._parse_excel(file_path)
        elif ext == ".csv":
            return ExcelParser._parse_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Use .xlsx or .csv")

    @staticmethod
    def parse_content(content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Parse file content from bytes (e.g., uploaded file).
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".xlsx", ".xls"):
            return ExcelParser._parse_excel_bytes(content)
        elif ext == ".csv":
            return ExcelParser._parse_csv_bytes(content)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _parse_excel(file_path: str) -> List[Dict[str, Any]]:
        """Parse an .xlsx file."""
        import openpyxl

        wb = openpyxl.load_workbook(file_path, data_only=True)

        # Try to find the "datos" sheet, fall back to first sheet
        sheet_name = "datos" if "datos" in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]

        return ExcelParser._parse_worksheet(ws)

    @staticmethod
    def _parse_excel_bytes(content: bytes) -> List[Dict[str, Any]]:
        """Parse an .xlsx file from bytes."""
        import openpyxl

        wb = openpyxl.load_workbook(BytesIO(content), data_only=True)

        sheet_name = "datos" if "datos" in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]

        return ExcelParser._parse_worksheet(ws)

    @staticmethod
    def _parse_worksheet(ws) -> List[Dict[str, Any]]:
        """Parse an openpyxl worksheet."""
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        # First row: detect column structure
        header = rows[0]
        if (
            header
            and header[0]
            and str(header[0]).strip().upper()
            in ("ID_ANIMAL", "ANIMAL", "ID", "ANIMAL ID", "IDENTIFICACION", "IDENTIFICACIÓN")
        ):
            rows = rows[1:]  # Skip header row

        if not rows:
            return []

        # Las fechas, si las hay, están en las celdas B en adelante de la PRIMERA fila
        # (la cabecera). Antes se buscaban en la primera fila de DATOS: con la
        # cabecera ya saltada eso nunca encontraba nada, y hasta un Excel con fechas
        # reales salía con «date_1», «date_2».
        date_columns = [
            ExcelParser._try_parse_date(header[col_idx]) for col_idx in range(1, len(header))
        ]

        if not any(date_columns):
            # Sin fechas: se numeran las columnas (`_numerar_lecturas` las deja sin fecha)
            date_columns = [f"col_{col_idx}" for col_idx in range(1, len(rows[0]))]

        # Parse each animal row
        result = []
        for row in rows:
            if not row or row[0] is None:
                continue  # Skip empty rows

            animal_id = str(row[0]).strip()
            if not animal_id:
                continue

            readings = []
            for col_idx, date_str in enumerate(date_columns, start=1):
                if col_idx >= len(row):
                    break
                value = row[col_idx]
                if value is None:
                    continue
                try:
                    val = float(value)
                    readings.append(
                        {
                            "date": (
                                date_str
                                if date_str and not date_str.startswith("col_")
                                else f"date_{col_idx}"
                            ),
                            "value": val,
                        }
                    )
                except (ValueError, TypeError):
                    continue  # Skip non-numeric values

            if readings:
                result.append(
                    {
                        "animal_id": animal_id,
                        "readings": readings,
                    }
                )

        return ExcelParser._numerar_lecturas(result)

    @staticmethod
    def _try_parse_date(val) -> Optional[str]:
        """Try to parse a value as a date string. Returns YYYY-MM-DD or None."""
        if val is None:
            return None

        # openpyxl can return datetime objects
        if hasattr(val, "strftime"):
            try:
                return val.strftime("%Y-%m-%d")
            except Exception:
                return str(val).strip()

        val_str = str(val).strip()

        # Try common date formats
        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y%m%d",
            "%d.%m.%Y",
        ):
            try:
                return datetime.strptime(val_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    @staticmethod
    def _parse_csv(file_path: str) -> List[Dict[str, Any]]:
        """Parse a CSV file."""
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        return ExcelParser._parse_csv_content(content)

    @staticmethod
    def _parse_csv_bytes(content: bytes) -> List[Dict[str, Any]]:
        """Parse a CSV file from bytes."""
        return ExcelParser._parse_csv_content(content.decode("utf-8-sig"))

    @staticmethod
    def _parse_csv_content(content: str) -> List[Dict[str, Any]]:
        """Parse CSV content string."""
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        if not rows:
            return []

        # Detect header
        header_rows = 0
        if (
            rows
            and rows[0]
            and rows[0][0].strip().upper()
            in ("ID_ANIMAL", "ANIMAL", "ID", "ANIMAL ID", "IDENTIFICACION", "IDENTIFICACIÓN")
        ):
            header_rows = 1

        # Parse date columns from header if available
        date_columns = []
        if header_rows > 0 and len(rows[0]) > 1:
            for col_idx in range(1, len(rows[0])):
                val = rows[0][col_idx].strip()
                parsed = ExcelParser._try_parse_date(val)
                date_columns.append(parsed or val)
        elif len(rows) > 1 and len(rows[1]) > 1:
            # Use first data row's header positions
            for col_idx in range(1, len(rows[1])):
                date_columns.append(f"date_{col_idx}")
        else:
            for col_idx in range(1, len(rows[0])):
                date_columns.append(f"date_{col_idx}")

        # Parse data rows
        result = []
        data_rows = rows[header_rows:] if header_rows else rows

        for row in data_rows:
            if not row or not row[0].strip():
                continue

            animal_id = row[0].strip()
            readings = []

            for col_idx, date_str in enumerate(date_columns, start=1):
                if col_idx >= len(row):
                    break
                val_str = row[col_idx].strip()
                if not val_str:
                    continue
                try:
                    val = float(val_str)
                    readings.append(
                        {
                            "date": date_str,
                            "value": val,
                        }
                    )
                except ValueError:
                    continue

            if readings:
                result.append(
                    {
                        "animal_id": animal_id,
                        "readings": readings,
                    }
                )

        return ExcelParser._numerar_lecturas(result)

    @staticmethod
    def detect_date_columns(file_path: str) -> List[str]:
        """
        Quick scan to detect date column headers without parsing all data.
        Useful for preview purposes.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            import openpyxl

            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet_name = "datos" if "datos" in wb.sheetnames else wb.sheetnames[0]
            ws = wb[sheet_name]
            header_row = next(ws.iter_rows(values_only=True), [])
        elif ext == ".csv":
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header_row = next(reader, [])
        else:
            return []

        dates = []
        for col_idx in range(1, len(header_row)):
            val = header_row[col_idx]
            parsed = ExcelParser._try_parse_date(val)
            if parsed:
                dates.append(parsed)
            else:
                dates.append(str(val).strip() if val else f"col_{col_idx}")
        return dates
