(() => {
  const config = window.graphExplorerConfig;
  const nodeStore = nodes.get({ returnType: "Object" });
  const edgeStore = edges.get({ returnType: "Object" });
  const expanded = new Set(config.initialExpanded);
  let selectedNode = null;
  let nodeTypeFilter = "all";
  let relationFilter = "all";
  let physicsEnabled = false;
  let physicsTimeout = null;

  const searchInput = document.getElementById("graph-search");
  const nodeFilter = document.getElementById("graph-node-filter");
  const relationSelect = document.getElementById("graph-edge-filter");
  const expandButton = document.getElementById("graph-expand");
  const collapseButton = document.getElementById("graph-collapse");
  const countLabel = document.getElementById("graph-count");
  const statusLabel = document.getElementById("graph-status");
  const physicsButton = document.getElementById("graph-physics");

  function childrenOf(nodeId) {
    return config.childrenByParent[nodeId] || [];
  }

  function descendantsOf(nodeId) {
    const descendants = new Set();
    const queue = [...childrenOf(nodeId)];
    while (queue.length) {
      const current = queue.shift();
      if (descendants.has(current)) continue;
      descendants.add(current);
      queue.push(...childrenOf(current));
    }
    return descendants;
  }

  function ancestorsOf(nodeId) {
    const ancestors = [];
    let current = config.parentByNode[nodeId];
    while (current && !ancestors.includes(current)) {
      ancestors.push(current);
      current = config.parentByNode[current];
    }
    return ancestors;
  }

  function structuralVisibility() {
    const visible = new Set(config.rootNodeIds);
    let changed = true;
    while (changed) {
      changed = false;
      Object.entries(config.parentByNode).forEach(([child, parent]) => {
        if (visible.has(parent) && expanded.has(parent) && !visible.has(child)) {
          visible.add(child);
          changed = true;
        }
      });
    }
    return visible;
  }

  function filteredVisibility(visible) {
    if (nodeTypeFilter === "all") return visible;
    const contextual = new Set();
    visible.forEach((nodeId) => {
      if (nodeStore[nodeId].group !== nodeTypeFilter) return;
      contextual.add(nodeId);
      ancestorsOf(nodeId).forEach((ancestor) => contextual.add(ancestor));
    });
    return contextual;
  }

  function refresh() {
    const structural = structuralVisibility();
    const visible = filteredVisibility(structural);
    nodes.update(Object.keys(nodeStore).map((nodeId) => ({
      id: nodeId,
      hidden: !visible.has(nodeId),
      physics: visible.has(nodeId),
    })));
    edges.update(Object.values(edgeStore).map((edge) => ({
      id: edge.id,
      hidden: !visible.has(String(edge.from)) ||
        !visible.has(String(edge.to)) ||
        (relationFilter !== "all" && edge.relationKey !== relationFilter),
      physics: visible.has(String(edge.from)) &&
        visible.has(String(edge.to)) &&
        (relationFilter === "all" || edge.relationKey === relationFilter),
    })));
    const visibleEdges = Object.values(edgeStore).filter((edge) =>
      visible.has(String(edge.from)) &&
      visible.has(String(edge.to)) &&
      (relationFilter === "all" || edge.relationKey === relationFilter)
    ).length;
    countLabel.textContent = `${visible.size} nodes · ${visibleEdges} relationships`;
    expandButton.disabled = !selectedNode || childrenOf(selectedNode).length === 0;
    collapseButton.disabled = !selectedNode || descendantsOf(selectedNode).size === 0;
  }

  function stopLayout() {
    if (physicsTimeout) clearTimeout(physicsTimeout);
    physicsTimeout = null;
    physicsEnabled = false;
    network.stopSimulation();
    network.setOptions({ physics: { enabled: false, stabilization: { enabled: false } } });
    physicsButton.textContent = "Resume layout";
  }

  function startLayout(autoStopMilliseconds = null) {
    if (physicsTimeout) clearTimeout(physicsTimeout);
    physicsEnabled = true;
    network.setOptions({ physics: { enabled: true, stabilization: { enabled: false } } });
    network.startSimulation();
    physicsButton.textContent = "Pause layout";
    if (autoStopMilliseconds) {
      physicsTimeout = setTimeout(() => {
        stopLayout();
        network.fit({ animation: { duration: 350 } });
      }, autoStopMilliseconds);
    }
  }

  function focusNode(nodeId) {
    selectedNode = nodeId;
    network.selectNodes([nodeId]);
    network.focus(nodeId, {
      scale: 1.15,
      animation: { duration: 450, easingFunction: "easeInOutQuad" },
    });
    statusLabel.textContent = nodeStore[nodeId].fullLabel;
    refresh();
  }

  function expandNode(nodeId) {
    expanded.add(nodeId);
    refresh();
    startLayout(650);
  }

  function collapseNode(nodeId) {
    expanded.delete(nodeId);
    descendantsOf(nodeId).forEach((descendant) => expanded.delete(descendant));
    refresh();
    startLayout(450);
    network.focus(nodeId, { animation: { duration: 350 } });
  }

  function findNode() {
    const query = searchInput.value.trim().toLowerCase();
    if (!query) return;
    const match = Object.values(nodeStore).find((node) =>
      node.fullLabel.toLowerCase() === query
    ) || Object.values(nodeStore).find((node) =>
      node.fullLabel.toLowerCase().includes(query)
    );
    if (!match) {
      statusLabel.textContent = `No node matches “${searchInput.value.trim()}”.`;
      return;
    }
    ancestorsOf(String(match.id)).forEach((ancestor) => expanded.add(ancestor));
    nodeTypeFilter = "all";
    nodeFilter.value = "all";
    refresh();
    startLayout(650);
    focusNode(String(match.id));
  }

  network.on("selectNode", (event) => {
    selectedNode = String(event.nodes[0]);
    statusLabel.textContent = nodeStore[selectedNode].fullLabel;
    refresh();
  });

  network.on("deselectNode", () => {
    selectedNode = null;
    statusLabel.textContent = "Select a node, then expand or collapse its branch.";
    refresh();
  });

  network.on("doubleClick", (event) => {
    if (!event.nodes.length) return;
    const nodeId = String(event.nodes[0]);
    if (expanded.has(nodeId)) collapseNode(nodeId);
    else expandNode(nodeId);
  });

  document.getElementById("graph-find").addEventListener("click", findNode);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") findNode();
  });
  nodeFilter.addEventListener("change", (event) => {
    nodeTypeFilter = event.target.value;
    refresh();
    network.fit({ animation: { duration: 350 } });
  });
  relationSelect.addEventListener("change", (event) => {
    relationFilter = event.target.value;
    refresh();
  });
  expandButton.addEventListener("click", () => selectedNode && expandNode(selectedNode));
  collapseButton.addEventListener("click", () => selectedNode && collapseNode(selectedNode));
  document.getElementById("graph-show-all").addEventListener("click", () => {
    Object.keys(config.childrenByParent).forEach((nodeId) => expanded.add(nodeId));
    nodeTypeFilter = "all";
    nodeFilter.value = "all";
    refresh();
    startLayout(1200);
  });
  document.getElementById("graph-reset").addEventListener("click", () => {
    expanded.clear();
    config.initialExpanded.forEach((nodeId) => expanded.add(nodeId));
    selectedNode = null;
    nodeTypeFilter = "all";
    relationFilter = "all";
    nodeFilter.value = "all";
    relationSelect.value = "all";
    searchInput.value = "";
    statusLabel.textContent = "Select a node, then expand or collapse its branch.";
    network.unselectAll();
    refresh();
    startLayout(650);
  });
  physicsButton.addEventListener("click", () => {
    if (physicsEnabled) stopLayout();
    else startLayout();
  });

  refresh();
  startLayout(650);
})();
