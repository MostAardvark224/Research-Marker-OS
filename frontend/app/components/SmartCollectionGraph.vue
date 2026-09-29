<template>
  <div ref="root" class="relative h-full w-full overflow-hidden">
    <div
      ref="graphContainer"
      class="absolute inset-0 cursor-grab active:cursor-grabbing"
    ></div>
    <div
      v-if="hover"
      class="pointer-events-none absolute z-30 max-w-[280px] -translate-x-1/2 -translate-y-full rounded-lg border border-white/10 bg-[#0b0b12]/95 px-2.5 py-1.5 shadow-xl backdrop-blur-sm"
      :style="{ left: `${hover.left}px`, top: `${hover.top - 8}px` }"
    >
      <p class="text-xs font-medium leading-snug text-white">{{ hover.title }}</p>
      <p v-if="hover.subtitle" class="mt-0.5 text-[10px] capitalize text-slate-400">
        {{ hover.subtitle }}
      </p>
    </div>
  </div>
</template>

<script setup>
import * as d3 from "d3";

const props = defineProps({
  papers: { type: Array, default: () => [] },
  ghosts: { type: Array, default: () => [] },
  heatmap: { type: Object, default: () => ({}) },
  colors: { type: Object, default: () => ({}) },
  selectedId: { type: [Number, String, null], default: null },
  selectedGhostId: { type: String, default: "" },
  isolatedTopic: { type: String, default: "" },
  showHeatmap: { type: Boolean, default: true },
  showGhosts: { type: Boolean, default: true },
  focusRequest: { type: Object, default: null },
});

const emit = defineEmits(["select-paper", "open-paper", "select-ghost", "background"]);

const root = ref(null);
const graphContainer = ref(null);
const zoomScale = defineModel("zoomScale", { type: Number, default: 1 });
const hover = ref(null);

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 20;

let svg;
let g;
let zoom;
let xScaleFn;
let yScaleFn;
let width = 0;
let height = 0;

const getTopicColor = (majorTopic, level) => {
  if (props.colors && props.colors[majorTopic]) {
    return props.colors[majorTopic][level];
  }
  if (level === "major") return "#e2e8f0";
  if (level === "sub") return "#c084fc";
  return "#60a5fa";
};

const roleRadius = (role) => {
  if (role === "pillar") return 7;
  if (role === "niche") return 3.2;
  return 4.6;
};

const processGraphData = () => {
  const papers = (props.papers || []).map((item) => ({
    ...item,
    title: item.doc_title || item.title,
    x: Number(item.x_coordinate),
    y: Number(item.y_coordinate),
    major: item.major_topic,
    sub: item.sub_topic,
    role: item.role || "core",
    influence: Number(item.influence || 0),
    centrality: Number(item.centrality || 0),
  }));
  const paperMap = new Map(papers.map((paper) => [paper.id, paper]));
  const links = [];
  papers.forEach((source) => {
    (source.similar_papers || []).forEach((targetId) => {
      const target = paperMap.get(targetId);
      if (target && source.id < target.id) {
        links.push({ source, target, id: `${source.id}-${target.id}` });
      }
    });
  });
  const majorMap = {};
  const subMap = {};
  papers.forEach((paper) => {
    if (!majorMap[paper.major]) majorMap[paper.major] = { xSum: 0, ySum: 0, count: 0 };
    majorMap[paper.major].xSum += paper.x;
    majorMap[paper.major].ySum += paper.y;
    majorMap[paper.major].count += 1;
    if (!paper.sub) return;
    if (!subMap[paper.sub]) {
      subMap[paper.sub] = { xSum: 0, ySum: 0, count: 0, major: paper.major, label: paper.sub };
    }
    subMap[paper.sub].xSum += paper.x;
    subMap[paper.sub].ySum += paper.y;
    subMap[paper.sub].count += 1;
  });
  const majorClusters = Object.keys(majorMap).map((key) => ({
    label: key,
    x: majorMap[key].xSum / majorMap[key].count,
    y: majorMap[key].ySum / majorMap[key].count,
  }));
  const subClusters = Object.keys(subMap).map((key) => ({
    label: subMap[key].label,
    major: subMap[key].major,
    x: subMap[key].xSum / subMap[key].count,
    y: subMap[key].ySum / subMap[key].count,
  }));
  const ghosts = (props.showGhosts ? props.ghosts || [] : []).map((ghost) => ({
    ...ghost,
    x: Number(ghost.x),
    y: Number(ghost.y),
  }));
  return { papers, majorClusters, subClusters, links, ghosts };
};

