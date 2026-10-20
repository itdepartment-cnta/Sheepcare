"""La observación de calidad de leche usa «alta/media», igual que la nube.

Es una convención común entre los dos calendarios (ver
version_cloud/docs/CONVENCIONES_FARM_CALENDAR_LECHE.md en Sheepcare_cloud): si el texto
difiere, la misma subida sale distinta en el Farm Calendar de la nube y en el local.
Lower = calidad alta (menos de 500000 células somáticas); Upper = calidad media.

    python -m unittest backend.tests.test_leche_alta_media -v

El Farm Calendar está simulado: no toca uno real.
"""
import unittest
from unittest import mock

from backend.data_access.farmcalendar_client import FarmCalendarClient


def _publicar(buena, mala, sample_details=None, details_text=None):
    """Devuelve el cuerpo que el cliente enviaría a Farm Calendar."""
    cliente = FarmCalendarClient(api_url="http://fc.invalid/api/v1/", jwt_signing_key="x" * 40)
    cliente._session = mock.Mock()
    cliente._session.post.return_value = mock.Mock(status_code=201)
    with mock.patch.object(cliente, "_ensure_auth"), \
            mock.patch.object(cliente, "get_or_create_milk_quality_activity_type", return_value="urn:tipo"):
        ok = cliente.post_milk_quality_detection(
            "Granja X", buena, mala, "leche.xlsx", upload_date="2026-03-11T09:00:00+00:00",
            details_text=details_text, sample_details=sample_details,
        )
    assert ok
    return cliente._session.post.call_args.kwargs["json"]


class LecheAltaMediaTest(unittest.TestCase):
    def test_el_valor_dice_media_primero_y_alta_despues(self):
        cuerpo = _publicar(3, 1)
        self.assertEqual(cuerpo["hasResult"]["hasValue"], "Calidad media: 1, Calidad alta: 3")

    def test_el_detalle_con_muestras_sigue_la_convencion_comun(self):
        muestras = [
            {"animal_id": "M1", "result": "Upper"},
            {"animal_id": "M2", "result": "Lower"},
            {"animal_id": "M3", "result": "Lower"},
            {"animal_id": "M4", "result": "Lower"},
        ]
        detalle = _publicar(3, 1, sample_details=muestras)["details"]
        self.assertEqual(
            detalle,
            "Archivo: leche.xlsx\n"
            "🟠 Calidad media: 1\n"
            "🟢 Calidad alta: 3\n"
            "\n"
            "🟠 CALIDAD MEDIA:\n"
            "  M1\n"
            "🟢 CALIDAD ALTA:\n"
            "  M2\n"
            "  M3\n"
            "  M4",
        )

    def test_solo_salen_las_categorias_con_muestras(self):
        detalle = _publicar(2, 0, sample_details=[
            {"animal_id": "M1", "result": "Lower"}, {"animal_id": "M2", "result": "Lower"},
        ])["details"]
        self.assertNotIn("media", detalle.lower())
        self.assertIn("🟢 Calidad alta: 2", detalle)

    def test_el_detalle_sin_muestras_es_una_sola_linea(self):
        detalle = _publicar(3, 1)["details"]
        self.assertEqual(detalle, "Archivo: leche.xlsx | 🟠 Calidad media: 1 | 🟢 Calidad alta: 3")

    def test_un_detalle_ya_redactado_se_respeta(self):
        self.assertEqual(_publicar(3, 1, details_text="texto propio")["details"], "texto propio")

    def test_no_queda_el_vocabulario_antiguo(self):
        cuerpo = _publicar(3, 1, sample_details=[{"animal_id": "M1", "result": "Upper"}])
        texto = (cuerpo["details"] + cuerpo["hasResult"]["hasValue"] + cuerpo["title"]).lower()
        for viejo in ("buena", "mala", "🔴"):
            self.assertNotIn(viejo, texto)

    def test_lo_que_no_cambia(self):
        cuerpo = _publicar(3, 1)
        self.assertEqual(cuerpo["title"], "Calidad de leche — Granja X")
        self.assertEqual(cuerpo["observedProperty"], "milk_quality_scc")
        self.assertEqual(cuerpo["madeBySensor"]["name"], "SHEEPCARE Milk Quality Engine")
        self.assertEqual(cuerpo["phenomenonTime"], "2026-03-11T09:00:00+00:00")
        self.assertEqual(cuerpo["activityType"], "urn:tipo")


if __name__ == "__main__":
    unittest.main()
