"""El parser de celo ya no inventa fechas: sin cabeceras de fecha, la lectura va por orden.

    python -m unittest backend.tests.test_excel_parser_fechas -v
"""
import io
import unittest
from datetime import datetime

import openpyxl

from backend.core.excel_parser import ExcelParser


def _xlsx(cabecera, filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(cabecera)
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _lecturas(datos, animal=0):
    return [(r["date"], r["order"], r["value"]) for r in datos[animal]["readings"]]


class ConCabecerasDeFecha(unittest.TestCase):
    def test_cabeceras_de_texto_iso_conservan_la_fecha_y_llevan_orden(self):
        d = ExcelParser.parse_content(_xlsx(["animal", "2026-05-18", "2026-05-19"], [["A-1", 300, 250]]), "t.xlsx")
        self.assertEqual(_lecturas(d), [("2026-05-18", 1, 300.0), ("2026-05-19", 2, 250.0)])

    def test_celdas_de_fecha_de_excel_tambien(self):
        d = ExcelParser.parse_content(
            _xlsx(["animal", datetime(2026, 5, 18), datetime(2026, 5, 19)], [["A-1", 300, 250]]), "t.xlsx")
        self.assertEqual(_lecturas(d), [("2026-05-18", 1, 300.0), ("2026-05-19", 2, 250.0)])


class SinFechas(unittest.TestCase):
    def test_dia_1_dia_2_no_inventa_fecha(self):
        d = ExcelParser.parse_content(_xlsx(["animal", "dia 1", "dia 2"], [["A-1", 300, 250], ["A-2", 200, 190]]), "t.xlsx")
        self.assertEqual(_lecturas(d, 0), [(None, 1, 300.0), (None, 2, 250.0)])
        self.assertEqual(_lecturas(d, 1), [(None, 1, 200.0), (None, 2, 190.0)])

    def test_la_decision_es_del_fichero_entero(self):
        # Una cabecera es fecha y la otra no: todas van sin fecha (no se parte el historial en dos)
        d = ExcelParser.parse_content(_xlsx(["animal", "2026-05-18", "dia 2"], [["A-1", 300, 250]]), "t.xlsx")
        self.assertEqual(_lecturas(d), [(None, 1, 300.0), (None, 2, 250.0)])

    def test_un_hueco_no_rompe_el_orden(self):
        d = ExcelParser.parse_content(_xlsx(["animal", "dia 1", "dia 2", "dia 3"], [["A-1", 300, None, 250]]), "t.xlsx")
        self.assertEqual(_lecturas(d), [(None, 1, 300.0), (None, 2, 250.0)])

    def test_csv_con_etiquetas_tampoco_guarda_la_etiqueta_como_fecha(self):
        d = ExcelParser.parse_content(b"animal,dia 1,dia 2\nA-1,300,250\n", "t.csv")
        self.assertEqual(_lecturas(d), [(None, 1, 300.0), (None, 2, 250.0)])

    def test_csv_con_fechas_las_conserva(self):
        d = ExcelParser.parse_content(b"animal,2026-05-18,2026-05-19\nA-1,300,250\n", "t.csv")
        self.assertEqual(_lecturas(d), [("2026-05-18", 1, 300.0), ("2026-05-19", 2, 250.0)])


if __name__ == "__main__":
    unittest.main()