const allPoints = (papers, ghosts) => {
  return [
    ...papers.map((paper) => [paper.x, paper.y]),
    ...ghosts.map((ghost) => [ghost.x, ghost.y]),
  ].filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
};

const nodeOpacity = (item) => {
  if (!props.isolatedTopic) return 1;
  if (item.major === props.isolatedTopic || item.cluster === props.isolatedTopic) return 1;
  return 0.12;
};

const drawHeatmap = (layer, heatmap) => {
  layer.selectAll("*").remove();
  const values = heatmap?.values;
  if (!props.showHeatmap || !Array.isArray(values) || values.length === 0) return;
  const resolution = values.length;
  const xMin = Number(heatmap.x_min);
  const xMax = Number(heatmap.x_max);
  const yMin = Number(heatmap.y_min);
  const yMax = Number(heatmap.y_max);
  if (![xMin, xMax, yMin, yMax].every(Number.isFinite) || xMax <= xMin || yMax <= yMin) return;

  const color = d3.scaleSequential(d3.interpolateRgb("#2e1064", "#fb923c")).domain([0.05, 1]);
  const grid = document.createElement("canvas");
  grid.width = resolution;
  grid.height = resolution;
  const gridContext = grid.getContext("2d");
  const pixels = gridContext.createImageData(resolution, resolution);
  for (let row = 0; row < resolution; row += 1) {
    // Row 0 is the bottom of the plot, but the top of the image.
    const imageRow = resolution - 1 - row;
    for (let col = 0; col < resolution; col += 1) {
      const value = Math.max(0, Math.min(1, Number(values[row]?.[col] || 0)));
      const rgb = d3.rgb(color(value));
      // Fade in from zero instead of a hard cutoff so the blob has soft edges.
      const fade = d3.easeCubicInOut(Math.max(0, Math.min(1, (value - 0.03) / 0.3)));
      const offset = (imageRow * resolution + col) * 4;
      pixels.data[offset] = rgb.r;
      pixels.data[offset + 1] = rgb.g;
      pixels.data[offset + 2] = rgb.b;
      pixels.data[offset + 3] = Math.round(255 * fade * (0.16 + value * 0.38));
    }
  }
  gridContext.putImageData(pixels, 0, 0);

  const size = 512;
  const smooth = document.createElement("canvas");
  smooth.width = size;
  smooth.height = size;
  const smoothContext = smooth.getContext("2d");
  smoothContext.imageSmoothingEnabled = true;
  smoothContext.imageSmoothingQuality = "high";
  smoothContext.filter = `blur(${Math.round((size / resolution) * 0.9)}px)`;
  smoothContext.drawImage(grid, 0, 0, size, size);

  const left = xScaleFn(xMin);
  const top = yScaleFn(yMax);
  layer
    .append("image")
    .attr("href", smooth.toDataURL("image/png"))
    .attr("x", left)
    .attr("y", top)
    .attr("width", Math.abs(xScaleFn(xMax) - left))
    .attr("height", Math.abs(yScaleFn(yMin) - top))
    .attr("preserveAspectRatio", "none")
    .style("pointer-events", "none");
};

const updateSemanticZoom = (k) => {
  if (!g) return;
  g.select(".layer-major").style("opacity", k < 1.8 ? 1 : 0);
  g.select(".layer-sub").style("opacity", k >= 1.8 && k < 4.5 ? 1 : 0);
  g.select(".layer-paper-labels").style("opacity", k >= 2.4 ? 1 : 0);
  g.select(".layer-links").style("opacity", k >= 1.6 ? 0.9 : 0.25);
  g.select(".layer-ghost-labels").style("opacity", k >= 1.4 ? 1 : 0.35);
  // Keep a ~10px on-screen hover target even when dots shrink at low zoom.
  g.selectAll(".hit-area").attr("r", (d) => Math.max(roleRadius(d.role) + 3, 10 / k));
};

