import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// A full parallel run (or a busy machine) stretches lazy chunk imports and msw round trips: give
// findBy and waitFor 5 s instead of 1 s so a slow worker is not read as a failure.
configure({ asyncUtilTimeout: 5000 });
