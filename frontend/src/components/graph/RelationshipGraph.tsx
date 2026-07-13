"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  Node,
  NodeMouseHandler,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { get, post } from "@/lib/api";

// --- API Types ---

interface GraphNode {
  id: number;
  name: string;
  client_status: "client" | "prospect" | "unknown";
  industry: string | null;
  overall_score: number | null;
}

interface GraphEdge {
  id: number;
  source_id: number;
  target_id: number;
  relation_type: string;
  confidence: number | null;
}

interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  center_node_id: number;
}

interface WarmPathEdge {
  source_id: number;
  target_id: number;
  relation_type: string;
}

interface WarmPathResponse {
  path: number[];
  edges: WarmPathEdge[];
  path_length: number;
  available: boolean;
}

// --- Props ---

interface RelationshipGraphProps {
  companyId: number;
}

// --- Constants ---

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  client: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  prospect: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  unknown: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" },
};

const WARM_PATH_EDGE_STYLE = {
  stroke: "#f59e0b",
  strokeWidth: 3,
  strokeDasharray: "none",
};

const WARM_PATH_NODE_STYLE = {
  border: "2px solid #f59e0b",
  boxShadow: "0 0 8px rgba(245, 158, 11, 0.4)",
};

// --- Layout Helper ---

/**
 * Simple radial layout: places the center node in the middle
 * and distributes other nodes in concentric circles.
 */
function computeRadialLayout(
  nodes: GraphNode[],
  centerNodeId: number
): Map<number, { x: number; y: number }> {
  const positions = new Map<number, { x: number; y: number }>();
  const centerX = 400;
  const centerY = 300;

  // Place center node
  positions.set(centerNodeId, { x: centerX, y: centerY });

  // Distribute remaining nodes in a circle
  const otherNodes = nodes.filter((n) => n.id !== centerNodeId);
  const radius = Math.max(200, otherNodes.length * 40);

  otherNodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / otherNodes.length;
    positions.set(node.id, {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    });
  });

  return positions;
}

// --- Component ---

/**
 * RelationshipGraph renders the company relationship graph using React Flow.
 * Nodes are colored by client_status (Client: green, Prospect: blue, Unknown: gray).
 * Edges are labeled with relation_type.
 * Clicking on unknown nodes offers one-click research initiation.
 * Warm path is highlighted when available.
 *
 * Validates: Requirements 7.5, 14.7
 */
