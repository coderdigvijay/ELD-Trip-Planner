import { memo, useId, useMemo, type ReactElement } from "react";

import { BLANK_FORM } from "./BlankForm";
import { formatLongDate } from "./format";
import { dropPath } from "./layoutRemarks";
import {
  BRACKET_W,
  DATE_X,
  DATE_Y,
  ENTRY_LG,
  ENTRY_MD,
  FOOTER_DATE_X,
  FOOTER_SHEET_X,
  FOOTER_Y,
  FROM_POS,
  GRAND_TOTAL_Y,
  HEADER_LINE_X,
  HEADER_LINE_Y,
  LABEL_Y,
  MILES_X,
  MILES_Y,
  NOTE_SIZE,
  RECAP_X,
  RECAP_Y,
  REMARK_NOTE_DY,
  REMARK_TEXT_DX,
  RESTART_POS,
  ROW_TOP,
  SHIPPER_LAST_Y,
  SHIPPER_LINE_H,
  SHIPPER_X,
  SHIPPING_DOC_POS,
  STATUS_W,
  TIME_BASE_POS,
  TO_POS,
  TOTALS_BASELINE_DY,
  TOTALS_X,
  VEHICLE_POS,
  VIEW_H,
  VIEW_W,
} from "./layout";
import { buildSheetModel, type FieldText } from "./sheetModel";
import { FONT_MONO, FONT_SANS, INK, PEN, SURFACE } from "./tokens";
import type { LogDay, LogHeader, TripTimezone } from "./types";
import { cn } from "@/lib/utils";

export interface LogSheetProps {
  day: LogDay;
  header: LogHeader;
  /** summary.sheet_count */
  sheetCount: number;
  timezone?: TripTimezone;
  /** Id of the visible day summary line; falls back to the sheet's own <desc>. */
  summaryId?: string;
  className?: string;
}

interface EntryProps {
  x: number;
  y: number;
  size: number;
  anchor?: "start" | "middle" | "end";
  weight?: 400 | 500;
  children: string;
  title?: string;
}

/** A filled-in value: pen ink, mono. Renders nothing for an empty value. */
function Entry({
  x: ex,
  y: ey,
  size,
  anchor = "start",
  weight = 500,
  children,
  title,
}: EntryProps) {
  if (children === "") return null;
  return (
    <text x={ex} y={ey} fontSize={size} fontWeight={weight} textAnchor={anchor}>
      {title ? <title>{title}</title> : null}
      {children}
    </text>
  );
}

function FieldEntry({
  f,
  ...pos
}: {
  f: FieldText;
  x: number;
  y: number;
  anchor?: "start" | "middle" | "end";
}) {
  return (
    <Entry {...pos} size={f.size} title={f.clipped ? f.full : undefined}>
      {f.text}
    </Entry>
  );
}

