import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Check, LoaderCircle, MapPin } from "lucide-react";
import { useId, useState, type Ref } from "react";
import { useDebounce } from "use-debounce";

import {
  Autocomplete,
  AutocompleteInput,
  AutocompleteInputGroup,
  AutocompleteItem,
  AutocompleteList,
  AutocompletePopup,
} from "@/components/ui/autocomplete";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { splitMatch } from "@/lib/normalize";
import { ApiError } from "@/services/errors";
import { autocomplete, type PlaceSuggestion } from "@/services/places";

import { locationLabel, type LocationValue } from "./schema";

export const SUGGEST_DEBOUNCE_MS = 300;
export const SUGGEST_MIN_CHARS = 3;
export const SUGGEST_MAX_CHARS = 100;
const MAX_ROWS = 5;

interface LocationFieldProps {
  id: string;
  name: string;
  value: LocationValue;
  onChange: (value: LocationValue) => void;
  onBlur: () => void;
  inputRef?: Ref<HTMLInputElement>;
  readOnly?: boolean;
  invalid?: true | undefined;
  describedBy?: string | undefined;
}

function isSamePick(value: LocationValue, item: PlaceSuggestion): boolean {
  return typeof value !== "string" && value.lat === item.lat && value.lng === item.lng;
}

function Emphasis({ text, needle }: { text: string; needle: string }) {
  const { before, match, after } = splitMatch(text, needle);
  return (
    <span className="line-clamp-2 min-w-0 flex-1 font-medium" title={text}>
      {before}
      {match ? <strong className="font-semibold">{match}</strong> : null}
      {after}
    </span>
  );
}

/** Free text plus server suggestions. The value is a PlaceInput when picked, else the typed string. */
export function LocationField({
  id,
  name,
  value,
  onChange,
  onBlur,
  inputRef,
  readOnly,
  invalid,
  describedBy,
}: LocationFieldProps) {
  const statusId = useId();
  const [open, setOpen] = useState(false);
  const text = locationLabel(value);
  const trimmed = text.trim();
  const [term] = useDebounce(trimmed, SUGGEST_DEBOUNCE_MS);
  const typing = typeof value === "string";
  const searchable = typing && term.length >= SUGGEST_MIN_CHARS && term.length <= SUGGEST_MAX_CHARS;

  const query = useQuery({
    queryKey: ["places", term],
    queryFn: ({ signal }) => autocomplete(term, signal),
    enabled: searchable,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const items = searchable && !query.isError ? (query.data ?? []).slice(0, MAX_ROWS) : [];
  const settled = searchable && term === trimmed && query.isSuccess && !query.isPlaceholderData;
  const waiting = typing && trimmed.length >= SUGGEST_MIN_CHARS && !settled && !query.isError;
  const showLoader = waiting && items.length > 0;
  const rateLimited = query.error instanceof ApiError && query.error.code === "RATE_LIMITED";

  function handleValueChange(next: string, details: { reason: string }) {
    if (details.reason === "item-press") {
      const picked = items.find((item) => item.label === next);
      if (picked) {
        onChange({ label: picked.label, lat: picked.lat, lng: picked.lng });
        return;
      }
    }
    onChange(next);
  }

  let popupBody;
  if (trimmed.length < SUGGEST_MIN_CHARS) {
    popupBody = <p className="px-3 py-2.5 text-base text-ink-3">Type 3 or more characters</p>;
  } else if (query.isError) {
    popupBody = (
      <div className="flex flex-col items-start gap-2 px-3 py-2.5">
        <p className="text-base text-ink-2">
          Suggestions are unavailable. Type the full place, like Dallas, TX.
        </p>
        {rateLimited ? null : (
          <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
            Retry
          </Button>
        )}
      </div>
    );
  } else if (waiting && items.length === 0) {
    popupBody = (
      <div className="flex flex-col gap-2 p-3" aria-hidden="true">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    );
  } else if (settled && items.length === 0) {
    popupBody = (
      <p className="px-3 py-2.5 text-base text-ink-2">
        No places match &ldquo;{trimmed}&rdquo;. Try a city and state, like Dallas, TX.
      </p>
    );
  }

  let announcement = "";
  if (open && settled) {
    announcement =
      items.length === 0
        ? "No suggestions"
        : `${String(items.length)} ${items.length === 1 ? "suggestion" : "suggestions"}`;
  } else if (open && query.isError) {
    announcement = "Suggestions are unavailable";
  }

  return (
    <>
      <Autocomplete
        items={items}
        filter={null}
        mode="list"
        value={text}
        onValueChange={handleValueChange}
        itemToStringValue={(item: PlaceSuggestion) => item.label}
        open={open && !readOnly}
        onOpenChange={setOpen}
        name={name}
      >
        <AutocompleteInputGroup>
          <MapPin
            aria-hidden="true"
            className="pointer-events-none absolute start-3 z-10 size-4 text-ink-3"
          />
          <AutocompleteInput
            id={id}
            ref={inputRef}
            placeholder="City, address or place"
            autoComplete="off"
            readOnly={readOnly}
            aria-invalid={invalid}
            aria-describedby={describedBy}
            title={typing ? undefined : text}
            className="truncate"
            onBlur={onBlur}
          />
          {showLoader ? (
            <LoaderCircle
              aria-hidden="true"
              className="pointer-events-none absolute end-3 z-10 size-4 animate-spin text-ink-3"
            />
          ) : null}
        </AutocompleteInputGroup>
        <AutocompletePopup>
          {popupBody}
          <AutocompleteList>
            {(item: PlaceSuggestion) => (
              <AutocompleteItem
                key={`${item.label}-${String(item.lat)}-${String(item.lng)}`}
                value={item}
              >
                <Emphasis text={item.label} needle={trimmed} />
                {isSamePick(value, item) ? (
                  <Check aria-hidden="true" className="size-4 shrink-0 text-ink-2" />
                ) : null}
              </AutocompleteItem>
            )}
          </AutocompleteList>
        </AutocompletePopup>
      </Autocomplete>
      <p id={statusId} role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </>
  );
}
