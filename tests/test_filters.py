"""Filter rules exercised with titles seen in real searches."""
import unittest

from radar.config import load_config
from radar.filters import JobFilter
from radar.models import Job
from radar.text import spanish_ratio

ES_TEXT = (
    "Buscamos un/a Project Manager para coordinar proyectos con clientes y proveedores. "
    "Serás responsable de la planificación, el seguimiento de hitos y la comunicación con los stakeholders. "
    "Ofrecemos incorporación inmediata en un equipo dinámico. Requisitos: experiencia en gestión de proyectos."
)
EN_TEXT = (
    "We are looking for a Project Manager to join our team. You will be responsible for planning, "
    "tracking milestones and communicating with stakeholders. Experience with Agile is a must."
)


REMOTE = " Trabajo 100% remoto."


def job(title, location="Madrid, Community of Madrid, Spain", description=ES_TEXT, remote=False, company="ACME", labels=None):
    return Job(id="t:1", source="test", title=title, company=company, location=location,
               url="https://example.test", description=description, remote_flag=remote, labels=labels or [])


class FilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = JobFilter(load_config())

    # -- title gate -----------------------------------------------------------
    def test_pm_titles_pass_title_gate(self):
        for title in ["Project Manager", "GESTOR DE PROYECTOS", "Jefe/a de Proyecto (Project Manager)",
                      "Responsable de Proyectos", "Coordinadora de proyectos", "Técnico PMO",
                      "Project Manager Junior - Ourense (h/m)", "Digital Project Manager"]:
            self.assertTrue(self.f.title_passes(title), title)

    def test_technical_titles_fail_title_gate(self):
        for title in ["Project Manager ALM – Codebeamer - 3DExperience (Automoción)",
                      "Project Manager DATA/ IA -IBM", "Jefe de obra - Project manager",
                      "Project Manager (Microsoft Dynamics 365 F&SCM)", "IT Project Manager Java",
                      "Delineante Junior-Oficina Técnica", "Big Data Engineer | Scala & Spark | Remoto",
                      "Ingeniero de proyectos", "Construction Project Manager - Barcelona",
                      "Project Manager Data Centers", "Gestor de Proyectos I+D - Energía Cloud",
                      "PROJECT MANAGER OBRAS", "Project Manager Senior de Obras – Retail / Hostelería",
                      "PROJECT MANAGER DE EDIFICACIÓN HOTELERA (Alicante)", "Project Manager - Estructuras Metálicas",
                      "Project Manager Infraestructuras Workplace", "Jefe de Proyecto - Sector Automatización (h/m)"]:
            self.assertFalse(self.f.title_passes(title), title)

    # -- location rule --------------------------------------------------------
    def test_galicia_any_modality(self):
        v = self.f.evaluate(job("GESTOR DE PROYECTOS", "Pazos, Galicia, Spain", ES_TEXT + " Modalidad híbrida."))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.modality, "galicia")

    def test_indeed_galicia_region_code(self):
        v = self.f.evaluate(job("Project Manager", "Vigo, GA, ES"))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.modality, "galicia")

    def test_full_remote_outside_galicia(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Trabajo 100% remoto."))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.modality, "remoto")

    def test_portal_remote_flag_with_silent_text_is_accepted_but_flagged(self):
        v = self.f.evaluate(job("Project Manager", remote=True))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual((v.modality, v.workplace), ("remoto", "sin confirmar"))
        confirmed = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE))
        self.assertLess(v.score, confirmed.score)

    def test_silent_text_without_remote_flag_is_rejected(self):
        v = self.f.evaluate(job("Project Manager"))
        self.assertFalse(v.accepted)
        self.assertEqual(v.workplace, "sin especificar")

    def test_remote_word_in_text_without_onsite_hints_is_remote(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Modalidad de trabajo: teletrabajo."))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.modality, "remoto")

    def test_remote_label_overridden_by_onsite_text(self):
        for phrase in ["Residencia en Las Palmas, ya que el puesto requiere presencialidad en cliente.",
                       "Flexibilidad: de lunes a jueves en las oficinas, y los viernes podrás teletrabajar.",
                       "Trabajo presencial en nuestras oficinas de Madrid.",
                       "Teletrabajo los viernes."]:
            v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Trabajo en remoto. " + phrase, labels=["remoto"]))
            self.assertFalse(v.accepted, phrase)
            self.assertTrue(v.reason.startswith("location"), phrase)

    def test_portal_labels_decide_when_text_is_silent(self):
        remote = self.f.evaluate(job("Project Manager", labels=["remoto"]))
        self.assertTrue(remote.accepted, remote.reason)
        self.assertEqual(remote.workplace, "remoto")
        onsite = self.f.evaluate(job("Project Manager", labels=["presencial", "hibrido"]))
        self.assertFalse(onsite.accepted)
        self.assertEqual(onsite.workplace, "hibrido")
        vigo_onsite = self.f.evaluate(job("Project Manager", "Vigo, Galicia, Spain", labels=["presencial"]))
        self.assertTrue(vigo_onsite.accepted, vigo_onsite.reason)
        self.assertEqual(vigo_onsite.workplace, "presencial")

    def test_onsite_label_beats_remote_words_in_text(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Posibilidad de teletrabajo.", labels=["presencial"]))
        self.assertFalse(v.accepted)
        self.assertEqual(v.workplace, "presencial")

    def test_explicit_full_remote_wins_over_occasional_onsite_mentions(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Puesto 100% remoto con reuniones presenciales puntuales."))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.workplace, "remoto")

    def test_negated_onsite_requirement_is_ignored(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Trabajo en remoto. No es necesario acudir a la oficina."))
        self.assertTrue(v.accepted, v.reason)

    def test_onsite_allowed_only_in_pontevedra(self):
        onsite = ES_TEXT + " Trabajo presencial en nuestras oficinas."
        vigo = self.f.evaluate(job("Project Manager", "Vigo, Galicia, Spain", onsite))
        self.assertTrue(vigo.accepted, vigo.reason)
        self.assertEqual((vigo.modality, vigo.workplace), ("galicia", "presencial"))
        coruna = self.f.evaluate(job("Project Manager", "A Coruña, Galicia, Spain", onsite))
        self.assertFalse(coruna.accepted)
        hybrid_coruna = self.f.evaluate(job("Project Manager", "A Coruña, Galicia, Spain", ES_TEXT + " Modalidad híbrida."))
        self.assertTrue(hybrid_coruna.accepted, hybrid_coruna.reason)
        self.assertEqual(hybrid_coruna.workplace, "hibrido")

    def test_region_only_location_uses_description_city(self):
        v = self.f.evaluate(job("Project Manager", "Galicia, España", ES_TEXT + " Puesto presencial en nuestra planta de Vigo."))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.workplace, "presencial")

    def test_hybrid_outside_galicia_rejected(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + " Modelo híbrido con dos días de teletrabajo."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("location"))

    def test_onsite_outside_galicia_rejected(self):
        v = self.f.evaluate(job("Project Manager", "Barcelona, Spain"))
        self.assertFalse(v.accepted)

    # -- language -------------------------------------------------------------
    def test_english_description_rejected(self):
        v = self.f.evaluate(job("Project Manager", description=EN_TEXT + REMOTE))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("language"))

    def test_spanish_ratio(self):
        self.assertGreater(spanish_ratio(ES_TEXT), 0.8)
        self.assertLess(spanish_ratio(EN_TEXT), 0.2)
        self.assertIsNone(spanish_ratio("Project Manager"))

    # -- technical requirements in the description ---------------------------
    def test_developer_experience_required_rejected(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE + " Imprescindible experiencia previa como desarrollador."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("text"))

    def test_technical_profile_not_required_is_neutralised(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE + " No es necesario un perfil técnico."))
        self.assertTrue(v.accepted, v.reason)

    def test_engineering_degree_required_rejected(self):
        v = self.f.evaluate(job("Coordinador de proyectos", description=ES_TEXT + REMOTE + " Formación: Grado en Ingeniería Informática."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("degree"))

    def test_engineering_company_description_is_not_a_degree_requirement(self):
        v = self.f.evaluate(job("PMO", description=ES_TEXT + REMOTE + " Somos una consultora de formación y servicios de ingeniería."))
        self.assertTrue(v.accepted, v.reason)

    def test_engineering_or_similar_engineering_rejected(self):
        v = self.f.evaluate(job("Project Manager Junior", "Ourense, Galicia, Spain",
                                description=ES_TEXT + " Grado en Ingeniería Industrial, Ingeniería de Organización Industrial o similar."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("degree"))

    def test_neutraliser_in_another_sentence_does_not_apply(self):
        v = self.f.evaluate(job("Project Manager Junior", description=ES_TEXT + REMOTE + " Formación: Ingeniería Industrial, Telecomunicaciones, Informática o titulaciones similares. Se valorarán conocimientos en finanzas."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("degree"))

    def test_engineering_among_other_degrees_accepted(self):
        v = self.f.evaluate(job("Coordinador de proyectos", description=ES_TEXT + REMOTE + " Titulación universitaria en Ingeniería, ADE, Derecho o similar."))
        self.assertTrue(v.accepted, v.reason)

    # -- languages ------------------------------------------------------------
    def test_high_english_required_rejected(self):
        for phrase in ["Inglés alto imprescindible.", "Nivel de inglés C1.", "Inglés: C1", "Inglés fluido.",
                       "Nivel alto de inglés.", "English C1 required.", "Perfil bilingüe inglés-español."]:
            v = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE + " " + phrase))
            self.assertFalse(v.accepted, phrase)
            self.assertTrue(v.reason.startswith("text"), phrase)

    def test_intermediate_english_accepted(self):
        for phrase in ["Inglés B2.", "Inglés intermedio.", "Inglés conversacional.", "Inglés profesional.",
                       "Nivel medio-alto de inglés.", "Inglés medio-alto.", "Valorable inglés alto.",
                       "No es imprescindible inglés alto."]:
            v = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE + " " + phrase))
            self.assertTrue(v.accepted, f"{phrase} -> {v.reason}")

    def test_other_languages_required_rejected(self):
        for title, phrase in [("Project Manager Junior (CHINO alto)", ""),
                              ("Project Manager", "Imprescindible nivel alto de francés."),
                              ("Project Manager", "Idiomas: alemán C1."),
                              ("Gestor de proyectos", "Portugués nativo.")]:
            v = self.f.evaluate(job(title, description=ES_TEXT + REMOTE + " " + phrase))
            self.assertFalse(v.accepted, title + phrase)

    def test_other_language_only_valued_is_accepted(self):
        v = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE + " Se valorará francés."))
        self.assertTrue(v.accepted, v.reason)

    # -- scoring --------------------------------------------------------------
    def test_pm_signals_raise_score(self):
        plain = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE))
        rich = self.f.evaluate(job("Project Manager",
                                   description=ES_TEXT + REMOTE + " Metodologías Agile y Scrum, uso de Jira. Sin experiencia previa necesaria."))
        self.assertGreater(rich.score, plain.score)
        self.assertIn("+Agile", rich.signals)

    def test_senior_and_years_lower_score(self):
        plain = self.f.evaluate(job("Project Manager", description=ES_TEXT + REMOTE))
        hard = self.f.evaluate(job("Project Manager",
                                   description=ES_TEXT + REMOTE + " Perfil senior con mínimo 5 años de experiencia."))
        self.assertLess(hard.score, plain.score)

    # -- deduplication --------------------------------------------------------
    def test_fingerprint_ignores_company_suffixes(self):
        a = job("Innovation Project Manager A Coruña o Madrid", company="Nauterra España")
        b = job("Innovation Project Manager A Coruña o Madrid", company="NAUTERRA")
        c = job("Innovation Project Manager A Coruña o Madrid", company="Otra Empresa")
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertNotEqual(a.fingerprint, c.fingerprint)


if __name__ == "__main__":
    unittest.main()
