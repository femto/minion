from metagpt.minion.minion import Minion


class PreprocessingMinion(Minion):
    """
    PreprocessingMinion handles the transformation of raw input into refined perceptions.

    While named 'Preprocessing' for general understanding, this minion actually performs
    complex cognitive enhancements analogous to the perception process in the Active
    Inference Framework (AIF). It transforms raw observations into meaningful internal
    representations through various cognitive processes.
    """

    async def execute(self):
        if not self.input.ensemble_logic or "preprocessing" not in self.input.ensemble_logic:
            return self.input

        observations = self.collect_raw_observations()
        enhanced_perceptions = await self.enhance_cognitive_representations(observations)
        self.update_input_with_enhanced_perceptions(enhanced_perceptions)

        return self.input

    def collect_raw_observations(self):
        return {
            field: getattr(self.input, field)
            for field in ["query", "short_context", "instruction", "solution", "answer", "feedback"]
            if hasattr(self.input, field)
        }

    async def enhance_cognitive_representations(self, observations):
        enhanced_perceptions = observations.copy()
        for step in self.input.ensemble_logic["preprocessing"]["cognitive_enhancements"]:
            if step["type"] == "re2":
                enhanced_perceptions = self.apply_attention_enhancement(enhanced_perceptions, step)
            elif step["type"] == "rephrase":
                enhanced_perceptions = await self.apply_semantic_refinement(enhanced_perceptions, step)
            # 可以在这里添加更多的处理步骤

        return enhanced_perceptions

    def update_input_with_enhanced_perceptions(self, enhanced_perceptions):
        for field, value in enhanced_perceptions.items():
            setattr(self.input, field, value)

    def apply_attention_enhancement(self, perceptions, step):
        for field in step["apply_to"]:
            if field in perceptions:
                for _ in range(step.get("repeat", 1)):
                    perceptions[field] = self.apply_re2(perceptions[field])
        return perceptions

    async def apply_semantic_refinement(self, perceptions, step):
        for field in step["apply_to"]:
            if field in perceptions:
                perceptions[field] = await self.apply_rephrase(perceptions[field])
        return perceptions

    def apply_re2(self, text):
        if not text:
            return text
        return f"{text}\nRead the above again: {text}"

    async def apply_rephrase(self, text):
        if not text:
            return text
        rephrase_prompt = f"Rephrase the following without changing its meaning: {text}"
        rephrased_text = await self.brain.llm.aask(rephrase_prompt)
        return rephrased_text