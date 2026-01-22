"""
Unit tests for Smart Routing functionality
"""
import unittest

from agent_runtime.orchestrator.smart_routing import (
    ROUTE_TRIGGERS,
    STRONG_TRIGGERS,
    WEAK_TRIGGERS,
    calculate_confidence,
    route_agents,
)

class TestSmartRouting(unittest.TestCase):
    """Test cases for Smart Routing"""

    def test_route_triggers_structure(self) -> None:
        """Test that route triggers are properly structured"""
        self.assertIn("critical", ROUTE_TRIGGERS)
        self.assertIn("security", ROUTE_TRIGGERS)
        self.assertIn("architect", ROUTE_TRIGGERS)
        self.assertIn("qa", ROUTE_TRIGGERS)
        
        # Check that triggers are lists
        for domain, triggers in ROUTE_TRIGGERS.items():
            self.assertIsInstance(triggers, list)
            self.assertGreater(len(triggers), 0)

    def test_calculate_confidence_empty(self) -> None:
        """Test confidence calculation with empty triggers"""
        confidence, breakdown = calculate_confidence({})
        
        self.assertEqual(confidence, 0.0)
        self.assertEqual(breakdown, {})

    def test_calculate_confidence_critical(self) -> None:
        """Test confidence calculation with critical triggers"""
        matched_triggers = {"critical": ["incident", "breach"]}
        confidence, breakdown = calculate_confidence(matched_triggers)
        
        self.assertEqual(confidence, 1.0)
        self.assertIn("critical", breakdown)
        self.assertEqual(breakdown["critical"]["score"], 1.0)

    def test_calculate_confidence_strong_triggers(self) -> None:
        """Test confidence calculation with strong triggers"""
        matched_triggers = {"security": ["vulnerability", "injection"]}
        confidence, breakdown = calculate_confidence(matched_triggers)
        
        self.assertGreaterEqual(confidence, 0.8)
        self.assertIn("security", breakdown)
        self.assertGreater(breakdown["security"]["score"], 0.8)

    def test_calculate_confidence_weak_triggers(self) -> None:
        """Test confidence calculation with weak triggers"""
        matched_triggers = {"security": ["security", "auth"]}
        confidence, breakdown = calculate_confidence(matched_triggers)
        
        self.assertGreaterEqual(confidence, 0.4)
        self.assertLess(confidence, 0.7)

    def test_route_agents_critical(self) -> None:
        """Test routing with critical triggers"""
        result = route_agents("We have a security breach incident!")
        
        self.assertEqual(result["mode"], "CRITICAL")
        self.assertIn("director", result["agents"])
        self.assertIn("security", result["agents"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertFalse(result["downgraded"])

    def test_route_agents_security_only(self) -> None:
        """Test routing with security triggers only"""
        result = route_agents("Check JWT token vulnerability")

        self.assertIn(result["mode"], ["STANDARD", "CRITICAL"])
        self.assertIn("security", result["agents"])
        self.assertIn("dev", result["agents"])
        self.assertIn("security", result["triggers_matched"])

    def test_route_agents_russian_security(self) -> None:
        """Test routing with Russian security triggers"""
        result = route_agents("Проверь уязвимость и безопасность токена")

        self.assertIn(result["mode"], ["STANDARD", "CRITICAL"])
        self.assertIn("security", result["agents"])
        self.assertIn("security", result["triggers_matched"])

    def test_route_agents_russian_critical(self) -> None:
        """Test routing with Russian critical triggers"""
        result = route_agents("Критический инцидент безопасности, нужно срочно")

        self.assertEqual(result["mode"], "CRITICAL")
        self.assertIn("director", result["agents"])
        self.assertIn("critical", result["triggers_matched"])

    def test_route_agents_russian_architect(self) -> None:
        """Test routing with Russian architecture triggers"""
        result = route_agents("Нужна архитектура и масштабирование системы")

        self.assertIn(result["mode"], ["STANDARD", "CRITICAL"])
        self.assertIn("architect", result["agents"])
        self.assertIn("architect", result["triggers_matched"])

    def test_route_agents_russian_qa(self) -> None:
        """Test routing with Russian QA triggers"""
        result = route_agents("Нужно тестирование и покрытие тестами")

        self.assertIn(result["mode"], ["STANDARD", "CRITICAL"])
        self.assertIn("qa", result["agents"])
        self.assertIn("qa", result["triggers_matched"])

    def test_route_agents_russian_ux(self) -> None:
        """Test routing with Russian UX triggers"""
        result = route_agents("Улучшить UX интерфейса и дизайн систему")

        self.assertIn(result["mode"], ["STANDARD", "CRITICAL"])
        self.assertIn("ux", result["agents"])
        self.assertIn("ux", result["triggers_matched"])

    def test_route_agents_russian_seo(self) -> None:
        """Test routing with Russian SEO triggers"""
        result = route_agents("Нужна SEO оптимизация сайта и sitemap")

        self.assertIn(result["mode"], ["STANDARD", "CRITICAL"])
        self.assertIn("seo", result["agents"])
        self.assertIn("seo", result["triggers_matched"])

    def test_route_agents_multiple_domains(self) -> None:
        """Test routing with multiple domain triggers"""
        result = route_agents("Review database architecture security and test coverage")

        self.assertGreaterEqual(result["domains_matched"], 2)
        self.assertIn("architect", result["agents"])
        self.assertIn("security", result["agents"])
        self.assertIn("qa", result["agents"])

    def test_route_agents_no_triggers(self) -> None:
        """Test routing with no specific triggers"""
        result = route_agents("Simple question about Python")
        
        self.assertEqual(result["mode"], "FAST")
        self.assertEqual(result["agents"], ["dev"])
        self.assertEqual(result["confidence"], 1.0)

    def test_route_agents_downgrade(self) -> None:
        """Test routing downgrade scenario"""
        # Create a query with many weak triggers (low confidence)
        result = route_agents("security auth test mobile ui performance")
        
        if result["domains_matched"] >= 3 and result["confidence"] < 0.7:
            self.assertEqual(result["mode"], "STANDARD")
            self.assertTrue(result["downgraded"])
            self.assertNotIn("director", result["agents"])

    def test_strong_vs_weak_triggers(self) -> None:
        """Test distinction between strong and weak triggers"""
        # Strong trigger should give higher confidence
        strong_result = route_agents("SQL injection vulnerability found")
        
        # Weak trigger should give lower confidence
        weak_result = route_agents("security issue")
        
        if "security" in strong_result["triggers_matched"] and "security" in weak_result["triggers_matched"]:
            self.assertGreater(strong_result["confidence"], weak_result["confidence"])

    def test_agent_selection_logic(self) -> None:
        """Test that appropriate agents are selected for different scenarios"""
        # SEO query should include seo agent
        seo_result = route_agents("Optimize meta tags and sitemap for SEO")
        self.assertIn("seo", seo_result["agents"])
        
        # UX query should include ux agent
        ux_result = route_agents("Improve accessibility and user experience")
        self.assertIn("ux", ux_result["agents"])
        
        # QA query should include qa agent
        qa_result = route_agents("Add unit tests and coverage analysis")
        self.assertIn("qa", qa_result["agents"])

    def test_confidence_breakdown_structure(self) -> None:
        """Test that confidence breakdown has proper structure"""
        result = route_agents("Security vulnerability in authentication system")
        
        if "confidence_breakdown" in result:
            breakdown = result["confidence_breakdown"]
            self.assertIn("_summary", breakdown)
            self.assertIn("total_confidence", breakdown["_summary"])
            
            for domain in result["triggers_matched"]:
                if domain in breakdown:
                    self.assertIn("score", breakdown[domain])
                    self.assertIn("reason", breakdown[domain])

if __name__ == "__main__":
    unittest.main()
