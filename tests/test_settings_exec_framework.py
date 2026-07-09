from skillhub_eval.settings import Settings


def test_exec_framework_timeouts_have_defaults():
    s = Settings()
    assert s.model_discovery_timeout_s == 20.0
    assert s.agent_detect_cache_ttl_s == 86400
