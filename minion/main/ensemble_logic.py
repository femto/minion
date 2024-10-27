GSM8K_ENSEMBLE_LOGIC = {
    "ensemble_strategy": {
        "ensemble_minions": [
            {"name": "python", "count": 1, "post_processing": "extract_number_from_string"},
            {"name": "cot", "count": 2, "post_processing": "extract_number_from_string"},
        ],
        "ensemble_logic": "majority_voting",
    }
}
GSM8K_HEAVYWEIGHT_ENSEMBLE_LOGIC = {
    "ensemble_strategy": {
        "ensemble_minions": [
            {"name": "python", "count": 2, "post_processing": "extract_number_from_string"},
            {"name": "cot", "count": 3, "post_processing": "extract_number_from_string"},
        ],
        "ensemble_logic": "majority_voting",
    }
}