function LogSheetImpl({
  day,
  header,
  sheetCount,
  timezone,
  summaryId,
  className,
}: LogSheetProps): ReactElement {
  const uid = useId();
  const titleId = `${uid}-title`;
  const descId = `${uid}-desc`;
  const remarksId = `${uid}-remarks`;
  const model = useMemo(() => buildSheetModel(day, header, timezone), [day, header, timezone]);
  const { date, remarks, recap } = model;
  const title = `Driver's daily log, ${formatLongDate(day.date)}, sheet ${day.sheet_index} of ${sheetCount}`;

  const describedBy = [summaryId ?? descId, model.remarksText === "" ? null : remarksId]
    .filter(Boolean)
    .join(" ");

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      width="100%"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-labelledby={titleId}
      aria-describedby={describedBy}
      className={cn("block h-auto w-full", className)}
      style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}
    >
      <title id={titleId}>{title}</title>
      <desc id={descId}>{model.summary}</desc>
      {model.remarksText === "" ? null : <desc id={remarksId}>{model.remarksText}</desc>}
      <rect width={VIEW_W} height={VIEW_H} fill={SURFACE} />
      {BLANK_FORM}

      <g
        data-part="entries"
        fontFamily={FONT_MONO}
        fill={PEN}
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        <Entry x={DATE_X.mm} y={DATE_Y} size={ENTRY_LG} anchor="middle">
          {date.mm}
        </Entry>
        <Entry x={DATE_X.dd} y={DATE_Y} size={ENTRY_LG} anchor="middle">
          {date.dd}
        </Entry>
        <Entry x={DATE_X.yyyy} y={DATE_Y} size={ENTRY_LG} anchor="middle">
          {date.yyyy}
        </Entry>
        <FieldEntry f={model.from} {...FROM_POS} />
        <FieldEntry f={model.to} {...TO_POS} />
        <Entry x={MILES_X.driving} y={MILES_Y} size={ENTRY_LG} anchor="middle">
          {model.miles}
        </Entry>
        <Entry x={MILES_X.total} y={MILES_Y} size={ENTRY_LG} anchor="middle">
          {model.miles}
        </Entry>
        <FieldEntry f={model.vehicle} {...VEHICLE_POS} anchor="middle" />
        <FieldEntry f={model.driver} x={HEADER_LINE_X} y={HEADER_LINE_Y.driver} anchor="middle" />
        <FieldEntry f={model.carrier} x={HEADER_LINE_X} y={HEADER_LINE_Y.carrier} anchor="middle" />
        <FieldEntry
          f={model.mainOffice}
          x={HEADER_LINE_X}
          y={HEADER_LINE_Y.mainOffice}
          anchor="middle"
        />
        <FieldEntry
          f={model.homeTerminal}
          x={HEADER_LINE_X}
          y={HEADER_LINE_Y.homeTerminal}
          anchor="middle"
        />
        <FieldEntry f={model.shippingDoc} {...SHIPPING_DOC_POS} />
        {model.shipper.lines.map((line, i, all) => (
          <Entry
            key={`${i}-${line}`}
            x={SHIPPER_X}
            y={SHIPPER_LAST_Y - (all.length - 1 - i) * SHIPPER_LINE_H}
            size={model.shipper.size}
            title={i === all.length - 1 && model.shipper.clipped ? model.shipper.full : undefined}
          >
            {line}
          </Entry>
        ))}

        {(["off", "sleeper", "driving", "on_duty"] as const).map((status) => (
          <Entry
            key={status}
            x={TOTALS_X}
            y={ROW_TOP[status] + TOTALS_BASELINE_DY}
            size={ENTRY_MD}
            anchor="end"
          >
            {model.rowTotals[status]}
          </Entry>
        ))}
        <Entry x={TOTALS_X} y={GRAND_TOTAL_Y} size={ENTRY_MD} anchor="end">
          {model.grandTotal}
        </Entry>

        {(
          [
            [RECAP_X.today, recap.today],
            [RECAP_X.a, recap.a],
            [RECAP_X.b, recap.b],
            [RECAP_X.c, recap.c],
            [RECAP_X.a60, "N/A"],
            [RECAP_X.b60, "N/A"],
            [RECAP_X.c60, "N/A"],
          ] as const
        ).map(([rx, value]) => (
          <Entry key={rx} x={rx} y={RECAP_Y} size={ENTRY_MD} anchor="middle">
            {value}
          </Entry>
        ))}
        {recap.restartLines.map((line, i) => (
          <Entry
            key={line}
            x={RESTART_POS.x}
            y={RESTART_POS.y + i * RESTART_POS.lineH}
            size={NOTE_SIZE}
            weight={400}
            title={i === 0 ? (recap.restartFull ?? undefined) : undefined}
          >
            {line}
          </Entry>
        ))}
        {remarks.mode === "list"
          ? remarks.list.map((e) => (
              <Entry key={e.key} x={e.x} y={e.y} size={e.size} title={e.title}>
                {e.text}
              </Entry>
            ))
          : null}
      </g>

      <g data-part="pen" fill="none" stroke={PEN}>
        <path
          d={model.dutyD}
          strokeWidth={STATUS_W}
          strokeLinecap="square"
          strokeLinejoin="miter"
          data-part="duty-line"
        />
        <path
          d={model.bracketD}
          strokeWidth={BRACKET_W}
          strokeLinejoin="miter"
          data-part="brackets"
        />
        <path d={dropPath(remarks)} strokeWidth={BRACKET_W} data-part="drops" />
      </g>

      <g
        data-part="remarks"
        fontFamily={FONT_MONO}
        fill={PEN}
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {remarks.mode === "list"
          ? null
          : remarks.drawn.map((r) => (
              <g
                key={r.key}
                data-remark={r.minute}
                transform={`translate(${r.ax} ${LABEL_Y}) rotate(45)`}
              >
                <title>{r.title}</title>
                <text x={REMARK_TEXT_DX} y={0} fontSize={r.size} fontWeight={500}>
                  {r.line1}
                </text>
                {r.line2 !== null ? (
                  <text x={REMARK_TEXT_DX} y={REMARK_NOTE_DY} fontSize={NOTE_SIZE} fontWeight={400}>
                    {r.line2}
                  </text>
                ) : null}
              </g>
            ))}
      </g>

      <g data-part="footer" fill={INK} fontSize={10}>
        <text x={FOOTER_DATE_X} y={FOOTER_Y} fontFamily={FONT_MONO} fontWeight={400}>
          {`${date.mm}/${date.dd}/${date.yyyy}`}
        </text>
        <text
          x={FOOTER_SHEET_X}
          y={FOOTER_Y}
          fontFamily={FONT_SANS}
          fontWeight={600}
          textAnchor="end"
        >
          {`Sheet ${day.sheet_index} of ${sheetCount}`}
        </text>
        {model.timeBase ? (
          <text
            x={TIME_BASE_POS.x}
            y={TIME_BASE_POS.y}
            fontFamily={FONT_SANS}
            fontWeight={400}
            textAnchor="end"
          >
            {model.timeBase}
          </text>
        ) : null}
      </g>
    </svg>
  );
}

export const LogSheet = memo(LogSheetImpl);
