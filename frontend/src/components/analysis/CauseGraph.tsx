import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useResource } from "../../lib/resource";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

type Kind = "evidence" | "hypothesis" | "category" | "abstain" | "action" | "missing" | "document";
interface GraphNodeData extends Record<string, unknown> {
  kind: Kind; label: string; description?: string; signal?: string; machine?: string | null; value?: number | string | null;
  polarity?: "supporting" | "contradicting"; confidence?: string; narrative?: string; step?: string; source?: string;
  link?: string; scope?: string | null; why_allowed?: string; page_or_section?: string | null; chunk_id?: string | null;
  dimmed?: boolean; selected?: boolean;
}
interface GraphEdge { id: string; source: string; target: string; kind: string; label: string | null; weight: number | null }
interface GraphResponse { mode: "ranked" | "abstain"; nodes: Node<GraphNodeData>[]; edges: GraphEdge[] }

const STYLE: Record<Kind, { box: string; tag: string }> = {
  evidence: { box: "border-slate-200 bg-white", tag: "Evidence" },
  hypothesis: { box: "border-indigo-700 bg-indigo-50", tag: "Hypothesis" },
  category: { box: "border-slate-300 bg-surface-alt", tag: "Category (below minimum)" },
  abstain: { box: "border-warning bg-warning-tint", tag: "Abstained" },
  action: { box: "border-mint-400 bg-mint-100", tag: "Verification action" },
  missing: { box: "border-dashed border-slate-300 bg-white", tag: "Missing check" },
  document: { box: "border-cyan-400 bg-white", tag: "Cited document" },
};