const showHover = (event, title, subtitle) => {
  if (!root.value) return;
  const target = event.currentTarget.getBoundingClientRect();
  const bounds = root.value.getBoundingClientRect();
  const x = target.left + target.width / 2 - bounds.left;
  hover.value = {
    title,
    subtitle,
    left: Math.min(Math.max(x, 140), Math.max(bounds.width - 140, 140)),
    top: target.top - bounds.top,
  };
};

const hideHover = () => {
  hover.value = null;
};

const wheelPixels = (delta, event) => {
  if (event.deltaMode === 1) return delta * 16;
  if (event.deltaMode === 2) return delta * (height || 800);
  return delta;
};

// Touchpads send many small pixel deltas (two-finger swipe) or ctrl+wheel (pinch);
// d3's default wheel scaling is tuned for mouse notches and feels dead on a touchpad.
const handleWheel = (event) => {
  if (!svg || !zoom) return;
  event.preventDefault();
  const dx = wheelPixels(event.deltaX, event);
  const dy = wheelPixels(event.deltaY, event);
  if (!event.ctrlKey && Math.abs(dx) > Math.abs(dy)) {
    const k = d3.zoomTransform(svg.node()).k;
    zoom.translateBy(svg, -dx / k, 0);
    return;
  }
  const sensitivity = event.ctrlKey ? 0.012 : 0.004;
  const step = Math.max(-60, Math.min(60, dy));
  zoom.scaleBy(svg, Math.exp(-step * sensitivity), d3.pointer(event, svg.node()));
};

