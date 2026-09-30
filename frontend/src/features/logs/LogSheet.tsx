import { memo, useId, useMemo, type ReactElement } from "react";

import { BLANK_FORM } from "./BlankForm";
import { formatLongDate } from "./format";
import { dropPath } from "./layoutRemarks";
import { BRACKET_W, LABEL_Y, STATUS_W, VIEW_H, VIEW_W, ROW_TOP } from "./layout";
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
  const model = useMemo(() => buildSheetModel(day, header, timezone), [day, header, timezone]);
  const { date, remarks, recap } = model;
  const title = `Driver's daily log, ${formatLongDate(day.date)}, sheet ${day.sheet_index} of ${sheetCount}`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      width="100%"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-labelledby={titleId}
      aria-describedby={summaryId ?? descId}
      className={cn("block h-auto w-full", className)}
      style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}
    >
      <title id={titleId}>{title}</title>
      <desc id={descId}>{model.summary}</desc>
      <rect width={VIEW_W} height={VIEW_H} fill={SURFACE} />
      {BLANK_FORM}

      <g
        data-part="entries"
        fontFamily={FONT_MONO}
        fill={PEN}
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        <Entry x={365} y={35} size={18} anchor="middle">
          {date.mm}
        </Entry>
        <Entry x={456} y={35} size={18} anchor="middle">
          {date.dd}
        </Entry>
        <Entry x={546} y={35} size={18} anchor="middle">
          {date.yyyy}
        </Entry>
        <FieldEntry f={model.from} x={116} y={83} />
        <FieldEntry f={model.to} x={546} y={83} />
        <Entry x={190} y={158} size={18} anchor="middle">
          {model.miles}
        </Entry>
        <Entry x={357} y={158} size={18} anchor="middle">
          {model.miles}
        </Entry>
        <FieldEntry f={model.vehicle} x={271} y={225} anchor="middle" />
        <FieldEntry f={model.driver} x={700} y={107} anchor="middle" />
        <FieldEntry f={model.carrier} x={700} y={147} anchor="middle" />
        <FieldEntry f={model.mainOffice} x={700} y={189} anchor="middle" />
        <FieldEntry f={model.homeTerminal} x={700} y={231} anchor="middle" />
        <FieldEntry f={model.shippingDoc} x={48} y={670} />
        {model.shipper.lines.map((line, i, all) => (
          <Entry
            key={`${i}-${line}`}
            x={48}
            y={730 - (all.length - 1 - i) * 12}
            size={model.shipper.size}
            title={i === all.length - 1 && model.shipper.clipped ? model.shipper.full : undefined}
          >
            {line}
          </Entry>
        ))}

        <Entry x={954} y={ROW_TOP.off + 29} size={15} anchor="end">
          {model.rowTotals.off}
        </Entry>
        <Entry x={954} y={ROW_TOP.sleeper + 29} size={15} anchor="end">
          {model.rowTotals.sleeper}
        </Entry>
        <Entry x={954} y={ROW_TOP.driving + 29} size={15} anchor="end">
          {model.rowTotals.driving}
        </Entry>
        <Entry x={954} y={ROW_TOP.on_duty + 29} size={15} anchor="end">
          {model.rowTotals.on_duty}
        </Entry>
        <Entry x={954} y={499} size={15} anchor="end">
          {model.grandTotal}
        </Entry>

        <Entry x={176} y={879} size={15} anchor="middle">
          {recap.today}
        </Entry>
        <Entry x={331} y={879} size={15} anchor="middle">
          {recap.a}
        </Entry>
        <Entry x={411} y={879} size={15} anchor="middle">
          {recap.b}
        </Entry>
        <Entry x={491} y={879} size={15} anchor="middle">
          {recap.c}
        </Entry>
        <Entry x={651} y={879} size={15} anchor="middle">
          N/A
        </Entry>
        <Entry x={731} y={879} size={15} anchor="middle">
          N/A
        </Entry>
        <Entry x={811} y={879} size={15} anchor="middle">
          N/A
        </Entry>
        {recap.restartLines.map((line, i) => (
          <Entry
            key={line}
            x={856}
            y={910 + i * 13}
            size={10}
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
                <text x={4} y={0} fontSize={r.size} fontWeight={500}>
                  {r.line1}
                </text>
                {r.line2 !== null ? (
                  <text x={4} y={13} fontSize={10} fontWeight={400}>
                    {r.line2}
                  </text>
                ) : null}
              </g>
            ))}
      </g>

      <g data-part="footer" fill={INK} fontSize={10}>
        <text x={44} y={1008} fontFamily={FONT_MONO} fontWeight={400}>
          {`${date.mm}/${date.dd}/${date.yyyy}`}
        </text>
        <text x={944} y={1008} fontFamily={FONT_SANS} fontWeight={600} textAnchor="end">
          {`Sheet ${day.sheet_index} of ${sheetCount}`}
        </text>
        {model.timeBase ? (
          <text x={500} y={1008} fontFamily={FONT_SANS} fontWeight={400} textAnchor="middle">
            {model.timeBase}
          </text>
        ) : null}
      </g>
    </svg>
  );
}

export const LogSheet = memo(LogSheetImpl);