export default function RelationshipGraph({ companyId }: RelationshipGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);

  // Fetch graph data
  const {
    data: graphData,
    isLoading: graphLoading,
    error: graphError,
  } = useQuery<GraphResponse>({
    queryKey: ["company-graph", companyId],
    queryFn: () => get<GraphResponse>(`/companies/${companyId}/graph?depth=1`),
  });

  // Fetch warm path data
  const { data: warmPathData } = useQuery<WarmPathResponse>({
    queryKey: ["company-warm-path", companyId],
    queryFn: () => get<WarmPathResponse>(`/companies/${companyId}/warm-path`),
  });

  // Track which nodes/edges are on the warm path
  const warmPathNodeIds = useMemo(() => {
    if (!warmPathData?.available || !warmPathData.path) return new Set<number>();
    return new Set(warmPathData.path);
  }, [warmPathData]);

  const warmPathEdgeKeys = useMemo(() => {
    if (!warmPathData?.available || !warmPathData.edges) return new Set<string>();
    return new Set(
      warmPathData.edges.map((e) => `${e.source_id}-${e.target_id}`)
    );
  }, [warmPathData]);

  // Convert API data to React Flow format
  useEffect(() => {
    if (!graphData) return;

    const positions = computeRadialLayout(graphData.nodes, graphData.center_node_id);

    const flowNodes: Node[] = graphData.nodes.map((node) => {
      const pos = positions.get(node.id) ?? { x: 0, y: 0 };
      const colors = STATUS_COLORS[node.client_status] ?? STATUS_COLORS.unknown;
      const isOnWarmPath = warmPathNodeIds.has(node.id);
      const isCenter = node.id === graphData.center_node_id;

      return {
        id: String(node.id),
        position: pos,
        data: {
          label: node.name,
          clientStatus: node.client_status,
          industry: node.industry,
          overallScore: node.overall_score,
          originalNode: node,
        },
        style: {
          backgroundColor: colors.bg,
          borderColor: colors.border,
          border: `2px solid ${colors.border}`,
          borderRadius: "8px",
          padding: "10px 16px",
          color: colors.text,
          fontWeight: isCenter ? "700" : "500",
          fontSize: isCenter ? "14px" : "12px",
          minWidth: "120px",
          textAlign: "center" as const,
          cursor: node.client_status === "unknown" ? "pointer" : "default",
          ...(isOnWarmPath ? WARM_PATH_NODE_STYLE : {}),
        },
      };
    });

    const flowEdges: Edge[] = graphData.edges.map((edge) => {
      const edgeKey = `${edge.source_id}-${edge.target_id}`;
      const isOnWarmPath = warmPathEdgeKeys.has(edgeKey);

      return {
        id: String(edge.id),
        source: String(edge.source_id),
        target: String(edge.target_id),
        label: edge.relation_type,
        type: "default",
        animated: isOnWarmPath,
        style: isOnWarmPath
          ? WARM_PATH_EDGE_STYLE
          : { stroke: "#94a3b8", strokeWidth: 1.5 },
        labelStyle: {
          fontSize: "10px",
          fontWeight: isOnWarmPath ? "600" : "400",
          fill: isOnWarmPath ? "#d97706" : "#64748b",
        },
        labelBgStyle: {
          fill: isOnWarmPath ? "#fef3c7" : "#f8fafc",
          fillOpacity: 0.9,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isOnWarmPath ? "#f59e0b" : "#94a3b8",
          width: 16,
          height: 16,
        },
      };
    });

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [graphData, warmPathNodeIds, warmPathEdgeKeys, setNodes, setEdges]);

  // Handle node click - show research modal for unknown nodes
  const onNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    const originalNode = node.data.originalNode as GraphNode;
    if (originalNode.client_status === "unknown") {
      setSelectedNode(originalNode);
      setResearchError(null);
    }
  }, []);

  // Initiate research for an unknown company
  const handleResearch = useCallback(async () => {
    if (!selectedNode) return;

    setIsResearching(true);
    setResearchError(null);

    try {
      await post("/companies/research", { company_name: selectedNode.name });
      setSelectedNode(null);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to initiate research";
      setResearchError(message);
    } finally {
      setIsResearching(false);
    }
  }, [selectedNode]);

  // Loading state
  if (graphLoading) {
    return (
      <div className="flex items-center justify-center h-[500px]">
        <span className="loading loading-spinner loading-lg text-primary"></span>
      </div>
    );
  }

  // Error state
  if (graphError) {
    return (
      <div className="p-4">
        <div className="alert alert-error">
          <span>Failed to load relationship graph.</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="p-4">
        <div className="flex flex-col items-center justify-center py-12 text-base-content/60">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-12 w-12 mb-4 opacity-40"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
          <p className="text-lg font-medium">No connections found</p>
          <p className="text-sm mt-1">
            This company has no known relationships yet.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative p-4">
      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4">
        <div className="flex items-center gap-2 text-xs">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: STATUS_COLORS.client.border }}
          />
          <span>Client</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: STATUS_COLORS.prospect.border }}
          />
          <span>Prospect</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: STATUS_COLORS.unknown.border }}
          />
          <span>Unknown</span>
        </div>
        {warmPathData?.available && (
          <div className="flex items-center gap-2 text-xs">
            <div
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: "#f59e0b" }}
            />
            <span>Warm Path</span>
          </div>
        )}
      </div>

      {/* Warm Path Info */}
      {warmPathData?.available && (
        <div className="alert alert-warning mb-4 py-2 text-sm">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>
            Warm path available! {warmPathData.path_length} hop
            {warmPathData.path_length !== 1 ? "s" : ""} to an existing client.
          </span>
        </div>
      )}

      {/* React Flow Graph */}
      <div className="h-[500px] w-full border border-base-300 rounded-lg overflow-hidden bg-base-200">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.3}
          maxZoom={2}
          attributionPosition="bottom-left"
        >
          <Background color="#94a3b8" gap={20} size={1} />
          <Controls />
        </ReactFlow>
      </div>

      {/* Research Modal for Unknown Nodes */}
      {selectedNode && (
        <div className="modal modal-open" role="dialog" aria-modal="true">
          <div className="modal-box max-w-sm">
            <h3 className="font-bold text-lg">Research Company</h3>
            <p className="py-4 text-sm text-base-content/70">
              <span className="font-semibold text-base-content">
                {selectedNode.name}
              </span>{" "}
              is not yet researched. Would you like to initiate research to build
              a full company profile?
            </p>

            {researchError && (
              <div className="alert alert-error text-sm mb-4">
                <span>{researchError}</span>
              </div>
            )}

            <div className="modal-action">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setSelectedNode(null)}
                disabled={isResearching}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleResearch}
                disabled={isResearching}
              >
                {isResearching ? (
                  <>
                    <span className="loading loading-spinner loading-xs"></span>
                    Researching...
                  </>
                ) : (
                  "Research this company"
                )}
              </button>
            </div>
          </div>
          <div
            className="modal-backdrop"
            onClick={() => !isResearching && setSelectedNode(null)}
          />
        </div>
      )}
    </div>
  );
}
