import {
  AX_HI,
  AX_LO,
  DROP_Y0_BRACKET,
  DROP_Y0_GRID,
  LEADER_Y0,
  LEADER_Y1,
  LABEL_RIGHT,
  MONO_ADVANCE,
  SIN45,
} from "./layout";
import { fitMono, formatClock, truncate } from "./format";
import { x } from "./geometry";
import type { LogRemark, LogSegment } from "./types";

// Remark placement (LOG_SHEET_RENDER_SPEC 3.4 and 3.5). Pure and deterministic: monospace arithmetic only.

export type RemarkMode = "full" | "compact" | "list";

const NOTE_LINE_STEP = 13;
const NOTE_SIZE = 10;
const PAD = 2;
const MAX_LOC_CHARS = 28;
const MAX_NOTE_CHARS = 30;
const MAX_LIST_ROWS = 16;
const LIST_X0 = 220;
const LIST_WIDTH = 724;
const LIST_Y0 = 560;
const LIST_STEP = 13;

interface Candidate {
  minute: number;
  location: string;
  note: string;
  /** Where the drop line starts: grid bottom, or bracket bottom when anchored to a bracket. */
  ax0: number;
  dropY0: number;
}

export interface DrawnRemark {
  key: string;
  minute: number;
  ax0: number;
  ax: number;
  dropY0: number;
  /** True when the label moved off its ideal x, so the drop line ends in a leader. */
  leader: boolean;
  line1: string;
  line2: string | null;
  size: number;
  /** Full untruncated "HH:MM place, note" for hover. */
  title: string;
}

export interface ListEntry {
  key: string;
  x: number;
  y: number;
  text: string;
  size: number;
  title: string;
}

export interface RemarkLayout {
  mode: RemarkMode;
  drawn: DrawnRemark[];
  folded: LogRemark[];
  list: ListEntry[];
}

function locSize(mode: RemarkMode): number {
  return mode === "full" ? 11 : 10;
}

/** Minimum x distance between label i and its right neighbour, which depends on the right-hand label. */
export function labelGap(mode: RemarkMode, rightHasNote: boolean): number {
  const size = locSize(mode);
  const asc = 0.75 * size;
  const desc = mode === "full" && rightHasNote ? NOTE_LINE_STEP + 0.25 * NOTE_SIZE : 0.25 * size;
  return Math.ceil((asc + desc + PAD) / SIN45);
}

function chooseCandidates(remarks: readonly LogRemark[], segments: readonly LogSegment[]) {
  const stationary = segments.filter((s) => s.stationary);
  const startsAt = (minute: number) => stationary.find((s) => s.start_min === minute);
  const endsAt = (minute: number) => stationary.find((s) => s.end_min === minute);
  const labeled = new Set<LogSegment>();

  interface Event {
    minute: number;
    location: string;
    note: string;
    remark: LogRemark | null;
  }
  const events: Event[] = remarks.map((r) => ({
    minute: r.minute,
    location: r.location_label,
    note: r.note,
    remark: r,
  }));
  // A same-status stop boundary without a remark (pre-trip then pickup) is labeled from its own segment.
  segments.forEach((seg, i) => {
    const prev = segments[i - 1];
    const missing = !remarks.some((r) => r.minute === seg.start_min);
    if (seg.stationary && missing && prev?.stationary && prev.status === seg.status) {
      events.push({
        minute: seg.start_min,
        location: seg.location_label,
        note: seg.note,
        remark: null,
      });
    }
  });
  events.sort((a, b) => a.minute - b.minute);

  const drawn: Candidate[] = [];
  const folded: LogRemark[] = [];
  for (const ev of events) {
    const ending = endsAt(ev.minute);
    const nextStop = startsAt(ev.minute);
    const fold =
      ev.remark !== null &&
      ending !== undefined &&
      labeled.has(ending) &&
      ev.location === ending.location_label &&
      !(nextStop !== undefined && nextStop.note !== ending.note);
    if (fold && ev.remark) {
      folded.push(ev.remark);
      continue;
    }
    const bracket = startsAt(ev.minute);
    if (bracket) labeled.add(bracket);
    drawn.push({
      minute: ev.minute,
      location: ev.location,
      note: ev.note,
      ax0: bracket ? (x(bracket.start_min) + x(bracket.end_min)) / 2 : x(ev.minute),
      dropY0: bracket ? DROP_Y0_BRACKET : DROP_Y0_GRID,
    });
  }
  return { drawn, folded };
}

