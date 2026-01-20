#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Decision insights from summary JSON.")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to decision summary JSON.")
    parser.add_argument("--lang", choices=["ru", "en"], default="ru", help="Language for output.")
    args = parser.parse_args()

    path = Path(args.input_path)
    if not path.exists():
        print("NO_INPUT")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    events = data.get("events") or 0
    confidence = data.get("confidence") or {}
    buckets = data.get("confidence_buckets") or {}
    top_next_steps = data.get("top_next_steps") or []

    translations = {
        "ru": {
            "low_conf": "низкая уверенность, нужно расширить smoke/coverage",
            "very_low_conf": "есть решения с очень низкой уверенностью",
            "low_data": "слишком мало данных для выводов",
            "need_more": "нужно собрать больше данных по решениям",
            "repeat_top": "повторяющийся next_step: \"{text}\" — возможно, стоит автоматизировать или оформить чеклист",
            "action": "Следующий шаг: увеличить покрытие smoke/CI и собрать больше решений",
            "insights": "Insights:",
            "action_label": "Action:",
        },
        "en": {
            "low_conf": "low confidence, expand smoke/coverage",
            "very_low_conf": "there are decisions with very low confidence",
            "low_data": "too little data to draw conclusions",
            "need_more": "collect more data on decisions",
            "repeat_top": "repeating next_step: \"{text}\" — consider automating or making a checklist",
            "action": "Next step: expand smoke/CI coverage and gather more decisions",
            "insights": "Insights:",
            "action_label": "Action:",
        },
    }
    t = translations[args.lang]

    insights = []
    mean_conf = confidence.get("mean")
    if isinstance(mean_conf, (int, float)) and mean_conf < 0.5:
        insights.append(t["low_conf"])
    if buckets.get("0.0-0.2"):
        insights.append(t["very_low_conf"])
    if isinstance(events, int) and events < 5:
        insights.append(t["low_data"])
    if top_next_steps and isinstance(top_next_steps, list):
        top = top_next_steps[0]
        if isinstance(top, dict):
            count = top.get("count")
            text = top.get("text")
            if isinstance(count, int) and count >= 3 and isinstance(text, str) and text.strip():
                insights.append(t["repeat_top"].format(text=text.strip()))

    while len(insights) < 3:
        insights.append(t["need_more"])

    action = t["action"]

    print(t["insights"])
    for item in insights[:3]:
        print(f"- {item}")
    print(t["action_label"])
    print(f"- {action}")

if __name__ == "__main__":
    main()
