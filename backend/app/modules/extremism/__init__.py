from ...core.kits.label import LabelModule


class ExtremismModule(LabelModule):
    name = 'extremism'
    title = 'Extremist narrative'
    description = 'Explicit violent-extremist narratives, separated from condemnation and reporting. Non-none outputs require analyst review.'

    def needs_review(self, result):
        # Confidence alone did not catch false positives in the EN/RO smoke evaluation.
        return bool(result) and (result['label'] != 'none' or super().needs_review(result))

    def summarize(self, job, results):
        summary = super().summarize(job, results)
        summary['needs_review'] = sum(self.needs_review(result) for result in results)
        return summary
