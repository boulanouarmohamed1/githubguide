"use client";

import { ChevronRight, FileCode, Folder } from "lucide-react";
import type { FileNode } from "@/lib/api";

type Props = {
  nodes: FileNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
};

export function FileTree({ nodes, selectedPath, onSelect }: Props) {
  return (
    <div className="file-tree">
      {nodes.map((node) => (
        <TreeNode key={node.path} node={node} selectedPath={selectedPath} onSelect={onSelect} depth={0} />
      ))}
    </div>
  );
}

function TreeNode({
  node,
  selectedPath,
  onSelect,
  depth
}: {
  node: FileNode;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  depth: number;
}) {
  const isFile = node.kind === "file";
  return (
    <div>
      <button
        className={`tree-row ${selectedPath === node.path ? "active" : ""}`}
        style={{ paddingLeft: 10 + depth * 14 }}
        onClick={() => isFile && onSelect(node.path)}
        disabled={!isFile}
        title={node.path}
      >
        {isFile ? <FileCode size={15} /> : <Folder size={15} />}
        <span>{node.path.split("/").at(-1)}</span>
        {!isFile && <ChevronRight size={13} className="tree-chevron" />}
      </button>
      {!isFile &&
        node.children.map((child) => (
          <TreeNode key={child.path} node={child} selectedPath={selectedPath} onSelect={onSelect} depth={depth + 1} />
        ))}
    </div>
  );
}

