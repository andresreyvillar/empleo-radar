import unittest

from radar.details import extract_details

HAYS = """¿Tienes experiencia en gestión de proyectos industriales?

📌 Funciones principales

✅ Planificación, seguimiento y gestión integral de proyectos industriales.
✅ Seguimiento de hitos, plazos y resolución de incidencias.

🎯 Requisitos

✔ Formación en Ingeniería, Diseño Industrial o similar.
✔ Experiencia de 3 a 5 años como Project Manager o posiciones similares.
✔ Nivel alto de inglés imprescindible.

🎁 ¿Qué ofrece la compañía?

✅ Contrato indefinido.
✅ Horario flexible.
✅ Jornada intensiva durante el verano.
✅ Salario entre 38.000€ y 45.000€ brutos anuales , según experiencia.

📍 Ubicación: Madrid

Si buscas crecer como Project Manager, estaremos encantados de conocerte."""

EURO = """¿Cuál será tu misión?

✏️ Identificación de oportunidades de financiación para proyectos de I+D+i.

Requisitos del puesto

¿Qué perfil buscamos?

Formación: Ingeniería Industrial, Informática o titulaciones similares.
Habilidades personales: capacidad de trabajo en equipo, capacidad de análisis y redacción.
Otros: inglés.

¿Qué ofrecemos?

¿Qué te ofrecemos?

✅ Contrato indefinido a jornada completa.
✅ Flexibilidad horaria y teletrabajo.
✅ Jornada intensiva los meses de verano

Contáctanos

En Euro-Funding creemos en la igualdad de oportunidades."""

CAPITOLE = """Requisitos

Mínimo 3 años de experiencia en análisis PMO.
Experiencia en uso de herramientas de automatización como Power Automate.

¿Por qué unirte a nosotros?

1.200€ al año en formación
Seguro médico privado gratuito

Tomar decisiones con agilidad y responder con flexibilidad ante imprevistos.
Coordinar las diferentes áreas implicadas: Comercial, Oficina Técnica, Compras.
Perfil orientado a resultados, con iniciativa, autónomo y resolutivo.
Salario
Banda salarial: 25\\.000 \\- 30\\.000 €"""

FLAT = "Buscamos Project Manager con 3 años de experiencia en gestión de proyectos. Ofrecemos salario de 32.000 € brutos anuales y horario flexible con teletrabajo."


class DetailsTests(unittest.TestCase):
    def test_sections_from_headings(self):
        d = extract_details(HAYS)
        self.assertEqual(d["requisitos"][0], "Formación en Ingeniería, Diseño Industrial o similar.")
        self.assertEqual(len(d["requisitos"]), 3)
        self.assertIn("Horario flexible.", d["ofrecen"])
        self.assertNotIn("Ubicación: Madrid", d["ofrecen"])          # stops at the next heading
        self.assertNotIn("Planificación, seguimiento y gestión integral de proyectos industriales.", d["requisitos"])
        self.assertTrue(d["claves"]["salario"].startswith("Salario entre 38.000€"))
        self.assertEqual(d["claves"]["horario"], "Horario flexible.")
        self.assertIn("3 a 5 años", d["claves"]["experiencia"])
        self.assertEqual(d["claves"]["contrato"], "Contrato indefinido.")

    def test_consecutive_headings_and_question_style(self):
        d = extract_details(EURO)
        self.assertEqual(d["requisitos"][0], "Formación: Ingeniería Industrial, Informática o titulaciones similares.")
        self.assertIn("Flexibilidad horaria y teletrabajo.", d["ofrecen"])
        self.assertNotIn("En Euro-Funding creemos en la igualdad de oportunidades.", d["ofrecen"])
        self.assertEqual(d["claves"]["modalidad"], "Flexibilidad horaria y teletrabajo.")

    def test_fallback_to_keyword_lines_when_no_headings(self):
        d = extract_details(FLAT)
        self.assertTrue(d["requisitos"])
        self.assertTrue(d["ofrecen"])
        self.assertIn("32.000 €", d["claves"]["salario"])

    def test_question_headings_close_sections_and_noisy_keys_are_skipped(self):
        d = extract_details(CAPITOLE)
        self.assertEqual(len(d["requisitos"]), 2)                      # stops at "¿Por qué unirte a nosotros?"
        self.assertIn("Seguro médico privado gratuito", d["ofrecen"])   # that heading opens the offer section
        self.assertNotIn("horario", d["claves"])                        # "flexibilidad" alone is not a schedule
        self.assertNotIn("modalidad", d["claves"])                      # "Oficina Técnica" is not a modality
        self.assertNotIn("contrato", d["claves"])                       # "autónomo y resolutivo" is not a contract
        self.assertTrue(d["claves"]["salario"].startswith("Banda salarial"))   # not the bare "Salario" line

    def test_empty_description(self):
        d = extract_details("")
        self.assertEqual(d, {"requisitos": [], "ofrecen": [], "claves": {}})


if __name__ == "__main__":
    unittest.main()
