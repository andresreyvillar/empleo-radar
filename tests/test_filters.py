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


def job(title, location="Madrid, Community of Madrid, Spain", description=ES_TEXT, remote=False, company="ACME"):
    return Job(id="t:1", source="test", title=title, company=company, location=location,
               url="https://example.test", description=description, remote_flag=remote)


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

    def test_source_remote_flag_without_hybrid_signal(self):
        v = self.f.evaluate(job("Project Manager", remote=True))
        self.assertTrue(v.accepted, v.reason)
        self.assertEqual(v.modality, "remoto")

    def test_hybrid_outside_galicia_rejected(self):
        v = self.f.evaluate(job("Project Manager", remote=True,
                                description=ES_TEXT + " Modelo híbrido con dos días de teletrabajo."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("location"))

    def test_onsite_outside_galicia_rejected(self):
        v = self.f.evaluate(job("Project Manager", "Barcelona, Spain"))
        self.assertFalse(v.accepted)

    # -- language -------------------------------------------------------------
    def test_english_description_rejected(self):
        v = self.f.evaluate(job("Project Manager", remote=True, description=EN_TEXT))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("language"))

    def test_spanish_ratio(self):
        self.assertGreater(spanish_ratio(ES_TEXT), 0.8)
        self.assertLess(spanish_ratio(EN_TEXT), 0.2)
        self.assertIsNone(spanish_ratio("Project Manager"))

    # -- technical requirements in the description ---------------------------
    def test_developer_experience_required_rejected(self):
        v = self.f.evaluate(job("Project Manager", remote=True,
                                description=ES_TEXT + " Imprescindible experiencia previa como desarrollador."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("text"))

    def test_technical_profile_not_required_is_neutralised(self):
        v = self.f.evaluate(job("Project Manager", remote=True,
                                description=ES_TEXT + " No es necesario un perfil técnico."))
        self.assertTrue(v.accepted, v.reason)

    def test_engineering_degree_required_rejected(self):
        v = self.f.evaluate(job("Coordinador de proyectos", remote=True,
                                description=ES_TEXT + " Formación: Grado en Ingeniería Informática."))
        self.assertFalse(v.accepted)
        self.assertTrue(v.reason.startswith("degree"))

    def test_engineering_company_description_is_not_a_degree_requirement(self):
        v = self.f.evaluate(job("PMO", remote=True,
                                description=ES_TEXT + " Somos una consultora de formación y servicios de ingeniería."))
        self.assertTrue(v.accepted, v.reason)

    def test_engineering_among_other_degrees_accepted(self):
        v = self.f.evaluate(job("Coordinador de proyectos", remote=True,
                                description=ES_TEXT + " Titulación universitaria en Ingeniería, ADE, Derecho o similar."))
        self.assertTrue(v.accepted, v.reason)

    # -- scoring --------------------------------------------------------------
    def test_pm_signals_raise_score(self):
        plain = self.f.evaluate(job("Project Manager", remote=True))
        rich = self.f.evaluate(job("Project Manager", remote=True,
                                   description=ES_TEXT + " Metodologías Agile y Scrum, uso de Jira. Sin experiencia previa necesaria."))
        self.assertGreater(rich.score, plain.score)
        self.assertIn("+Agile", rich.signals)

    def test_senior_and_years_lower_score(self):
        plain = self.f.evaluate(job("Project Manager", remote=True))
        hard = self.f.evaluate(job("Project Manager", remote=True,
                                   description=ES_TEXT + " Perfil senior con mínimo 5 años de experiencia. Inglés C1."))
        self.assertLess(hard.score, plain.score)


if __name__ == "__main__":
    unittest.main()
