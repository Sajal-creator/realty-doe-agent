'use client';

import React, { useMemo, useCallback } from 'react';
import { ReactFlow, useNodesState, useEdgesState, Controls, Background, Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useStore } from '@/store/useStore';
import { getWarmthColor } from '@/lib/utils';

export default function SessionCanvas() {
  const { leads, pipeline } = useStore();

  const initialNodes: Node[] = useMemo(() => {
    const nodes: Node[] = [];

    // Agent nodes (center)
    nodes.push({
      id: 'agent-1',
      position: { x: 400, y: 300 },
      data: { label: '🧑‍💼 Agent' },
      style: {
        background: '#1e293b',
        border: '2px solid #10b981',
        borderRadius: '50%',
        width: 80,
        height: 80,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        fontSize: 12,
      },
    });

    // Lead nodes (satellites)
    const allLeadIds = [...pipeline.hot, ...pipeline.warm, ...pipeline.new];
    const angleStep = (2 * Math.PI) / Math.max(allLeadIds.length, 1);

    allLeadIds.forEach((id, i) => {
      const lead = leads.get(id);
      if (!lead) return;

      const angle = angleStep * i;
      const radius = 150 + (lead.warmth_score >= 80 ? 0 : 50);
      const x = 400 + Math.cos(angle) * radius;
      const y = 300 + Math.sin(angle) * radius;

      const color = getWarmthColor(lead.warmth_score);

      nodes.push({
        id: `lead-${id}`,
        position: { x, y },
        data: { label: `${lead.name || lead.phone}\n${lead.warmth_score}%` },
        style: {
          background: '#1e293b',
          border: `2px solid ${color}`,
          borderRadius: 12,
          padding: 8,
          color: 'white',
          fontSize: 10,
          textAlign: 'center' as const,
          boxShadow: lead.warmth_score >= 80 ? `0 0 20px ${color}` : 'none',
          animation: lead.warmth_score >= 80 ? 'pulse-glow 2s infinite' : 'none',
        },
      });
    });

    return nodes;
  }, [leads, pipeline]);

  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    const allLeadIds = [...pipeline.hot, ...pipeline.warm, ...pipeline.new];

    allLeadIds.forEach((id) => {
      const lead = leads.get(id);
      if (!lead) return;
      const color = getWarmthColor(lead.warmth_score);

      edges.push({
        id: `edge-agent-${id}`,
        source: 'agent-1',
        target: `lead-${id}`,
        style: { stroke: color, strokeWidth: lead.warmth_score >= 80 ? 3 : 1 },
        animated: lead.warmth_score >= 80,
      });
    });

    return edges;
  }, [leads, pipeline]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        attributionPosition="bottom-left"
      >
        <Controls className="!bg-slate-800 !border-slate-700 !text-white" />
        <Background gap={20} size={1} color="#334155" />
      </ReactFlow>
    </div>
  );
}
