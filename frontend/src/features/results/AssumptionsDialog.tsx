import { Dialog } from "@base-ui/react/dialog";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Assumption } from "./types";

export interface AssumptionsDialogProps {
  assumptions: readonly Assumption[];
}

/** Every assumption the engine made, as the API returns them (A1 to A17). Base UI traps focus, closes on Escape and returns focus to the trigger. */
export function AssumptionsDialog({ assumptions }: AssumptionsDialogProps) {
  return (
    <Dialog.Root>
      <Dialog.Trigger render={<Button variant="ghost" size="sm" />}>Assumptions</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 bg-ink/40 transition-opacity duration-160 ease-standard data-ending-style:opacity-0 data-ending-style:duration-120 data-ending-style:ease-exit data-starting-style:opacity-0" />
        <Dialog.Popup className="fixed start-1/2 top-1/2 flex max-h-[85dvh] w-[calc(100%-2rem)] max-w-140 -translate-x-1/2 -translate-y-1/2 flex-col rounded-md border border-rule bg-surface p-4 shadow-lg transition-[opacity,scale] duration-160 ease-standard outline-none data-ending-style:scale-98 data-ending-style:opacity-0 data-ending-style:duration-120 data-ending-style:ease-exit data-starting-style:scale-98 data-starting-style:opacity-0 md:p-5">
          <div className="flex items-start justify-between gap-3">
            <Dialog.Title className="text-xl font-semibold">Assumptions</Dialog.Title>
            <Dialog.Close
              render={<Button variant="ghost" size="icon" aria-label="Close assumptions" />}
            >
              <X aria-hidden="true" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-base text-ink-2">
            The rules this plan followed. Each one is applied the same way on every day.
          </Dialog.Description>
          {assumptions.length === 0 ? (
            <p className="mt-4 text-base text-ink-2">
              The server listed no assumptions for this plan.
            </p>
          ) : (
            <ol
              className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pe-1"
              tabIndex={0}
              aria-label="Assumption list"
            >
              {assumptions.map((a) => (
                <li key={a.id} className="grid grid-cols-[3rem_1fr] gap-2 text-base">
                  <span className="font-mono text-sm text-ink-3 num">{a.id}</span>
                  <span className="min-w-0 wrap-break-word">{a.text}</span>
                </li>
              ))}
            </ol>
          )}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
