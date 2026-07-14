from platform_scan.collectors import ai_info, cluster_info, driver_info, llm_info, platform_info, reliability_info


COLLECTORS = [
    ("platform", platform_info.TITLE, platform_info.collect),
    ("llm", llm_info.TITLE, llm_info.collect),
    ("cluster", cluster_info.TITLE, cluster_info.collect),
    ("ai", ai_info.TITLE, ai_info.collect),
    ("driver", driver_info.TITLE, driver_info.collect),
    ("reliability", reliability_info.TITLE, reliability_info.collect),
]
