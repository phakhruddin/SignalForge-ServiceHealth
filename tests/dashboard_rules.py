"""Semantic checks for CloudWatch dashboard metric math."""

import re


def has_journey_ratio(body, namespace, deployment):
    """Find a Good/Total expression linked to the real summed canary series."""
    for widget in body.get("widgets", []):
        if widget.get("type") != "metric":
            continue

        metric_ids = {}
        expressions = []
        for row in widget.get("properties", {}).get("metrics", []):
            if not isinstance(row, list) or not row:
                continue
            if len(row) == 1 and isinstance(row[0], dict):
                expression = row[0].get("expression")
                if isinstance(expression, str):
                    expressions.append(expression)
                continue
            if len(row) < 7 or not isinstance(row[-1], dict):
                continue

            dimension_pairs = row[2:-1]
            if len(dimension_pairs) % 2:
                continue
            dimensions = dict(zip(dimension_pairs[::2], dimension_pairs[1::2]))
            if (row[0] != namespace or row[1] not in ("JourneyGood", "JourneyTotal")
                    or dimensions.get("Deployment") != deployment
                    or dimensions.get("Service") != "canary"
                    or row[-1].get("stat") != "Sum"):
                continue

            metric_id = row[-1].get("id")
            if isinstance(metric_id, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", metric_id):
                metric_ids[metric_id.lower()] = row[1]

        good_ids = [key for key, name in metric_ids.items() if name == "JourneyGood"]
        total_ids = [key for key, name in metric_ids.items() if name == "JourneyTotal"]
        for expression in expressions:
            normalized = re.sub(r"[\s()]", "", expression).lower()
            for good_id in good_ids:
                for total_id in total_ids:
                    ratio = rf"(?<![a-z0-9_]){re.escape(good_id)}/{re.escape(total_id)}(?![a-z0-9_])"
                    if re.search(ratio, normalized):
                        return True
    return False
