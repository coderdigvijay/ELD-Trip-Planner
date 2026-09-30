// Literal values for SVG presentation attributes (var() is not valid there) and for the PDF exporter.
// A test asserts these equal the @theme / --log-* tokens in src/index.css.
export const INK = "#15171a";
export const PEN = "#1c3f94";
export const SURFACE = "#ffffff";

export const FONT_SANS =
  '"Public Sans Variable", "Public Sans Fallback", ui-sans-serif, system-ui, sans-serif';
export const FONT_MONO =
  '"IBM Plex Mono", "IBM Plex Mono Fallback", ui-monospace, "SFMono-Regular", Menlo, monospace';

// Stroke weights (CSS px for the non-scaling form group, viewBox units for pen marks).
export const FRAME_W = 1.5;
export const HOUR_W = 1;
export const HALF_W = 0.75;
export const QUARTER_W = 0.75;
export const RULE_W = 0.75;
export const HEAVY_W = 2.5;
export const STATUS_W = 2.5;
export const BRACKET_W = 1;
export const BRACKET_ARM = 6;

// Text sizes in viewBox units.
export const LABEL_SIZE = 11;
export const TITLE_SIZE = 28;
export const HOUR_SIZE = 10.5;
export const ENTRY_LG = 18;
export const ENTRY_MD = 15;
export const ENTRY_SM = 13;
export const REMARK_SIZE = 11;
export const REMARK_WEIGHT = 500;
export const TEXT_MIN = 10;

/** Every numeric or keyword `--log-*` token in src/index.css, by name without the prefix. */
export const LOG_TOKENS = {
  "frame-w": FRAME_W,
  "hour-w": HOUR_W,
  "half-w": HALF_W,
  "half-len": 0.5,
  "quarter-w": QUARTER_W,
  "quarter-len": 0.3,
  "rule-w": RULE_W,
  "heavy-w": HEAVY_W,
  "status-w": STATUS_W,
  "status-cap": "square",
  "status-join": "miter",
  "bracket-w": BRACKET_W,
  "bracket-tick": BRACKET_ARM,
  "label-size": LABEL_SIZE,
  "title-size": TITLE_SIZE,
  "hour-size": HOUR_SIZE,
  "entry-size-lg": ENTRY_LG,
  "entry-size": ENTRY_MD,
  "entry-size-sm": ENTRY_SM,
  "remark-size": REMARK_SIZE,
  "remark-weight": REMARK_WEIGHT,
  "remark-rotate": 45,
  "text-min": TEXT_MIN,
} as const;