const render = () => {
  if (!graphContainer.value) return;
  const { clientWidth, clientHeight } = graphContainer.value;
  if (!clientWidth || !clientHeight) return;
  width = clientWidth;
  height = clientHeight;
  const { papers, majorClusters, subClusters, links, ghosts } = processGraphData();
  const points = allPoints(papers, ghosts);
  if (!points.length) return;

  const previousTransform = svg ? d3.zoomTransform(svg.node()) : null;
  d3.select(graphContainer.value).selectAll("*").remove();
  svg = d3
    .select(graphContainer.value)
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", [0, 0, width, height])
    .style("display", "block")
    .style("background-color", "#020204")
    .on("click", (event) => {
      if (event.target === svg.node()) emit("background");
    });

  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  let xExtent = d3.extent(xs);
  let yExtent = d3.extent(ys);
  if (xExtent[0] === xExtent[1]) {
    xExtent = [xExtent[0] - 1, xExtent[1] + 1];
  }
  if (yExtent[0] === yExtent[1]) {
    yExtent = [yExtent[0] - 1, yExtent[1] + 1];
  }
  const xPadding = (xExtent[1] - xExtent[0]) * 0.16;
  const yPadding = (yExtent[1] - yExtent[0]) * 0.16;
  xScaleFn = d3
    .scaleLinear()
    .domain([xExtent[0] - xPadding, xExtent[1] + xPadding])
    .range([0, width]);
  yScaleFn = d3
    .scaleLinear()
    .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
    .range([height, 0]);

  g = svg.append("g");
  drawHeatmap(g.append("g").attr("class", "layer-heatmap"), props.heatmap);

  g.append("g")
    .attr("class", "layer-links")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("x1", (d) => xScaleFn(d.source.x))
    .attr("y1", (d) => yScaleFn(d.source.y))
    .attr("x2", (d) => xScaleFn(d.target.x))
    .attr("y2", (d) => yScaleFn(d.target.y))
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 0.6)
    .attr("stroke-opacity", (d) => 0.12 * nodeOpacity(d.source) * nodeOpacity(d.target));

  const paperGroup = g.append("g").attr("class", "layer-papers");
  const nodes = paperGroup
    .selectAll("g.node")
    .data(papers)
    .join("g")
    .attr("class", "node")
    .attr("transform", (d) => `translate(${xScaleFn(d.x)}, ${yScaleFn(d.y)})`)
    .style("cursor", "pointer")
    .style("opacity", (d) => nodeOpacity(d))
    .on("click", (event, d) => {
      event.stopPropagation();
      emit("select-paper", d);
    })
    .on("dblclick", (event, d) => {
      event.stopPropagation();
      emit("open-paper", d);
    })
    .on("mouseenter mousemove", (event, d) =>
      showHover(event, d.title, [d.major, d.role].filter(Boolean).join(" · "))
    )
    .on("mouseleave", hideHover);

  nodes
    .append("circle")
    .attr("class", "hit-area")
    .attr("r", (d) => roleRadius(d.role) + 3)
    .attr("fill", "transparent");

  nodes
    .append("circle")
    .attr("class", "role-ring")
    .attr("r", (d) => (d.role === "pillar" ? roleRadius(d.role) + 4 : 0))
    .attr("fill", "none")
    .attr("stroke", (d) => getTopicColor(d.major, "major"))
    .attr("stroke-opacity", 0.7)
    .attr("stroke-width", 1.4);

  nodes
    .append("circle")
    .attr("class", "paper-dot")
    .attr("r", (d) => roleRadius(d.role))
    .attr("fill", (d) => getTopicColor(d.major, "paper"))
    .attr("stroke", (d) =>
      d.id === props.selectedId ? "#ffffff" : getTopicColor(d.major, "sub")
    )
    .attr("stroke-width", (d) => (d.id === props.selectedId ? 2 : d.role === "niche" ? 1 : 1.2))
    .attr("stroke-dasharray", (d) => (d.role === "niche" ? "2 2" : null))
    .style("filter", (d) => `drop-shadow(0 0 ${d.role === "pillar" ? 8 : 3}px ${getTopicColor(d.major, "paper")})`);

  g.append("g")
    .attr("class", "layer-paper-labels")
    .selectAll("text")
    .data(papers)
    .join("text")
    .attr("x", (d) => xScaleFn(d.x))
    .attr("y", (d) => yScaleFn(d.y) - roleRadius(d.role) - 6)
    .text((d) => d.title)
    .attr("text-anchor", "middle")
    .attr("font-size", "7px")
    .attr("fill", "#cbd5e1")
    .style("opacity", 0)
    .style("pointer-events", "none");

  const ghostGroup = g.append("g").attr("class", "layer-ghosts");
  const ghostNodes = ghostGroup
    .selectAll("g.ghost")
    .data(ghosts)
    .join("g")
    .attr("class", "ghost")
    .attr("transform", (d) => `translate(${xScaleFn(d.x)}, ${yScaleFn(d.y)})`)
    .style("cursor", "pointer")
    .style("opacity", (d) => nodeOpacity({ major: d.cluster, cluster: d.cluster }))
    .on("click", (event, d) => {
      event.stopPropagation();
      emit("select-ghost", d);
    })
    .on("mouseenter mousemove", (event, d) =>
      showHover(event, d.title || "Knowledge gap", `Missing paper · ${d.cluster || "Gap"}`)
    )
    .on("mouseleave", hideHover);

  ghostNodes
    .append("polygon")
    .attr("points", "0,-8 8,0 0,8 -8,0")
    .attr("fill", "rgba(251, 191, 36, 0.12)")
    .attr("stroke", (d) => (d.id === props.selectedGhostId ? "#fde68a" : "#f59e0b"))
    .attr("stroke-width", 1.6)
    .attr("stroke-dasharray", "3 2")
    .attr("class", "ghost-diamond");

  g.append("g")
    .attr("class", "layer-ghost-labels")
    .selectAll("text")
    .data(ghosts)
    .join("text")
    .attr("x", (d) => xScaleFn(d.x))
    .attr("y", (d) => yScaleFn(d.y) - 14)
    .text((d) => `Missing · ${(d.title || "Gap").slice(0, 42)}`)
    .attr("text-anchor", "middle")
    .attr("font-size", "8px")
    .attr("fill", "#fbbf24")
    .style("pointer-events", "none");

  g.append("g")
    .attr("class", "layer-sub")
    .style("opacity", 0)
    .selectAll("text")
    .data(subClusters.filter((item) => item.label))
    .join("text")
    .attr("x", (d) => xScaleFn(d.x))
    .attr("y", (d) => yScaleFn(d.y))
    .text((d) => d.label)
    .attr("text-anchor", "middle")
    .attr("font-size", "12px")
    .attr("font-weight", "600")
    .attr("fill", (d) => getTopicColor(d.major, "sub"))
    .style("text-shadow", "0 2px 4px rgba(0,0,0,0.8)")
    .style("pointer-events", "none");

  g.append("g")
    .attr("class", "layer-major")
    .selectAll("text")
    .data(majorClusters)
    .join("text")
    .attr("x", (d) => xScaleFn(d.x))
    .attr("y", (d) => yScaleFn(d.y))
    .text((d) => d.label)
    .attr("text-anchor", "middle")
    .attr("font-size", "22px")
    .attr("font-weight", "bold")
    .attr("fill", (d) => getTopicColor(d.label, "major"))
    .style("text-shadow", "0 4px 12px rgba(0,0,0,0.9)")
    .style("pointer-events", "none");

  zoom = d3
    .zoom()
    .scaleExtent([ZOOM_MIN, ZOOM_MAX])
    .on("zoom", (event) => {
      hideHover();
      g.attr("transform", event.transform);
      zoomScale.value = Number(event.transform.k.toFixed(2));
      updateSemanticZoom(event.transform.k);
    });
  svg
    .call(zoom)
    .on("dblclick.zoom", null)
    .on("wheel.zoom", handleWheel, { passive: false });
  if (previousTransform) {
    svg.call(zoom.transform, previousTransform);
  } else {
    updateSemanticZoom(1);
  }
};

