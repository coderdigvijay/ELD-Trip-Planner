import { Autocomplete as AutocompletePrimitive } from "@base-ui/react/autocomplete";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { controlClasses } from "./input";

/**
 * Base UI Autocomplete parts, styled with the InputGroup look (DESIGN_SYSTEM 5.1, 5.3).
 * Autocomplete rather than Combobox because our value may be free text, not only a list item.
 */
const Autocomplete = AutocompletePrimitive.Root;

function AutocompleteInputGroup({
  className,
  ...props
}: ComponentProps<typeof AutocompletePrimitive.InputGroup>) {
  return (
    <AutocompletePrimitive.InputGroup
      data-slot="autocomplete-group"
      className={cn(
        "relative flex w-full items-center",
        typeof className === "string" ? className : undefined,
      )}
      {...props}
    />
  );
}

function AutocompleteInput({
  className,
  ...props
}: ComponentProps<typeof AutocompletePrimitive.Input>) {
  return (
    <AutocompletePrimitive.Input
      data-slot="autocomplete-input"
      className={cn(
        controlClasses,
        "ps-9 pe-9",
        typeof className === "string" ? className : undefined,
      )}
      {...props}
    />
  );
}

function AutocompletePopup({
  className,
  ...props
}: ComponentProps<typeof AutocompletePrimitive.Popup>) {
  return (
    <AutocompletePrimitive.Portal>
      <AutocompletePrimitive.Positioner sideOffset={4} align="start" className="z-50 outline-none">
        <AutocompletePrimitive.Popup
          data-slot="autocomplete-popup"
          className={cn(
            "w-(--anchor-width) max-w-(--available-width) origin-(--transform-origin) rounded-md border border-rule-strong bg-popover text-popover-foreground shadow-md transition-[opacity,scale] duration-160 ease-standard outline-none data-ending-style:scale-98 data-ending-style:opacity-0 data-ending-style:duration-120 data-ending-style:ease-exit data-starting-style:scale-98 data-starting-style:opacity-0",
            typeof className === "string" ? className : undefined,
          )}
          {...props}
        />
      </AutocompletePrimitive.Positioner>
    </AutocompletePrimitive.Portal>
  );
}

function AutocompleteItem({
  className,
  ...props
}: ComponentProps<typeof AutocompletePrimitive.Item>) {
  return (
    <AutocompletePrimitive.Item
      data-slot="autocomplete-item"
      className={cn(
        "flex min-h-11 cursor-pointer items-center gap-2 px-3 py-2 text-base text-foreground outline-none select-none data-highlighted:bg-accent md:min-h-10",
        typeof className === "string" ? className : undefined,
      )}
      {...props}
    />
  );
}

export {
  Autocomplete,
  AutocompleteInput,
  AutocompleteInputGroup,
  AutocompleteItem,
  AutocompletePopup,
};
export const AutocompleteList = AutocompletePrimitive.List;
