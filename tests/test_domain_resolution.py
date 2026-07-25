import unittest

from Api.deepseek_client import DeepSeekClient


class DomainResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = DeepSeekClient()

    def test_corporate_learning_wins_over_generic_development_marker(self) -> None:
        position = "Менеджер по корпоративному обучению"
        duties = "Разработка программ обучения, организация тренингов, работа с LMS и подрядчиками"
        industry = "Корпоративное обучение"

        family = self.client._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=industry,
        )
        profile = self.client._fallback_domain_profile(
            position=position,
            duties=duties,
            company_industry=industry,
            role_name=None,
        )

        self.assertEqual(family, "learning_and_development")
        self.assertTrue(
            self.client._should_prioritize_runtime_domain(
                position=position,
                duties=duties,
                company_industry=industry,
            )
        )
        self.assertEqual(profile["domain_label"], "обучения и развития персонала")
        self.assertTrue(any("обуч" in item.lower() for item in profile["processes"]))
        self.assertFalse(any("чертеж" in item.lower() or "plm" in item.lower() for item in profile["systems"]))

    def test_learning_profile_rejects_engineering_llm_domain_payload(self) -> None:
        fallback = self.client._fallback_domain_profile(
            position="Специалист по обучению",
            duties="Разрабатывает учебные курсы и проводит тренинги",
            company_industry="Корпоративное обучение",
            role_name=None,
        )
        normalized = self.client._normalize_domain_profile_with_profile(
            {
                "domain_label": "разработка программных продуктов",
                "processes": ["выпуск релиза"],
                "tasks": ["проверить код"],
                "stakeholders": ["команда разработки"],
                "systems": ["Git и PLM"],
                "artifacts": ["репозиторий"],
                "risks": ["срыв релиза"],
                "constraints": ["окно деплоя"],
            },
            fallback,
            position="Специалист по обучению",
            duties="Разрабатывает учебные курсы и проводит тренинги",
            company_industry="Корпоративное обучение",
        )

        self.assertEqual(normalized, fallback)


if __name__ == "__main__":
    unittest.main()