interface Cluster {
  first: number;
  last: number;
  offsets: number[];
  p: number;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

/** Pool adjacent clusters (1D least squares label dodging). Returns integer anchors. */
export function placeAnchors(ax0: readonly number[], gaps: readonly number[]): number[] {
  const stack: Cluster[] = [];
  ax0.forEach((wish, i) => {
    stack.push({ first: i, last: i, offsets: [0], p: clamp(wish, AX_LO, AX_HI) });
    for (;;) {
      const c = stack[stack.length - 1];
      const b = stack[stack.length - 2];
      if (!c || !b) break;
      const width = b.offsets[b.offsets.length - 1] ?? 0;
      const gap = gaps[c.first] ?? 0;
      if (b.p + width + gap <= c.p) break;
      const bridge = width + gap;
      const offsets = [...b.offsets, ...c.offsets.map((o) => o + bridge)];
      let sum = 0;
      offsets.forEach((off, k) => {
        sum += (ax0[b.first + k] ?? 0) - off;
      });
      const total = offsets[offsets.length - 1] ?? 0;
      const p = clamp(Math.round(sum / offsets.length), AX_LO, AX_HI - total);
      stack.splice(stack.length - 2, 2, { first: b.first, last: c.last, offsets, p });
    }
  });
  const anchors: number[] = new Array<number>(ax0.length).fill(0);
  for (const cluster of stack) {
    cluster.offsets.forEach((off, k) => {
      anchors[cluster.first + k] = cluster.p + off;
    });
  }
  return anchors;
}

function gapsFor(items: readonly Candidate[], mode: RemarkMode): number[] {
  // gaps[i] is the gap between label i - 1 and label i (depends on label i).
  return items.map((c) => labelGap(mode, c.note !== ""));
}

function sumGaps(gaps: readonly number[]): number {
  return gaps.slice(1).reduce((a, b) => a + b, 0);
}

export function layoutRemarks(
  remarks: readonly LogRemark[],
  segments: readonly LogSegment[],
): RemarkLayout {
  const { drawn: candidates, folded } = chooseCandidates(remarks, segments);
  const budget = AX_HI - AX_LO;

  let mode: RemarkMode = "full";
  if (sumGaps(gapsFor(candidates, "full")) > budget) mode = "compact";
  if (mode === "compact" && sumGaps(gapsFor(candidates, "compact")) > budget) mode = "list";

  const title = (c: Candidate) =>
    `${formatClock(c.minute)} ${c.location}${c.note ? `, ${c.note}` : ""}`;

  if (mode === "list") {
    const columns = Math.max(1, Math.ceil(candidates.length / MAX_LIST_ROWS));
    const colWidth = Math.floor(LIST_WIDTH / columns);
    const drawn: DrawnRemark[] = candidates.map((c, i) => ({
      key: `${c.minute}-${i}`,
      minute: c.minute,
      ax0: c.ax0,
      ax: c.ax0,
      dropY0: c.dropY0,
      leader: false,
      line1: "",
      line2: null,
      size: 10,
      title: title(c),
    }));
    const list: ListEntry[] = candidates.map((c, i) => {
      const fit = fitMono(`${formatClock(c.minute)} ${c.location}`, colWidth - 8, 10, 10);
      return {
        key: `${c.minute}-${i}`,
        x: LIST_X0 + Math.floor(i / MAX_LIST_ROWS) * colWidth,
        y: LIST_Y0 + (i % MAX_LIST_ROWS) * LIST_STEP,
        text: fit.text,
        size: fit.size,
        title: title(c),
      };
    });
    return { mode, drawn, folded, list };
  }

  const size = locSize(mode);
  const anchors = placeAnchors(
    candidates.map((c) => c.ax0),
    gapsFor(candidates, mode),
  );
  const drawn: DrawnRemark[] = candidates.map((c, i) => {
    const ax = anchors[i] ?? c.ax0;
    const run = (LABEL_RIGHT - ax) / SIN45;
    const chars1 = Math.min(MAX_LOC_CHARS, Math.floor((run - 4) / (MONO_ADVANCE * size)));
    const chars2 = Math.min(MAX_NOTE_CHARS, Math.floor((run + 9) / (MONO_ADVANCE * NOTE_SIZE)));
    return {
      key: `${c.minute}-${i}`,
      minute: c.minute,
      ax0: c.ax0,
      ax,
      dropY0: c.dropY0,
      leader: ax !== c.ax0,
      line1: truncate(c.location, chars1),
      line2: mode === "full" && c.note !== "" ? truncate(c.note, chars2) : null,
      size,
      title: title(c),
    };
  });
  return { mode, drawn, folded, list: [] };
}

/** All drop lines and leaders as one path (pen, width 1). */
export function dropPath(layout: RemarkLayout): string {
  return layout.drawn
    .map((r) => {
      if (layout.mode === "list") return `M${r.ax0} ${r.dropY0} V${LEADER_Y0}`;
      if (!r.leader) return `M${r.ax0} ${r.dropY0} V${LEADER_Y1}`;
      return `M${r.ax0} ${r.dropY0} V${LEADER_Y0} L${r.ax} ${LEADER_Y1}`;
    })
    .join(" ");
}