function CauseNode({ data }: NodeProps<Node<GraphNodeData>>) {
  const s = STYLE[data.kind];
  const contra = data.polarity === "contradicting";
  return (
    <div className={`w-[300px] rounded-md border-2 px-3 py-2 text-left shadow-card transition-opacity duration-150 ${s.box} ${contra ? "!border-danger" : ""} ${data.selected ? "ring-4 ring-indigo-500/30" : ""} ${data.dimmed ? "opacity-25" : ""}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !bg-slate-300" />
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{contra ? "Contradicting evidence" : s.tag}{data.confidence ? ` · ${data.confidence}` : ""}</p>
      <p className={`mt-0.5 line-clamp-2 text-[13px] font-semibold text-ink-900 ${data.kind === "evidence" ? "font-mono" : ""}`}>{data.label}</p>
      {data.kind === "evidence" && data.description && <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-600">{data.description}</p>}
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !bg-slate-300" />
    </div>
  );
}

const nodeTypes = { cause: CauseNode };

function Detail({ node, edges, byId }: { node: Node<GraphNodeData>; edges: GraphEdge[]; byId: Map<string, Node<GraphNodeData>> }) {
  const d = node.data;
  const links = edges.filter((e) => e.source === node.id || e.target === node.id);
  return (
    <div className="space-y-2 text-sm">
      <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{STYLE[d.kind].tag}</p>
      <p className="font-semibold text-ink-900">{d.label}</p>
      {d.description && <p>{d.description}</p>}
      {d.signal && <p className="font-mono text-xs">signal {d.signal}{d.machine ? ` · ${d.machine}` : ""}{d.value !== null && d.value !== undefined ? ` · value ${d.value}` : ""}</p>}
      {d.narrative && <p className="text-slate-600">{d.narrative}</p>}
      {d.step && d.kind !== "missing" && <p>{d.step} <span className="font-mono text-xs text-slate-500">({d.source}{d.chunk_id ? `, ${d.chunk_id}` : ""})</span></p>}
      {d.why_allowed && <p className="text-slate-600">{d.why_allowed}{d.page_or_section ? ` · ${d.page_or_section}` : ""}</p>}
      {d.link && <Link to={d.link} className="inline-block font-semibold text-indigo-700">Open cited chunk →</Link>}
      <ul className="mt-2 space-y-1 border-t border-slate-200 pt-2">
        {links.map((e) => {
          const other = byId.get(e.source === node.id ? e.target : e.source);
          return <li key={e.id} className="text-xs text-ink-700">{e.source === node.id ? "→" : "←"} {e.kind.replace("_", " ")}{e.label && e.label !== e.kind ? ` (${e.label})` : ""}: {other?.data.label}</li>;
        })}
      </ul>
    </div>
  );
}

/** Cause-and-effect graph from the stored analysis. Click a node to highlight its connections and read its evidence. */
export default function CauseGraph({ runId }: { runId: string }) {
  const { data, error } = useResource<GraphResponse>(`/api/analyses/${encodeURIComponent(runId)}/graph`);
  const [selected, setSelected] = useState<string | null>(null);
  const byId = useMemo(() => new Map((data?.nodes || []).map((n) => [n.id, n])), [data]);
  const connected = useMemo(() => {
    if (!selected || !data) return null;
    // The whole causal chain through the clicked node: everything upstream and everything downstream.
    const ids = new Set([selected]);
    for (const [from, to] of [["source", "target"], ["target", "source"]] as const) {
      const queue = [selected];
      const seen = new Set(queue);
      while (queue.length) {
        const current = queue.shift()!;
        for (const e of data.edges) {
          if (e[from] === current && !seen.has(e[to])) { seen.add(e[to]); ids.add(e[to]); queue.push(e[to]); }
        }
      }
    }
    return ids;
  }, [selected, data]);
  const nodes = useMemo(() => (data?.nodes || []).map((n) => ({ ...n, data: { ...n.data, dimmed: !!connected && !connected.has(n.id), selected: n.id === selected } })), [data, connected, selected]);
  const edges: Edge[] = useMemo(() => (data?.edges || []).map((e) => {
    const contra = e.kind === "contradicts";
    const active = !connected || (connected.has(e.source) && connected.has(e.target));
    return {
      id: e.id, source: e.source, target: e.target, label: e.label ?? undefined, animated: active && !!connected,
      style: { stroke: contra ? "var(--color-danger)" : e.kind === "supports" ? "var(--color-indigo-500)" : "var(--color-slate-300)",
               strokeWidth: e.weight ? 1 + Math.abs(e.weight) / 1.5 : 1.5, strokeDasharray: contra || e.kind === "missing" ? "6 4" : undefined, opacity: active ? 1 : 0.15 },
      labelStyle: { fontFamily: "var(--font-mono)", fontSize: 11, fill: contra ? "var(--color-danger-ink)" : "var(--color-ink-700)" },
      labelBgStyle: { fill: "var(--color-white)" },
    };
  }), [data, connected, selected]);

  if (error) return <Card className="p-5 text-sm">Graph unavailable: {error}</Card>;
  if (!data) return <Card className="flex h-[560px] items-center justify-center"><Spinner label="Building graph…" /></Card>;
  const current = selected ? byId.get(selected) : null;
  return (
    <div className="grid gap-4 xl:grid-cols-12">
      <Card className="h-[560px] overflow-hidden xl:col-span-9" aria-label="Cause-and-effect graph">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2} nodesDraggable={false} nodesConnectable={false}
          onNodeClick={(_, n) => setSelected((s) => (s === n.id ? null : n.id))} onPaneClick={() => setSelected(null)} proOptions={{ hideAttribution: true }}>
          <Background gap={24} color="var(--color-slate-200)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </Card>
      <Card className="p-4 xl:col-span-3">
        {current ? <Detail node={current} edges={data.edges} byId={byId} /> : (
          <div className="space-y-3 text-sm text-slate-600">
            <p className="font-semibold text-ink-900">{data.mode === "abstain" ? "No hypothesis reached the minimum score" : "How to read it"}</p>
            <p>Left to right: evidence → {data.mode === "abstain" ? "categories that had evidence → missing checks and references" : "hypotheses → verification actions → cited documents"}.</p>
            <p>Edge labels show the rule weight from the cause configuration; dashed red edges are contradicting evidence.</p>
            <p>Click a node to highlight its connections and read its evidence.</p>
          </div>
        )}
      </Card>
    </div>
  );
}