const focusOn = (x, y, scale = 5) => {
  if (!svg || !zoom || !graphContainer.value || !xScaleFn) return;
  const { clientWidth, clientHeight } = graphContainer.value;
  svg
    .transition()
    .duration(900)
    .call(
      zoom.transform,
      d3.zoomIdentity
        .translate(clientWidth / 2, clientHeight / 2)
        .scale(scale)
        .translate(-xScaleFn(x), -yScaleFn(y))
    );
};

const resetZoom = () => {
  if (!svg || !zoom || !graphContainer.value) return;
  const { clientWidth, clientHeight } = graphContainer.value;
  svg
    .transition()
    .duration(650)
    .call(
      zoom.transform,
      d3.zoomIdentity
        .translate(clientWidth / 2, clientHeight / 2)
        .scale(1)
        .translate(-clientWidth / 2, -clientHeight / 2)
    );
};

const setZoomLevel = (scale) => {
  if (!svg || !zoom || !graphContainer.value) return;
  const clamped = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, scale));
  const { clientWidth, clientHeight } = graphContainer.value;
  svg.transition().duration(150).call(zoom.scaleTo, clamped, [clientWidth / 2, clientHeight / 2]);
};

defineExpose({ resetZoom, setZoomLevel, focusOn, ZOOM_MIN, ZOOM_MAX });

const restyle = () => {
  if (!g) return;
  g.selectAll("g.node").style("opacity", (d) => nodeOpacity(d));
  g.selectAll("g.ghost").style("opacity", (d) =>
    nodeOpacity({ major: d.cluster, cluster: d.cluster })
  );
  g.selectAll(".paper-dot")
    .attr("stroke", (d) =>
      d.id === props.selectedId ? "#ffffff" : getTopicColor(d.major, "sub")
    )
    .attr("stroke-width", (d) =>
      d.id === props.selectedId ? 2 : d.role === "niche" ? 1 : 1.2
    );
  g.selectAll(".ghost polygon").attr("stroke", (d) =>
    d.id === props.selectedGhostId ? "#fde68a" : "#f59e0b"
  );
};

watch(
  () => [props.papers, props.ghosts, props.heatmap, props.colors, props.showHeatmap, props.showGhosts],
  () => nextTick(() => render()),
  { deep: true }
);

watch(
  () => [props.selectedId, props.selectedGhostId, props.isolatedTopic],
  () => restyle()
);

watch(
  () => props.focusRequest,
  (request) => {
    if (!request) return;
    nextTick(() => focusOn(request.x, request.y, request.scale || 5));
  }
);

onMounted(() => {
  nextTick(() => render());
  if (typeof ResizeObserver === "undefined" || !root.value) return;
  let frame = 0;
  const observer = new ResizeObserver(() => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      if (!graphContainer.value) return;
      const { clientWidth, clientHeight } = graphContainer.value;
      if (clientWidth === width && clientHeight === height) return;
      render();
    });
  });
  observer.observe(root.value);
  onBeforeUnmount(() => {
    cancelAnimationFrame(frame);
    observer.disconnect();
  });
});
</script>
