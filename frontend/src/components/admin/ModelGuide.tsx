import { Collapse, Drawer, Table, Tag } from "antd";

const MODELS = [
  { name: "Laya", purpose: "Fast closed-label decisions", rate: "51–112 records/s", example: "Relevance, routing, risk, event type, sentiment, intent and toxicity.", detail: "An encoder that chooses among your configured labels and returns a probability distribution. Start here for high-volume classification. A 1,500-character lead at 512 tokens is fastest; 3,500 characters at 1,024 tokens preserved more event accuracy in the benchmark. Use longer context when evidence occurs later. It does not generate summaries or extract character spans." },
  { name: "GLiNER", purpose: "Spans, relations and structured extraction", rate: "≈21 entities/s; ≈13 relations/s", example: "Find people and places with exact offsets; link actors; extract structured event fields.", detail: "A schema-guided encoder. Use the multilingual extraction checkpoint for entities, relations and fields. The Decide checkpoints also classify, but were slower than Laya on the measured topic task. Distinct label names matter: overlapping labels compete. Code and numerical tables need validation; confidence alone does not make a span correct. Combined entity/relation extraction measured 1.5× faster but changed many relations, so separate passes remain the default." },
  { name: "Kev", purpose: "Alternative decisions with a quality tradeoff", rate: "34–50 records/s on short leads", example: "Try difficult topic distinctions where accuracy matters more than classifier speed.", detail: "Kev 0.8B uses a Qwen3.5 backbone with an adapter and decision head. It returns closed-label probabilities rather than generated prose. Topic accuracy was 80% on 70 labelled synthetic articles, versus 65.7% for the fastest Laya setting. Its short-lead topic speed was 34/s versus 104/s for Laya. Additional GPU memory prevented safe concurrent serving with the full live stack on this 10 GB card; validate memory and end-to-end time before switching." },
  { name: "Qwen", purpose: "Optional larger-model reasoning", rate: "Not measured in this comparison", example: "Evaluate ambiguous entity-pair decisions or a future on-demand generative task.", detail: "This application's optional Qwen3-4B AWQ/vLLM path exposes closed-label decisions through a log-probability adapter. It is a different serving path from Kev. A generative Qwen model could support summaries with additional implementation, but the current pipeline API does not generate them. Start with a small evaluation set: GPU memory and prefill latency can outweigh a quality gain. No throughput number is claimed here." },
];

export function ModelGuide({ open, onClose }: { open: boolean; onClose: () => void }) {
  return <Drawer title="Choosing a model" open={open} onClose={onClose} size={800}>
    <p>Choose by task first, then validate quality and processing time on your own documents. Engine choices in each task only include compatible adapters.</p>
    <Table size="small" pagination={false} rowKey="name" scroll={{ x: 570 }} dataSource={MODELS} columns={[
      { title: "Model", dataIndex: "name", width: 90, render: (name) => <strong>{name}</strong> },
      { title: "Best starting point", dataIndex: "purpose" }, { title: "Measured task throughput", dataIndex: "rate" },
    ]} />
    <p className="muted small">RTX 3080 10 GB · October 2026 · task alone, not full-pipeline throughput. Classification: 100 documents, median of three trials. Topic/event accuracy uses 70 labelled synthetic documents; this is not production accuracy. Extraction figures use the earlier 500-document benchmark.</p>
    <Collapse defaultActiveKey={["Laya"]} items={MODELS.map((model) => ({ key: model.name, label: model.name,
      children: <><Tag>{model.purpose}</Tag><p><strong>When to choose it:</strong> {model.example}</p><p>{model.detail}</p></> }))} />
    <p className="muted small">For speed: shorten the input only when the task's evidence is near the beginning, batch requests, and avoid unnecessary tasks. Review thresholds change review flags; they do not make inference faster. Model confidence is not interchangeable across engines.</p>
  </Drawer>;
}
